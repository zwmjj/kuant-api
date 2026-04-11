"""A-share backtest service — CN-specific signal + execution."""
import numpy as np
import pandas as pd
from qf.signals import SignalGenerator
from qf.backtest import DataHandler, StrategyEngine, Portfolio, EventDrivenBacktester
from qf.costs import ExecutionHandler
from qf.risk import RiskAnalyzer
from qf.attribution import AttributionAnalyzer

sg = SignalGenerator()

# CN factor signal builders
CN_SIGNAL_MAP = {
    'cn_reversal':  lambda d: -d['returns'].shift(1),
    'cn_lowvol':    lambda d: -sg.volatility(d['returns'], 12),
    'cn_vol_blend': lambda d: _vol_blend(d),
    'cn_defensive': lambda d: _defensive(d),
}

def _vol_blend(d):
    r = d['returns']
    lowvol = -sg.volatility(r, 12)
    downvol = -sg.downside_vol(r, 12)
    skew = -sg.skewness(r, 12)
    vov = -sg.vol_of_vol(r)
    return (0.25 * sg.cross_sectional_rank(lowvol) +
            0.25 * sg.cross_sectional_rank(downvol) +
            0.25 * sg.cross_sectional_rank(skew) +
            0.25 * sg.cross_sectional_rank(vov))

def _defensive(d):
    r = d['returns']
    turn = d.get('turnover', r * 0)
    rev = -r.shift(1)
    lowvol = -sg.volatility(r, 12)
    skew = -sg.skewness(r, 12)
    low_turn = -turn
    return (0.25 * sg.cross_sectional_rank(rev.astype(float)) +
            0.25 * sg.cross_sectional_rank(lowvol) +
            0.25 * sg.cross_sectional_rank(skew) +
            0.25 * sg.cross_sectional_rank(low_turn.astype(float)))


def build_cn_signal(strategy_id, d):
    """Build A-share signal for given strategy."""
    if strategy_id not in CN_SIGNAL_MAP:
        raise ValueError(f"Unknown CN strategy: {strategy_id}")
    raw = CN_SIGNAL_MAP[strategy_id](d).astype(float)
    ranked = sg.cross_sectional_rank(raw)
    mktcap = d['mktcap']
    pct = mktcap.quantile(0.70, axis=1)
    cap_mask = mktcap.ge(pct, axis=0).reindex(index=ranked.index, columns=ranked.columns)
    return ranked.where(cap_mask)


def run_cn_backtest(d, signal, long_n=30, short_n=1, long_pct=100, short_pct=0,
                    turnover_penalty=0.25, cost_bps=5, sd='2010-01-01', ed='2025-12-31',
                    initial_capital=100000):
    """Run A-share backtest with CN cost model."""
    mask = (signal.index >= sd) & (signal.index <= ed)
    sig_p = signal.loc[mask]
    pp = d['prices'].loc[(d['prices'].index >= sd) & (d['prices'].index <= ed)]
    rp = d['returns'].loc[(d['returns'].index >= sd) & (d['returns'].index <= ed)]

    if len(sig_p) < 3:
        return None

    inv_vol = 1.0 / rp.rolling(12).std().replace(0, np.nan)
    dh = DataHandler(pp, rp, d.get('volume'))
    se = StrategyEngine(sig_p, long_n=long_n, short_n=max(short_n, 1),
                        long_pct=long_pct / 100, short_pct=short_pct / 100,
                        weight_mode='inv_vol', inv_vol_df=inv_vol,
                        turnover_penalty=turnover_penalty)
    port = Portfolio(initial_capital=int(initial_capital))
    # A-share costs: commission 2.5bp, spread 5bp, stamp tax 5bp (as sec_fee), no short borrow
    exe = ExecutionHandler(cost_model='sqrt', commission_bps=2.5,
                           spread_bps=float(cost_bps) / 2 if cost_bps else 2.5,
                           impact_coeff=0.3, short_borrow_bps=0, sec_fee_bps=5.0)
    eng = EventDrivenBacktester(dh, se, port, exe)

    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        res = eng.run(verbose=False)

    rets = res.returns.dropna()
    if len(rets) < 2:
        return None

    # Metrics
    rf = d.get('rf', pd.Series(0, index=rets.index))
    excess = rets - rf.reindex(rets.index).fillna(0)
    years = max((rets.index[-1] - rets.index[0]).days / 365.25, 0.01)
    pv = res.pv
    total_ret = pv.iloc[-1] / pv.iloc[0] - 1
    cagr = (1 + total_ret) ** (1 / years) - 1
    sharpe = excess.mean() / excess.std() * np.sqrt(12) if excess.std() > 0 else 0
    ds = rets[rets < 0].std() * np.sqrt(12)
    sortino = excess.mean() * 12 / ds if ds > 0 else 0
    dd = (pv - pv.cummax()) / pv.cummax()

    m = {
        'total_return': float(total_ret), 'cagr': float(cagr),
        'sharpe': float(sharpe), 'sortino': float(sortino),
        'max_drawdown': float(dd.min()), 'win_rate': float((rets > 0).mean()),
        'final_value': float(pv.iloc[-1]), 'n_months': int(len(rets)),
        'alpha': 0, 'beta': 0,
    }

    # Benchmark (CSI300)
    idx_ret = d.get('index_ret', pd.Series())
    if len(idx_ret) > 0:
        idx_m = idx_ret.copy()
        idx_m.index = idx_m.index.to_period('M')
        rp_m = rets.copy()
        rp_m.index = rp_m.index.to_period('M')
        common = rp_m.index.intersection(idx_m.index)
        if len(common) > 6:
            bm = idx_m.loc[common]
            bm_cagr = ((1 + bm).prod()) ** (1 / years) - 1
            m['benchmark_cagr'] = float(bm_cagr)
            m['excess_return'] = float(cagr - bm_cagr)
            m['alpha'] = float(cagr - bm_cagr)

    return {'res': res, 'm': m, 'port': port}
