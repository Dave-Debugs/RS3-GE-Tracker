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
    mode: Annotated[str, Query()] = "manual",
) -> dict[str, Any]:
    res = await repo.scan_alchemy(
        min_volume=min_volume,
        members=members,
        limit=limit,
        sort_by=sort_by,
        mode="machine" if mode == "machine" else "manual",
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
        "mode": res.get("mode", "manual"),
        "nature_rune_price": res["nature_rune_price"],
        "fire_rune_price": res.get("fire_rune_price", 60),
        "divine_charge_price": res.get("divine_charge_price", 85000),
        "cast_cost": res.get("cast_cost", res["nature_rune_price"]),
        "items": items,
        "count": len(items),
    }

@router.get("/recipes")
async def get_recipe_arbitrage_scanner(
    repo: RepoDep,
    execution_mode: Annotated[str, Query()] = "patient",
    min_volume: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    sort_by: Annotated[str, Query()] = "limit_profit",
) -> dict[str, Any]:
    mode = "instant" if execution_mode == "instant" else "patient"
    rows = await repo.scan_crafting_arbitrage(
        execution_mode=mode,
        min_volume=min_volume,
        limit=limit,
        sort_by=sort_by,
    )
    items = []
    for r in rows:
        name = r.get("name") or f"Item {r['output_item_id']}"
        ings = []
        for ing in r.get("ingredients", []):
            ings.append({
                **ing,
                "icon_url": icon_url(ing.get("icon"), ing["item_id"]),
                "wiki_url": _wiki_url(ing["name"]),
            })
        items.append({
            **r,
            "icon_url": icon_url(r.get("icon"), r["output_item_id"]),
            "wiki_url": _wiki_url(name),
            "ingredients": ings,
        })
    return {"items": items, "count": len(items), "execution_mode": mode}
