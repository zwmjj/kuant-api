"""Shared config for API server.

Secrets and user credentials are loaded from environment variables at
runtime. Set them in .env (gitignored) or inject via your deployment
platform's secret manager. See .env.example for the required variables.

This file used to claim "No secrets are hardcoded in this file." That was
not true in the way that matters. `SECRET_KEY` fell back to a fixed string
committed in this public repository, and `USERS` fell back to demo/demo.
Neither is a secret in any useful sense: an instance deployed without the
environment variables set signs its tokens with a key any reader of this
repo can look up, so anyone could forge a valid token for any username,
and the demo account would accept a password that is also public.

The fallbacks are still here, because local development needs something to
work against. What has changed is that they no longer engage silently:
using either one now requires setting KUANT_API_ALLOW_INSECURE_DEV=1,
and the process refuses to start otherwise.
"""
import hashlib
import os

# Opt-in switch for the insecure development fallbacks below.
ALLOW_INSECURE_DEV = os.environ.get("KUANT_API_ALLOW_INSECURE_DEV", "").strip() in {"1", "true", "yes"}

_DEV_SECRET_KEY = "dev-only-secret-do-not-use-in-prod"

SECRET_KEY = os.environ.get("KUANT_API_SECRET_KEY", "")
if not SECRET_KEY:
    if not ALLOW_INSECURE_DEV:
        raise RuntimeError(
            "KUANT_API_SECRET_KEY is not set. Tokens would be signed with a key "
            "that is published in this repository, so anyone could forge one. "
            "Set KUANT_API_SECRET_KEY to a random value in your deployment's "
            "environment, or set KUANT_API_ALLOW_INSECURE_DEV=1 to run locally "
            "with the known development key."
        )
    SECRET_KEY = _DEV_SECRET_KEY

DEFAULT_START = "2015-01-01"


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


# Users are loaded from env vars as `username:password_hash` pairs
# separated by commas: e.g. KUANT_API_USERS="alice:<sha256>,bob:<sha256>"
# For local dev convenience, a demo user is provided when no env var is set.
def _load_users() -> dict:
    raw = os.environ.get("KUANT_API_USERS", "")
    if raw:
        out = {}
        for pair in raw.split(","):
            if ":" in pair:
                name, hsh = pair.split(":", 1)
                out[name.strip()] = hsh.strip()
        return out
    # Development fallback: username "demo", password "demo". Both are public,
    # so this is an open door, not an account. It engages only behind the
    # explicit KUANT_API_ALLOW_INSECURE_DEV opt-in.
    if not ALLOW_INSECURE_DEV:
        raise RuntimeError(
            "KUANT_API_USERS is not set. The only account would be demo/demo, "
            "whose password is published in this repository. Set KUANT_API_USERS "
            'as "name:<sha256 of password>,..." or set '
            "KUANT_API_ALLOW_INSECURE_DEV=1 to run locally with the demo account."
        )
    return {"demo": _hash("demo")}


USERS = _load_users()

