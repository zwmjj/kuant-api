"""Walk-forward, optimisation, stress-test and sensitivity analysis."""
import math, random as _rand
import numpy as np
import pandas as pd
from api.services.backtest_service import run_single, _clean
from qf.risk import RiskAnalyzer


# ── helpers ──────────────────────────────────────────────────────────

def _metrics(d, result):
    res, m = result['res'], result['m']
    rk = RiskAnalyzer(res.returns, res.pv)
    mdd = rk.max_drawdown()
    cal = rk.calmar(m['cagr'])
    return {
        'sharpe': float(m['sharpe']),
        'sortino': float(m['sortino']),
        'cagr': float(m['cagr']),
        'mdd': float(mdd),
        'calmar': float(cal),
        'win_rate': float(m['win_rate']),
        'alpha': float(m.get('alpha', 0)),
        'total_return': float(m['total_return']),
    }


def _obj(metrics, objective):
    return {'sharpe': metrics['sharpe'],
            'sortino': metrics['sortino'],
            'calmar': metrics['calmar']}.get(objective, metrics['sharpe'])


def _safe(v):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return 0.0
    return round(float(v), 4)


def _candidates_random(n):
    """Signal-weight tuples summing to 100. Starts with proven combos, adds random."""
    # Core combos that span the parameter space well
    core = [
        (100,0,0,0), (75,25,0,0), (50,25,25,0), (50,20,20,10),
        (60,15,0,25), (45,20,25,10), (70,20,10,0), (55,30,0,15),
        (40,25,25,10), (80,10,10,0), (60,25,15,0), (50,15,10,25),
    ]
    out = list(dict.fromkeys(core[:n]))  # dedupe, preserve order
    while len(out) < n:
        raw = np.random.dirichlet([1,1,1,1]) * 100
        t = tuple(int(round(v / 5) * 5) for v in raw)
        s = sum(t)
        if s == 0:
            continue
        t = tuple(int(v / s * 100) for v in t)
        diff = 100 - sum(t)
        t = (t[0] + diff, t[1], t[2], t[3])
        if any(v < 0 for v in t) or t in out:
            continue
        out.append(t)
    return out[:n]


def _candidates_grid(step):
    out = []
    for wm in range(0, 101, step):
        for wa in range(0, 101 - wm, step):
            for wq in range(0, 101 - wm - wa, step):
                wv = 100 - wm - wa - wq
                if wm + wa + wq + wv == 100:
                    out.append((wm, wa, wq, wv))
    return out


def _run(d, wm, wa, wq, wv, p, sd, ed):
    return run_single(d, wm, wa, wq, wv,
                      p.long_n, p.short_n, p.long_pct, p.short_pct,
                      p.turnover_penalty, p.cost_bps, sd, ed, p.initial_capital)


# ── walk-forward ─────────────────────────────────────────────────────

def walk_forward(d, p):
    prices = d['prices']
    periods = prices.index.to_period('M').unique().sort_values()
    sd, ed = p.start_date or '2015-01-01', p.end_date or str(pd.Timestamp.now().date())
    periods = periods[(periods.start_time >= sd) & (periods.end_time <= ed)]
    n = len(periods)
    if n < p.is_months + p.oos_months:
        return _clean({'error': 'Date range too short', 'windows': [], 'summary': {}})

    windows = []
    pos = 0
    while pos + p.is_months + p.oos_months <= n:
        is0 = 0 if p.window_type == 'anchored' else pos
        is1 = pos + p.is_months - 1
        oos0 = pos + p.is_months
        oos1 = min(pos + p.is_months + p.oos_months - 1, n - 1)
        windows.append((is0, is1, oos0, oos1))
        pos += p.step_months

    rows = []
    oos_dates, oos_vals = [], []
    user_w = (p.w_mom, p.w_accel, p.w_quality, p.w_vol)

    for wi, (is0, is1, oos0, oos1) in enumerate(windows):
        is_sd = str(periods[is0].start_time.date())
        is_ed = str(periods[is1].end_time.date())
        oos_sd = str(periods[oos0].start_time.date())
        oos_ed = str(periods[oos1].end_time.date())

        # Choose weights: optimize per window or use fixed user weights
        if p.optimize_per_window:
            cands = _candidates_random(p.n_candidates)
            best_s, best_w, best_m = -1e9, user_w, None
            for wm, wa, wq, wv in cands:
                r = _run(d, wm, wa, wq, wv, p, is_sd, is_ed)
                if r is None:
                    continue
                try:
                    m = _metrics(d, r)
                    s = _obj(m, p.objective)
                    if s > best_s:
                        best_s, best_w, best_m = s, (wm, wa, wq, wv), m
                except Exception:
                    continue
        else:
            # Fixed mode: just run user's weights on IS period
            best_w = user_w
            r = _run(d, *user_w, p, is_sd, is_ed)
            best_m = _metrics(d, r) if r else None

        if best_m is None:
            continue

        # OOS with chosen weights
        wm, wa, wq, wv = best_w
        oos_r = _run(d, wm, wa, wq, wv, p, oos_sd, oos_ed)
        if oos_r is None:
            continue
        oos_m = _metrics(d, oos_r)

        # equity curve
        pv = oos_r['res'].pv
        norm = pv / pv.iloc[0]
        scale = oos_vals[-1] if oos_vals else 1.0
        for idx, val in norm.items():
            oos_dates.append(str(idx)[:10])
            oos_vals.append(float(val) * scale)

        rows.append({
            'window': wi + 1,
            'is_period': f"{is_sd[:7]} ~ {is_ed[:7]}",
            'oos_period': f"{oos_sd[:7]} ~ {oos_ed[:7]}",
            'best_params': {'w_mom': wm, 'w_accel': wa, 'w_quality': wq, 'w_vol': wv},
            'is_sharpe': _safe(best_m['sharpe']),
            'is_cagr': _safe(best_m['cagr'] * 100),
            'oos_sharpe': _safe(oos_m['sharpe']),
            'oos_cagr': _safe(oos_m['cagr'] * 100),
            'oos_mdd': _safe(oos_m['mdd'] * 100),
            'oos_sortino': _safe(oos_m['sortino']),
        })

    avg_is = np.mean([r['is_sharpe'] for r in rows]) if rows else 0
    avg_oos = np.mean([r['oos_sharpe'] for r in rows]) if rows else 0
    return _clean({
        'windows': rows,
        'oos_equity': {'dates': oos_dates, 'values': oos_vals},
        'summary': {
            'total_windows': len(rows),
            'avg_is_sharpe': round(avg_is, 2),
            'avg_oos_sharpe': round(avg_oos, 2),
            'decay': round(avg_is - avg_oos, 2),
            'decay_ratio': round(avg_oos / avg_is, 2) if avg_is > 0 else 0,
            'best_window': max(rows, key=lambda r: r['oos_sharpe'])['window'] if rows else 0,
            'worst_window': min(rows, key=lambda r: r['oos_sharpe'])['window'] if rows else 0,
        },
    })


