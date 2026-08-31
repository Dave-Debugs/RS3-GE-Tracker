from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..config import ALLOWED_RANGES
from ..db.repository import Repository
from ..deps import get_repo
from ..services.analytics import downsample, merge_sources, moving_average
from .helpers import range_to_since

router = APIRouter(prefix="/api/prices", tags=["prices"])

MA_WINDOWS = {"1h": 3600, "6h": 6 * 3600, "24h": 24 * 3600, "7d": 7 * 86400}


@router.get("/{item_id}")
async def price_history(
    item_id: int,
    request: Request,
    range: str = Query("24h"),
    ma: str | None = Query(None, description="comma list of 1h,6h,24h,7d"),
    repo: Repository = Depends(get_repo),
) -> dict:
    if range not in ALLOWED_RANGES:
        raise HTTPException(422, f"range must be one of {sorted(ALLOWED_RANGES)}")
    item = await repo.get_item(item_id)
    if not item:
        raise HTTPException(404, f"Unknown item id {item_id}")

    since, now = range_to_since(range)
    # Pull a little extra history so leading moving averages have context.
    raw = await repo.get_price_history(item_id, since - 7 * 86400, now)
    if len(raw) < 5 and hasattr(request.app.state, "collector"):
        try:
            await request.app.state.collector.backfill_item(item_id)
            raw = await repo.get_price_history(item_id, since - 7 * 86400, now)
        except Exception:
            pass

    merged = merge_sources(raw)
    window_points = [p for p in merged if p["timestamp"] >= since]
    charted = downsample(window_points)

    mas = {}
    if ma:
        for key in [k.strip() for k in ma.split(",") if k.strip()]:
            if key not in MA_WINDOWS:
                raise HTTPException(422, f"unknown moving average '{key}'")
            series = moving_average(merged, MA_WINDOWS[key])
            mas[key] = [p for p in series if p["timestamp"] >= since]

    return {
        "item_id": item_id,
        "name": item["name"],
        "range": range,
        "points": [
            {
                "timestamp": p["timestamp"],
                "high_price": p.get("high_price"),
                "low_price": p.get("low_price"),
                "average_price": p.get("average_price"),
                "volume": p.get("volume") or 0,
            }
            for p in charted
        ],
        "moving_averages": mas,
    }
