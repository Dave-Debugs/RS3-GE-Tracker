from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db.repository import Repository, compute_ge_tax
from ..deps import get_repo
from .helpers import icon_url

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

VALID_METRICS = {"either", "high", "low", "net_margin", "volume_24h"}

class AlertCreate(BaseModel):
    item_id: int
    condition: str
    threshold_price: int
    metric: str = "either"
    cooldown_minutes: int = 0

class AlertUpdate(BaseModel):
    active: bool

@router.get("")
async def get_alerts(repo: Repository = Depends(get_repo)) -> dict:
    rows = await repo.get_alerts()
    out = []
    for r in rows:
        high = r.get("latest_high")
        low = r.get("latest_low")
        margin = (high - low - compute_ge_tax(high)) if (high and low) else None
        out.append({
            "id": r["id"],
            "item_id": r["item_id"],
            "name": r.get("name") or f"Item {r['item_id']}",
            "icon_url": icon_url(r.get("icon"), r["item_id"]),
            "condition": r["condition"],
            "threshold_price": r["threshold_price"],
            "metric": r.get("metric") or "either",
            "cooldown_minutes": int(r.get("cooldown_minutes") or 0),
            "active": bool(r["active"]),
            "last_triggered": r.get("last_triggered"),
            "current_price": high or low,
            "latest_high": high,
            "latest_low": low,
            "latest_net_margin": margin,
        })
    return {"alerts": out}

@router.post("", status_code=201)
async def create_alert(alert: AlertCreate, repo: Repository = Depends(get_repo)) -> dict:
    if alert.condition not in [">", "<", ">=", "<="]:
        raise HTTPException(400, "Invalid condition: must be one of >, <, >=, <=")
    if alert.metric not in VALID_METRICS:
        raise HTTPException(400, f"Invalid metric: must be one of {sorted(VALID_METRICS)}")

    item = await repo.get_item(alert.item_id)
    if not item:
        raise HTTPException(404, f"Unknown item id {alert.item_id}")

    alert_id = await repo.create_alert(
        item_id=alert.item_id,
        condition=alert.condition,
        threshold_price=alert.threshold_price,
        metric=alert.metric,
        cooldown_minutes=alert.cooldown_minutes,
    )
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
