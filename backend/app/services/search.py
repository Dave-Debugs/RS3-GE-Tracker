"""Item search: exact / prefix / substring via SQL, plus fuzzy fallback."""
from __future__ import annotations

import difflib

from ..db.repository import Repository


async def search_items(repo: Repository, query: str, limit: int = 25) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []

    # Numeric query -> item id lookup first
    results: list[dict] = []
    seen: set[int] = set()
    if query.isdigit():
        item = await repo.get_item(int(query))
        if item:
            results.append(item)
            seen.add(item["item_id"])

    for item in await repo.search_items(query, limit=limit):
        if item["item_id"] not in seen:
            results.append(item)
            seen.add(item["item_id"])

    # Fuzzy fallback when substring search finds little (typos like "abysal")
    if len(results) < 5 and len(query) >= 3 and not query.isdigit():
        names = await repo.all_item_names()
        matches = difflib.get_close_matches(
            query.lower(), [n.lower() for _, n in names], n=10, cutoff=0.75
        )
        if matches:
            wanted = set(matches)
            fuzzy_ids = [iid for iid, n in names if n.lower() in wanted]
            for item in (await repo.get_items(fuzzy_ids)).values():
                if item["item_id"] not in seen:
                    results.append(item)
                    seen.add(item["item_id"])

    return results[:limit]
