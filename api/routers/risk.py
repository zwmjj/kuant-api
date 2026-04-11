"""实时风控 API — 提供组合风险指标、告警、压力测试等端点"""
import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from qf.risk_manager import RiskManager, STRESS_SCENARIOS
from qf.risk import RiskAnalyzer
from qf.anomaly_detector import StrategyAnomalyDetector

router = APIRouter()

# ---------------------------------------------------------------------------
# 全局实例（模块级单例）
# ---------------------------------------------------------------------------
_risk_mgr = RiskManager(risk_log_path="risk_log.csv")
_anomaly_detector = StrategyAnomalyDetector(
    window=30, z_threshold=2.5,
    drawdown_warning=0.08, drawdown_critical=0.15,
)

# ---------------------------------------------------------------------------
# 风控限制参数（可在运行时通过 PUT /limits 更新）
# ---------------------------------------------------------------------------
_risk_limits: Dict[str, float] = {
    "max_drawdown_warning": 0.08,       # 回撤 warning 阈值
    "max_drawdown_critical": 0.15,      # 回撤 critical 阈值
    "var_95_limit": 0.05,               # 日 VaR(95%) 上限
    "concentration_hhi_limit": 0.25,    # HHI 集中度上限
    "single_position_limit": 0.10,      # 单一持仓占比上限
    "sector_concentration_limit": 0.30, # 行业集中度上限
    "target_volatility": 0.10,          # 目标年化波动率
}


# ===========================================================================
# Pydantic 模型
# ===========================================================================

class StressTestRequest(BaseModel):
    """压力测试请求体"""
    scenarios: List[str] = Field(
        default=["COVID_2020", "FLASH_CRASH"],
        description="压力情景名称列表，可选: COVID_2020, BEAR_2022, FLASH_CRASH, BOND_CRASH, CRYPTO_CRASH",
    )
    portfolio_value: float = Field(default=100000.0, description="组合市值")


class RiskLimitsUpdate(BaseModel):
    """风控限制参数更新请求"""
    max_drawdown_warning: Optional[float] = None
    max_drawdown_critical: Optional[float] = None
    var_95_limit: Optional[float] = None
    concentration_hhi_limit: Optional[float] = None
    single_position_limit: Optional[float] = None
    sector_concentration_limit: Optional[float] = None
    target_volatility: Optional[float] = None


# ===========================================================================
# 模拟数据生成（当真实数据不可用时）
# ===========================================================================

