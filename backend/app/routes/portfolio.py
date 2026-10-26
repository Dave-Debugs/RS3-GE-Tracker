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

class PortfolioCloseRequest(BaseModel):
    sell_price_per_item: int
    quantity_sold: int | None = None
    notes: str | None = None

class FlipHistoryAdd(BaseModel):
    item_id: int
    quantity: int
    buy_price: int
    sell_price: int
    notes: str | None = None

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

@router.post("/{port_id}/close")
async def close_portfolio_item(
    port_id: int,
    body: PortfolioCloseRequest,
    repo: Repository = Depends(get_repo),
) -> dict:
    res = await repo.close_portfolio_item(
        port_id=port_id,
        sell_price_per_item=body.sell_price_per_item,
        quantity_sold=body.quantity_sold,
        notes=body.notes,
    )
    if not res:
        raise HTTPException(404, "Portfolio position not found")
    return {"status": "ok", **res}

@router.delete("/{port_id}")
async def delete_portfolio_item(port_id: int, repo: Repository = Depends(get_repo)) -> dict:
    deleted = await repo.delete_portfolio_item(port_id)
    if not deleted:
        raise HTTPException(404, "Portfolio position not found")
    return {"status": "ok", "id": port_id}

@router.get("/history")
async def get_flip_history(repo: Repository = Depends(get_repo)) -> dict:
    data = await repo.get_flip_history()
    for flip in data.get("flips", []):
        flip["icon_url"] = icon_url(flip.get("icon"), flip["item_id"])
    return data

@router.post("/history", status_code=201)
async def add_flip_history(body: FlipHistoryAdd, repo: Repository = Depends(get_repo)) -> dict:
    if not await repo.get_item(body.item_id):
        raise HTTPException(404, f"Unknown item id {body.item_id}")
    res = await repo.add_flip_history(
        item_id=body.item_id,
        quantity=body.quantity,
        buy_price=body.buy_price,
        sell_price=body.sell_price,
        notes=body.notes,
    )
    return {"status": "ok", **res}

@router.delete("/history/{flip_id}")
async def delete_flip_history(flip_id: int, repo: Repository = Depends(get_repo)) -> dict:
    deleted = await repo.delete_flip_history(flip_id)
    if not deleted:
        raise HTTPException(404, "Flip history record not found")
    return {"status": "ok", "id": flip_id}
