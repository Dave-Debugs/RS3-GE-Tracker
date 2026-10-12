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
    group: str | None = None
    group_name: str | None = None

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
        buy_price = lp.get("high") if lp else None
        sell_price = lp.get("low") if lp else None

        margin = None
        tax = None
        net_profit = None
        roi_pct = None
        limit_profit_4h = None
        buy_limit = t.get("buy_limit")
        if buy_price and sell_price:
            margin = buy_price - sell_price
            tax = int(min(buy_price * 0.02, 50000000)) if buy_price >= 50 else 0
            net_profit = margin - tax
            if sell_price > 0:
                roi_pct = round((net_profit / sell_price) * 100, 2)
            if buy_limit:
                limit_profit_4h = net_profit * buy_limit

        out.append({
            "item_id": iid,
            "name": t.get("name") or f"Item {iid}",
            "icon_url": icon_url(t.get("icon"), iid),
            "description": t.get("description"),
            "members": bool(t.get("members")),
            "buy_limit": buy_limit,
            "highalch": t.get("highalch"),
            "favorite": bool(t.get("favorite")),
            "current_price": current,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "margin": margin,
            "tax": tax,
            "net_profit": net_profit,
            "roi_pct": roi_pct,
            "limit_profit_4h": limit_profit_4h,
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
        scheduler.trigger_now()
    return {"item_id": body.item_id, "added": added}

@router.delete("/groups/{group_name}")
async def delete_group(group_name: str, repo: Repository = Depends(get_repo)) -> dict:
    count = await repo.delete_group(group_name.strip())
    return {"deleted_group": group_name, "items_moved_to_default": count}

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
    group_val = (body.group or body.group_name or "Default").strip()
    await repo.set_group(item_id, group_val)
    return {"item_id": item_id, "group": group_val, "group_name": group_val}
