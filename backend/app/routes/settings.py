from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..config import ALLOWED_INTERVALS, ALLOWED_RANGES, DEFAULT_SETTINGS
from ..db.repository import Repository
from ..deps import get_repo

router = APIRouter(prefix="/api/settings", tags=["settings"])

class SettingsUpdate(BaseModel):
    update_interval_minutes: str | None = None
    theme: str | None = None
    default_chart_range: str | None = None
    user_agent: str | None = None
    collector_autostart: str | None = None

VALIDATORS = {
    "update_interval_minutes": lambda v: v in ALLOWED_INTERVALS,
    "theme": lambda v: v in {"dark", "light"},
    "default_chart_range": lambda v: v in ALLOWED_RANGES,
    "user_agent": lambda v: 10 <= len(v) <= 300,
    "collector_autostart": lambda v: v in {"true", "false"},
}

@router.get("")
async def get_settings(repo: Repository = Depends(get_repo)) -> dict:
    return await repo.get_settings(DEFAULT_SETTINGS)

@router.put("")
async def update_settings(body: SettingsUpdate,
                    repo: Repository = Depends(get_repo)) -> dict:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(422, "No settings provided")
    for key, value in updates.items():
        validator = VALIDATORS.get(key)
        if validator and not validator(value):
            raise HTTPException(422, f"Invalid value for {key}: {value!r}")
    for key, value in updates.items():
        await repo.set_setting(key, value)
    return await repo.get_settings(DEFAULT_SETTINGS)
