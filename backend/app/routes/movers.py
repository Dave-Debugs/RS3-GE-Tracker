from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..db.repository import Repository
from ..deps import get_repo
from .helpers import icon_url

router = APIRouter(prefix="/api/movers", tags=["movers"])

PERIODS = {"24h": 86400, "7d": 7 * 86400}
MIN_PRICE = 100          # ignore junk items whose 1gp swings dominate
MIN_VOLUME_24H = 2000    # require real liquidity so manipulation spikes
                         # on dead items don't dominate the board


@router.get("")
async def top_movers(
    request: Request,
    period: str = Query("24h"),
    limit: int = Query(10, le=50),
    repo: Repository = Depends(get_repo),
) -> dict:
    if period not in PERIODS:
        raise HTTPException(422, f"period must be one of {sorted(PERIODS)}")
    now = int(time.time())
    then = now - PERIODS[period]

    current = await repo.avg_price_around(now, window=3 * 3600)
    if len(current) < 100:
        client = request.app.state.client
        try:
            api_data = await client.latest()
            for iid_str, entry in api_data.items():
                try:
                    iid = int(iid_str)
                    high = entry.get("high")
                    low = entry.get("low")
                    if high is not None and low is not None:
                        current[iid] = (high + low) / 2
                    elif high is not None:
                        current[iid] = high
                    elif low is not None:
                        current[iid] = low
                except (ValueError, TypeError):
                    continue
        except Exception as e:
            pass
            
    past = await repo.avg_price_around(then, window=6 * 3600)
    
    if len(past) < 100:
        # Fallback to API if database is empty/missing old data
        client = request.app.state.client
        try:
            # wiki API accepts closest 1h bucket timestamp
            bucket_ts = (then // 3600) * 3600
            _, api_data = await client.one_hour(bucket_ts)
            for iid_str, entry in api_data.items():
                try:
                    iid = int(iid_str)
                    high = entry.get("avgHighPrice")
                    low = entry.get("avgLowPrice")
                    if high is not None and low is not None:
                        past[iid] = (high + low) / 2
                    elif high is not None:
                        past[iid] = high
                    elif low is not None:
                        past[iid] = low
                except (ValueError, TypeError):
                    continue
        except Exception as e:
            pass # ignore and just use what we have

    volume = await repo.volume_since(now - 86400)
    has_volume_data = len(volume) > 100
    min_vol = MIN_VOLUME_24H if has_volume_data else 0

    changes = []
    for iid, price_now in current.items():
        price_then = past.get(iid)
        if (
            price_then is None or price_then < MIN_PRICE
            or price_now < MIN_PRICE
            or volume.get(iid, 0) < min_vol
        ):
            continue
        changes.append((iid, price_now, price_then,
                        (price_now - price_then) / price_then * 100))

    changes.sort(key=lambda c: c[3])
    losers = changes[:limit]
    gainers = list(reversed(changes[-limit:]))
    vol_sorted = sorted(volume.items(), key=lambda kv: kv[1], reverse=True)[:limit]

    ids = {c[0] for c in gainers + losers} | {iid for iid, _ in vol_sorted}
    items = await repo.get_items(ids)

    def fmt(iid: int, price_now: float, price_then: float, pct: float) -> dict:
        item = items.get(iid, {})
        return {
            "item_id": iid,
            "name": item.get("name", f"Item {iid}"),
            "icon_url": icon_url(item.get("icon"), iid),
            "current_price": round(price_now),
            "previous_price": round(price_then),
            "change_pct": round(pct, 2),
            "volume_24h": volume.get(iid, 0),
        }

    return {
        "period": period,
        "gainers": [fmt(*c) for c in gainers if c[3] > 0],
        "losers": [fmt(*c) for c in losers if c[3] < 0],
        "highest_volume": [
            {
                "item_id": iid,
                "name": items.get(iid, {}).get("name", f"Item {iid}"),
                "icon_url": icon_url(items.get(iid, {}).get("icon"), iid),
                "current_price": round(current[iid]) if iid in current else None,
                "volume_24h": vol,
            }
            for iid, vol in vol_sorted
        ],
    }
