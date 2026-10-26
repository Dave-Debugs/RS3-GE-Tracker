from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from ..db.repository import Repository
from ..deps import get_repo
from .helpers import icon_url

router = APIRouter(prefix="/api/ge-slots", tags=["ge-slots"])

class GeSlotUpsertRequest(BaseModel):
    item_id: int
    offer_type: str = "buy"
    target_price: int
    quantity: int = 1
    filled_qty: int = 0
    buy_cost_ref: int | None = None
    reset_timer: bool = True
    notes: str | None = None

class GeSlotCompleteRequest(BaseModel):
    sell_price: int | None = None
    quantity: int | None = None
    action: str = "auto"  # "portfolio" | "flip" | "auto"

@router.get("")
async def list_ge_slots(repo: Repository = Depends(get_repo)) -> dict:
    slots = await repo.get_ge_slots()
    for s in slots:
        if not s.get("empty"):
            s["icon_url"] = icon_url(s.get("icon"), s["item_id"])
    return {"slots": slots}

@router.put("/{slot_index}")
async def upsert_ge_slot(
    body: GeSlotUpsertRequest,
    slot_index: int = Path(..., ge=1, le=8),
    repo: Repository = Depends(get_repo),
) -> dict:
    if not await repo.get_item(body.item_id):
        raise HTTPException(404, f"Unknown item id {body.item_id}")
    slot = await repo.upsert_ge_slot(
        slot_index=slot_index,
        item_id=body.item_id,
        offer_type=body.offer_type,
        target_price=body.target_price,
        quantity=body.quantity,
        filled_qty=body.filled_qty,
        buy_cost_ref=body.buy_cost_ref,
        reset_timer=body.reset_timer,
        notes=body.notes,
    )
    if slot and not slot.get("empty"):
        slot["icon_url"] = icon_url(slot.get("icon"), slot["item_id"])
    return {"status": "ok", "slot": slot}

@router.post("/{slot_index}/complete")
async def complete_ge_slot(
    body: GeSlotCompleteRequest,
    slot_index: int = Path(..., ge=1, le=8),
    repo: Repository = Depends(get_repo),
) -> dict:
    slots = await repo.get_ge_slots()
    slot = next((s for s in slots if s["slot_index"] == slot_index), None)
    if not slot or slot.get("empty"):
        raise HTTPException(404, f"GE Slot #{slot_index} is empty")

    qty = body.quantity or slot["filled_qty"] or slot["quantity"] or 1
    offer_type = slot["offer_type"]
    action = body.action
    if action == "auto":
        action = "portfolio" if offer_type == "buy" else "flip"

    if action == "portfolio":
        port_id = await repo.add_portfolio_item(
            item_id=slot["item_id"],
            quantity=qty,
            buy_price_per_item=slot["target_price"],
        )
        await repo.clear_ge_slot(slot_index)
        return {"status": "ok", "action": "portfolio", "portfolio_id": port_id}

    buy_px = slot.get("buy_cost_ref") or slot.get("market_sell") or slot["target_price"]
    sell_px = body.sell_price or slot["target_price"]
    flip = await repo.add_flip_history(
        item_id=slot["item_id"],
        quantity=qty,
        buy_price=buy_px,
        sell_price=sell_px,
        notes=f"GE Slot #{slot_index}",
    )
    await repo.clear_ge_slot(slot_index)
    return {"status": "ok", "action": "flip", "flip": flip}

@router.delete("/{slot_index}")
async def clear_ge_slot(
    slot_index: int = Path(..., ge=1, le=8),
    repo: Repository = Depends(get_repo),
) -> dict:
    await repo.clear_ge_slot(slot_index)
    return {"status": "ok", "slot_index": slot_index}
