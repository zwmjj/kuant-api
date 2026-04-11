from pydantic import BaseModel
from typing import Optional


class BacktestRequest(BaseModel):
    strategy_id: Optional[str] = None  # If set, used to route to CN/US engine
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
    end_date: str = ""  # empty = today
    initial_capital: float = 100000
    compare_id: Optional[str] = None


class KPI(BaseModel):
    label: str
    value: str
    color: str = "#0f172a"
    vs_text: str = ""
    tooltip: str = ""


class GateCheck(BaseModel):
    name: str
    passed: bool


class ChartSeries(BaseModel):
    dates: list[str] = []
    values: list[float] = []
    name: str = ""


class EquityChart(BaseModel):
    strategy: ChartSeries
    spy: ChartSeries
    drawdown: ChartSeries
    compare: Optional[ChartSeries] = None


class HeatmapData(BaseModel):
    years: list[str]
    months: list[str]
    values: list[list[Optional[float]]]


class DistributionData(BaseModel):
    bins: list[float]
    var_95: float
    cvar_95: float
    mean: float


class RollingSharpeData(BaseModel):
    strategy: ChartSeries
    compare: Optional[ChartSeries] = None


class YearlyData(BaseModel):
    years: list[str]
    strategy: list[float]
    benchmark: list[float]
    compare: Optional[list[float]] = None
    compare_name: str = ""


class FactorData(BaseModel):
    names: list[str]
    betas: list[float]
    alpha: float
    r2: float


class StatsRow(BaseModel):
    metric: str
    value: str
    compare_value: str = ""


class BacktestResponse(BaseModel):
    status: str
    kpis: list[KPI]
    gates: list[GateCheck]
    gates_passed: int
    gates_total: int
    equity: EquityChart
    heatmap: HeatmapData
    distribution: DistributionData
    rolling_sharpe: RollingSharpeData
    yearly: YearlyData
    factor: FactorData
    stats: list[StatsRow]
    compare_name: str = ""