STRATS = [
    {'id':'mom12','cat':'Price Momentum','icon':'🚀','name':'12-1 Momentum',
     'desc':'Cross-sectional 12-month momentum, skip recent month','ic':'—','hold':'Monthly',
     'tags':['L/S','Core'],'w_mom':100,'w_accel':0,'w_quality':0,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'mom_accel','cat':'Price Momentum','icon':'⚡','name':'Momentum Acceleration',
     'desc':'Multi-TF momentum + acceleration (trend inflection)','ic':'—','hold':'Monthly',
     'tags':['L/S','Signal'],'w_mom':75,'w_accel':25,'w_quality':0,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'str','cat':'Price Momentum','icon':'🔄','name':'Short-Term Reversal',
     'desc':'1-week reversal, needs daily TAQ data','ic':'—','hold':'Weekly',
     'tags':['Needs Daily Data'],'needs_data':True},
    {'id':'bm','cat':'Fundamental Value','icon':'📖','name':'Book-to-Market (HML)',
     'desc':'Value factor with momentum confirmation, L/S optimized','ic':'—','hold':'Annual',
     'tags':['L/S','Value'],'w_mom':50,'w_accel':30,'w_quality':20,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'ep','cat':'Fundamental Value','icon':'💰','name':'Earnings Yield (E/P)',
     'desc':'Inverse P/E ratio selection, deep value tilt','ic':'—','hold':'Quarterly',
     'tags':['Needs Compustat Ext'],'needs_data':True},
    {'id':'quality','cat':'Quality & Profitability','icon':'💎','name':'ROE Quality',
     'desc':'High ROE + low leverage, quality-dominant composite','ic':'—','hold':'Annual',
     'tags':['L/S','Quality'],'w_mom':50,'w_accel':25,'w_quality':25,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'gpa','cat':'Quality & Profitability','icon':'🏛️','name':'Gross Profitability',
     'desc':'Novy-Marx GP/A factor, quality premium','ic':'—','hold':'Annual',
     'tags':['Academic'],'needs_data':True},
    {'id':'lowvol','cat':'Low Volatility','icon':'🛡️','name':'Low-Vol Momentum',
     'desc':'Momentum tilted to low-vol stocks, defensive profile','ic':'—','hold':'Monthly',
     'tags':['L/S','Defensive'],'w_mom':75,'w_accel':15,'w_quality':0,'w_vol':10,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'minvol','cat':'Low Volatility','icon':'🧊','name':'Minimum Volatility',
     'desc':'Low-vol with momentum-acceleration tilt, min drawdown focus','ic':'—','hold':'Monthly',
     'tags':['L/S','Min-Risk'],'w_mom':45,'w_accel':45,'w_quality':0,'w_vol':10,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'illiq','cat':'Liquidity','icon':'💧','name':'Amihud ILLIQ',
     'desc':'Illiquidity premium, |ret|/volume','ic':'—','hold':'Monthly',
     'tags':['Needs Daily Volume'],'needs_data':True},
    {'id':'sue','cat':'Earnings Surprise','icon':'📢','name':'SUE / PEAD',
     'desc':'Post-earnings drift, needs I/B/E/S data','ic':'—','hold':'Quarterly',
     'tags':['Needs IBES'],'needs_data':True},
    {'id':'momqual','cat':'Multi-Factor','icon':'🧬','name':'Momentum + Quality',
     'desc':'Momentum-acceleration with quality overlay','ic':'—','hold':'Monthly',
     'tags':['L/S','Composite'],'w_mom':55,'w_accel':35,'w_quality':10,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'sent','cat':'Alternative Data','icon':'🤖','name':'Sentiment NLP',
     'desc':'News/social sentiment, needs RavenPack/GDELT','ic':'—','hold':'Daily',
     'tags':['Needs External API'],'needs_data':True},
    {'id':'si','cat':'Alternative Data','icon':'📉','name':'Short Interest',
     'desc':'Short interest ratio, needs FINRA data','ic':'—','hold':'Bi-weekly',
     'tags':['Needs FINRA'],'needs_data':True},
    {'id':'regime','cat':'Macro & Regime','icon':'🌍','name':'Market Regime Filter',
     'desc':'VIX/trend-based regime overlay, needs FRED','ic':'—','hold':'Monthly',
     'tags':['Needs FRED'],'needs_data':True},
    # ── Top Strategies (Phase 3+4 A-rated, from real backtest results) ──
    {'id':'wrds_at_turn','cat':'Quality & Profitability','icon':'🏆','name':'Asset Turnover (WRDS)',
     'desc':'Quarterly asset turnover from WRDS FinRatios. Sharpe 1.18, OOS 1.30, MDD -10.7%. Best overall strategy.','ic':'—','hold':'Quarterly',
     'tags':['A-rated','6/6 Gates','WRDS','Best'],
     'w_mom':0,'w_accel':0,'w_quality':100,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'macro_regime_blend','cat':'Macro & Regime','icon':'🌊','name':'Macro Regime Blend',
     'desc':'VIX-adjusted momentum + yield-curve-adjusted quality. Sharpe 1.07, OOS 0.87.','ic':'—','hold':'Monthly',
     'tags':['A-rated','6/6 Gates','FRED','Regime'],
     'w_mom':35,'w_accel':0,'w_quality':65,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'wrds_inv_turn','cat':'Quality & Profitability','icon':'📦','name':'Inventory Turnover (WRDS)',
     'desc':'Quarterly inventory turnover. Sharpe 1.12, OOS 1.17, low decay.','ic':'—','hold':'Quarterly',
     'tags':['A-rated','6/6 Gates','WRDS'],
     'w_mom':0,'w_accel':0,'w_quality':100,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'wrds_de','cat':'Fundamental Value','icon':'🏦','name':'Low Debt/Equity (WRDS)',
     'desc':'Low leverage ratio from quarterly data. Sharpe 1.04, OOS 1.00, MDD -16.3%.','ic':'—','hold':'Quarterly',
     'tags':['A-rated','6/6 Gates','WRDS'],
     'w_mom':0,'w_accel':0,'w_quality':50,'w_vol':50,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'ceo_ownership','cat':'Quality & Profitability','icon':'👔','name':'CEO Ownership %',
     'desc':'CEO stock ownership percentage. Skin-in-the-game signal. Sharpe 1.06, OOS 1.33.','ic':'—','hold':'Annual',
     'tags':['A-rated','6/6 Gates','ExecComp','Governance'],
     'w_mom':0,'w_accel':0,'w_quality':100,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'macro_wrds_ps','cat':'Multi-Factor','icon':'🔮','name':'Macro + Price/Sales (WRDS)',
     'desc':'Macro regime overlay + quarterly P/S. Sharpe 0.81, OOS 1.10.','ic':'—','hold':'Monthly',
     'tags':['B-rated','4/6 Gates','FRED+WRDS','Fusion'],
     'w_mom':50,'w_accel':0,'w_quality':50,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'governance_macro','cat':'Multi-Factor','icon':'🏛️','name':'Governance + Macro',
     'desc':'CEO ownership + culture quality + innovation + macro regime. Sharpe 1.15, MDD -17.8%.','ic':'—','hold':'Monthly',
     'tags':['A-rated','6/6 Gates','ExecComp+Culture+FRED'],
     'w_mom':40,'w_accel':0,'w_quality':60,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'governance_composite','cat':'Quality & Profitability','icon':'⚖️','name':'Governance Composite',
     'desc':'CEO ownership + culture quality + innovation (equal weight). Sharpe 1.18, OOS 1.03.','ic':'—','hold':'Annual',
     'tags':['A-rated','6/6 Gates','Zero Decay'],
     'w_mom':0,'w_accel':0,'w_quality':100,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    {'id':'ultimate_4f','cat':'Multi-Factor','icon':'💎','name':'Ultimate 4-Factor',
     'desc':'Asset turnover + macro regime + CEO ownership + GPA. Sharpe 0.88, MDD -22.2%.','ic':'—','hold':'Monthly',
     'tags':['B-rated','4/6 Gates','All Sources'],
     'w_mom':25,'w_accel':0,'w_quality':75,'w_vol':0,
     'long_n':20,'short_n':20,'long_pct':115,'short_pct':15},
    # ── A-Share Strategies ──
    {'id':'cn_reversal','cat':'A-Share','icon':'🇨🇳','name':'A股短期反转',
     'desc':'1个月收益率反转，A股特有异象。Long-only CSI300。','ic':'—','hold':'Monthly',
     'tags':['A-Share','Long-only','Reversal'],
     'w_mom':100,'w_accel':0,'w_quality':0,'w_vol':0,
     'long_n':30,'short_n':1,'long_pct':100,'short_pct':0},
    {'id':'cn_lowvol','cat':'A-Share','icon':'🛡️','name':'A股低波动',
     'desc':'12月滚动波动率取反，Long-only CSI300。','ic':'—','hold':'Monthly',
     'tags':['A-Share','Defensive','LowVol'],
     'w_mom':0,'w_accel':0,'w_quality':0,'w_vol':100,
     'long_n':30,'short_n':1,'long_pct':100,'short_pct':0},
    {'id':'cn_vol_blend','cat':'A-Share','icon':'🌊','name':'A股Vol组合',
     'desc':'低波+下行波动+偏度+VoV等权混合，CSI300。','ic':'—','hold':'Monthly',
     'tags':['A-Share','Multi-Vol','Composite'],
     'w_mom':0,'w_accel':0,'w_quality':0,'w_vol':100,
     'long_n':30,'short_n':1,'long_pct':100,'short_pct':0},
    {'id':'cn_defensive','cat':'A-Share','icon':'🏰','name':'A股防御组合',
     'desc':'反转+低波+偏度+低换手 多因子防御。','ic':'—','hold':'Monthly',
     'tags':['A-Share','Defensive','Composite'],
     'w_mom':25,'w_accel':0,'w_quality':25,'w_vol':50,
     'long_n':30,'short_n':1,'long_pct':100,'short_pct':0},
]

CAT_COLORS = {
    'Price Momentum':'#6366f1','Fundamental Value':'#ec4899','Quality & Profitability':'#8b5cf6',
    'Low Volatility':'#06b6d4','Liquidity':'#14b8a6','Earnings Surprise':'#f59e0b',
    'Multi-Factor':'#a855f7','Alternative Data':'#f97316','Macro & Regime':'#64748b',
    'A-Share':'#ef4444',
    'HK':'#f59e0b',
}

# HK strategies
STRATS += [
    {'id':'hk_mom_vol','cat':'HK','icon':'🇭🇰','name':'HK Momentum+LowVol',
     'desc':'6M动量50%+低波动50%, HSI成分股, Long-only','ic':'—','hold':'Monthly',
     'tags':['HK','Long-only','Composite'],
     'w_mom':50,'w_accel':0,'w_quality':0,'w_vol':50,
     'long_n':15,'short_n':1,'long_pct':100,'short_pct':0},
    {'id':'hk_best3','cat':'HK','icon':'🏆','name':'HK Best 3 Factor',
     'desc':'6M动量35%+下行波动35%+偏度30%, Phase3+4 A级','ic':'—','hold':'Monthly',
     'tags':['HK','Long-only','Best'],
     'w_mom':35,'w_accel':0,'w_quality':0,'w_vol':65,
     'long_n':15,'short_n':1,'long_pct':100,'short_pct':0},
    {'id':'hk_defensive','cat':'HK','icon':'🛡️','name':'HK Defensive',
     'desc':'低波+下行波+波动率动量+反转, 防御组合','ic':'—','hold':'Monthly',
     'tags':['HK','Defensive'],
     'w_mom':20,'w_accel':0,'w_quality':0,'w_vol':80,
     'long_n':15,'short_n':1,'long_pct':100,'short_pct':0},
]
