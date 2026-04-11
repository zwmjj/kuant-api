"""Factor Lab API — 8个因子研究端点"""
import os, pickle, logging
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("yfinance")
logger.setLevel(logging.CRITICAL)

router = APIRouter()

# ── Universe ──
SYMS = [
    'AAPL','MSFT','NVDA','TSLA','AMZN','GOOG','META','JPM','V','UNH',
    'XOM','JNJ','PG','MA','HD','CVX','ABBV','MRK','KO','PEP',
    'COST','NFLX','CRM','ADBE','AVGO','LLY','WMT','BAC','ORCL','AMD',
    'QCOM','INTC','DIS','CMCSA','NKE','TMO','ABT','DHR','PM','UPS',
    'GS','MS','BLK','SCHW','AXP','PYPL','UBER','ABNB','COIN','SPY',
]

# Fama-French风格因子名 (用于style exposure)
STYLE_FACTORS = ['market','size','value','momentum','volatility','quality']

CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"

# ── Request/Response Models ──

class FactorRequest(BaseModel):
    strategy_id: str = "realized_spread"
    factor_name: str = "realized_spread"
    start_date: str = "2015-01-01"
    end_date: Optional[str] = "2026-03-28"
    universe: str = "sp500"
    n_deciles: int = Field(default=10, ge=2, le=20)
    forward_period: int = Field(default=1, ge=1, le=60)

class DecileNavResponse(BaseModel):
    dates: List[str]
    d1_nav: List[Optional[float]]
    d10_nav: List[Optional[float]]
    d_spread: List[Optional[float]]

class DecileReturnsResponse(BaseModel):
    deciles: List[int]
    mean_returns: List[Optional[float]]
    benchmark_return: float
    is_monotonic: bool

class LongOnlyNavResponse(BaseModel):
    dates: List[str]
    long_nav: List[Optional[float]]
    index_nav: List[Optional[float]]

class LongShortNavResponse(BaseModel):
    dates: List[str]
    ls_nav: List[Optional[float]]
    index_nav: List[Optional[float]]

class ICStabilityResponse(BaseModel):
    dates: List[str]
    ic_series: List[Optional[float]]
    ic_ma3: List[Optional[float]]
    ic_ma6: List[Optional[float]]
    ic_ma12: List[Optional[float]]
    ic_std: List[Optional[float]]

class CumulativeICResponse(BaseModel):
    dates: List[str]
    cumulative_ic: List[Optional[float]]
    mean_ic: float
    ic_ir: float

class ICDecayResponse(BaseModel):
    forward_periods: List[int]
    mean_ic: List[Optional[float]]
    ic_ir: List[Optional[float]]

class StyleExposureResponse(BaseModel):
    factor_names: List[str]
    exposures: List[Optional[float]]
    t_stats: List[Optional[float]]
    r_squared: float

# ── Data Loading ──

def _load_data(start: str, end: str) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_key = f"{start}_{end}".replace(':','-')
    cache_file = CACHE_DIR / f"factor_lab_{safe_key}.pkl"
    if cache_file.exists():
        age = pd.Timestamp.now().timestamp() - cache_file.stat().st_mtime
        if age < 86400:
            with open(cache_file, "rb") as f:
                return pickle.load(f)

    import yfinance as yf
    raw = yf.download(SYMS, start=start, end=end, auto_adjust=True, progress=False)
    if raw.empty:
        raise HTTPException(502, "yfinance returned empty data")

    data = {
        "close": raw["Close"], "open": raw["Open"],
        "high": raw["High"], "low": raw["Low"],
        "volume": raw["Volume"],
    }
    data["ret"] = data["close"].pct_change()
    with open(cache_file, "wb") as f:
        pickle.dump(data, f)
    return data

# ── Factor Computation ──

def _cross_rank(df):
    return df.rank(axis=1, pct=True) * 2 - 1

