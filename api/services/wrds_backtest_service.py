"""WRDS-based strategy signal builder — for wrds_at_turn, macro_regime, CEO, etc."""
import os, pickle
import numpy as np
import pandas as pd
from qf.signals import SignalGenerator, build_factor_signal

sg = SignalGenerator()
CACHE = "data_cache"

_cache = {}

def _load(name):
    if name not in _cache:
        path = os.path.join(CACHE, name)
        if os.path.exists(path):
            with open(path, 'rb') as f:
                _cache[name] = pickle.load(f)
        else:
            _cache[name] = None
    return _cache[name]


def _ratio_to_monthly(ratios, returns, mktcap, col, ascending=True, cap_q=0.75):
    sub = ratios[['permno', 'public_date', col]].dropna().sort_values('public_date')
    sub['month'] = sub['public_date'].dt.to_period('M').dt.to_timestamp('M')
    sub = sub.drop_duplicates(subset=['permno', 'month'], keep='last')
    pivot = sub.pivot_table(index='month', columns='permno', values=col)
    aligned = pivot.reindex(index=returns.index, method='ffill', limit=6)
    aligned = aligned.reindex(columns=returns.columns)
    if not ascending:
        aligned = -aligned
    ranked = sg.cross_sectional_rank(aligned.astype(float))
    pct = mktcap.quantile(cap_q, axis=1)
    cap_mask = mktcap.ge(pct, axis=0).reindex(index=ranked.index, columns=ranked.columns)
    return ranked.where(cap_mask)


def _gvkey_annual(data, gvkey_to_permno, returns, mktcap, col, ascending=True, cap_q=0.75):
    df = data.copy()
    df['gvkey'] = df['gvkey'].astype(str)
    df['permno'] = df['gvkey'].map(gvkey_to_permno)
    df = df.dropna(subset=['permno', col])
    if 'year' in df.columns:
        df['month'] = df['year'].apply(lambda y: pd.Timestamp(f'{int(y)+1}-07-01'))
    pivot = df.pivot_table(index='month', columns='permno', values=col, aggfunc='last')
    aligned = pivot.reindex(index=returns.index, method='ffill', limit=18)
    aligned = aligned.reindex(columns=returns.columns)
    if not ascending:
        aligned = -aligned
    ranked = sg.cross_sectional_rank(aligned.astype(float))
    pct = mktcap.quantile(cap_q, axis=1)
    cap_mask = mktcap.ge(pct, axis=0).reindex(index=ranked.index, columns=ranked.columns)
    return ranked.where(cap_mask)


