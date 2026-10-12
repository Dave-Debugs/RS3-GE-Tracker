from __future__ import annotations

import os
import threading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.updater import check_for_updates, download_and_apply_update

router = APIRouter(prefix="/api/updater", tags=["updater"])


class ApplyUpdateRequest(BaseModel):
    download_url: str
    checksum_url: str | None = None
    asset_name: str = ""


@router.get("/check")
async def get_update_check() -> dict:
    return await check_for_updates()


@router.post("/apply")
async def post_apply_update(body: ApplyUpdateRequest) -> dict:
    if not body.download_url:
        raise HTTPException(status_code=400, detail="download_url is required")
    try:
        result = await download_and_apply_update(
            download_url=body.download_url,
            checksum_url=body.checksum_url,
            asset_name=body.asset_name or "RS3-GE-Tracker-Setup.exe",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Update failed"))
    if result.get("applied"):
        threading.Timer(1.0, lambda: os._exit(0)).start()
    return result
