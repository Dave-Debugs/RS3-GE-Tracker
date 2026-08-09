"""Background price collector.

Each cycle:
  1. Refresh the item mapping (at most every 24 h).
  2. Fetch /latest for live card prices (single bulk request).
  3. Incrementally fetch missed /5m buckets (rows kept for tracked items).
  4. Incrementally fetch missed /1h buckets (rows kept for ALL items —
     powers Top Movers and 14-day stats).
  5. Backfill newly tracked items via /timeseries (30d + 7d + 24h).
  6. Enforce rolling retention (default 14 days).
  7. Record run statistics and update sync state.
"""
from __future__ import annotations

import logging
import time

from ..api_client.client import ApiError, RS3PriceClient
from ..config import (
    BUCKET_1H,
    BUCKET_5M,
    MAPPING_REFRESH_SECONDS,
    MAX_CATCHUP_1H_BUCKETS,
    MAX_CATCHUP_5M_BUCKETS,
    RETENTION_DAYS,
)
from ..db.repository import Repository

log = logging.getLogger(__name__)


def normalize_bucket_row(item_id: int, ts: int, entry: dict, source: str) -> dict | None:
    if not isinstance(entry, dict):
        return None
    high = entry.get("avgHighPrice")
    low = entry.get("avgLowPrice")
    if not isinstance(high, (int, float)):
        high = None
    if not isinstance(low, (int, float)):
        low = None
    if high is None and low is None:
        return None
    if high is not None and low is not None:
        avg = (high + low) / 2
    else:
        avg = high if high is not None else low
    vol_h = entry.get("highPriceVolume") or 0
    vol_l = entry.get("lowPriceVolume") or 0
    try:
        volume = int(vol_h) + int(vol_l)
    except (TypeError, ValueError):
        volume = 0
    return {
        "item_id": item_id,
        "timestamp": ts,
        "high_price": high,
        "low_price": low,
        "average_price": avg,
        "volume": volume,
        "source": source,
    }


class Collector:
    def __init__(self, repo: Repository, client: RS3PriceClient,
                 retention_days: int = RETENTION_DAYS):
        self.repo = repo
        self.client = client
        self.retention_days = retention_days

    # ------------------------------------------------------------- mapping
    async def refresh_mapping_if_stale(self) -> bool:
        last = int(await self.repo.get_state("mapping_refreshed_at", "0") or 0)
        count = await self.repo.item_count()
        if time.time() - last < MAPPING_REFRESH_SECONDS and count:
            return False
        items = await self.client.mapping()
        n = await self.repo.upsert_items(items)
        await self.repo.set_state("mapping_refreshed_at", str(int(time.time())))
        log.info("Item mapping refreshed: %d items", n)
        return True

    # ------------------------------------------------------------- buckets
    async def _catchup_buckets(self, kind: str, bucket: int, cap: int,
                               keep_ids: set[int] | None) -> tuple[int, int]:
        fetch = self.client.five_minute if kind == "5m" else self.client.one_hour
        state_key = f"last_{kind}_ts"
        now = int(time.time())
        newest_complete = (now // bucket - 1) * bucket
        last = int(await self.repo.get_state(state_key, "0") or 0)

        if last == 0:
            if kind == "1h":
                targets = list(range(newest_complete - 23 * bucket,
                                     newest_complete + 1, bucket))
            else:
                targets = [None]
        else:
            missing = list(range(last + bucket, newest_complete + 1, bucket))
            if len(missing) > cap:
                log.warning("%s: %d missed buckets, fetching newest %d ",
                            kind, len(missing), cap)
                missing = missing[-cap:]
            targets = missing  # type: ignore[assignment]

        inserted = skipped = 0
        newest_ts = last
        for target in targets:
            try:
                ts, data = await fetch(target)
            except ApiError as e:
                log.error("%s bucket fetch failed (ts=%s): %s", kind, target, e)
                break
            rows = []
            for iid_str, entry in data.items():
                try:
                    iid = int(iid_str)
                except (TypeError, ValueError):
                    continue
                if keep_ids is not None and iid not in keep_ids:
                    continue
                row = normalize_bucket_row(iid, ts, entry, kind)
                if row:
                    rows.append(row)
            ins, skp = await self.repo.insert_price_rows(rows)
            inserted += ins
            skipped += skp
            newest_ts = max(newest_ts, ts)
        if newest_ts > last:
            await self.repo.set_state(state_key, str(newest_ts))
        return inserted, skipped

    # ------------------------------------------------------------ backfill
    async def backfill_item(self, item_id: int) -> tuple[int, int]:
        total_ins = total_skip = 0
        for lookback, source in (("30d", "ts6h"), ("7d", "1h"), ("24h", "5m")):
            try:
                points = await self.client.timeseries(item_id, lookback)
            except ApiError as e:
                log.error("backfill %s lookback=%s failed: %s", item_id, lookback, e)
                raise
            rows = []
            for p in points:
                ts = p.get("timestamp")
                if not isinstance(ts, int):
                    continue
                row = normalize_bucket_row(item_id, ts, p, source)
                if row:
                    rows.append(row)
            ins, skp = await self.repo.insert_price_rows(rows)
            total_ins += ins
            total_skip += skp
        await self.repo.set_backfilled(item_id)
        log.info("Backfilled item %d: %d rows inserted", item_id, total_ins)
        return total_ins, total_skip

    # ------------------------------------------------------------ retention
    async def enforce_retention(self) -> int:
        cutoff = int(time.time()) - self.retention_days * 86400
        deleted = await self.repo.delete_older_than(cutoff)
        if deleted:
            log.info("Retention: deleted %d rows older than %d days",
                     deleted, self.retention_days)
        return deleted

    # ----------------------------------------------------------------- run
    async def run_cycle(self) -> dict:
        run_id = await self.repo.start_run()
        start_requests = self.client.request_count
        inserted = skipped = deleted = 0
        error: str | None = None
        try:
            await self.refresh_mapping_if_stale()

            latest = await self.client.latest()
            await self.repo.upsert_latest(latest, int(time.time()))

            tracked = set(await self.repo.tracked_ids())

            for item_id in await self.repo.pending_backfill_ids():
                try:
                    ins, skp = await self.backfill_item(item_id)
                    inserted += ins
                    skipped += skp
                except ApiError:
                    pass

            ins, skp = await self._catchup_buckets("5m", BUCKET_5M,
                                             MAX_CATCHUP_5M_BUCKETS, tracked)
            inserted += ins
            skipped += skp
            ins, skp = await self._catchup_buckets("1h", BUCKET_1H,
                                             MAX_CATCHUP_1H_BUCKETS, None)
            inserted += ins
            skipped += skp

            deleted = await self.enforce_retention()
            await self.repo.set_state("last_sync_at", str(int(time.time())))
            await self.repo.set_state("last_sync_ok", "1")
            ok = True
        except ApiError as e:
            error = str(e)
            await self.repo.set_state("last_sync_ok", "0")
            log.error("Collection cycle failed: %s", e)
            ok = False
        except Exception as e:
            error = f"unexpected: {e}"
            await self.repo.set_state("last_sync_ok", "0")
            log.exception("Unexpected collector error")
            ok = False

        api_requests = self.client.request_count - start_requests
        await self.repo.finish_run(run_id, ok, inserted, skipped, deleted,
                             api_requests, error)
        log.info("Cycle done ok=%s inserted=%d skipped=%d deleted=%d requests=%d",
                 ok, inserted, skipped, deleted, api_requests)
        return {"ok": ok, "inserted": inserted, "skipped": skipped,
                "deleted": deleted, "api_requests": api_requests, "error": error}
