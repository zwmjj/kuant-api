"""Code execution & source viewer API."""
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional
from api.services.code_service import execute_code, get_source_code, TEMPLATES

router = APIRouter()


class RunCodeRequest(BaseModel):
    code: str
    mode: str = "backtest"  # "backtest" | "research"
    params: Optional[dict] = None


@router.post("/run")
async def run_code(req: RunCodeRequest, request: Request):
    data = request.app.state.data
    result = execute_code(req.code, req.mode, data, req.params or {})
    return result


@router.get("/templates")
async def get_templates():
    return {"templates": [
        {"id": k, "name": v["name"], "description": v["description"], "code": v["code"]}
        for k, v in TEMPLATES.items()
    ]}


@router.get("/source/{source_id:path}")
async def get_source(source_id: str):
    return get_source_code(source_id)


@router.get("/files")
async def list_source_files():
    """List viewable source files."""
    return {"files": [
        {"path": "qf/signals.py", "name": "Signal Generator", "category": "Core"},
        {"path": "qf/backtest.py", "name": "Backtest Engine", "category": "Core"},
        {"path": "qf/costs.py", "name": "Cost Models", "category": "Core"},
        {"path": "qf/data.py", "name": "Data Loader", "category": "Core"},
        {"path": "qf/risk.py", "name": "Risk Analysis", "category": "Analysis"},
        {"path": "qf/stress.py", "name": "Stress Testing", "category": "Analysis"},
        {"path": "qf/optimizer.py", "name": "Optimizer", "category": "Analysis"},
        {"path": "qf/attribution.py", "name": "Factor Attribution", "category": "Analysis"},
        {"path": "qf/portfolio.py", "name": "Portfolio Optimization", "category": "Analysis"},
        {"path": "qf/strategy.py", "name": "Strategy Base Class", "category": "Framework"},
        {"path": "qf/framework.py", "name": "Framework Orchestrator", "category": "Framework"},
        {"path": "strategies/factors.py", "name": "Factor Strategies", "category": "Strategies"},
        {"path": "strategies/momentum.py", "name": "Momentum Strategies", "category": "Strategies"},
    ]}
