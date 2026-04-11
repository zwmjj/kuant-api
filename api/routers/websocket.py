"""WebSocket 实时推送端点 — 行情、信号、持仓、风控告警。"""
import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


# ---------------------------------------------------------------------------
# 连接管理器：维护多客户端连接与订阅关系
# ---------------------------------------------------------------------------

class ConnectionManager:
    """管理 WebSocket 连接的生命周期和消息分发。"""

    def __init__(self):
        # channel -> 已连接的 WebSocket 集合
        self.channels: Dict[str, Set[WebSocket]] = {
            "market": set(),
            "signals": set(),
            "portfolio": set(),
            "alerts": set(),
        }
        # 每个 WebSocket 对应的订阅频道集合
        self.subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, ws: WebSocket, channel: str):
        """接受连接并自动订阅默认频道。"""
        await ws.accept()
        self.subscriptions.setdefault(ws, set())
        self._subscribe(ws, channel)

    def disconnect(self, ws: WebSocket):
        """断开连接，从所有频道中移除。"""
        for ch in list(self.subscriptions.get(ws, [])):
            self.channels.get(ch, set()).discard(ws)
        self.subscriptions.pop(ws, None)

    def _subscribe(self, ws: WebSocket, channel: str):
        """将客户端订阅到指定频道。"""
        if channel in self.channels:
            self.channels[channel].add(ws)
            self.subscriptions.setdefault(ws, set()).add(channel)

    def _unsubscribe(self, ws: WebSocket, channel: str):
        """取消客户端对指定频道的订阅。"""
        self.channels.get(channel, set()).discard(ws)
        subs = self.subscriptions.get(ws)
        if subs:
            subs.discard(channel)

    async def handle_client_message(self, ws: WebSocket, raw: str) -> dict | None:
        """
        处理客户端发来的 JSON 消息。
        支持的 action:
          - subscribe   {"action": "subscribe",   "channel": "market"}
          - unsubscribe {"action": "unsubscribe", "channel": "signals"}
          - ping        {"action": "ping"}
        返回需要回复给客户端的消息字典，若无需回复则返回 None。
        """
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return _make_msg("error", {"detail": "无效的 JSON 格式"})

        action = msg.get("action", "").lower()
        channel = msg.get("channel", "")

        if action == "ping":
            return _make_msg("pong", {})

        if action == "subscribe":
            if channel not in self.channels:
                return _make_msg("error", {"detail": f"未知频道: {channel}"})
            self._subscribe(ws, channel)
            return _make_msg("subscribed", {"channel": channel})

        if action == "unsubscribe":
            self._unsubscribe(ws, channel)
            return _make_msg("unsubscribed", {"channel": channel})

        return _make_msg("error", {"detail": f"未知操作: {action}"})

    async def broadcast(self, channel: str, data: dict):
        """向指定频道的所有客户端广播消息。"""
        payload = _make_msg(channel, data)
        text = json.dumps(payload, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in list(self.channels.get(channel, [])):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        # 清理已断开的连接
        for ws in dead:
            self.disconnect(ws)


# 全局单例
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _make_msg(msg_type: str, data: dict) -> dict:
    """构造标准 JSON 消息，包含 timestamp / type / data。"""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": msg_type,
        "data": data,
    }


# ---------------------------------------------------------------------------
# 心跳：服务端定时发送 ping，检测死连接
# ---------------------------------------------------------------------------

async def _heartbeat(ws: WebSocket, interval: int = 30):
    """每隔 interval 秒向客户端发送心跳 ping。"""
    try:
        while True:
            await asyncio.sleep(interval)
            await ws.send_text(json.dumps(_make_msg("ping", {}), ensure_ascii=False))
    except Exception:
        # 连接已关闭，静默退出
        pass


# ---------------------------------------------------------------------------
# WebSocket 端点
# ---------------------------------------------------------------------------

async def _ws_loop(ws: WebSocket, channel: str):
    """通用 WebSocket 主循环：连接 → 心跳 → 收消息 → 断开。"""
    await manager.connect(ws, channel)
    # 启动心跳协程
    hb_task = asyncio.create_task(_heartbeat(ws))
    try:
        # 发送欢迎消息
        welcome = _make_msg("connected", {
            "channel": channel,
            "message": f"已连接到 {channel} 频道",
        })
        await ws.send_text(json.dumps(welcome, ensure_ascii=False))

        # 持续接收客户端消息
        while True:
            raw = await ws.receive_text()
            reply = await manager.handle_client_message(ws, raw)
            if reply:
                await ws.send_text(json.dumps(reply, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    finally:
        hb_task.cancel()
        manager.disconnect(ws)


@router.websocket("/market")
async def ws_market(ws: WebSocket):
    """实时行情数据推送。"""
    await _ws_loop(ws, "market")


@router.websocket("/signals")
async def ws_signals(ws: WebSocket):
    """实时因子信号推送。"""
    await _ws_loop(ws, "signals")


@router.websocket("/portfolio")
async def ws_portfolio(ws: WebSocket):
    """持仓和 PnL 变化推送。"""
    await _ws_loop(ws, "portfolio")


@router.websocket("/alerts")
async def ws_alerts(ws: WebSocket):
    """风控告警推送。"""
    await _ws_loop(ws, "alerts")
