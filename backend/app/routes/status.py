from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from ..db.repository import Repository
from ..deps import get_repo, get_scheduler

router = APIRouter(prefix="/api/status", tags=["status"])

@router.get("")
async def status(repo: Repository = Depends(get_repo),
           scheduler=Depends(get_scheduler)) -> dict:
    last_run = await repo.last_run()
    last_ok = await repo.last_successful_run()
    last_sync_at = int(await repo.get_state("last_sync_at", "0") or 0)
    last_sync_ok = await repo.get_state("last_sync_ok", "0") == "1"
    now = int(time.time())

    run_online = bool(
        last_run and last_run.get("ok")
        and last_run.get("finished_at")
        and now - last_run["finished_at"] < 2 * 3600
    )
    sync_online = bool(last_sync_ok and last_sync_at and now - last_sync_at < 2 * 3600)
    api_online = run_online or sync_online

    last_ok_ts = last_ok.get("finished_at") if last_ok else None
    last_update = max(filter(None, [last_ok_ts, last_sync_at or None]), default=None)

    return {
        "api_online": api_online,
        "collector_running": bool(scheduler and scheduler.running),
        "last_update": last_update,
        "next_update": int(scheduler.next_run_at) if scheduler and scheduler.next_run_at else None,
        "last_run_ok": bool((last_run and last_run.get("ok")) or sync_online),
        "last_run_error": last_run.get("error") if last_run and not sync_online else None,
        "tracked_items": len(await repo.tracked_ids()),
        "database_records": await repo.price_history_count(),
        "data_coverage_days": await repo.data_coverage_days(),
        "item_count": await repo.item_count(),
        "server_time": now,
    }

@router.post("/collect-now")
def collect_now(scheduler=Depends(get_scheduler)) -> dict:
    if scheduler is None or not scheduler.running:
        return {"triggered": False, "reason": "collector not running"}
    scheduler.trigger_now()
    return {"triggered": True}
