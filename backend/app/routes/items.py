from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db.repository import Repository
from ..deps import get_repo
from ..services.search import search_items
from .helpers import item_summary

router = APIRouter(prefix="/api/items", tags=["items"])

@router.get("/search")
async def search(q: str = Query("", max_length=100), limit: int = Query(25, le=100),
           repo: Repository = Depends(get_repo)) -> dict:
    items = await search_items(repo, q, limit=limit)
    latest = await repo.get_latest([i["item_id"] for i in items])
    out = []
    for item in items:
        lp = latest.get(item["item_id"])
        current = None
        if lp:
            prices = [p for p in (lp.get("high"), lp.get("low")) if p]
            current = round(sum(prices) / len(prices)) if prices else None
        out.append({
            **item_summary(item),
            "current_price": current,
            "buy_price": lp.get("high") if lp else None,
            "sell_price": lp.get("low") if lp else None,
        })
    return {"query": q, "results": out}

@router.get("/{item_id}")
async def get_item(item_id: int, repo: Repository = Depends(get_repo)) -> dict:
    item = await repo.get_item(item_id)
    if not item:
        raise HTTPException(404, f"Unknown item id {item_id}")
    return item_summary(item)
