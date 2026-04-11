"""Agent 管理 API — 列出、启动、监控 Claude Code Agent 任务。"""

import asyncio
import uuid
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# ── 项目根目录和 agent 定义目录 ──
PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"

# ── 全局任务存储 ──
_tasks: dict[str, "AgentTask"] = {}          # task_id -> AgentTask
_activity_log: list[dict] = []               # 最近活动日志


# ====================================================================
# 数据模型
# ====================================================================

class AgentInfo(BaseModel):
    """Agent 基本信息（从 .md frontmatter 解析）"""
    name: str
    description: str
    status: str = "idle"          # idle / running / completed / failed
    last_run: Optional[str] = None
    duration: Optional[float] = None  # 秒


class AgentTask(BaseModel):
    """一次 agent 执行任务"""
    id: str
    agent_name: str
    prompt: str
    status: str = "pending"       # pending / running / completed / failed
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    output: Optional[str] = None


class StartRequest(BaseModel):
    """启动单个 agent 的请求"""
    agent_name: str
    prompt: str


class StartParallelRequest(BaseModel):
    """并行启动多个 agent 的请求"""
    tasks: list[StartRequest]


# ====================================================================
# 辅助函数
# ====================================================================

def _parse_frontmatter(path: Path) -> dict:
    """解析 Markdown 文件的 YAML frontmatter，返回 {name, description}。"""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {"name": path.stem, "description": ""}
    block = m.group(1)
    info: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            info[key.strip()] = val.strip()
    return {
        "name": info.get("name", path.stem),
        "description": info.get("description", ""),
    }