# ── optimize ─────────────────────────────────────────────────────────

def optimize(d, p):
    sd = p.start_date or '2015-01-01'
    ed = p.end_date or str(pd.Timestamp.now().date())
    cands = _candidates_grid(p.grid_step) if p.method == 'grid' else _candidates_random(p.n_iter)

    results = []
    for wm, wa, wq, wv in cands:
        r = _run(d, wm, wa, wq, wv, p, sd, ed)
        if r is None:
            continue
        try:
            m = _metrics(d, r)
            s = _obj(m, p.objective)
            results.append({
                'w_mom': wm, 'w_accel': wa, 'w_quality': wq, 'w_vol': wv,
                'sharpe': _safe(m['sharpe']), 'sortino': _safe(m['sortino']),
                'cagr': _safe(m['cagr'] * 100), 'mdd': _safe(m['mdd'] * 100),
                'calmar': _safe(m['calmar']), 'win_rate': _safe(m['win_rate'] * 100),
                'alpha': _safe(m['alpha'] * 100), 'score': _safe(s),
            })
        except Exception:
            continue

    results.sort(key=lambda x: x['score'], reverse=True)

    # heatmap: best score for each (w_mom, w_accel) pair
    hmap = {}
    for r in results:
        k = (r['w_mom'], r['w_accel'])
        if k not in hmap or r['score'] > hmap[k]:
            hmap[k] = r['score']
    heatmap = [{'w_mom': k[0], 'w_accel': k[1], 'score': v} for k, v in hmap.items()]

    return _clean({
        'best': results[0] if results else None,
        'top_10': results[:10],
        'total_evaluated': len(results),
        'heatmap': heatmap,
    })


# ── stress test ──────────────────────────────────────────────────────

SCENARIOS = [
    ('dotcom',       'Dot-Com Crash',      '2000-03-01', '2002-10-31'),
    ('gfc',          'GFC 2008',           '2007-10-01', '2009-03-31'),
    ('eu_debt',      'EU Debt 2011',       '2011-05-01', '2011-10-31'),
    ('taper',        'Taper Tantrum 2013', '2013-05-01', '2013-09-30'),
    ('china',        'China Shock 2015',   '2015-06-01', '2016-02-29'),
    ('volmageddon',  'Volmageddon 2018',   '2018-01-01', '2018-03-31'),
    ('q4_2018',      'Q4 Selloff 2018',    '2018-10-01', '2018-12-31'),
    ('covid',        'COVID Crash 2020',   '2020-02-01', '2020-04-30'),
    ('fed_2022',     'Fed Hikes 2022',     '2022-01-01', '2022-10-31'),
    ('bank_2023',    'Banking Crisis 2023','2023-02-01', '2023-04-30'),
]

SCENARIO_MAP = {s[0]: s for s in SCENARIOS}


