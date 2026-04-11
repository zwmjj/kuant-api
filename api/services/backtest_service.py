"""Core backtest execution — wraps qf/ framework."""
import sys, io, contextlib
import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))

from qf.data import prepare_data
from qf.signals import build_signal
from qf.backtest import DataHandler, StrategyEngine, Portfolio, EventDrivenBacktester
from qf.costs import ExecutionHandler
from qf.attribution import AttributionAnalyzer
from qf.risk import RiskAnalyzer


def load_data():
    """Load data once at startup, including pre-computed signal components."""
    d = prepare_data()
    # Pre-compute signal components (expensive, ~5s each, but only once)
    sg = __import__('qf.signals', fromlist=['SignalGenerator']).SignalGenerator()
    to_float = lambda df: df.apply(pd.to_numeric, errors='coerce')
    d['_sig_mom']   = to_float(sg.cross_sectional_rank(sg.multi_timeframe_momentum(d['returns'])))
    d['_sig_accel'] = to_float(sg.cross_sectional_rank(sg.momentum_acceleration(d['returns'])))
    d['_sig_vol']   = to_float(sg.cross_sectional_rank(sg.volatility(d['returns'], 12)))
    d['_sig_qual']  = to_float(sg.quality_signal(d['ccm_fund'], d['returns'])).fillna(0)
    pct = d['mktcap'].quantile(0.75, axis=1)
    cap_mask = d['mktcap'].ge(pct, axis=0)
    crash = sg.crash_filter(d['returns']).fillna(False)
    d['_sig_mask'] = (cap_mask & ~crash).reindex(index=d['_sig_mom'].index, columns=d['_sig_mom'].columns)
    return d


def _fast_signal(d, wm, wa, wq, wv):
    """Combine pre-computed signal components with given weights. ~0.01s vs ~5s."""
    tw = (wm or 0) + (wa or 0) + (wq or 0) + (wv or 0)
    if tw == 0:
        tw = 100
    wm, wa, wq, wv = (wm or 0)/tw, (wa or 0)/tw, (wq or 0)/tw, (wv or 0)/tw
    composite = wm * d['_sig_mom'] + wa * d['_sig_accel'] + wv * (-d['_sig_vol'])
    if wq > 0:
        composite = composite + wq * d['_sig_qual']
    return composite.where(d['_sig_mask'])


def run_single(d, wm, wa, wq, wv, ln, sn, lp, sp_, pen, cst, sd, ed, cap):
    """Run a single backtest. Uses pre-computed signals if available."""
    if '_sig_mom' in d:
        sig = _fast_signal(d, wm, wa, wq, wv)
    else:
        tw = (wm or 0) + (wa or 0) + (wq or 0) + (wv or 0)
        if tw == 0:
            tw = 100
        with contextlib.redirect_stdout(io.StringIO()):
            sig = build_signal(
                d['returns'], d['prices'], d['mktcap'], d['ccm_fund'],
                w_mom=(wm or 0)/tw, w_accel=(wa or 0)/tw,
                w_quality=(wq or 0)/tw, w_vol=(wv or 0)/tw, verbose=False,
            )

    mask = (sig.index >= sd) & (sig.index <= ed)
    sig_p = sig.loc[mask]
    pm = (d['prices'].index >= sd) & (d['prices'].index <= ed)
    pp = d['prices'].loc[pm]
    rp = d['returns'].loc[pm]

    if len(sig_p) < 3:
        return None

    iv = 1.0 / rp.rolling(12).std().replace(0, np.nan)
    dh = DataHandler(pp, rp)
    se = StrategyEngine(
        sig_p, long_n=ln, short_n=sn, long_pct=lp/100, short_pct=sp_/100,
        weight_mode='inv_vol', inv_vol_df=iv, turnover_penalty=pen or 0,
    )
    port = Portfolio(initial_capital=int(cap))
    exe = ExecutionHandler(cost_model='fixed', commission_bps=(cst or 2)/2, spread_bps=(cst or 2)/2)
    eng = EventDrivenBacktester(dh, se, port, exe)

    with contextlib.redirect_stdout(io.StringIO()):
        res = eng.run(verbose=False)

    m = res.metrics(rf=d['rf'], benchmark_returns=d['spy_ret'])
    return {'res': res, 'm': m, 'port': port}


def _clean(obj):
    """Recursively convert numpy types and NaN/inf to JSON-safe Python types."""
    import math
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.bool_, )):
        return bool(obj)
    if isinstance(obj, (np.integer, )):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(obj, np.ndarray):
        return _clean(obj.tolist())
    return obj


