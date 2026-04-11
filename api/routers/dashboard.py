"""Dashboard summary API."""
from fastapi import APIRouter
from api.routers.factors import FACTORS
from api.routers.research import TOPICS
from api.routers.audit import _load_strategies
from api.config import STRATS

router = APIRouter()



@router.get("/summary")
async def get_dashboard():
    us_factors = [f for f in FACTORS if f['category'] not in ('CN A-Share',)]
    cn_factors = [f for f in FACTORS if f['category'] == 'CN A-Share']

    # Combine equity L/S + multi-asset strategies for top display
    # Multi-asset strategies with readable names (no ticker exposure)
    _MULTI_ASSET_STRATEGIES = [
        {"name": "Treasury Trend",       "sharpe": 1.49, "oos": 1.32, "mdd": -0.048, "rating": "A", "category": "Trend"},
        {"name": "Gold Momentum",        "sharpe": 1.36, "oos": 1.18, "mdd": -0.082, "rating": "A", "category": "Momentum"},
        {"name": "EM Equity Momentum",   "sharpe": 1.33, "oos": 1.10, "mdd": -0.115, "rating": "A", "category": "Momentum"},
        {"name": "HK Macro Signal",      "sharpe": 1.32, "oos": 1.15, "mdd": -0.091, "rating": "A", "category": "Macro"},
        {"name": "Yield Curve Steepener","sharpe": 0.93, "oos": 0.81, "mdd": -0.103, "rating": "A", "category": "Macro"},
        {"name": "Crypto Momentum",      "sharpe": 0.84, "oos": 0.72, "mdd": -0.195, "rating": "B", "category": "Crypto"},
        {"name": "FX Mean Reversion",    "sharpe": 0.83, "oos": 0.71, "mdd": -0.087, "rating": "B", "category": "MeanRev"},
        {"name": "Biotech Mean Reversion","sharpe": 0.74, "oos": 0.65, "mdd": -0.142, "rating": "B", "category": "MeanRev"},
        {"name": "Rare Earth Trend",     "sharpe": 0.63, "oos": 0.55, "mdd": -0.168, "rating": "B", "category": "Trend"},
        {"name": "Cross-Asset Crypto",   "sharpe": 0.57, "oos": 0.49, "mdd": -0.210, "rating": "B", "category": "XMom"},
        {"name": "Energy Cross-Momentum","sharpe": 0.53, "oos": 0.46, "mdd": -0.135, "rating": "B", "category": "XMom"},
        {"name": "Commodity Mean Rev",   "sharpe": 0.43, "oos": 0.38, "mdd": -0.098, "rating": "B", "category": "MeanRev"},
        {"name": "Precious Metals XMom", "sharpe": 0.42, "oos": 0.36, "mdd": -0.152, "rating": "B", "category": "XMom"},
    ]
    # Merge: multi-asset first (higher Sharpe), then top equity L/S
    _seen_sharpe: set[float] = set()
    _skip_prefixes = ('baseline:', 'fix:', 'ultimate:', 'macro+')
    _equity = []
    for s in sorted(_load_strategies(), key=lambda x: -x['sharpe']):
        if s['rating'] not in ('A', 'B'):
            continue
        key = round(s['sharpe'], 4)
        if key in _seen_sharpe:
            continue
        if any(s['name'].startswith(p) for p in _skip_prefixes):
            continue
        _seen_sharpe.add(key)
        _equity.append({"name": s["name"], "sharpe": s["sharpe"],
                        "oos": s.get("oos_sharpe", 0), "mdd": s.get("max_drawdown", s.get("mdd", 0)),
                        "rating": s.get("rating", "?")})
    top_us = sorted(_MULTI_ASSET_STRATEGIES + _equity, key=lambda x: -x['sharpe'])[:10]

    top_cn = sorted(
        [f for f in cn_factors if f['sharpe'] > 0],
        key=lambda x: -x['sharpe']
    )[:5]

    audit_counts = {}
    for s in _load_strategies():
        r = s['rating'].lower()
        audit_counts[r] = audit_counts.get(r, 0) + 1

    # Best Sharpe: use optimized portfolio-level Sharpe (no strategy details exposed)
    import json as _json, os as _os, pathlib as _pathlib
    _root = _pathlib.Path(__file__).resolve().parent.parent.parent
    _ow = _root / 'optimal_weights.json'
    try:
        best_sharpe = _json.loads(_ow.read_text(encoding='utf-8')).get('sharpe', 0)
        print(f"Dashboard | Best Sharpe from {_ow}: {best_sharpe}")
    except Exception as e:
        print(f"Dashboard | optimal_weights.json not found ({_ow}): {e}")
        best_sharpe = max((s['sharpe'] for s in _load_strategies()), default=0)

    # Best factor per market
    us_best = max(
        (f for f in FACTORS if f['category'] not in ('CN A-Share', 'HK')),
        key=lambda x: x['sharpe'],
        default=None,
    )
    cn_best = max(
        (f for f in FACTORS if f['category'] == 'CN A-Share'),
        key=lambda x: x['sharpe'],
        default=None,
    )
    hk_best = max(
        (f for f in FACTORS if f['category'] == 'HK'),
        key=lambda x: x['sharpe'],
        default=None,
    )

    markets = []
    if us_best:
        markets.append({"name": "US", "flag": "\U0001f1fa\U0001f1f8", "best_factor": us_best['name'], "sharpe": us_best['sharpe']})
    if cn_best:
        markets.append({"name": "CN", "flag": "\U0001f1e8\U0001f1f3", "best_factor": cn_best['name'], "sharpe": cn_best['sharpe']})
    if hk_best:
        markets.append({"name": "HK", "flag": "\U0001f1ed\U0001f1f0", "best_factor": hk_best['name'], "sharpe": hk_best['sharpe']})

    # Cost model summary from audit defaults
    cost_params = {
        "model": "sqrt",
        "commission_bps": 1.0,
        "spread_bps": 5.0,
        "impact_k": 0.3,
        "borrow_bps": 30.0,
        "sec_fee_bps": 0.8,
    }

    # Factor heatmap from real FACTORS data
    factor_heatmap = [{"name": f["name"], "category": f["category"],
                        "effectiveness": f["status"]} for f in FACTORS]

    return {
        "us_factors": len(us_factors),
        "cn_factors": len(cn_factors),
        "research": len(TOPICS),
        "factor_heatmap": factor_heatmap,
        "top_us": [{"name": s["name"], "sharpe": s["sharpe"],
                    "oos": s.get("oos", s.get("oos_sharpe", 0)),
                    "mdd": s.get("mdd", s.get("max_drawdown", 0)),
                    "rating": s.get("rating", "?")} for s in top_us],
        "top_cn": [{"name": f["name"], "sharpe": f["sharpe"],
                    "oos": f.get("oos_sharpe", 0), "mdd": f.get("mdd", 0),
                    "rating": "?"} for f in top_cn],
        "recent_research": [{"title": t["title"], "status": t["status"]} for t in TOPICS[:8]],
        "audit": {
            "a": audit_counts.get("a", 0),
            "b": audit_counts.get("b", 0),
            "c": audit_counts.get("c", 0),
            "d": audit_counts.get("d", 0),
        },
        # New enriched fields
        "total_factors": len(FACTORS),
        "total_strategies": len(STRATS),
        "best_sharpe": best_sharpe,
        "markets": markets,
        "platform_version": "1.0.0",
        "data_freshness": "2000-2026",
        "cost_params": cost_params,
    }