def _now_iso() -> str:
    """返回当前 UTC 时间 ISO 格式字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _log_activity(event: str, agent_name: str, task_id: str):
    """记录活动日志，最多保留 200 条。"""
    _activity_log.append({
        "time": _now_iso(),
        "event": event,
        "agent_name": agent_name,
        "task_id": task_id,
    })
    if len(_activity_log) > 200:
        _activity_log.pop(0)


async def _run_agent(task_id: str):
    """在后台通过 subprocess 执行 claude CLI agent，完成后更新任务状态。"""
    task = _tasks[task_id]
    task.status = "running"
    task.started_at = _now_iso()
    _log_activity("started", task.agent_name, task_id)

    try:
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "--agent", task.agent_name,
            "-p", task.prompt,
            "--output-format", "text",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            task.status = "completed"
            task.output = stdout.decode("utf-8", errors="replace")
            _log_activity("completed", task.agent_name, task_id)
        else:
            task.status = "failed"
            task.output = stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace")
            _log_activity("failed", task.agent_name, task_id)
    except Exception as exc:
        task.status = "failed"
        task.output = str(exc)
        _log_activity("failed", task.agent_name, task_id)
    finally:
        task.finished_at = _now_iso()


# 保存进程句柄，用于 stop 功能
_processes: dict[str, asyncio.subprocess.Process] = {}


async def _run_agent_tracked(task_id: str):
    """带进程句柄追踪的 agent 执行器，支持取消。"""
    task = _tasks[task_id]
    task.status = "running"
    task.started_at = _now_iso()
    _log_activity("started", task.agent_name, task_id)

    try:
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "--agent", task.agent_name,
            "-p", task.prompt,
            "--output-format", "text",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        _processes[task_id] = proc
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            task.status = "completed"
            task.output = stdout.decode("utf-8", errors="replace")
            _log_activity("completed", task.agent_name, task_id)
        else:
            # 被 stop 终止时 returncode 不为 0
            if task.status != "failed":
                task.status = "failed"
            task.output = stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace")
            if task.status == "failed":
                _log_activity("failed", task.agent_name, task_id)
    except asyncio.CancelledError:
        task.status = "failed"
        task.output = "任务被取消"
        _log_activity("stopped", task.agent_name, task_id)
    except Exception as exc:
        task.status = "failed"
        task.output = str(exc)
        _log_activity("failed", task.agent_name, task_id)
    finally:
        task.finished_at = _now_iso()
        _processes.pop(task_id, None)


# ====================================================================
# 端点
# ====================================================================

@router.get("/list", summary="列出所有可用 Agent")
async def list_agents():
    """从 .claude/agents/ 目录读取所有 .md 文件，解析 frontmatter 返回 agent 列表。"""
    if not AGENTS_DIR.exists():
        return {"agents": []}

    agents: list[dict] = []
    for md in sorted(AGENTS_DIR.glob("*.md")):
        info = _parse_frontmatter(md)
        # 查找该 agent 最近一次任务
        agent_tasks = [t for t in _tasks.values() if t.agent_name == info["name"]]
        last_task = max(agent_tasks, key=lambda t: t.started_at or "", default=None)

        status = "idle"
        last_run = None
        duration = None
        if last_task:
            if last_task.status == "running":
                status = "running"
            else:
                status = last_task.status
            last_run = last_task.started_at
            # 计算耗时
            if last_task.started_at and last_task.finished_at:
                try:
                    t0 = datetime.fromisoformat(last_task.started_at)
                    t1 = datetime.fromisoformat(last_task.finished_at)
                    duration = round((t1 - t0).total_seconds(), 2)
                except Exception:
                    pass

        agents.append(AgentInfo(
            name=info["name"],
            description=info["description"],
            status=status,
            last_run=last_run,
            duration=duration,
        ).model_dump())

    return {"agents": agents}


@router.post("/start", summary="启动单个 Agent 任务")
async def start_agent(req: StartRequest):
    """启动一个 agent 执行任务，返回 task_id。"""
    # 验证 agent 是否存在
    agent_file = AGENTS_DIR / f"{req.agent_name}.md"
    if not agent_file.exists():
        raise HTTPException(status_code=404, detail=f"Agent '{req.agent_name}' 不存在")

    task_id = str(uuid.uuid4())[:8]
    task = AgentTask(id=task_id, agent_name=req.agent_name, prompt=req.prompt)
    _tasks[task_id] = task

    # 在后台启动 agent 进程
    asyncio.create_task(_run_agent_tracked(task_id))

    return {"task_id": task_id, "status": "pending", "agent_name": req.agent_name}


@router.post("/start-parallel", summary="并行启动多个 Agent 任务")
async def start_parallel(req: StartParallelRequest):
    """并行启动多个 agent，返回所有 task_id。"""
    results = []
    for item in req.tasks:
        agent_file = AGENTS_DIR / f"{item.agent_name}.md"
        if not agent_file.exists():
            results.append({"agent_name": item.agent_name, "error": f"Agent '{item.agent_name}' 不存在"})
            continue

        task_id = str(uuid.uuid4())[:8]
        task = AgentTask(id=task_id, agent_name=item.agent_name, prompt=item.prompt)
        _tasks[task_id] = task
        asyncio.create_task(_run_agent_tracked(task_id))
        results.append({"task_id": task_id, "status": "pending", "agent_name": item.agent_name})

    return {"tasks": results}


@router.get("/tasks", summary="列出所有任务")
async def list_tasks():
    """返回所有任务及其状态，按启动时间倒序。"""
    tasks = sorted(
        _tasks.values(),
        key=lambda t: t.started_at or "",
        reverse=True,
    )
    return {"tasks": [t.model_dump() for t in tasks]}


@router.get("/tasks/{task_id}", summary="获取单个任务详情")
async def get_task(task_id: str):
    """返回指定任务的详细信息和输出。"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 '{task_id}' 不存在")
    return task.model_dump()


@router.post("/tasks/{task_id}/stop", summary="停止运行中的任务")
async def stop_task(task_id: str):
    """终止运行中的 agent 进程。"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 '{task_id}' 不存在")
    if task.status != "running":
        raise HTTPException(status_code=400, detail=f"任务状态为 '{task.status}'，无法停止")

    proc = _processes.get(task_id)
    if proc:
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
        task.status = "failed"
        task.output = (task.output or "") + "\n[用户手动停止]"
        task.finished_at = _now_iso()
        _log_activity("stopped", task.agent_name, task_id)

    return {"task_id": task_id, "status": task.status}


@router.get("/activity", summary="获取最近活动日志")
async def get_activity():
    """返回最近 20 条 agent 活动事件。"""
    return {"activity": _activity_log[-20:]}
