from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException

from ..db.repository import Repository
from ..deps import get_repo
from ..services.analytics import analyze_trend, compute_stats, merge_sources

router = APIRouter(prefix="/api", tags=["stats"])


def _points(repo: Repository, item_id: int) -> list[dict]:
    if not repo.get_item(item_id):
        raise HTTPException(404, f"Unknown item id {item_id}")
    now = int(time.time())
    return merge_sources(repo.get_price_history(item_id, now - 7 * 86400))


@router.get("/stats/{item_id}")
def stats(item_id: int, repo: Repository = Depends(get_repo)) -> dict:
    points = _points(repo, item_id)
    return {"item_id": item_id, **compute_stats(points, int(time.time()))}


@router.get("/trends/{item_id}")
def trends(item_id: int, repo: Repository = Depends(get_repo)) -> dict:
    points = _points(repo, item_id)
    return {"item_id": item_id, **analyze_trend(points).to_dict()}
