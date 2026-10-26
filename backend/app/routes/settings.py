from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..collector.collector import send_discord_webhook
from ..config import ALLOWED_INTERVALS, ALLOWED_RANGES, DEFAULT_SETTINGS
from ..db.repository import Repository
from ..deps import get_repo

router = APIRouter(prefix="/api/settings", tags=["settings"])

class SettingsUpdate(BaseModel):
    update_interval_minutes: str | None = None
    theme: str | None = None
    default_chart_range: str | None = None
    show_item_tooltips: str | None = None
    user_agent: str | None = None
    collector_autostart: str | None = None
    discord_webhook_url: str | None = None

class WebhookTestRequest(BaseModel):
    discord_webhook_url: str | None = None

VALIDATORS = {
    "update_interval_minutes": lambda v: v in ALLOWED_INTERVALS,
    "theme": lambda v: v in {"dark", "light", "nox", "prif"},
    "default_chart_range": lambda v: v in ALLOWED_RANGES,
    "show_item_tooltips": lambda v: v in {"true", "false"},
    "user_agent": lambda v: 10 <= len(v) <= 300,
    "collector_autostart": lambda v: v in {"true", "false"},
    "discord_webhook_url": lambda v: v == "" or v.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")),
}

@router.get("")
async def get_settings(repo: Repository = Depends(get_repo)) -> dict:
    return await repo.get_settings(DEFAULT_SETTINGS)

@router.put("")
async def update_settings(
    body: SettingsUpdate,
    request: Request,
    repo: Repository = Depends(get_repo),
) -> dict:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(422, "No settings provided")
    for key, value in updates.items():
        validator = VALIDATORS.get(key)
        if validator and not validator(value):
            raise HTTPException(422, f"Invalid value for {key}: {value!r}")
    for key, value in updates.items():
        await repo.set_setting(key, value)

    if "user_agent" in updates and hasattr(request.app.state, "client"):
        client = request.app.state.client
        client.user_agent = updates["user_agent"]
        if getattr(client, "_client", None) is not None:
            client._client.headers["User-Agent"] = updates["user_agent"]

    if "collector_autostart" in updates and hasattr(request.app.state, "scheduler"):
        sched = request.app.state.scheduler
        if updates["collector_autostart"] == "true":
            sched.start()
        else:
            await sched.stop()

    return await repo.get_settings(DEFAULT_SETTINGS)

@router.post("/test-webhook")
async def test_webhook(
    body: WebhookTestRequest,
    repo: Repository = Depends(get_repo),
) -> dict:
    current = await repo.get_settings(DEFAULT_SETTINGS)
    url = (body.discord_webhook_url or current.get("discord_webhook_url") or "").strip()
    if not url:
        raise HTTPException(400, "No Discord webhook URL provided")
    ok = await send_discord_webhook(
        url,
        title="✅ RS3 GE Tracker Webhook Connected",
        description="Your Discord webhook is configured and ready to receive price alerts and 4h GE buy limit reset notifications!",
        color=0x98C379,
    )
    if not ok:
        raise HTTPException(400, "Failed to deliver test message to Discord webhook")
    return {"ok": True}
