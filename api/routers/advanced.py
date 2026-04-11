from fastapi import APIRouter, Request, HTTPException
from api.schemas.advanced import (
    WalkForwardRequest, OptimizeRequest, StressTestRequest, SensitivityRequest,
)
from api.services.advanced_service import (
    walk_forward, optimize, stress_test, sensitivity, SCENARIOS, PARAM_RANGES,
)

router = APIRouter()


def _get_data(request: Request):
    """Get preloaded data, raising clear error if not available."""
    d = getattr(request.app.state, 'data', None)
    if d is None:
        raise HTTPException(status_code=503, detail="Data not loaded yet. Server is starting up.")
    return d


# NOTE: sync def (not async) so FastAPI auto-runs in threadpool,
# preventing CPU-bound work from blocking the event loop.

@router.post("/walk-forward")
def api_walk_forward(req: WalkForwardRequest, request: Request):
    return walk_forward(_get_data(request), req)


@router.post("/optimize")
def api_optimize(req: OptimizeRequest, request: Request):
    return optimize(_get_data(request), req)


@router.post("/stress-test")
def api_stress_test(req: StressTestRequest, request: Request):
    return stress_test(_get_data(request), req)


@router.post("/sensitivity")
def api_sensitivity(req: SensitivityRequest, request: Request):
    return sensitivity(_get_data(request), req)


@router.get("/scenarios")
def api_scenarios():
    return [{'id': s[0], 'name': s[1], 'start': s[2], 'end': s[3]} for s in SCENARIOS]


@router.get("/param-ranges")
def api_param_ranges():
    return PARAM_RANGES