def _generate_mock_returns(days: int = 252, seed: int = 42) -> pd.Series:
    """生成模拟日收益率序列"""
    rng = np.random.RandomState(seed)
    returns = rng.normal(0.0004, 0.012, size=days)
    # 加入偶尔的尾部事件
    for i in rng.choice(days, size=max(1, days // 50), replace=False):
        returns[i] *= rng.choice([-3, -2.5, 2], p=[0.5, 0.3, 0.2])
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=days)
    return pd.Series(returns, index=dates, name="portfolio_return")


def _generate_mock_positions() -> Dict[str, float]:
    """生成模拟持仓权重"""
    return {
        "AAPL": 18500.0, "MSFT": 15200.0, "GOOGL": 12800.0,
        "AMZN": 9600.0, "NVDA": 11400.0, "META": 7200.0,
        "TSLA": 6800.0, "JPM": 5500.0, "V": 4800.0, "UNH": 4200.0,
    }


def _generate_mock_equity_curve(returns: pd.Series, initial: float = 100000.0) -> pd.Series:
    """根据收益率序列生成净值曲线"""
    return initial * (1 + returns).cumprod()


def _calc_hhi(positions: Dict[str, float]) -> float:
    """计算赫芬达尔指数 (HHI) 衡量集中度"""
    total = sum(abs(v) for v in positions.values())
    if total <= 0:
        return 0.0
    weights = [abs(v) / total for v in positions.values()]
    return sum(w ** 2 for w in weights)


def _calc_beta(port_returns: pd.Series, market_returns: Optional[pd.Series] = None) -> float:
    """计算组合对市场的 beta"""
    if market_returns is None:
        # 模拟市场收益率（与组合有一定相关性）
        rng = np.random.RandomState(99)
        noise = rng.normal(0, 0.005, size=len(port_returns))
        market_returns = pd.Series(
            port_returns.values * 0.7 + noise[:len(port_returns)],
            index=port_returns.index,
        )
    cov = np.cov(port_returns.values, market_returns.values)
    var_market = cov[1, 1]
    if var_market < 1e-12:
        return 1.0
    return float(cov[0, 1] / var_market)


# ===========================================================================
# 端点实现
# ===========================================================================

@router.get("/realtime")
async def get_realtime_risk():
    """
    返回实时风控指标

    包含 VaR、CVaR、回撤、集中度、beta、波动率等核心风险度量。
    当真实持仓数据不可用时，返回基于模拟数据的合理值。
    """
    # 获取模拟数据
    returns = _generate_mock_returns(days=252)
    positions = _generate_mock_positions()
    equity_curve = _generate_mock_equity_curve(returns)
    equity = float(equity_curve.iloc[-1])

    # 使用 RiskAnalyzer 计算 VaR / CVaR
    analyzer = RiskAnalyzer(returns)

    # 参数法 VaR (正态分布假设)
    mu = float(returns.mean())
    sigma = float(returns.std())
    from scipy import stats as sp_stats
    parametric_var_95 = mu + sp_stats.norm.ppf(0.05) * sigma

    # 历史法 VaR
    historical_var_95 = float(analyzer.var(0.95))

    # 综合 VaR（取两者中更保守的）
    portfolio_var_95 = min(parametric_var_95, historical_var_95)

    # CVaR (Expected Shortfall)
    portfolio_cvar_95 = float(analyzer.cvar(0.95))

    # 回撤
    max_dd = float(analyzer.max_drawdown())
    dd_series = analyzer.drawdown_series()
    current_dd = float(dd_series.iloc[-1])

    # 集中度 (HHI)
    hhi = _calc_hhi(positions)

    # Beta
    beta = _calc_beta(returns)

    # 年化波动率
    ann_vol = sigma * np.sqrt(252)

    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "portfolio_value": round(equity, 2),
        "metrics": {
            "portfolio_var_95": {
                "value": round(portfolio_var_95, 6),
                "parametric": round(parametric_var_95, 6),
                "historical": round(historical_var_95, 6),
                "dollar_amount": round(equity * abs(portfolio_var_95), 2),
                "description": "95% 日 VaR（综合参数法与历史法，取保守值）",
            },
            "portfolio_cvar_95": {
                "value": round(portfolio_cvar_95, 6),
                "dollar_amount": round(equity * abs(portfolio_cvar_95), 2),
                "description": "95% CVaR / Expected Shortfall",
            },
            "max_drawdown": {
                "value": round(max_dd, 6),
                "percentage": f"{max_dd:.2%}",
                "description": "历史最大回撤",
            },
            "current_drawdown": {
                "value": round(current_dd, 6),
                "percentage": f"{current_dd:.2%}",
                "description": "当前回撤水平",
            },
            "concentration_risk": {
                "hhi": round(hhi, 6),
                "equivalent_positions": round(1.0 / hhi, 1) if hhi > 0 else 0,
                "description": "持仓集中度 (赫芬达尔指数, 越低越分散)",
            },
            "beta": {
                "value": round(beta, 4),
                "description": "组合对市场的 Beta",
            },
            "volatility": {
                "annualized": round(ann_vol, 6),
                "daily": round(sigma, 6),
                "percentage": f"{ann_vol:.2%}",
                "description": "年化波动率",
            },
        },
        "data_source": "simulated",
    }


