from datetime import date
from fastapi import APIRouter, HTTPException, Request
from api.schemas.backtest import BacktestRequest
from api.config import STRATS

router = APIRouter()

CN_STRATEGY_IDS = {'cn_reversal', 'cn_lowvol', 'cn_vol_blend', 'cn_defensive'}
HK_STRATEGY_IDS = {'hk_mom_vol', 'hk_best3', 'hk_defensive'}
WRDS_STRATEGY_IDS = {
    'wrds_at_turn', 'wrds_inv_turn', 'wrds_de', 'wrds_curr', 'wrds_roe', 'wrds_ps',
    'macro_regime_blend', 'macro_wrds_ps', 'ceo_ownership', 'governance_macro',
    'governance_composite', 'ultimate_4f',
}


@router.post("/run")
async def run_backtest(req: BacktestRequest, request: Request):
    current_strat_id = req.strategy_id

    if current_strat_id in WRDS_STRATEGY_IDS:
        return await _run_wrds(req, request, current_strat_id)
    elif current_strat_id in CN_STRATEGY_IDS:
        return await _run_cn(req, request, current_strat_id)
    else:
        return await _run_us(req, request)


async def _run_cn(req: BacktestRequest, request: Request, strategy_id: str):
    """Run A-share backtest."""
    cn_data = getattr(request.app.state, 'cn_data', None)
    if cn_data is None:
        raise HTTPException(status_code=503, detail="A-share data not loaded")

    from api.services.cn_backtest_service import build_cn_signal, run_cn_backtest
    from api.services.backtest_service import _clean

    signal = build_cn_signal(strategy_id, cn_data)

    sd = req.start_date or "2010-01-01"
    ed = req.end_date or date.today().isoformat()
    cn_min = str(cn_data['prices'].index[0])[:10]
    cn_max = str(cn_data['prices'].index[-1])[:10]
    if sd < cn_min:
        sd = cn_min

    result = run_cn_backtest(
        cn_data, signal,
        long_n=req.long_n, short_n=req.short_n,
        long_pct=req.long_pct, short_pct=req.short_pct,
        turnover_penalty=req.turnover_penalty, cost_bps=req.cost_bps,
        sd=sd, ed=ed, initial_capital=req.initial_capital,
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Not enough A-share data for this range")

    # Build a US-compatible data dict so analyze() works
    from api.services.backtest_service import analyze, _clean
    import pandas as pd
    import numpy as np

    ret_idx = cn_data['returns'].index  # DatetimeIndex

    # CSI300 as benchmark (align index type)
    idx_ret = cn_data.get('index_ret', pd.Series(dtype=float))
    if len(idx_ret) > 0:
        # Ensure DatetimeIndex
        if hasattr(idx_ret.index, 'to_timestamp'):
            idx_ret = idx_ret.copy()
            idx_ret.index = idx_ret.index.to_timestamp()
        spy_proxy = idx_ret.reindex(ret_idx).fillna(0)
    else:
        spy_proxy = pd.Series(0.0, index=ret_idx)

    # FF5 stub with matching index
    ff5_stub = pd.DataFrame({
        'mktrf': spy_proxy.values,
        'smb': np.zeros(len(ret_idx)),
        'hml': np.zeros(len(ret_idx)),
        'umd': np.zeros(len(ret_idx)),
        'rf': np.full(len(ret_idx), 0.002),
    }, index=ret_idx)

    cn_compat = {**cn_data,
        'spy_ret': spy_proxy,
        'ff5': ff5_stub,
        'rf': pd.Series(0.002, index=ret_idx),
    }

    try:
        resp = analyze(cn_compat, result, sd, ed, req.initial_capital)
        resp['compare_name'] = ""
        resp['status'] = (
            f"\U0001f1e8\U0001f1f3 {sd} \u2192 {ed} \u00b7 {result['m']['n_months']}mo "
            f"\u00b7 SR {result['m']['sharpe']:.2f} "
            f"\u00b7 \u00a5{req.initial_capital:,.0f} \u2192 \u00a5{result['m']['final_value']:,.0f}"
        )
        return _clean(resp)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"CN analysis error: {str(e)}")


