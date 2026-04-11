"""Kuant API — FastAPI backend."""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# Ensure project root is in path so qf/ can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load market data once at startup (skipped in LITE_MODE)."""
    import os
    lite = os.environ.get("LITE_MODE", "").lower() in ("1", "true", "yes")

    if lite:
        print("Kuant API | LITE_MODE — skipping data load, serving pre-computed results only")
        app.state.data = None
        app.state.cn_data = None
    else:
        print("Kuant API | Loading US data...")
        try:
            from api.services.backtest_service import load_data
            app.state.data = load_data()
            dmin = str(app.state.data['prices'].index[0])[:10]
            dmax = str(app.state.data['prices'].index[-1])[:10]
            print(f"Kuant API | US data ready: {dmin} ~ {dmax}")
        except Exception as e:
            print(f"Kuant API | US data failed: {e} — falling back to lite mode")
            app.state.data = None

        print("Kuant API | Loading CN data...")
        try:
            from qf.data_cn import prepare_cn_data
            app.state.cn_data = prepare_cn_data()
            cn_min = str(app.state.cn_data['prices'].index[0])[:10]
            cn_max = str(app.state.cn_data['prices'].index[-1])[:10]
            print(f"Kuant API | CN data ready: {cn_min} ~ {cn_max}")
        except Exception as e:
            print(f"Kuant API | CN data failed: {e}")
            app.state.cn_data = None

    yield
    print("Kuant API | Shutting down.")


app = FastAPI(title="Kuant API", lifespan=lifespan)

import os
_extra_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000",
                   "https://web-rho-red-93.vercel.app"] + _extra_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

_lite = os.environ.get("LITE_MODE", "").lower() in ("1", "true", "yes")

# Core routers that work without heavy dependencies
from api.routers import auth, strategies, factors, research, audit, dashboard, sop, credits
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(factors.router, prefix="/api/factors", tags=["factors"])
app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(sop.router, prefix="/api/sop", tags=["sop"])
app.include_router(credits.router, prefix="/api/credits", tags=["credits"])

# Heavy routers: skip in LITE_MODE (require WRDS data / heavy packages)
if not _lite:
    from api.routers import backtest, advanced, code, downloads, factor_lab, websocket, agents, risk
    app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])
    app.include_router(advanced.router, prefix="/api/advanced", tags=["advanced"])
    app.include_router(code.router, prefix="/api/code", tags=["code"])
    app.include_router(downloads.router, prefix="/api/downloads", tags=["downloads"])
    app.include_router(factor_lab.router, prefix="/api/factor", tags=["factor"])
    app.include_router(websocket.router, prefix="/ws", tags=["websocket"])
    app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
    app.include_router(risk.router, prefix="/api/risk", tags=["risk"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
