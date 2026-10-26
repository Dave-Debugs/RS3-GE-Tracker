from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from ..db.repository import Repository
from ..deps import get_repo

router = APIRouter(prefix="/api/backup", tags=["backup"])

@router.get("/export")
async def export_workspace(repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    return await repo.export_workspace()

@router.post("/import")
async def import_workspace(payload: dict[str, Any], repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(400, "Invalid backup payload")
    counts = await repo.import_workspace(payload)
    return {"status": "ok", "restored": counts}
