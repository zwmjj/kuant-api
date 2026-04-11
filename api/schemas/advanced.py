from pydantic import BaseModel
from typing import Literal, Optional


class BaseParams(BaseModel):
    w_mom: float = 75
    w_accel: float = 25
    w_quality: float = 0
    w_vol: float = 0
    long_n: int = 20
    short_n: int = 20
    long_pct: float = 115
    short_pct: float = 15
    turnover_penalty: float = 0.25
    cost_bps: float = 2
    start_date: str = "2015-01-01"
    end_date: str = ""
    initial_capital: float = 100000


class WalkForwardRequest(BaseParams):
    window_type: Literal["rolling", "anchored"] = "rolling"
    is_months: int = 36
    oos_months: int = 12
    step_months: int = 12
    objective: Literal["sharpe", "sortino", "calmar"] = "sharpe"
    optimize_per_window: bool = False
    n_candidates: int = 12


class OptimizeRequest(BaseParams):
    method: Literal["grid", "random"] = "grid"
    objective: Literal["sharpe", "sortino", "calmar"] = "sharpe"
    grid_step: int = 25
    n_iter: int = 200


class StressTestRequest(BaseParams):
    scenarios: list[str] = []


class SensitivityRequest(BaseParams):
    param_name: str = "w_mom"
    param_min: float = 0
    param_max: float = 100
    param_step: float = 10