@router.get("/alerts")
async def get_risk_alerts():
    """
    返回当前告警列表

    检查回撤、VaR 超限、集中度过高、异常检测等维度，
    生成 warning / critical 级别的告警。
    """
    returns = _generate_mock_returns(days=252)
    positions = _generate_mock_positions()
    equity_curve = _generate_mock_equity_curve(returns)
    equity = float(equity_curve.iloc[-1])

    alerts: List[Dict] = []

    # --- 1. 回撤告警 ---
    analyzer = RiskAnalyzer(returns)
    dd_series = analyzer.drawdown_series()
    current_dd = float(dd_series.iloc[-1])
    abs_dd = abs(current_dd)

    if abs_dd >= _risk_limits["max_drawdown_critical"]:
        alerts.append({
            "id": "dd_critical",
            "type": "drawdown",
            "severity": "critical",
            "message": f"回撤 {current_dd:.2%} 超过严重阈值 {_risk_limits['max_drawdown_critical']:.0%}，建议立即减仓",
            "value": round(current_dd, 6),
            "threshold": _risk_limits["max_drawdown_critical"],
            "timestamp": datetime.datetime.now().isoformat(),
        })
    elif abs_dd >= _risk_limits["max_drawdown_warning"]:
        alerts.append({
            "id": "dd_warning",
            "type": "drawdown",
            "severity": "warning",
            "message": f"回撤 {current_dd:.2%} 超过预警阈值 {_risk_limits['max_drawdown_warning']:.0%}",
            "value": round(current_dd, 6),
            "threshold": _risk_limits["max_drawdown_warning"],
            "timestamp": datetime.datetime.now().isoformat(),
        })

    # --- 2. VaR 超限告警 ---
    var_95 = float(analyzer.var(0.95))
    if abs(var_95) > _risk_limits["var_95_limit"]:
        alerts.append({
            "id": "var_warning",
            "type": "var_breach",
            "severity": "warning",
            "message": f"日 VaR(95%) = {var_95:.4f}，超过限额 {_risk_limits['var_95_limit']:.2%}",
            "value": round(var_95, 6),
            "threshold": _risk_limits["var_95_limit"],
            "timestamp": datetime.datetime.now().isoformat(),
        })

    # --- 3. 集中度过高告警 ---
    hhi = _calc_hhi(positions)
    if hhi > _risk_limits["concentration_hhi_limit"]:
        alerts.append({
            "id": "concentration_warning",
            "type": "concentration",
            "severity": "warning",
            "message": f"持仓集中度 HHI={hhi:.4f}，超过限额 {_risk_limits['concentration_hhi_limit']:.2f}",
            "value": round(hhi, 6),
            "threshold": _risk_limits["concentration_hhi_limit"],
            "timestamp": datetime.datetime.now().isoformat(),
        })

    # --- 4. 单一持仓超限 ---
    total_mv = sum(abs(v) for v in positions.values())
    for ticker, mv in positions.items():
        weight = abs(mv) / total_mv if total_mv > 0 else 0
        if weight > _risk_limits["single_position_limit"]:
            alerts.append({
                "id": f"position_{ticker}",
                "type": "position_concentration",
                "severity": "warning",
                "message": f"持仓 {ticker} 占比 {weight:.1%}，超过单一持仓限额 {_risk_limits['single_position_limit']:.0%}",
                "value": round(weight, 6),
                "threshold": _risk_limits["single_position_limit"],
                "timestamp": datetime.datetime.now().isoformat(),
            })

    # --- 5. 异常检测告警（来自 anomaly_detector）---
    # 用最近数据喂入异常检测器
    _anomaly_detector.reset()
    ann_vol = float(returns.std()) * np.sqrt(252)
    for i in range(len(returns)):
        metrics = {
            "return": float(returns.iloc[i]),
            "volatility": ann_vol,
            "max_drawdown": float(dd_series.iloc[i]) if i < len(dd_series) else 0.0,
            "turnover": 0.05,
            "factor_exposure": 0.0,
        }
        ts = returns.index[i]
        _anomaly_detector.update(ts, metrics)

    anomaly_alerts = _anomaly_detector.check_alerts()
    for a in anomaly_alerts:
        alerts.append({
            "id": f"anomaly_{a['type']}",
            "type": f"anomaly_{a['type']}",
            "severity": a["severity"],
            "message": a["message"],
            "value": a.get("details", {}).get("z_score", None),
            "threshold": None,
            "timestamp": str(a.get("timestamp", "")),
        })

    # 按严重级别排序: critical 优先
    severity_order = {"critical": 0, "warning": 1}
    alerts.sort(key=lambda x: severity_order.get(x["severity"], 99))

    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "total_alerts": len(alerts),
        "critical_count": sum(1 for a in alerts if a["severity"] == "critical"),
        "warning_count": sum(1 for a in alerts if a["severity"] == "warning"),
        "alerts": alerts,
        "health_score": _anomaly_detector.get_health_score(),
        "data_source": "simulated",
    }


