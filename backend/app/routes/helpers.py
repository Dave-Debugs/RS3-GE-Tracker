from __future__ import annotations

import time

from ..config import CHART_RANGE_SECONDS

def icon_url(icon: str | None, item_id: int | None = None) -> str | None:

    if item_id is not None:
        return f"/api/icon/{item_id}"
    if not icon:
        return None
    return "https://runescape.wiki/images/" + icon.replace(" ", "_")

def range_to_since(range_key: str, now: int | None = None) -> tuple[int, int]:
    now = now or int(time.time())
    seconds = CHART_RANGE_SECONDS.get(range_key, CHART_RANGE_SECONDS["24h"])
    return now - seconds, now

def item_summary(item: dict) -> dict:
    return {
        "item_id": item["item_id"],
        "name": item["name"],
        "description": item.get("description"),
        "members": bool(item.get("members")),
        "icon_url": icon_url(item.get("icon"), item["item_id"]),
        "buy_limit": item.get("buy_limit"),
    }