def compute_factor(factor_id: str, data: dict) -> pd.DataFrame:
    C = data["close"]; R = data["ret"]; V = data["volume"]
    O = data["open"]; H = data["high"]; L = data["low"]
    ss = [s for s in C.columns if s != 'SPY']

    fmap = {
        'rev5': lambda: -R[ss].rolling(5).sum(),
        'rev10': lambda: -R[ss].rolling(10).sum(),
        'rev20': lambda: -R[ss].rolling(20).sum(),
        'mom20': lambda: R[ss].rolling(20).sum(),
        'mom60': lambda: R[ss].rolling(60).sum(),
        'lowvol': lambda: -R[ss].rolling(20).std(),
        'realized_spread': lambda: ((2*C[ss]-H[ss]-L[ss])/C[ss]).rolling(20).mean(),
        'oil_beta': lambda: _oil_beta(R, ss),
        'co_move': lambda: -R[ss].rolling(20).corr(R[ss].mean(axis=1)),
        'vpt': lambda: _vpt(R, V, ss),
        'clv': lambda: _clv(C, H, L, V, ss),
        'ad_line': lambda: _ad_line(C, H, L, V, ss),
        'obv': lambda: _obv(R, V, ss),
        'overnight_ret': lambda: (O[ss]/C[ss].shift(1)-1).rolling(20).mean(),
        'intraday_ret': lambda: (C[ss]/O[ss]-1).rolling(20).mean(),
        'volume_surge': lambda: V[ss]/V[ss].rolling(20).mean(),
    }
    fn = fmap.get(factor_id)
    if fn is None:
        raise HTTPException(400, f"Unknown factor: {factor_id}")
    return _cross_rank(fn())

def _oil_beta(R, ss):
    if 'XOM' in R.columns:
        proxy = R['XOM']
    elif 'SPY' in R.columns:
        proxy = R['SPY']
    else:
        return R[ss].rolling(60).std()
    return R[ss].rolling(60).corr(proxy) * R[ss].rolling(60).std() / proxy.rolling(60).std()

def _vpt(R, V, ss):
    raw = (R[ss]*V[ss]).cumsum()
    return raw - raw.rolling(20).mean()

def _clv(C, H, L, V, ss):
    hl = (H[ss]-L[ss]).replace(0, np.nan)
    clv = ((C[ss]-L[ss])-(H[ss]-C[ss]))/hl
    return (clv*V[ss]).rolling(20).sum()

def _ad_line(C, H, L, V, ss):
    hl = (H[ss]-L[ss]).replace(0, np.nan)
    mfm = ((C[ss]-L[ss])-(H[ss]-C[ss]))/hl
    ad = (mfm*V[ss]).cumsum()
    return ad - ad.rolling(20).mean()

def _obv(R, V, ss):
    raw = (np.sign(R[ss])*V[ss]).cumsum()
    return raw - raw.rolling(20).mean()

# ── Helpers ──

def _nan_to_none(arr) -> list:
    out = []
    for v in arr:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            out.append(None)
        else:
            out.append(round(float(v), 6))
    return out

def _rebal_dates(index, frequency='monthly'):
    s = index.to_series()
    if frequency == 'monthly':
        return pd.DatetimeIndex(s.groupby(s.dt.to_period('M')).idxmax().values)
    else:
        return pd.DatetimeIndex(s.groupby(s.dt.to_period('W')).idxmax().values)

def _build_decile_returns(signal, returns, rebal, n_groups):
    group_rets = {g: [] for g in range(n_groups)}
    bench_rets = []; dates_out = []
    rebal_list = sorted(rebal)
    common = signal.columns.intersection(returns.columns)
    signal = signal[common]; returns = returns[common]

    for i in range(len(rebal_list)-1):
        dt = rebal_list[i]; dt_next = rebal_list[i+1]
        if dt not in signal.index: continue
        sig_row = signal.loc[dt].dropna()
        if len(sig_row) < n_groups: continue

        ranked = sig_row.rank(method='first')
        gs = len(ranked) / n_groups
        assignments = ((ranked-1)/gs).astype(int).clip(0, n_groups-1)

        mask = (returns.index > dt) & (returns.index <= dt_next)
        period_ret = returns.loc[mask, sig_row.index]
        if period_ret.empty: continue
        cum_ret = (1+period_ret).prod()-1
        bench_rets.append(float(cum_ret.mean()))
        dates_out.append(str(dt_next.date()) if hasattr(dt_next,'date') else str(dt_next))

        for g in range(n_groups):
            stocks = assignments[assignments==g].index
            group_rets[g].append(float(cum_ret[stocks].mean()) if len(stocks)>0 else np.nan)

    return group_rets, bench_rets, dates_out