def stress_test(d, p):
    ids = p.scenarios or [s[0] for s in SCENARIOS]
    data_min = str(d['prices'].index[0])[:10]
    data_max = str(d['prices'].index[-1])[:10]

    # run full backtest once to get returns series
    full = _run(d, p.w_mom, p.w_accel, p.w_quality, p.w_vol, p, data_min, data_max)
    if full is None:
        return _clean({'scenarios': [], 'error': 'Full backtest failed'})

    strat_rets = full['res'].returns
    strat_rets.index = pd.to_datetime(strat_rets.index.to_timestamp()) if hasattr(strat_rets.index, 'to_timestamp') else strat_rets.index

    spy_ret = d['spy_ret'].copy()
    try:
        spy_ret.index = pd.to_datetime(spy_ret.index.to_timestamp())
    except Exception:
        pass

    rows = []
    for sc_id in ids:
        sc = SCENARIO_MAP.get(sc_id)
        if sc is None:
            continue
        _, name, sd, ed = sc

        sm = (strat_rets.index >= sd) & (strat_rets.index <= ed)
        sr = strat_rets.loc[sm]
        spm = (spy_ret.index >= sd) & (spy_ret.index <= ed)
        spr = spy_ret.loc[spm]

        if len(sr) < 1:
            rows.append({'id': sc_id, 'name': name, 'period': f"{sd[:7]} ~ {ed[:7]}",
                         'available': False})
            continue

        strat_cum = float((1 + sr).prod() - 1)
        spy_cum = float((1 + spr).prod() - 1) if len(spr) > 0 else 0
        strat_pv = (1 + sr).cumprod()
        strat_dd = float(((strat_pv - strat_pv.cummax()) / strat_pv.cummax()).min())

        # equity curves for chart
        eq_strat = (1 + sr).cumprod()
        eq_spy = (1 + spr).cumprod() if len(spr) > 0 else pd.Series()
        eq_dates = [str(x)[:10] for x in eq_strat.index]
        eq_s_vals = [round(float(v), 4) for v in eq_strat.values]
        eq_b_vals = [round(float(v), 4) for v in eq_spy.values] if len(eq_spy) > 0 else []

        rows.append({
            'id': sc_id, 'name': name, 'period': f"{sd[:7]} ~ {ed[:7]}",
            'available': True, 'months': len(sr),
            'strat_return': _safe(strat_cum * 100),
            'spy_return': _safe(spy_cum * 100),
            'excess': _safe((strat_cum - spy_cum) * 100),
            'mdd': _safe(strat_dd * 100),
            'equity': {'dates': eq_dates, 'strategy': eq_s_vals, 'spy': eq_b_vals},
        })

    return _clean({'scenarios': rows})


# ── sensitivity ──────────────────────────────────────────────────────

PARAM_RANGES = {
    'w_mom': (0, 100, 10), 'w_accel': (0, 100, 10),
    'w_quality': (0, 100, 10), 'w_vol': (0, 100, 10),
    'long_n': (5, 50, 5), 'short_n': (0, 40, 5),
    'turnover_penalty': (0, 0.5, 0.05), 'cost_bps': (0, 20, 2),
}


def sensitivity(d, p):
    sd = p.start_date or '2015-01-01'
    ed = p.end_date or str(pd.Timestamp.now().date())
    signal_keys = {'w_mom', 'w_accel', 'w_quality', 'w_vol'}
    base = {'w_mom': p.w_mom, 'w_accel': p.w_accel,
            'w_quality': p.w_quality, 'w_vol': p.w_vol}

    results = []
    vals = np.arange(p.param_min, p.param_max + p.param_step * 0.5, p.param_step)

    for v in vals:
        v = round(float(v), 4)
        cur = dict(base)
        if p.param_name in signal_keys:
            cur[p.param_name] = v
            others = [k for k in signal_keys if k != p.param_name]
            remaining = 100 - v
            osum = sum(base[k] for k in others)
            if osum > 0 and remaining >= 0:
                for k in others:
                    cur[k] = round(base[k] / osum * remaining)
            elif remaining >= 0:
                cur[others[0]] = remaining

        ln = p.long_n if p.param_name != 'long_n' else int(v)
        sn = p.short_n if p.param_name != 'short_n' else int(v)
        pen = p.turnover_penalty if p.param_name != 'turnover_penalty' else v
        cst = p.cost_bps if p.param_name != 'cost_bps' else v

        r = run_single(d, cur['w_mom'], cur['w_accel'], cur['w_quality'], cur['w_vol'],
                       ln, sn, p.long_pct, p.short_pct, pen, cst, sd, ed, p.initial_capital)
        if r is None:
            continue
        try:
            m = _metrics(d, r)
            results.append({
                'value': v,
                'sharpe': _safe(m['sharpe']),
                'sortino': _safe(m['sortino']),
                'cagr': _safe(m['cagr'] * 100),
                'mdd': _safe(m['mdd'] * 100),
                'calmar': _safe(m['calmar']),
                'alpha': _safe(m['alpha'] * 100),
            })
        except Exception:
            continue

    return _clean({'param_name': p.param_name, 'results': results})
