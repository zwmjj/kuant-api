"""SOP Pipeline API — Phase 1-5 documentation and status."""
from fastapi import APIRouter

router = APIRouter()

PHASES = [
    {
        "id": 1, "name": "Initiation", "icon": "📋", "status": "complete",
        "description": "Strategy proposal, capacity estimation, feasibility check",
        "modules": ["initiation_form.py", "capacity_estimator.py", "feasibility_check.py"],
        "gates": [
            {"name": "Economic mechanism documented", "type": "mandatory"},
            {"name": "Signal direction pre-specified", "type": "mandatory"},
            {"name": "Capacity ≥ target AUM", "type": "mandatory"},
            {"name": "Data sources confirmed", "type": "mandatory"},
            {"name": "Gate thresholds locked (immutable)", "type": "mandatory"},
        ],
        "deliverables": [
            "Initiation document with SHA256 hash",
            "Capacity estimate (theoretical + conservative)",
            "Feasibility report",
        ],
        "lines_of_code": 850,
    },
    {
        "id": 2, "name": "Research", "icon": "🔬", "status": "complete",
        "description": "PIT data pipeline, factor construction, IC testing, multi-factor synthesis",
        "modules": ["data_pipeline.py", "data_cleaner.py", "factor_builder.py",
                     "factor_analyzer.py", "factor_combiner.py", "walk_forward_cv.py"],
        "gates": [
            {"name": "|IC mean| > 0.03", "type": "mandatory"},
            {"name": "ICIR > 0.5", "type": "mandatory"},
            {"name": "IC > 0 ratio > 55%", "type": "mandatory"},
            {"name": "Layered test monotonic (Q1→Q5)", "type": "mandatory"},
        ],
        "deliverables": [
            "PIT-safe data (5 rules enforced)",
            "Cleaned factor (5-step pipeline)",
            "6-step factor processing chain",
            "IC/ICIR/half-life analysis",
            "5 combination methods (equal/IC/ICIR/Lasso/LightGBM)",
            "Walk-Forward CV with DSR",
        ],
        "lines_of_code": 2800,
    },
    {
        "id": 3, "name": "Backtest", "icon": "⚡", "status": "complete",
        "description": "Event-driven backtesting, cost modeling, portfolio optimization, stress testing",
        "modules": ["event_engine.py", "cost_model.py", "portfolio_optimizer.py",
                     "performance_metrics.py", "stress_test.py", "gate_checker.py"],
        "gates": [
            {"name": "Sharpe (net) > 1.0", "type": "mandatory"},
            {"name": "Max Drawdown < 15%", "type": "mandatory"},
            {"name": "IS→OOS decay < 50%", "type": "mandatory"},
            {"name": "OOS Sharpe > 0.5", "type": "mandatory"},
            {"name": "Calmar > 0.8", "type": "mandatory"},
            {"name": "DSR > 1.0 (if params > 2)", "type": "conditional"},
        ],
        "deliverables": [
            "Event-driven engine (bar-by-bar, T+1 execution)",
            "3 cost models (linear/Almgren-Chriss/power law)",
            "cvxpy optimizer (beta-neutral, industry, position limits)",
            "6 stress scenarios (2015 crash, circuit breaker, etc.)",
            "Full IS/OOS performance split",
        ],
        "lines_of_code": 3200,
    },
    {
        "id": 4, "name": "Review", "icon": "🔍", "status": "complete",
        "description": "Independent code review, bias detection, risk assessment, approval",
        "modules": ["code_reviewer.py", "independent_backtest.py", "risk_review.py", "approval_tracker.py"],
        "gates": [
            {"name": "7 bias checks passed", "type": "mandatory"},
            {"name": "Independent backtest CAGR diff < 0.5%", "type": "mandatory"},
            {"name": "Risk review cleared", "type": "mandatory"},
            {"name": "Investment committee approval", "type": "mandatory"},
        ],
        "deliverables": [
            "7-bias automated checker (lookahead, survivorship, snooping, etc.)",
            "Independent backtest verification",
            "Barra-style risk decomposition",
            "State machine approval tracker",
        ],
        "lines_of_code": 2400,
    },
    {
        "id": 5, "name": "Launch", "icon": "🚀", "status": "complete",
        "description": "Paper trading, seed capital, ramp-up, monitoring",
        "modules": ["paper_trading.py", "seed_capital.py", "ramp_up_controller.py", "adjustment_logger.py"],
        "gates": [
            {"name": "Signal correlation > 0.98", "type": "paper_trading"},
            {"name": "4 weeks zero downtime", "type": "paper_trading"},
            {"name": "Rolling 8w Sharpe > 0.8", "type": "seed"},
            {"name": "Cost ratio < 1.5x", "type": "ramp_up"},
            {"name": "Execution rate > 90%", "type": "ramp_up"},
        ],
        "deliverables": [
            "Paper trading engine (4-8 weeks)",
            "5-indicator monitoring dashboard",
            "5-stage ramp-up controller (7.5%→25%→50%→75%→100%)",
            "Adjustment logger (CSV+JSON, no deletion)",
            "3 prohibitions enforced",
        ],
        "lines_of_code": 1800,
    },
]

SHARED_INFRA = {
    "modules": ["audit_logger.py", "gate_framework.py", "pit_data_store.py", "universe_manager.py"],
    "lines_of_code": 1500,
    "features": [
        "Thread-safe audit logger (JSON lines + in-memory)",
        "Abstract gate framework with composite checker",
        "PIT data store with versioning (Parquet)",
        "Universe manager with survivorship validation",
    ],
}


@router.get("/phases")
async def get_phases():
    total_lines = sum(p["lines_of_code"] for p in PHASES) + SHARED_INFRA["lines_of_code"]
    total_modules = sum(len(p["modules"]) for p in PHASES) + len(SHARED_INFRA["modules"])
    return {
        "phases": PHASES,
        "shared": SHARED_INFRA,
        "summary": {
            "total_phases": 5,
            "total_modules": total_modules,
            "total_lines": total_lines,
            "total_gates": sum(len(p["gates"]) for p in PHASES),
        },
    }
