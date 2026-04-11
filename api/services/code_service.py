"""Safe code execution service — runs user-written strategies/factors."""
import sys, io, traceback, time
import numpy as np
import pandas as pd


# Templates for the IDE
TEMPLATES = {
    "custom_factor": {
        "name": "Custom Factor",
        "description": "Write your own factor signal",
        "code": '''"""Custom Factor Template
Write a generate_signal(data) function that returns a DataFrame (date x permno).
Positive values = long, negative = short.
"""
import numpy as np
import pandas as pd
from qf.signals import SignalGenerator

def generate_signal(data):
    sg = SignalGenerator()
    returns = data['returns']
    mktcap = data['mktcap']
    ccm_fund = data['ccm_fund']

    # Example: combine momentum + quality
    mom = sg.multi_timeframe_momentum(returns)
    quality = sg.quality_signal(ccm_fund, returns)

    # Cross-sectional rank each
    mom_r = sg.cross_sectional_rank(mom)
    qual_r = sg.cross_sectional_rank(quality)

    # Blend: 60% momentum + 40% quality
    composite = 0.6 * mom_r + 0.4 * qual_r.fillna(0)

    # Universe filter: top 25% by market cap
    pct = mktcap.quantile(0.75, axis=1)
    cap_mask = mktcap.ge(pct, axis=0)
    signal = sg.cross_sectional_rank(composite)
    signal = signal.where(cap_mask.reindex(index=signal.index, columns=signal.columns))

    return signal
''',
    },
    "momentum_variant": {
        "name": "Momentum Variant",
        "description": "Custom momentum strategy with volatility scaling",
        "code": '''"""Volatility-Scaled Momentum
Scale momentum signal by inverse of recent volatility.
"""
import numpy as np
import pandas as pd
from qf.signals import SignalGenerator

def generate_signal(data):
    sg = SignalGenerator()
    returns = data['returns']
    mktcap = data['mktcap']

    # 12-1 momentum
    mom = sg.momentum_12_1(returns, lookback=12, skip=1)

    # Rolling volatility (use shift(1) to avoid lookahead)
    vol = returns.shift(1).rolling(12).std()

    # Vol-scaled momentum: high momentum + low vol = strongest signal
    vol_scaled = mom / vol.replace(0, np.nan)

    # Rank cross-sectionally
    signal = sg.cross_sectional_rank(vol_scaled)

    # Cap filter
    pct = mktcap.quantile(0.75, axis=1)
    cap_mask = mktcap.ge(pct, axis=0)
    signal = signal.where(cap_mask.reindex(index=signal.index, columns=signal.columns))

    return signal
''',
    },
    "value_quality": {
        "name": "Value + Quality Interaction",
        "description": "Buy cheap stocks that are also high quality",
        "code": '''"""Value-Quality Interaction
Only buy value stocks (high BM) that are also profitable (high ROE).
This avoids value traps.
"""
import numpy as np
import pandas as pd
from qf.signals import SignalGenerator

def generate_signal(data):
    sg = SignalGenerator()
    returns = data['returns']
    mktcap = data['mktcap']
    ccm_fund = data['ccm_fund']

    # Value: book-to-market
    bm = sg.book_to_market(ccm_fund, returns)
    bm_r = sg.cross_sectional_rank(bm)

    # Quality: ROE
    roe = sg.return_on_equity(ccm_fund, returns)
    roe_r = sg.cross_sectional_rank(roe)

    # Interaction: multiply ranks
    # Both positive = very positive (cheap AND profitable)
    interaction = bm_r * roe_r
    signal = sg.cross_sectional_rank(interaction.astype(float))

    # Cap filter
    pct = mktcap.quantile(0.75, axis=1)
    cap_mask = mktcap.ge(pct, axis=0)
    signal = signal.where(cap_mask.reindex(index=signal.index, columns=signal.columns))

    return signal
''',
    },
    "research_decay": {
        "name": "Research: Signal Decay Analysis",
        "description": "Analyze how signal alpha decays with holding period",
        "code": '''"""Research: Signal Decay vs Holding Period
Test how a factor's alpha changes as we increase the rebalancing lag.
Returns a dict with decay curve data.
"""
import numpy as np
import pandas as pd
from qf.signals import build_factor_signal
from qf.backtest import run_event_driven

def run_research(data):
    results = []
    factor_id = 'gpa'  # Change this to test other factors

    signal = build_factor_signal(factor_id, data, verbose=False)

    # Test different turnover penalties (proxy for holding period)
    for penalty in [0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.80, 1.00]:
        _, m = run_event_driven(data, signal, turnover_penalty=penalty, verbose=False)
        results.append({
            'turnover_penalty': penalty,
            'sharpe': m['sharpe'],
            'cagr': m['cagr'],
            'max_drawdown': m['max_drawdown'],
            'n_months': m['n_months'],
        })

    return {
        'title': f'Signal Decay: {factor_id}',
        'description': 'Sharpe ratio vs turnover penalty (higher penalty = longer holding)',
        'results': results,
    }
''',
    },
    "research_cost_sensitivity": {
        "name": "Research: Cost Sensitivity",
        "description": "Test strategy robustness across cost scenarios",
        "code": '''"""Research: Cost Sensitivity Analysis
Test how strategy performance degrades under increasing transaction costs.
"""
import numpy as np
import pandas as pd
from qf.signals import build_factor_signal
from qf.backtest import run_event_driven

def run_research(data):
    results = []
    factor_id = 'gpa'  # Change this

    signal = build_factor_signal(factor_id, data, verbose=False)

    # Test different cost levels
    cost_scenarios = [
        {'label': '0.5x', 'commission_bps': 0.5, 'spread_bps': 2.5, 'impact_coeff': 0.15},
        {'label': '1x (base)', 'commission_bps': 1.0, 'spread_bps': 5.0, 'impact_coeff': 0.3},
        {'label': '2x', 'commission_bps': 2.0, 'spread_bps': 10.0, 'impact_coeff': 0.6},
        {'label': '3x', 'commission_bps': 3.0, 'spread_bps': 15.0, 'impact_coeff': 0.9},
        {'label': '5x', 'commission_bps': 5.0, 'spread_bps': 25.0, 'impact_coeff': 1.5},
    ]

    for scenario in cost_scenarios:
        label = scenario.pop('label')
        _, m = run_event_driven(data, signal, verbose=False, **scenario)
        results.append({
            'scenario': label,
            'sharpe': m['sharpe'],
            'cagr': m['cagr'],
            'max_drawdown': m['max_drawdown'],
        })

    return {
        'title': f'Cost Sensitivity: {factor_id}',
        'description': 'Performance under 0.5x to 5x cost multipliers',
        'results': results,
    }
''',
    },
    "research_crowding": {
        "name": "Research: Factor Crowding Test",
        "description": "Measure how much a custom signal overlaps with known factors",
        "code": '''"""Research: Factor Crowding / Orthogonality Test
Regress your custom signal returns on FF5 factors to check crowding.
"""
import numpy as np
import pandas as pd
from qf.signals import build_factor_signal
from qf.backtest import run_event_driven
from qf.attribution import AttributionAnalyzer

def run_research(data):
    factor_id = 'gpa'  # Change this

    signal = build_factor_signal(factor_id, data, verbose=False)
    r, m = run_event_driven(data, signal, verbose=False)

    attr = AttributionAnalyzer(data['ff5'])
    result = attr.ff5_regression(r.returns, factor_id)

    return {
        'title': f'Crowding Analysis: {factor_id}',
        'description': f'FF5 regression: Alpha={result["alpha"]:.2%}, R²={result["r2"]:.3f}',
        'results': [
            {'metric': 'Alpha (annual)', 'value': round(result['alpha'], 4)},
            {'metric': 'R²', 'value': round(result['r2'], 4)},
            {'metric': 'Beta MKT', 'value': round(result['betas']['MKT'], 4)},
            {'metric': 'Beta SMB', 'value': round(result['betas']['SMB'], 4)},
            {'metric': 'Beta HML', 'value': round(result['betas']['HML'], 4)},
            {'metric': 'Beta UMD', 'value': round(result['betas']['UMD'], 4)},
            {'metric': 'Sharpe', 'value': round(m['sharpe'], 4)},
            {'metric': 'CAGR', 'value': round(m['cagr'], 4)},
        ],
    }
''',
    },
}