def _clean_series(values):
    """Clean a list of numeric values: NaN/inf → None, valid → rounded float."""
    import math
    out = []
    for v in values:
        if v is None:
            out.append(None)
        else:
            fv = float(v)
            if math.isnan(fv) or math.isinf(fv):
                out.append(None)
            else:
                out.append(round(fv, 6))
    return out


def analyze(d, result, sd, ed, cap, cmp_result=None):
    """Post-process backtest result into all metrics, chart data, etc."""
    res, m, port = result['res'], result['m'], result['port']
    rets = res.returns
    pv = res.pv
    nm = len(rets)

    an = AttributionAnalyzer(d['ff5'])
    attr = an.ff5_regression(rets, "S")
    yr = an.yearly_attribution(rets, d['spy_ret'])
    rk = RiskAnalyzer(rets, pv)
    mdd = rk.max_drawdown()
    cal = rk.calmar(m['cagr'])
    tl = rk.tail_stats()
    dd_series = rk.drawdown_series()
    al = m.get('alpha', 0)
    beta = m.get('beta', 0)
    fi = m.get('final_value', cap)
    pnl = fi - cap

    # Extra metrics
    avg_dd = float(dd_series[dd_series < 0].mean()) if (dd_series < 0).any() else 0.0
    cummax = pv.cummax()
    in_dd = pv < cummax
    recovery_months = 0
    if in_dd.any():
        dd_runs = (in_dd != in_dd.shift()).cumsum()
        dd_groups = dd_runs[in_dd]
        if len(dd_groups) > 0:
            recovery_months = int(dd_groups.value_counts().mean())
    turnover_ann = port.trade_count / max(nm, 1) * 12

    # SPY benchmark aligned to strategy's actual trading period (not just sd/ed)
    spy_ret = d['spy_ret'].copy()
    try:
        spy_ret.index = pd.to_datetime(spy_ret.index.to_timestamp())
    except Exception:
        pass
    # Use strategy's first return date as start, not the requested sd
    strat_start = str(rets.index[0])[:10] if len(rets) > 0 else sd
    strat_end = str(rets.index[-1])[:10] if len(rets) > 0 else ed
    spy_mask = (spy_ret.index >= strat_start) & (spy_ret.index <= strat_end)
    spy_period = spy_ret.loc[spy_mask]
    spy_cagr = ((1 + spy_period).prod()) ** (12.0 / max(len(spy_period), 1)) - 1 if len(spy_period) > 0 else 0
    spy_sharpe = (spy_period.mean() / spy_period.std() * np.sqrt(12)) if len(spy_period) > 1 and spy_period.std() > 0 else 0
    spy_pv = (1 + spy_period).cumprod()
    spy_mdd = ((spy_pv - spy_pv.cummax()) / spy_pv.cummax()).min() if len(spy_pv) > 0 else 0

    # Normalize equity
    norm = pv / pv.iloc[0]
    dd = (pv - pv.cummax()) / pv.cummax()

    # Helper: convert to date strings + float lists (NaN/inf → None)
    def ser(s):
        return [str(v)[:10] for v in s.index], _clean_series(s.values)

    # Equity chart
    eq_dates, eq_vals = ser(norm)
    spy_dates, spy_vals = ser(spy_pv)
    dd_dates, dd_vals = ser(dd)

    # Comparison
    cmp_eq = None
    cmp_rolling = None
    cmp_yearly = None
    cmp_name = ""
    cmp_stats_col = []
    if cmp_result:
        cmp_pv_s = cmp_result['res'].pv
        cmp_norm = cmp_pv_s / cmp_pv_s.iloc[0]
        cd, cv = ser(cmp_norm)
        cmp_eq = {'dates': cd, 'values': cv, 'name': cmp_name}

        cmp_rets2 = cmp_result['res'].returns
        cmp_rs = cmp_rets2.rolling(12).mean() / cmp_rets2.rolling(12).std() * np.sqrt(12)
        crd, crv = ser(cmp_rs)
        cmp_rolling = {'dates': crd, 'values': crv, 'name': cmp_name}

        cmp_yr = an.yearly_attribution(cmp_rets2, d['spy_ret'])
        cmp_yearly = [round(float(v)*100, 2) for v in cmp_yr['strategy']]

    # Heatmap
    rdf = pd.DataFrame({
        'year': pd.to_datetime(rets.index).year,
        'month': pd.to_datetime(rets.index).month,
        'ret': rets.values,
    })
    piv = rdf.pivot_table(index='year', columns='month', values='ret', aggfunc='first') * 100
    months_list = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    heatmap_years = [str(y) for y in piv.index]
    heatmap_vals = []
    for _, row in piv.iterrows():
        heatmap_vals.append([round(float(row[c]), 1) if c in row.index and pd.notna(row[c]) else None
                             for c in range(1, 13)])

    # Distribution
    dist_vals = [round(float(v), 2) for v in (rets * 100)]
    var95 = round(float(rets.quantile(.05) * 100), 2)
    cvar95_val = rets[rets <= rets.quantile(.05)].mean() * 100
    cvar95 = round(float(cvar95_val), 2)
    mean_ret = round(float(rets.mean() * 100), 2)

    # Rolling Sharpe
    rs = rets.rolling(12).mean() / rets.rolling(12).std() * np.sqrt(12)
    rs_dates, rs_vals = ser(rs)

    # Yearly
    yr_years = [str(y) for y in yr.index]
    yr_strat = [round(float(v)*100, 2) for v in yr['strategy']]
    yr_bench = [round(float(v)*100, 2) for v in yr['benchmark']]

    # Factor
    fn = list(attr['betas'].keys())
    fv = [round(float(v), 4) for v in attr['betas'].values()]

    # KPIs
    G, R, W = '#059669', '#dc2626', '#d97706'
    def vs(val, bench, fmt='pct'):
        diff = val - bench
        arrow = '↑' if diff > 0 else '↓'
        if fmt == 'pct':
            return f"{arrow}{diff:+.1%} vs SPY"
        return f"{arrow}{diff:+.2f} vs SPY"

    kpis = [
        {'label':'CAGR','value':f"{m['cagr']:.1%}",'color':G if m['cagr']>0 else R,'vs_text':vs(m['cagr'],spy_cagr),'tooltip':'Compound Annual Growth Rate'},
        {'label':'Sharpe','value':f"{m['sharpe']:.2f}",'color':G if m['sharpe']>1.5 else W if m['sharpe']>0 else R,'vs_text':vs(m['sharpe'],spy_sharpe,'f'),'tooltip':'Annualized risk-adjusted return'},
        {'label':'Sortino','value':f"{m['sortino']:.2f}",'color':G if m['sortino']>1.5 else '#e2e8f0','tooltip':'Like Sharpe but only penalizes downside vol'},
        {'label':'Max DD','value':f"{mdd:.1%}",'color':R if mdd<-0.2 else G,'vs_text':vs(mdd,spy_mdd),'tooltip':'Largest peak-to-trough decline'},
        {'label':'Calmar','value':f"{cal:.2f}",'color':G if cal>1 else '#e2e8f0','tooltip':'CAGR / |Max Drawdown|'},
        {'label':'Win %','value':f"{m['win_rate']:.0%}",'color':G if m['win_rate']>0.55 else '#e2e8f0','tooltip':'Fraction of positive months'},
        {'label':'Alpha','value':f"{al:.1%}",'color':G if al>0 else R,'tooltip':'CAPM alpha vs benchmark'},
        {'label':'Beta','value':f"{beta:.2f}",'color':'#e2e8f0','tooltip':'Sensitivity to market returns'},
        {'label':'P&L','value':f"${pnl:+,.0f}",'color':G if pnl>0 else R,'tooltip':'Net profit / loss'},
        {'label':'Final $','value':f"${fi:,.0f}",'color':'#e2e8f0','tooltip':'Ending portfolio value'},
        {'label':'Duration','value':f"{nm}mo ({sd[:4]}–{ed[:4]})",'color':'#e2e8f0','tooltip':'Backtest period length'},
        {'label':'Best Mo','value':f"{tl['best_month']:.1%}",'color':G,'tooltip':'Highest single-month return'},
        {'label':'Worst Mo','value':f"{tl['worst_month']:.1%}",'color':R,'tooltip':'Lowest single-month return'},
        {'label':'VaR 95%','value':f"{tl['var_95']:.1%}",'color':R if tl['var_95']<-0.05 else '#e2e8f0','tooltip':'5th percentile monthly return'},
        {'label':'CVaR 95%','value':f"{tl['cvar_95']:.1%}",'color':R,'tooltip':'Average loss beyond VaR'},
        {'label':'Avg DD','value':f"{avg_dd:.1%}" if avg_dd!=0 else "0.0%",'color':R if avg_dd<-0.1 else '#e2e8f0','tooltip':'Mean drawdown depth'},
        {'label':'Recovery','value':f"{recovery_months}mo",'color':W if recovery_months>12 else '#e2e8f0','tooltip':'Avg months trough to new high'},
        {'label':'Turnover','value':f"{turnover_ann:.0f}/yr",'color':'#e2e8f0','tooltip':'Annualized position changes'},
    ]

    # Gates (explicit bool() to avoid numpy.bool_)
    gates = [
        {'name':'SR>1','passed':bool(m['sharpe']>1)},
        {'name':'DD>-25%','passed':bool(mdd>-0.25)},
        {'name':'Cal>0.5','passed':bool(cal>0.5)},
        {'name':'Sort>1.5','passed':bool(m['sortino']>1.5)},
        {'name':'Win>52%','passed':bool(m['win_rate']>0.52)},
        {'name':'α>0','passed':bool(al>0)},
    ]

    # Stats rows
    stats = [
        ('CAGR', f"{m['cagr']:.2%}"), ('Volatility', f"{rets.std()*np.sqrt(12):.2%}"),
        ('Sharpe', f"{m['sharpe']:.3f}"), ('Sortino', f"{m['sortino']:.3f}"), ('Calmar', f"{cal:.3f}"),
        ('Max Drawdown', f"{mdd:.2%}"), ('Win Rate', f"{m['win_rate']:.1%}"),
        ('P/L Ratio', f"{tl['profit_loss_ratio']:.2f}"),
        ('Max Consec Loss', f"{tl['max_consecutive_loss']}mo"),
        ('Skewness', f"{tl['skew']:.3f}"), ('Kurtosis', f"{tl['kurtosis']:.3f}"),
        ('VaR 95%', f"{tl['var_95']:.2%}"), ('CVaR 95%', f"{tl['cvar_95']:.2%}"),
        ('VaR 99%', f"{tl['var_99']:.2%}"), ('CVaR 99%', f"{tl['cvar_99']:.2%}"),
        ('Best Month', f"{tl['best_month']:.2%}"), ('Worst Month', f"{tl['worst_month']:.2%}"),
        ('Avg Drawdown', f"{avg_dd:.2%}"), ('Avg Recovery', f"{recovery_months}mo"),
        ('Turnover/yr', f"{turnover_ann:.0f}"),
        ('Alpha (CAPM)', f"{al:.2%}"), ('Beta', f"{beta:.3f}"),
        ('FF Alpha', f"{attr['alpha']:.2%}"), ('R²', f"{attr['r2']:.3f}"),
        ('MKT-RF', f"{attr['betas']['MKT']:.3f}"), ('SMB', f"{attr['betas']['SMB']:.3f}"),
        ('HML', f"{attr['betas']['HML']:.3f}"), ('UMD', f"{attr['betas']['UMD']:.3f}"),
        ('Initial Capital', f"${cap:,.0f}"), ('Final Value', f"${fi:,.0f}"),
        ('Net P&L', f"${pnl:+,.0f}"), ('Total Return', f"{m['total_return']:.1%}"),
        ('Months', f"{nm}"), ('Trades', f"{port.trade_count:,}"),
    ]
    stats_rows = [{'metric': k, 'value': v} for k, v in stats]

    resp = {
        'status': f"✓ {sd} → {ed} · {nm}mo · SR {m['sharpe']:.2f} · ${cap:,} → ${fi:,.0f}",
        'kpis': kpis,
        'gates': gates,
        'gates_passed': sum(g['passed'] for g in gates),
        'gates_total': len(gates),
        'equity': {
            'strategy': {'dates': eq_dates, 'values': eq_vals, 'name': 'Strategy'},
            'spy': {'dates': spy_dates, 'values': spy_vals, 'name': 'SPY'},
            'drawdown': {'dates': dd_dates, 'values': dd_vals, 'name': 'Drawdown'},
            'compare': cmp_eq,
        },
        'heatmap': {'years': heatmap_years, 'months': months_list, 'values': heatmap_vals},
        'distribution': {'bins': dist_vals, 'var_95': var95, 'cvar_95': cvar95, 'mean': mean_ret},
        'rolling_sharpe': {
            'strategy': {'dates': rs_dates, 'values': rs_vals, 'name': 'Strategy'},
            'compare': cmp_rolling,
        },
        'yearly': {
            'years': yr_years, 'strategy': yr_strat, 'benchmark': yr_bench,
            'compare': cmp_yearly, 'compare_name': cmp_name,
        },
        'factor': {'names': fn, 'betas': fv, 'alpha': round(float(attr['alpha']), 6), 'r2': round(float(attr['r2']), 4)},
        'stats': stats_rows,
        'compare_name': cmp_name,
    }
    return _clean(resp)
