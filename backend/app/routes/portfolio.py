from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db.repository import Repository
from ..deps import get_repo
from .helpers import icon_url

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

class PortfolioItemAdd(BaseModel):
    item_id: int
    quantity: int
    buy_price_per_item: int

@router.get("")
async def get_portfolio(repo: Repository = Depends(get_repo)) -> dict:
    data = await repo.get_portfolio()
    for item in data.get("items", []):
        resolved = icon_url(item.get("icon"), item["item_id"])
        item["icon"] = resolved
        item["icon_url"] = resolved
    return data

@router.post("", status_code=201)
async def add_portfolio_item(data: PortfolioItemAdd, repo: Repository = Depends(get_repo)) -> dict:
    if not await repo.get_item(data.item_id):
        raise HTTPException(404, f"Unknown item id {data.item_id}")

    port_id = await repo.add_portfolio_item(data.item_id, data.quantity, data.buy_price_per_item)
    return {"status": "ok", "id": port_id}

@router.delete("/{port_id}")
async def delete_portfolio_item(port_id: int, repo: Repository = Depends(get_repo)) -> dict:
    deleted = await repo.delete_portfolio_item(port_id)
    if not deleted:
        raise HTTPException(404, "Portfolio position not found")
    return {"status": "ok", "id": port_id}
