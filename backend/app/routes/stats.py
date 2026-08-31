from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request

from ..db.repository import Repository
from ..deps import get_repo
from ..services.analytics import analyze_trend, compute_stats, merge_sources

router = APIRouter(prefix="/api", tags=["stats"])


async def _points(repo: Repository, item_id: int, request: Request | None = None) -> list[dict]:
    if not await repo.get_item(item_id):
        raise HTTPException(404, f"Unknown item id {item_id}")
    now = int(time.time())
    raw = await repo.get_price_history(item_id, now - 7 * 86400)
    if len(raw) < 5 and request and hasattr(request.app.state, "collector"):
        try:
            await request.app.state.collector.backfill_item(item_id)
            raw = await repo.get_price_history(item_id, now - 7 * 86400)
        except Exception:
            pass
    return merge_sources(raw)


@router.get("/stats/{item_id}")
async def stats(item_id: int, request: Request, repo: Repository = Depends(get_repo)) -> dict:
    points = await _points(repo, item_id, request)
    return {"item_id": item_id, **compute_stats(points, int(time.time()))}


@router.get("/trends/{item_id}")
async def trends(item_id: int, request: Request, repo: Repository = Depends(get_repo)) -> dict:
    points = await _points(repo, item_id, request)
    return {"item_id": item_id, **analyze_trend(points).to_dict()}
