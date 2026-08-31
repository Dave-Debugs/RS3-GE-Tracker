from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db.repository import Repository
from ..deps import get_repo
from .helpers import icon_url

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertCreate(BaseModel):
    item_id: int
    condition: str  # ">", "<", ">=", "<="
    threshold_price: int


class AlertUpdate(BaseModel):
    active: bool


@router.get("")
async def get_alerts(repo: Repository = Depends(get_repo)) -> dict:
    rows = await repo.get_alerts()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "item_id": r["item_id"],
            "name": r.get("name") or f"Item {r['item_id']}",
            "icon_url": icon_url(r.get("icon"), r["item_id"]),
            "condition": r["condition"],
            "threshold_price": r["threshold_price"],
            "active": bool(r["active"]),
            "last_triggered": r.get("last_triggered"),
            "current_price": r.get("latest_high") or r.get("latest_low"),
            "latest_high": r.get("latest_high"),
            "latest_low": r.get("latest_low"),
        })
    return {"alerts": out}


@router.post("", status_code=201)
async def create_alert(alert: AlertCreate, repo: Repository = Depends(get_repo)) -> dict:
    if alert.condition not in [">", "<", ">=", "<="]:
        raise HTTPException(400, "Invalid condition: must be one of >, <, >=, <=")

    item = await repo.get_item(alert.item_id)
    if not item:
        raise HTTPException(404, f"Unknown item id {alert.item_id}")

    alert_id = await repo.create_alert(alert.item_id, alert.condition, alert.threshold_price)
    return {"status": "ok", "id": alert_id}


@router.put("/{alert_id}")
async def update_alert(alert_id: int, alert: AlertUpdate, repo: Repository = Depends(get_repo)) -> dict:
    updated = await repo.update_alert(alert_id, alert.active)
    if not updated:
        raise HTTPException(404, "Alert not found")
    return {"status": "ok", "id": alert_id, "active": alert.active}


@router.delete("/{alert_id}")
async def delete_alert(alert_id: int, repo: Repository = Depends(get_repo)) -> dict:
    deleted = await repo.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(404, "Alert not found")
    return {"status": "ok", "id": alert_id}