def _compute_ic_series(signal, returns, rebal, forward_period=1):
    """Spearman IC at each rebalance date."""
    rebal_list = sorted(rebal)
    common = signal.columns.intersection(returns.columns)
    signal = signal[common]; returns = returns[common]
    ic_vals = []; ic_dates = []

    for i in range(len(rebal_list)-1):
        dt = rebal_list[i]
        # forward return: next forward_period rebal periods
        j = min(i+forward_period, len(rebal_list)-1)
        dt_end = rebal_list[j]
        if dt not in signal.index: continue
        sig_row = signal.loc[dt].dropna()
        mask = (returns.index > dt) & (returns.index <= dt_end)
        fwd = returns.loc[mask, sig_row.index]
        if fwd.empty or len(sig_row)<5: continue
        fwd_ret = (1+fwd).prod()-1
        common2 = sig_row.index.intersection(fwd_ret.index)
        if len(common2)<5: continue
        rho, _ = sp_stats.spearmanr(sig_row[common2].values, fwd_ret[common2].values)
        ic_vals.append(rho)
        ic_dates.append(str(dt_end.date()) if hasattr(dt_end,'date') else str(dt_end))

    return ic_vals, ic_dates

# ── 8 Endpoints ──

@router.post("/decile-nav", response_model=DecileNavResponse)
async def decile_nav(req: FactorRequest):
    data = _load_data(req.start_date, req.end_date or '2026-03-28')
    signal = compute_factor(req.factor_name, data)
    rebal = _rebal_dates(signal.index)
    gr, br, dates = _build_decile_returns(signal, data["ret"], rebal, req.n_deciles)

    d1_nav=[1.0]; d10_nav=[1.0]; spread=[1.0]
    top = req.n_deciles - 1
    for i in range(len(dates)):
        d1r = gr[0][i] if not np.isnan(gr[0][i]) else 0
        d10r = gr[top][i] if not np.isnan(gr[top][i]) else 0
        b = br[i] if not np.isnan(br[i]) else 0
        d1_nav.append(d1_nav[-1]*(1+d1r-b))
        d10_nav.append(d10_nav[-1]*(1+d10r-b))
        spread.append(spread[-1]*(1+d10r-d1r))

    all_dates = [dates[0] if dates else req.start_date] + dates
    return DecileNavResponse(dates=all_dates, d1_nav=_nan_to_none(d1_nav),
                             d10_nav=_nan_to_none(d10_nav), d_spread=_nan_to_none(spread))


@router.post("/decile-returns", response_model=DecileReturnsResponse)
async def decile_returns(req: FactorRequest):
    data = _load_data(req.start_date, req.end_date or '2026-03-28')
    signal = compute_factor(req.factor_name, data)
    rebal = _rebal_dates(signal.index)
    gr, br, dates = _build_decile_returns(signal, data["ret"], rebal, req.n_deciles)

    means = []
    for g in range(req.n_deciles):
        arr = [x for x in gr[g] if not np.isnan(x)]
        means.append(np.mean(arr) if arr else np.nan)
    valid = [m for m in means if not np.isnan(m)]
    mono = all(valid[i]<=valid[i+1] for i in range(len(valid)-1)) if len(valid)>1 else False

    return DecileReturnsResponse(deciles=list(range(1,req.n_deciles+1)),
        mean_returns=_nan_to_none(means),
        benchmark_return=round(float(np.nanmean(br)),6) if br else 0,
        is_monotonic=mono)


@router.post("/longonly-nav", response_model=LongOnlyNavResponse)
async def longonly_nav(req: FactorRequest):
    data = _load_data(req.start_date, req.end_date or '2026-03-28')
    signal = compute_factor(req.factor_name, data)
    rebal = _rebal_dates(signal.index)
    gr, br, dates = _build_decile_returns(signal, data["ret"], rebal, req.n_deciles)

    long_nav=[1.0]; idx_nav=[1.0]; top=req.n_deciles-1
    for i in range(len(dates)):
        lr = gr[top][i] if not np.isnan(gr[top][i]) else 0
        b = br[i] if not np.isnan(br[i]) else 0
        long_nav.append(long_nav[-1]*(1+lr))
        idx_nav.append(idx_nav[-1]*(1+b))
    all_dates = [dates[0] if dates else req.start_date] + dates
    return LongOnlyNavResponse(dates=all_dates, long_nav=_nan_to_none(long_nav),
                               index_nav=_nan_to_none(idx_nav))


