from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query

from ..db.repository import Repository
from ..deps import get_repo
from .helpers import icon_url

router = APIRouter(prefix="/api/scanner", tags=["scanner"])

RepoDep = Annotated[Repository, Depends(get_repo)]

def _wiki_url(name: str) -> str:
    clean = name.replace(" ", "_")
    return f"https://runescape.wiki/w/{quote(clean)}"

@router.get("/flips")
async def get_flip_scanner(
    repo: RepoDep,
    min_price: Annotated[int, Query(ge=1)] = 100,
    max_price: Annotated[int | None, Query(ge=1)] = None,
    min_volume: Annotated[int, Query(ge=0)] = 0,
    members: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    sort_by: Annotated[str, Query()] = "limit_profit",
) -> dict[str, Any]:
    rows = await repo.scan_flips(
        min_price=min_price,
        max_price=max_price,
        min_volume=min_volume,
        members=members,
        limit=limit,
        sort_by=sort_by,
    )
    items = []
    for r in rows:
        name = r.get("name") or f"Item {r['item_id']}"
        items.append({
            **r,
            "icon_url": icon_url(r.get("icon"), r["item_id"]),
            "wiki_url": _wiki_url(name),
        })
    return {"items": items, "count": len(items)}

@router.get("/alch")
async def get_alchemy_scanner(
    repo: RepoDep,
    min_volume: Annotated[int, Query(ge=0)] = 0,
    members: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    sort_by: Annotated[str, Query()] = "limit_profit",
) -> dict[str, Any]:
    res = await repo.scan_alchemy(
        min_volume=min_volume,
        members=members,
        limit=limit,
        sort_by=sort_by,
    )
    items = []
    for r in res["items"]:
        name = r.get("name") or f"Item {r['item_id']}"
        items.append({
            **r,
            "icon_url": icon_url(r.get("icon"), r["item_id"]),
            "wiki_url": _wiki_url(name),
        })
    return {
        "nature_rune_price": res["nature_rune_price"],
        "items": items,
        "count": len(items),
    }