def execute_code(code: str, mode: str, data: dict, params: dict = None):
    """Execute user code safely and return results.

    mode: 'backtest' | 'research'
    - backtest: expects generate_signal(data) -> DataFrame, runs backtest
    - research: expects run_research(data) -> dict, returns raw results
    """
    if params is None:
        params = {}

    # Restricted namespace
    allowed_imports = {
        'np': np, 'numpy': np,
        'pd': pd, 'pandas': pd,
    }

    namespace = {'__builtins__': __builtins__, **allowed_imports}

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured = io.StringIO()

    start = time.time()
    try:
        exec(compile(code, '<user_code>', 'exec'), namespace)
        elapsed = time.time() - start

        if mode == 'backtest':
            if 'generate_signal' not in namespace:
                return {'error': 'Code must define generate_signal(data) function', 'stdout': captured.getvalue()}

            signal = namespace['generate_signal'](data)

            if not isinstance(signal, pd.DataFrame):
                return {'error': f'generate_signal must return DataFrame, got {type(signal).__name__}', 'stdout': captured.getvalue()}

            # Run backtest
            from qf.backtest import run_event_driven
            from qf.risk import RiskAnalyzer
            from qf.attribution import AttributionAnalyzer

            bt_params = {
                'long_n': params.get('long_n', 20),
                'short_n': params.get('short_n', 20),
                'long_pct': params.get('long_pct', 1.15),
                'short_pct': params.get('short_pct', 0.15),
                'turnover_penalty': params.get('turnover_penalty', 0.25),
            }

            result, metrics = run_event_driven(data, signal, verbose=False, **bt_params)

            # IS/OOS split
            sig_is = signal.loc[signal.index <= '2020-12-31']
            sig_oos = signal.loc[signal.index >= '2021-01-01']
            _, m_is = run_event_driven(data, sig_is, verbose=False, **bt_params)
            _, m_oos = run_event_driven(data, sig_oos, verbose=False, **bt_params)

            is_sh = m_is.get('sharpe', 0) if m_is else 0
            oos_sh = m_oos.get('sharpe', 0) if m_oos else 0
            decay = 1 - oos_sh / max(is_sh, 0.01) if is_sh > 0.01 else 1

            risk = RiskAnalyzer(result.returns, result.pv)
            calmar = risk.calmar(metrics['cagr'])
            dsr = risk.dsr(20)
            tail = risk.tail_stats()

            attr = AttributionAnalyzer(data['ff5'])
            attribution = attr.ff5_regression(result.returns, 'custom')

            # Gate checks
            gates = 0
            gate_results = []
            for name, val, thresh, comp in [
                ('Sharpe > 1.0', metrics['sharpe'], 1.0, '>'),
                ('MaxDD < 25%', metrics['max_drawdown'], -0.25, '>'),
                ('Decay < 50%', decay, 0.50, '<'),
                ('OOS Sharpe > 0.5', oos_sh, 0.5, '>'),
                ('Calmar > 0.5', calmar, 0.5, '>'),
                ('DSR > 1.0', dsr['z_score'], 1.0, '>'),
            ]:
                passed = val > thresh if comp == '>' else val < thresh
                if passed: gates += 1
                gate_results.append({'name': name, 'passed': passed, 'value': round(float(val), 4)})

            # Equity curve
            pv = result.pv
            equity = {
                'dates': [str(d)[:10] for d in pv.index],
                'values': [round(float(v), 2) for v in pv.values],
            }

            # Monthly returns for heatmap
            rets = result.returns
            heatmap_data = []
            for date, ret in rets.items():
                heatmap_data.append({'year': date.year, 'month': date.month, 'return': round(float(ret), 4)})

            return {
                'status': 'ok',
                'mode': 'backtest',
                'elapsed': round(elapsed, 2),
                'metrics': {k: round(float(v), 4) if isinstance(v, (int, float, np.floating)) else v
                           for k, v in metrics.items()},
                'is_metrics': {k: round(float(v), 4) if isinstance(v, (int, float, np.floating)) else v
                              for k, v in (m_is or {}).items()},
                'oos_metrics': {k: round(float(v), 4) if isinstance(v, (int, float, np.floating)) else v
                               for k, v in (m_oos or {}).items()},
                'sharpe_decay': round(float(decay), 4),
                'gates': gate_results,
                'gates_passed': gates,
                'calmar': round(float(calmar), 4),
                'dsr_z': round(float(dsr['z_score']), 4),
                'attribution': {
                    'alpha': round(float(attribution['alpha']), 4),
                    'r2': round(float(attribution['r2']), 4),
                    'betas': {k: round(float(v), 4) for k, v in attribution['betas'].items()},
                },
                'tail': {k: round(float(v), 4) if isinstance(v, (int, float, np.floating)) else v
                        for k, v in tail.items()},
                'equity': equity,
                'heatmap': heatmap_data,
                'signal_shape': list(signal.shape),
                'signal_coverage': round(float(signal.notna().sum(axis=1).median()), 0),
                'stdout': captured.getvalue(),
            }

        elif mode == 'research':
            if 'run_research' not in namespace:
                return {'error': 'Code must define run_research(data) function', 'stdout': captured.getvalue()}

            research_result = namespace['run_research'](data)
            elapsed = time.time() - start

            return {
                'status': 'ok',
                'mode': 'research',
                'elapsed': round(elapsed, 2),
                'research': research_result,
                'stdout': captured.getvalue(),
            }

        else:
            return {'error': f'Unknown mode: {mode}'}

    except Exception as e:
        elapsed = time.time() - start
        return {
            'error': str(e),
            'traceback': traceback.format_exc(),
            'elapsed': round(elapsed, 2),
            'stdout': captured.getvalue(),
        }
    finally:
        sys.stdout = old_stdout


def get_source_code(source_id: str):
    """Get source code of existing strategies/factors."""
    import inspect
    try:
        if source_id.startswith('signal:'):
            fid = source_id.replace('signal:', '')
            from qf.signals import SignalGenerator
            method = getattr(SignalGenerator, fid, None)
            if method:
                return {'id': source_id, 'code': inspect.getsource(method)}

        elif source_id.startswith('file:'):
            path = source_id.replace('file:', '')
            safe_paths = ['qf/signals.py', 'qf/backtest.py', 'qf/costs.py', 'qf/data.py',
                          'qf/risk.py', 'qf/stress.py', 'qf/optimizer.py', 'qf/attribution.py',
                          'qf/portfolio.py', 'qf/strategy.py', 'qf/framework.py',
                          'strategies/factors.py', 'strategies/momentum.py']
            if path in safe_paths:
                with open(path, 'r', encoding='utf-8') as f:
                    return {'id': source_id, 'code': f.read()}

        return {'error': f'Source not found: {source_id}'}
    except Exception as e:
        return {'error': str(e)}