@router.post("/longshort-nav", response_model=LongShortNavResponse)
async def longshort_nav(req: FactorRequest):
    data = _load_data(req.start_date, req.end_date or '2026-03-28')
    signal = compute_factor(req.factor_name, data)
    rebal = _rebal_dates(signal.index)
    gr, br, dates = _build_decile_returns(signal, data["ret"], rebal, req.n_deciles)

    ls_nav=[1.0]; idx_nav=[1.0]; top=req.n_deciles-1
    for i in range(len(dates)):
        d10 = gr[top][i] if not np.isnan(gr[top][i]) else 0
        d1 = gr[0][i] if not np.isnan(gr[0][i]) else 0
        b = br[i] if not np.isnan(br[i]) else 0
        ls_nav.append(ls_nav[-1]*(1+d10-d1))
        idx_nav.append(idx_nav[-1]*(1+b))
    all_dates = [dates[0] if dates else req.start_date] + dates
    return LongShortNavResponse(dates=all_dates, ls_nav=_nan_to_none(ls_nav),
                                index_nav=_nan_to_none(idx_nav))


@router.post("/ic-stability", response_model=ICStabilityResponse)
async def ic_stability(req: FactorRequest):
    data = _load_data(req.start_date, req.end_date or '2026-03-28')
    signal = compute_factor(req.factor_name, data)
    rebal = _rebal_dates(signal.index)
    ic_vals, ic_dates = _compute_ic_series(signal, data["ret"], rebal, req.forward_period)

    ic_s = pd.Series(ic_vals, dtype=float)
    return ICStabilityResponse(
        dates=ic_dates,
        ic_series=_nan_to_none(ic_s.values),
        ic_ma3=_nan_to_none(ic_s.rolling(3,min_periods=1).mean().values),
        ic_ma6=_nan_to_none(ic_s.rolling(6,min_periods=1).mean().values),
        ic_ma12=_nan_to_none(ic_s.rolling(12,min_periods=1).mean().values),
        ic_std=_nan_to_none(ic_s.rolling(6,min_periods=1).std().values),
    )


@router.post("/cumulative-ic", response_model=CumulativeICResponse)
async def cumulative_ic(req: FactorRequest):
    """累积IC曲线 + IC均值 + ICIR"""
    data = _load_data(req.start_date, req.end_date or '2026-03-28')
    signal = compute_factor(req.factor_name, data)
    rebal = _rebal_dates(signal.index)
    ic_vals, ic_dates = _compute_ic_series(signal, data["ret"], rebal, req.forward_period)

    cum_ic = list(np.cumsum(ic_vals))
    mean_ic = float(np.mean(ic_vals)) if ic_vals else 0
    ic_std = float(np.std(ic_vals)) if ic_vals else 1
    ic_ir = mean_ic / ic_std if ic_std > 0 else 0

    return CumulativeICResponse(
        dates=ic_dates,
        cumulative_ic=_nan_to_none(cum_ic),
        mean_ic=round(mean_ic, 6),
        ic_ir=round(ic_ir, 6),
    )


@router.post("/ic-decay", response_model=ICDecayResponse)
async def ic_decay(req: FactorRequest):
    """IC衰减: 不同前视期的IC"""
    data = _load_data(req.start_date, req.end_date or '2026-03-28')
    signal = compute_factor(req.factor_name, data)
    rebal = _rebal_dates(signal.index)

    periods = [1, 2, 3, 6, 12]
    mean_ics = []; ic_irs = []
    for fp in periods:
        ic_vals, _ = _compute_ic_series(signal, data["ret"], rebal, fp)
        m = float(np.mean(ic_vals)) if ic_vals else 0
        s = float(np.std(ic_vals)) if ic_vals else 1
        mean_ics.append(m)
        ic_irs.append(m/s if s>0 else 0)

    return ICDecayResponse(
        forward_periods=periods,
        mean_ic=_nan_to_none(mean_ics),
        ic_ir=_nan_to_none(ic_irs),
    )


