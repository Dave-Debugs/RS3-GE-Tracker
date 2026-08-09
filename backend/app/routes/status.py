from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from ..db.repository import Repository
from ..deps import get_repo, get_scheduler

router = APIRouter(prefix="/api/status", tags=["status"])


@router.get("")
def status(repo: Repository = Depends(get_repo),
           scheduler=Depends(get_scheduler)) -> dict:
    last_run = repo.last_run()
    last_ok = repo.last_successful_run()
    now = int(time.time())
    api_online = bool(
        last_run and last_run.get("ok")
        and last_run.get("finished_at")
        and now - last_run["finished_at"] < 2 * 3600
    )
    return {
        "api_online": api_online,
        "collector_running": bool(scheduler and scheduler.running),
        "last_update": last_ok.get("finished_at") if last_ok else None,
        "next_update": int(scheduler.next_run_at) if scheduler and scheduler.next_run_at else None,
        "last_run_ok": bool(last_run and last_run.get("ok")),
        "last_run_error": last_run.get("error") if last_run else None,
        "tracked_items": len(repo.tracked_ids()),
        "database_records": repo.price_history_count(),
        "data_coverage_days": repo.data_coverage_days(),
        "item_count": repo.item_count(),
        "server_time": now,
    }


@router.post("/collect-now")
def collect_now(scheduler=Depends(get_scheduler)) -> dict:
    if scheduler is None or not scheduler.running:
        return {"triggered": False, "reason": "collector not running"}
    scheduler.trigger_now()
    return {"triggered": True}
