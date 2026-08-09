from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db.repository import Repository
from ..deps import get_repo, get_scheduler
from ..services.analytics import analyze_trend, merge_sources, pct_change, price_at_or_before
from .helpers import icon_url

router = APIRouter(prefix="/api/tracked", tags=["tracked"])


class TrackRequest(BaseModel):
    item_id: int


class FavoriteRequest(BaseModel):
    favorite: bool


class GroupRequest(BaseModel):
    group: str


@router.get("")
async def list_tracked(repo: Repository = Depends(get_repo)) -> dict:
    now = int(time.time())
    tracked = await repo.tracked()
    latest = await repo.get_latest([t["item_id"] for t in tracked])
    out = []
    for t in tracked:
        iid = t["item_id"]
        points = merge_sources(await repo.get_price_history(iid, now - 7 * 86400))
        lp = latest.get(iid)
        current = None
        updated = None
        if lp:
            prices = [p for p in (lp.get("high"), lp.get("low")) if p]
            current = round(sum(prices) / len(prices)) if prices else None
            updated = max(lp.get("high_time") or 0, lp.get("low_time") or 0) or None
        if current is None and points:
            current = points[-1].get("average_price")
            updated = points[-1]["timestamp"]
        trend = analyze_trend(points)
        vol_24h = sum(
            p.get("volume") or 0 for p in points if p["timestamp"] >= now - 86400
        )
        out.append({
            "item_id": iid,
            "name": t.get("name") or f"Item {iid}",
            "icon_url": icon_url(t.get("icon"), iid),
            "members": bool(t.get("members")),
            "favorite": bool(t.get("favorite")),
            "current_price": current,
            "buy_price": lp.get("high") if lp else None,
            "sell_price": lp.get("low") if lp else None,
            "change_24h": pct_change(price_at_or_before(points, now - 86400), current),
            "change_7d": pct_change(price_at_or_before(points, now - 7 * 86400), current),
            "trend": trend.classification,
            "volume_24h": int(vol_24h),
            "last_updated": updated,
            "backfilled": bool(t.get("backfilled")),
            "group_name": t.get("group_name") or "Default",
        })
    return {"tracked": out}


@router.post("", status_code=201)
async def add_tracked(body: TrackRequest, repo: Repository = Depends(get_repo),
                scheduler=Depends(get_scheduler)) -> dict:
    if not await repo.get_item(body.item_id):
        raise HTTPException(404, f"Unknown item id {body.item_id}")
    added = await repo.add_tracked(body.item_id)
    if added and scheduler is not None:
        scheduler.trigger_now()  # kick off backfill promptly
    return {"item_id": body.item_id, "added": added}


@router.delete("/{item_id}")
async def remove_tracked(item_id: int, repo: Repository = Depends(get_repo)) -> dict:
    removed = await repo.remove_tracked(item_id)
    if not removed:
        raise HTTPException(404, "Item is not tracked")
    return {"item_id": item_id, "removed": True}


@router.put("/{item_id}/favorite")
async def set_favorite(item_id: int, body: FavoriteRequest,
                 repo: Repository = Depends(get_repo)) -> dict:
    if item_id not in await repo.tracked_ids():
        raise HTTPException(404, "Item is not tracked")
    await repo.set_favorite(item_id, body.favorite)
    return {"item_id": item_id, "favorite": body.favorite}


@router.put("/{item_id}/group")
async def set_group(item_id: int, body: GroupRequest,
              repo: Repository = Depends(get_repo)) -> dict:
    if item_id not in await repo.tracked_ids():
        raise HTTPException(404, "Item is not tracked")
    await repo.set_group(item_id, body.group.strip())
    return {"item_id": item_id, "group": body.group.strip()}
