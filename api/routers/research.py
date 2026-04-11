"""Research Library API — serves computed research data with charts."""
import json, os
from fastapi import APIRouter

router = APIRouter()

# Load computed research data
_DATA = None
def _load():
    global _DATA
    if _DATA is None:
        path = os.path.join(os.path.dirname(__file__), '..', '..', 'research_data.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                _DATA = json.load(f)
        else:
            _DATA = {}
    return _DATA


TOPICS = [
    {
        "id": "signal_decay_vs_cost",
        "title": "Signal Decay vs Transaction Cost Trade-off",
        "category": "Execution",
        "icon": "⚖️",
        "status": "completed",
        "abstract": "How does alpha decay as we reduce rebalancing frequency? What's the optimal turnover penalty for each factor?",
        "tags": ["Turnover", "Alpha Decay", "Market Impact"],
        "charts": [
            {"type": "line", "key": "factors", "title": "Sharpe vs Turnover Penalty", "x": "penalty", "y": "sharpe", "group_by": "factor"},
            {"type": "line", "key": "autocorrelation", "title": "Signal Autocorrelation (Half-Life)", "x": "lag", "y": "acf", "group_by": "factor"},
            {"type": "grouped_bar", "key": "cost_scenarios", "title": "Sharpe Under Cost Multipliers", "x": "multiplier", "y": "sharpe", "group_by": "factor"},
        ],
    },
    {
        "id": "survivorship_bias_impact",
        "title": "Survivorship Bias: Measured Impact",
        "category": "Data Quality",
        "icon": "👻",
        "status": "completed",
        "abstract": "8,446 delisting returns applied. Average delisting return: -5.3%. How much did each factor's performance change?",
        "tags": ["Delisting", "CRSP", "Shumway 1997"],
        "charts": [
            {"type": "bar", "key": "factors", "title": "Factor Performance (with Delisting Returns)", "x": "factor", "y": "sharpe_with_delist"},
            {"type": "table", "key": "factors", "title": "Detailed Metrics"},
        ],
    },
    {
        "id": "factor_crowding",
        "title": "Factor Crowding: R², Alpha Purity, and Orthogonalization",
        "category": "Factor Research",
        "icon": "🏢",
        "status": "completed",
        "abstract": "Which factors are just replicating known risk premia? Orthogonalization results show how to extract purer alpha.",
        "tags": ["R²", "Crowding", "Orthogonalization", "FF5"],
        "charts": [
            {"type": "scatter", "key": "factors", "title": "R² vs Alpha (bubble = Sharpe)", "x": "r2", "y": "alpha"},
            {"type": "hbar", "key": "factors", "title": "Factor Exposures (β_HML, β_UMD)", "x": "factor"},
            {"type": "comparison_table", "key": "orthogonal", "title": "Raw vs Orthogonalized"},
        ],
    },
    {
        "id": "regime_timing",
        "title": "Regime Timing: Does It Work?",
        "category": "Portfolio Construction",
        "icon": "🌊",
        "status": "completed",
        "abstract": "Scaling momentum exposure based on market volatility. Works at portfolio level, not single-factor level.",
        "tags": ["Regime", "Volatility", "Momentum Crash"],
        "charts": [
            {"type": "comparison_bar", "key": "factors", "title": "Base vs Regime-Adjusted", "metrics": ["sharpe", "mdd"]},
            {"type": "table", "key": "blend_comparison", "title": "Blend Comparison"},
        ],
    },
    {
        "id": "multifactor_construction",
        "title": "Multi-Factor Construction: How Many Factors?",
        "category": "Portfolio Construction",
        "icon": "🧩",
        "status": "completed",
        "abstract": "Testing 1 to 6 factor combinations. Signal-level integration vs portfolio mixing. Diminishing returns beyond 3-4 factors.",
        "tags": ["Multi-Factor", "Diversification", "Integration"],
        "charts": [
            {"type": "line", "key": "combos", "title": "Sharpe vs Number of Factors", "x": "n_factors", "y": "sharpe"},
            {"type": "table", "key": "combos", "title": "All Combinations"},
        ],
    },
    {
        "id": "execution_model",
        "title": "Execution Model: Layer-by-Layer Cost Impact",
        "category": "Execution",
        "icon": "⚠️",
        "status": "completed",
        "abstract": "How much does each cost component (commission, spread, impact, borrow, SEC) reduce performance?",
        "tags": ["Transaction Cost", "Market Impact", "Liquidity"],
        "charts": [
            {"type": "waterfall", "key": "cost_impact", "title": "Cumulative Cost Impact on Sharpe", "x": "label", "y": "sharpe"},
            {"type": "stats", "key": "adv_stats", "title": "ADV Distribution"},
        ],
    },
    {
        "id": "optimization_diminishing",
        "title": "Optimization Layers: Diminishing Returns",
        "category": "Portfolio Construction",
        "icon": "📉",
        "status": "completed",
        "abstract": "Each optimization layer (vol target, multi-factor, orthogonal, regime) tested sequentially. Stacking all ≠ best.",
        "tags": ["Optimization", "Diminishing Returns", "Signal Dilution"],
        "charts": [
            {"type": "bar", "key": "layers", "title": "Sharpe by Optimization Layer", "x": "layer", "y": "sharpe"},
            {"type": "bar", "key": "layers", "title": "MaxDD by Layer", "x": "layer", "y": "mdd"},
        ],
    },
    {
        "id": "equity_vol_factors",
        "title": "Equity Volatility Factor Zoo",
        "category": "Vol Research",
        "icon": "🌪️",
        "status": "completed",
        "abstract": "8 volatility factors tested: LowVol, Vol-of-Vol, Downside Vol, MAX, Skewness, Beta, Vol Term Structure, Vol Momentum. Best standalone: Skew (Sh=0.78). Best combo: downvol×gpa (Sh=1.12, MDD=-18.7%).",
        "tags": ["Volatility", "Low-Vol Anomaly", "BAB", "Skewness", "Defensive"],
        "charts": [
            {"type": "bar", "key": "vol_factor_audit", "title": "Vol Factor Sharpe Comparison"},
            {"type": "grouped_bar", "key": "vol_strategies", "title": "Vol Strategies & Combos"},
            {"type": "line", "key": "vol_decay", "title": "Signal Decay by Turnover Penalty"},
            {"type": "table", "key": "vol_regime", "title": "Performance by Market Regime"},
            {"type": "line", "key": "vol_rolling_sharpe", "title": "Rolling 3Y Sharpe"},
        ],
    },
    {
        "id": "cn_factors",
        "title": "A-Share Cross-Market: Factor & Regime Analysis",
        "category": "Cross-Market",
        "icon": "🇨🇳",
        "status": "completed",
        "abstract": "A-share style indices as factor proxies. Key findings: LowVol factor Sharpe=0.93 (strongest), Value cycle flips every 3 years, US-CN correlation ~0.5, US vol regime impacts CN differently.",
        "tags": ["A-Shares", "CSI 300", "Cross-Market", "Low-Vol", "Value-Growth Cycle", "Regime"],
        "charts": [
            {"type": "bar", "key": "cn_factor_proxies", "title": "A-Share Factor Proxies (Long-Short)"},
            {"type": "table", "key": "us_vol_cn_regime", "title": "US Vol Regime → CN Returns"},
            {"type": "table", "key": "value_growth_cycle", "title": "A-Share Value vs Growth Cycle"},
            {"type": "corr", "key": "cross_correlation", "title": "Cross-Market Correlation Matrix"},
        ],
    },
    {
        "id": "cross_market_robustness",
        "title": "Cross-Market Factor Robustness (US vs China)",
        "category": "Cross-Market",
        "icon": "🌐",
        "status": "completed",
        "abstract": "Same factors tested in US (CRSP stock-level) and China (CSI index-level). US-CN factor correlation near zero — excellent diversification. Low-Vol is the only factor robust in both markets.",
        "tags": ["Cross-Market", "Robustness", "US-CN", "Diversification", "Regime"],
        "charts": [
            {"type": "comparison_bar", "key": "factor_comparison", "title": "US vs CN Factor Sharpe"},
            {"type": "table", "key": "robustness_scores", "title": "Robustness Scores"},
            {"type": "table", "key": "cross_factor_correlation", "title": "US-CN Factor Return Correlation"},
            {"type": "table", "key": "regime_robustness", "title": "Regime-Conditional Performance"},
        ],
    },
    {
        "id": "industry_rotation",
        "title": "Industry/Sector Rotation & Factor Decomposition",
        "category": "Factor Research",
        "icon": "🏭",
        "status": "completed",
        "abstract": "10-industry momentum rotation using Kenneth French data. Profitability premium (OP Hi-Lo) Sharpe=0.47. Industry momentum Sharpe=0.23 — weak standalone but useful as diversifier.",
        "tags": ["Sector Rotation", "Industry Momentum", "Kenneth French", "OP", "INV"],
        "charts": [
            {"type": "bar", "key": "industry_stats", "title": "10-Industry Sharpe Comparison"},
            {"type": "table", "key": "momentum_deciles", "title": "Momentum Decile Returns"},
            {"type": "line", "key": "industry_momentum_rolling", "title": "Industry Momentum Rolling Sharpe"},
        ],
    },
    {
        "id": "new_factors",
        "title": "New Factor Discovery: 8 Factors from Existing Data",
        "category": "Factor Research",
        "icon": "🔍",
        "status": "completed",
        "abstract": "8 new factors built from existing CRSP+Compustat data. Best: Price-to-Sales (Sh=1.08, OOS=1.22), Momentum Breadth (OOS=1.24), Leverage Change (Sh=0.98).",
        "tags": ["New Factors", "P/S", "Earnings Quality", "Leverage", "Breadth"],
        "charts": [
            {"type": "bar", "key": "individual_factors", "title": "New Factor Sharpe: Full vs OOS"},
            {"type": "table", "key": "combo_strategies", "title": "Combo Strategies with New Factors"},
        ],
    },
    {
        "id": "hk_factors",
        "title": "Hong Kong HSI Factor Analysis + 3-Market Comparison",
        "category": "Cross-Market",
        "icon": "🇭🇰",
        "status": "completed",
        "abstract": "10 factors on 57 HSI stocks (2015-2025). Best: 12M Momentum (Sh=0.70) but 90% OOS decay. Downside Vol is only 6/6 factor. Cross-market: US factors consistently stronger than HK/CN.",
        "tags": ["Hong Kong", "HSI", "Cross-Market", "Momentum", "Volatility", "3-Market"],
        "charts": [
            {"type": "bar", "key": "factors", "title": "HK Factor Sharpe: Full vs OOS"},
            {"type": "bar", "key": "strategies", "title": "HK Combo Strategies"},
            {"type": "comparison_bar", "key": "cross_market", "title": "US vs CN vs HK Factor Comparison"},
        ],
    },
    {
        "id": "is_oos_stability",
        "title": "IS vs OOS: What Predicts Out-of-Sample Success?",
        "category": "Statistical",
        "icon": "🎯",
        "status": "completed",
        "abstract": "Low R² (less crowding) is the best predictor of OOS stability. High IS Sharpe is NOT a good predictor.",
        "tags": ["Overfitting", "IS/OOS", "Decay", "Prediction"],
        "charts": [
            {"type": "scatter", "key": "factors", "title": "IS Sharpe vs OOS Sharpe", "x": "is_sharpe", "y": "oos_sharpe"},
            {"type": "scatter", "key": "factors", "title": "R² vs Decay", "x": "r2", "y": "decay"},
            {"type": "table", "key": "factors", "title": "All Factors IS/OOS"},
        ],
    },
]


@router.get("/library")
async def get_research_library():
    data = _load()
    # Attach computed data to each topic
    enriched = []
    for topic in TOPICS:
        t = {**topic}
        t["data"] = data.get(topic["id"], {})
        enriched.append(t)
    return {"topics": enriched}
