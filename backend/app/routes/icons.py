from __future__ import annotations

import logging
import re
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response

from ..config import DATABASE_DIR
from ..db.repository import Repository
from ..deps import get_repo

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/icon", tags=["icons"])

ICON_DIR = DATABASE_DIR / "icon_cache"
_TRANSPARENT_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63640000000600022a2c6a0e0000000049454e44ae426082"
)

@router.get("/{item_id}")
async def icon(item_id: int, request: Request,
         repo: Repository = Depends(get_repo)) -> Response:
    item = await repo.get_item(item_id)
    if not item:
        raise HTTPException(404, "unknown item")
    name = item.get("icon")
    if not name:
        return Response(_TRANSPARENT_PNG, media_type="image/png")

    safe = re.sub(r"[^A-Za-z0-9_\-. ()'&+!]", "", name)
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    cached = ICON_DIR / f"{item_id}.png"
    if cached.exists():
        return FileResponse(cached, media_type="image/png",
                            headers={"Cache-Control": "public, max-age=604800"})

    url = "https://runescape.wiki/images/" + safe.replace(" ", "_")
    try:
        client = request.app.state.client
        resp = await client._client.get(url, headers={"User-Agent": client.user_agent},
                         timeout=15, follow_redirects=True)
        if resp.status_code == 200 and resp.content:
            cached.write_bytes(resp.content)
            return Response(resp.content, media_type="image/png",
                            headers={"Cache-Control": "public, max-age=604800"})
        log.warning("icon fetch failed for %s: HTTP %s", name, resp.status_code)
    except httpx.HTTPError as e:
        log.warning("icon fetch error for %s: %s", name, e)
    return Response(_TRANSPARENT_PNG, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})
