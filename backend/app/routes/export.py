from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..config import ALLOWED_RANGES
from ..db.repository import Repository
from ..deps import get_repo
from ..services.analytics import merge_sources
from ..services.export import to_csv, to_json
from .helpers import range_to_since

router = APIRouter(prefix="/api/export", tags=["export"])

@router.get("/{item_id}")
async def export_item(
    item_id: int,
    format: str = Query("csv", pattern="^(csv|json)$"),
    range: str = Query("24h"),
    repo: Repository = Depends(get_repo),
) -> Response:
    if range not in ALLOWED_RANGES:
        raise HTTPException(422, f"range must be one of {sorted(ALLOWED_RANGES)}")
    item = await repo.get_item(item_id)
    if not item:
        raise HTTPException(404, f"Unknown item id {item_id}")
    since, now = range_to_since(range)
    points = merge_sources(await repo.get_price_history(item_id, since, now))
    safe_name = "".join(
        c if c.isalnum() or c in " -_" else "_" for c in item["name"]
    ).strip().replace(" ", "_")
    filename = f"rs3_{safe_name}_{range}.{format}"

    if format == "csv":
        content = to_csv(item_id, item["name"], points)
        media = "text/csv"
    else:
        content = to_json(item_id, item["name"], points)
        media = "application/json"
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