async def _run_wrds(req: BacktestRequest, request: Request, strategy_id: str):
    """Run WRDS-based strategy backtest with optimized settings (vol target + DD control)."""
    from api.services.wrds_backtest_service import build_wrds_signal
    from api.services.backtest_service import analyze, _clean
    from qf.optimizer import run_optimized_backtest

    d = request.app.state.data
    signal = build_wrds_signal(strategy_id, d)

    sd = req.start_date or "2015-01-01"
    ed = req.end_date or date.today().isoformat()
    dmin = str(d['prices'].index[0])[:10]
    if sd < dmin: sd = dmin

    import pandas as pd
    mask = (signal.index >= sd) & (signal.index <= ed)
    sig_p = signal.loc[mask]

    if len(sig_p) < 3:
        raise HTTPException(status_code=400, detail="Not enough data")

    # Use same params as audit: vol_target=0.10, dd_control, sqrt cost model
    result_obj, metrics = run_optimized_backtest(
        d, sig_p, target_vol=0.10, dd_control=True,
        long_n=req.long_n, short_n=req.short_n,
        base_long_pct=req.long_pct / 100, base_short_pct=req.short_pct / 100,
        turnover_penalty=req.turnover_penalty or 0.25,
        initial_capital=int(req.initial_capital),
        verbose=False,
    )

    if len(result_obj.returns) < 2:
        raise HTTPException(status_code=400, detail="Not enough return data")

    from qf.backtest import Portfolio
    port = Portfolio(initial_capital=int(req.initial_capital))
    port.trade_count = len(result_obj.returns) * 5  # approximate
    result = {'res': result_obj, 'm': metrics, 'port': port}

    resp = analyze(d, result, sd, ed, req.initial_capital)
    resp['compare_name'] = ""
    return _clean(resp)


async def _run_us(req: BacktestRequest, request: Request):
    """Run US backtest (original logic)."""
    from api.services.backtest_service import run_single, analyze

    d = request.app.state.data
    dmin = str(d['prices'].index[0])[:10]
    dmax = str(d['prices'].index[-1])[:10]

    sd = req.start_date or "2015-01-01"
    ed = req.end_date or date.today().isoformat()
    today = date.today().isoformat()
    if ed > today:
        ed = today
    if sd > ed:
        sd = ed
    if sd < dmin:
        sd = dmin

    result = run_single(
        d, req.w_mom, req.w_accel, req.w_quality, req.w_vol,
        req.long_n, req.short_n, req.long_pct, req.short_pct,
        req.turnover_penalty, req.cost_bps, sd, ed, req.initial_capital,
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Not enough data for this date range")

    if len(result['res'].returns) < 2:
        raise HTTPException(status_code=400, detail="Not enough return data")

    # Comparison
    cmp_result = None
    cmp_name = ""
    if req.compare_id:
        cs = next((x for x in STRATS if x['id'] == req.compare_id and not x.get('needs_data')), None)
        if cs:
            cmp_name = cs['name']
            cmp_result = run_single(
                d, cs.get('w_mom', 50), cs.get('w_accel', 20),
                cs.get('w_quality', 0), cs.get('w_vol', 0),
                cs.get('long_n', 20), cs.get('short_n', 20),
                cs.get('long_pct', 115), cs.get('short_pct', 15),
                req.turnover_penalty, req.cost_bps, sd, ed, req.initial_capital,
            )

    from api.services.backtest_service import _clean
    resp = analyze(d, result, sd, ed, req.initial_capital, cmp_result)
    resp['compare_name'] = cmp_name
    return _clean(resp)


@router.get("/data-range")
async def get_data_range(request: Request):
    d = request.app.state.data
    return {
        'min': str(d['prices'].index[0])[:10],
        'max': str(d['prices'].index[-1])[:10],
        'today': date.today().isoformat(),
    }