@router.get("/history")
async def get_risk_history(days: int = Query(default=30, ge=1, le=365, description="历史天数")):
    """
    返回历史风控指标时间序列

    提供每日的 VaR、CVaR、回撤、波动率等指标，用于趋势分析。
    """
    # 生成足够长的模拟数据
    total_days = days + 60  # 额外 60 天用于滚动窗口计算
    returns = _generate_mock_returns(days=total_days)
    equity_curve = _generate_mock_equity_curve(returns)

    history = []
    window = 60  # 滚动窗口

    for i in range(window, len(returns)):
        date = returns.index[i]
        window_returns = returns.iloc[i - window:i]
        window_equity = equity_curve.iloc[:i + 1]

        ra = RiskAnalyzer(window_returns)
        dd_series = ra.drawdown_series()

        var_95 = float(ra.var(0.95))
        cvar_95 = float(ra.cvar(0.95))
        max_dd = float(ra.max_drawdown())
        current_dd = float(dd_series.iloc[-1])
        vol = float(window_returns.std()) * np.sqrt(252)

        history.append({
            "date": str(date.date()),
            "portfolio_var_95": round(var_95, 6),
            "portfolio_cvar_95": round(cvar_95, 6),
            "max_drawdown": round(max_dd, 6),
            "current_drawdown": round(current_dd, 6),
            "volatility": round(vol, 6),
            "portfolio_value": round(float(equity_curve.iloc[i]), 2),
        })

    # 只返回最近 N 天
    history = history[-days:]

    return {
        "days": days,
        "total_points": len(history),
        "history": history,
        "data_source": "simulated",
    }


@router.post("/stress-test")
async def run_stress_test(request: StressTestRequest):
    """
    执行压力测试

    根据预定义的历史情景（如新冠暴跌、闪崩等），
    估算组合在各场景下的预计损失。
    """
    returns = _generate_mock_returns(days=252)
    portfolio_value = request.portfolio_value

    # 筛选请求的情景
    available_scenarios = {}
    unknown_scenarios = []
    for name in request.scenarios:
        key = name.upper()
        if key in STRESS_SCENARIOS:
            available_scenarios[key] = STRESS_SCENARIOS[key]
        else:
            unknown_scenarios.append(name)

    # 如果没有匹配的情景，使用全部
    if not available_scenarios:
        available_scenarios = STRESS_SCENARIOS

    # 使用 RiskManager 执行压力测试
    results_df = _risk_mgr.stress_test(returns, scenarios=available_scenarios)

    results = []
    for _, row in results_df.iterrows():
        estimated_loss_pct = float(row["estimated_loss"])
        estimated_loss_dollar = portfolio_value * abs(estimated_loss_pct)
        worst_day_pct = float(row["worst_day"])
        worst_day_dollar = portfolio_value * abs(worst_day_pct)

        results.append({
            "scenario": row["scenario"],
            "description": row["description"],
            "spy_shock": f"{float(row['spy_shock']):.1%}",
            "estimated_loss": {
                "percentage": round(estimated_loss_pct, 6),
                "dollar": round(estimated_loss_dollar, 2),
                "display": f"{estimated_loss_pct:.2%}",
            },
            "worst_single_day": {
                "percentage": round(worst_day_pct, 6),
                "dollar": round(worst_day_dollar, 2),
                "display": f"{worst_day_pct:.2%}",
            },
            "duration_days": int(row["duration_days"]),
        })

    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "portfolio_value": portfolio_value,
        "scenarios_tested": len(results),
        "unknown_scenarios": unknown_scenarios,
        "available_scenarios": list(STRESS_SCENARIOS.keys()),
        "results": results,
        "data_source": "simulated",
    }


@router.get("/limits")
async def get_risk_limits():
    """返回当前风控限制参数"""
    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "limits": _risk_limits,
        "description": {
            "max_drawdown_warning": "回撤 warning 阈值",
            "max_drawdown_critical": "回撤 critical 阈值",
            "var_95_limit": "日 VaR(95%) 上限",
            "concentration_hhi_limit": "HHI 集中度上限",
            "single_position_limit": "单一持仓占比上限",
            "sector_concentration_limit": "行业集中度上限",
            "target_volatility": "目标年化波动率",
        },
    }


@router.put("/limits")
async def update_risk_limits(update: RiskLimitsUpdate):
    """
    更新风控限制参数

    只更新请求中提供的字段，其余保持不变。
    """
    updated_fields = {}
    for field_name, value in update.model_dump(exclude_none=True).items():
        if field_name in _risk_limits:
            old_value = _risk_limits[field_name]
            _risk_limits[field_name] = value
            updated_fields[field_name] = {"old": old_value, "new": value}

    # 同步更新异常检测器的回撤阈值
    if "max_drawdown_warning" in updated_fields:
        _anomaly_detector.drawdown_warning = _risk_limits["max_drawdown_warning"]
    if "max_drawdown_critical" in updated_fields:
        _anomaly_detector.drawdown_critical = _risk_limits["max_drawdown_critical"]

    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "message": f"已更新 {len(updated_fields)} 个风控参数" if updated_fields else "未提供需要更新的参数",
        "updated_fields": updated_fields,
        "current_limits": _risk_limits,
    }