def build_wrds_signal(strategy_id, d):
    """Build signal for WRDS-based strategies."""
    returns = d['returns']
    mktcap = d['mktcap']

    ratios = _load('wrds_finratios.pkl')
    macro = _load('fred_macro.pkl')
    execcomp = _load('execcomp.pkl')
    culture = _load('corporate_culture.pkl')

    # Build gvkey->permno map
    ccm = d.get('ccm_fund', pd.DataFrame())
    gvkey_to_permno = {}
    if 'permno' in ccm.columns and 'gvkey' in ccm.columns:
        for _, row in ccm[['gvkey', 'permno']].drop_duplicates().iterrows():
            gvkey_to_permno[str(row['gvkey'])] = row['permno']

    pct = mktcap.quantile(0.75, axis=1)
    cap_mask = mktcap.ge(pct, axis=0)

    def blend(sigs, weights):
        ci = list(sigs.values())[0].index
        cc = list(sigs.values())[0].columns
        for s in sigs.values():
            ci = ci.intersection(s.index)
            cc = cc.intersection(s.columns)
        b = sum(w * sigs[k].loc[ci, cc].fillna(0) for k, w in weights.items() if k in sigs)
        r = sg.cross_sectional_rank(b.astype(float))
        return r.where(cap_mask.reindex(index=ci, columns=cc))

    def macro_regime_signal():
        if macro is None:
            return build_factor_signal('gpa', d, verbose=False)
        vix = macro['VIX'].resample('ME').last()
        vix_med = vix.expanding(24).median()
        curve_data = macro['T10Y2Y'].resample('ME').last()
        gpa = build_factor_signal('gpa', d, verbose=False)
        mom12 = build_factor_signal('mom12', d, verbose=False)
        vs = pd.Series(1.0, index=returns.index)
        cs_v = pd.Series(1.0, index=returns.index)
        for date in returns.index:
            vi = vix.index[vix.index <= date]
            if len(vi) > 0:
                v = vix.loc[vi[-1]]
                m = vix_med.loc[vi[-1]] if vi[-1] in vix_med.index else 20
                if pd.notna(v) and pd.notna(m):
                    if v > m * 1.5: vs[date] = 0.5
                    elif v > m * 1.2: vs[date] = 0.75
            ci = curve_data.index[curve_data.index <= date]
            if len(ci) > 0:
                c = curve_data.loc[ci[-1]]
                if pd.notna(c):
                    if c < 0: cs_v[date] = 1.5
                    elif c < 0.5: cs_v[date] = 1.2
        sig = sg.cross_sectional_rank(
            (0.35 * mom12.mul(vs, axis=0) + 0.65 * gpa.mul(cs_v, axis=0)).astype(float))
        return sig.where(cap_mask.reindex(index=sig.index, columns=sig.columns))

    # Route by strategy ID
    if strategy_id == 'wrds_at_turn' and ratios is not None:
        return _ratio_to_monthly(ratios, returns, mktcap, 'at_turn', True)
    elif strategy_id == 'wrds_inv_turn' and ratios is not None:
        return _ratio_to_monthly(ratios, returns, mktcap, 'inv_turn', True)
    elif strategy_id == 'wrds_de' and ratios is not None:
        return _ratio_to_monthly(ratios, returns, mktcap, 'de_ratio', False)
    elif strategy_id == 'wrds_curr' and ratios is not None:
        return _ratio_to_monthly(ratios, returns, mktcap, 'curr_ratio', True)
    elif strategy_id == 'wrds_roe' and ratios is not None:
        return _ratio_to_monthly(ratios, returns, mktcap, 'roe', True)
    elif strategy_id == 'wrds_ps' and ratios is not None:
        return _ratio_to_monthly(ratios, returns, mktcap, 'ps', False)
    elif strategy_id == 'macro_regime_blend':
        return macro_regime_signal()
    elif strategy_id == 'macro_wrds_ps':
        mb = macro_regime_signal()
        ps = _ratio_to_monthly(ratios, returns, mktcap, 'ps', False) if ratios is not None else build_factor_signal('bm', d, verbose=False)
        return blend({'mb': mb, 'ps': ps}, {'mb': 0.50, 'ps': 0.50})
    elif strategy_id == 'ceo_ownership' and execcomp is not None:
        ceo = execcomp[execcomp['ceoann'] == 'CEO']
        return _gvkey_annual(ceo, gvkey_to_permno, returns, mktcap, 'shrown_tot_pct', True)
    elif strategy_id == 'governance_composite' and execcomp is not None and culture is not None:
        ceo = execcomp[execcomp['ceoann'] == 'CEO']
        sig_ceo = _gvkey_annual(ceo, gvkey_to_permno, returns, mktcap, 'shrown_tot_pct', True)
        sig_cq = _gvkey_annual(culture, gvkey_to_permno, returns, mktcap, 's_quality', True)
        sig_ci = _gvkey_annual(culture, gvkey_to_permno, returns, mktcap, 's_innovation', True)
        return blend({'ceo': sig_ceo, 'cq': sig_cq, 'ci': sig_ci},
                     {'ceo': 0.34, 'cq': 0.33, 'ci': 0.33})
    elif strategy_id == 'governance_macro':
        gov_sigs = {}
        if execcomp is not None:
            ceo = execcomp[execcomp['ceoann'] == 'CEO']
            gov_sigs['ceo'] = _gvkey_annual(ceo, gvkey_to_permno, returns, mktcap, 'shrown_tot_pct', True)
        if culture is not None:
            gov_sigs['cq'] = _gvkey_annual(culture, gvkey_to_permno, returns, mktcap, 's_quality', True)
        if len(gov_sigs) < 1:
            gov_sigs['gpa'] = build_factor_signal('gpa', d, verbose=False)
        gov = blend(gov_sigs, {k: 1.0 / len(gov_sigs) for k in gov_sigs})
        mb = macro_regime_signal()
        return blend({'gov': gov, 'mb': mb}, {'gov': 0.40, 'mb': 0.60})
    elif strategy_id == 'ultimate_4f':
        at = _ratio_to_monthly(ratios, returns, mktcap, 'at_turn', True) if ratios is not None else build_factor_signal('gpa', d, verbose=False)
        mb = macro_regime_signal()
        gpa = build_factor_signal('gpa', d, verbose=False)
        ceo_sigs = {}
        if execcomp is not None:
            ceo_data = execcomp[execcomp['ceoann'] == 'CEO']
            ceo_sigs['ceo'] = _gvkey_annual(ceo_data, gvkey_to_permno, returns, mktcap, 'shrown_tot_pct', True)
        else:
            ceo_sigs['ceo'] = build_factor_signal('roe', d, verbose=False)
        return blend({'at': at, 'mb': mb, 'ceo': ceo_sigs['ceo'], 'gpa': gpa},
                     {'at': 0.35, 'mb': 0.25, 'ceo': 0.20, 'gpa': 0.20})
    else:
        # Fallback to GPA
        return build_factor_signal('gpa', d, verbose=False)
