from fastapi import APIRouter, HTTPException
from api.config import STRATS, CAT_COLORS

router = APIRouter()


@router.get("/list")
async def get_strategies():
    return {'strategies': STRATS, 'cat_colors': CAT_COLORS}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str):
    s = next((x for x in STRATS if x['id'] == strategy_id), None)
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return s
