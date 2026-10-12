from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

CSV_FIELDS = [
    "timestamp", "item_id", "item_name", "high_price", "low_price",
    "average_price", "volume",
]

def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

def to_csv(item_id: int, item_name: str, points: list[dict]) -> str:

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\r\n")
    writer.writeheader()
    for p in points:
        writer.writerow({
            "timestamp": _iso(p["timestamp"]),
            "item_id": item_id,
            "item_name": item_name,
            "high_price": p.get("high_price") if p.get("high_price") is not None else "",
            "low_price": p.get("low_price") if p.get("low_price") is not None else "",
            "average_price": p.get("average_price") if p.get("average_price") is not None else "",
            "volume": p.get("volume") or 0,
        })
    return buf.getvalue()

def to_json(item_id: int, item_name: str, points: list[dict]) -> str:
    return json.dumps({
        "item_id": item_id,
        "item_name": item_name,
        "points": [
            {
                "timestamp": p["timestamp"],
                "datetime_utc": _iso(p["timestamp"]),
                "high_price": p.get("high_price"),
                "low_price": p.get("low_price"),
                "average_price": p.get("average_price"),
                "volume": p.get("volume") or 0,
            }
            for p in points
        ],
    }, indent=2)