@router.post("/style-exposure", response_model=StyleExposureResponse)
async def style_exposure(req: FactorRequest):
    """风格因子暴露: 将因子收益对风格因子做回归"""
    data = _load_data(req.start_date, req.end_date or '2026-03-28')
    signal = compute_factor(req.factor_name, data)
    rebal = _rebal_dates(signal.index)
    gr, br, dates = _build_decile_returns(signal, data["ret"], rebal, req.n_deciles)

    # Long-short returns
    top = req.n_deciles - 1
    ls_rets = []
    for i in range(len(dates)):
        d10 = gr[top][i] if not np.isnan(gr[top][i]) else 0
        d1 = gr[0][i] if not np.isnan(gr[0][i]) else 0
        ls_rets.append(d10 - d1)
    ls_rets = np.array(ls_rets)

    # 构建风格因子proxy (从日线数据)
    R = data["ret"]; C = data["close"]
    ss = [s for s in C.columns if s != 'SPY']
    rebal_list = sorted(rebal)

    # 每个rebal period的截面风格因子收益
    style_rets = {f: [] for f in STYLE_FACTORS}
    for i in range(len(rebal_list)-1):
        dt = rebal_list[i]; dt_next = rebal_list[i+1]
        if dt not in R.index: continue
        mask = (R.index > dt) & (R.index <= dt_next)
        period_ret = R.loc[mask, ss]
        if period_ret.empty: continue
        cum = (1+period_ret).prod()-1

        # Market: equal-weight return
        style_rets['market'].append(float(cum.mean()))
        # Size: large vs small (by price as proxy)
        if dt in C.index:
            px = C.loc[dt, ss].dropna()
            med = px.median()
            big = cum[px[px>=med].index].mean() if len(px[px>=med])>0 else 0
            small = cum[px[px<med].index].mean() if len(px[px<med])>0 else 0
            style_rets['size'].append(float(small - big))  # SMB
        else:
            style_rets['size'].append(0)
        # Value: low P/E proxy (high earnings yield = high book/price proxy via low vol)
        rv = R[ss].iloc[max(0,R.index.get_loc(dt)-60):R.index.get_loc(dt)].std()
        if len(rv.dropna()) > 10:
            med_v = rv.median()
            hi_val = cum[rv[rv<=med_v].index].mean() if len(rv[rv<=med_v])>0 else 0
            lo_val = cum[rv[rv>med_v].index].mean() if len(rv[rv>med_v])>0 else 0
            style_rets['value'].append(float(hi_val - lo_val))
        else:
            style_rets['value'].append(0)
        # Momentum: past 60d winner vs loser
        mom = R[ss].iloc[max(0,R.index.get_loc(dt)-60):R.index.get_loc(dt)].sum()
        if len(mom.dropna()) > 10:
            med_m = mom.median()
            win = cum[mom[mom>=med_m].index].mean() if len(mom[mom>=med_m])>0 else 0
            lose = cum[mom[mom<med_m].index].mean() if len(mom[mom<med_m])>0 else 0
            style_rets['momentum'].append(float(win - lose))
        else:
            style_rets['momentum'].append(0)
        # Volatility: low vol vs high vol
        if len(rv.dropna()) > 10:
            style_rets['volatility'].append(float(hi_val - lo_val))  # same as value proxy
        else:
            style_rets['volatility'].append(0)
        # Quality: high return consistency
        consistency = (R[ss].iloc[max(0,R.index.get_loc(dt)-60):R.index.get_loc(dt)]>0).mean()
        if len(consistency.dropna()) > 10:
            med_q = consistency.median()
            hq = cum[consistency[consistency>=med_q].index].mean() if len(consistency[consistency>=med_q])>0 else 0
            lq = cum[consistency[consistency<med_q].index].mean() if len(consistency[consistency<med_q])>0 else 0
            style_rets['quality'].append(float(hq - lq))
        else:
            style_rets['quality'].append(0)

    # 对齐长度
    min_len = min(len(ls_rets), min(len(v) for v in style_rets.values()))
    y = ls_rets[:min_len]
    X = np.column_stack([np.array(style_rets[f][:min_len]) for f in STYLE_FACTORS])

    # OLS回归
    if len(y) < 10 or X.shape[0] < 10:
        return StyleExposureResponse(
            factor_names=STYLE_FACTORS,
            exposures=[0]*len(STYLE_FACTORS),
            t_stats=[0]*len(STYLE_FACTORS),
            r_squared=0,
        )

    X = np.column_stack([np.ones(len(y)), X])  # add intercept
    try:
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        y_pred = X @ beta
        residuals = y - y_pred
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((y - y.mean())**2)
        r2 = 1 - ss_res/ss_tot if ss_tot > 0 else 0

        # t-stats
        n_obs = len(y); k = X.shape[1]
        mse = ss_res / max(n_obs - k, 1)
        try:
            cov_beta = mse * np.linalg.inv(X.T @ X)
            se = np.sqrt(np.diag(cov_beta))
            t_stats = beta / se
        except:
            t_stats = np.zeros(k)

        exposures = beta[1:].tolist()  # skip intercept
        t_vals = t_stats[1:].tolist()
    except:
        exposures = [0]*len(STYLE_FACTORS)
        t_vals = [0]*len(STYLE_FACTORS)
        r2 = 0

    return StyleExposureResponse(
        factor_names=STYLE_FACTORS,
        exposures=_nan_to_none(exposures),
        t_stats=_nan_to_none(t_vals),
        r_squared=round(float(r2), 6),
    )
