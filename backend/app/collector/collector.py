from __future__ import annotations

import asyncio
import logging
import time
import httpx

from ..api_client.client import ApiError, RS3PriceClient
from ..config import (
    BUCKET_1H,
    BUCKET_5M,
    DEFAULT_SETTINGS,
    LONG_RETENTION_DAYS,
    MAPPING_REFRESH_SECONDS,
    MAX_CATCHUP_1H_BUCKETS,
    MAX_CATCHUP_5M_BUCKETS,
    RETENTION_DAYS,
)
from ..db.repository import Repository, compute_ge_tax

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

async def send_discord_webhook(webhook_url: str, title: str, description: str, color: int = 0xE8B64C) -> bool:
    url = (webhook_url or "").strip()
    if not url or not url.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")):
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={
                    "username": "RS3 Grand Exchange Tracker",
                    "embeds": [
                        {
                            "title": title,
                            "description": description,
                            "color": color,
                            "footer": {"text": "RS3 GE Tracker v1.3"},
                        }
                    ],
                },
            )
            return resp.status_code in (200, 204)
    except Exception as e:
        log.debug("Discord webhook failed: %s", e)
        return False

class Collector:
    def __init__(
        self,
        repo: Repository,
        client: RS3PriceClient,
        retention_days: int = RETENTION_DAYS,
        long_retention_days: int = LONG_RETENTION_DAYS,
    ):
        self.repo = repo
        self.client = client
        self.retention_days = retention_days
        self.long_retention_days = long_retention_days
        self._backfilled_session: set[int] = set()
        self._long_backfilled_session: set[tuple[int, str]] = set()
        self._backfill_locks: dict[int, asyncio.Lock] = {}

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
            targets = missing

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

    async def backfill_item(self, item_id: int) -> tuple[int, int]:
        lock = self._backfill_locks.setdefault(item_id, asyncio.Lock())
        async with lock:
            if item_id in self._backfilled_session:
                await self.repo.set_backfilled(item_id)
                return 0, 0
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
            self._backfilled_session.add(item_id)
            await self.repo.set_backfilled(item_id)
            log.info("Backfilled item %d: %d rows inserted", item_id, total_ins)
            return total_ins, total_skip

    async def backfill_long_horizon(self, item_id: int, lookback: str = "1y") -> tuple[int, int]:
        if lookback not in ("6m", "1y"):
            lookback = "1y"
        lock = self._backfill_locks.setdefault(item_id, asyncio.Lock())
        async with lock:
            if (item_id, lookback) in self._long_backfilled_session:
                return 0, 0
            try:
                points = await self.client.timeseries(item_id, lookback)
            except ApiError as e:
                log.warning("long backfill %s (%s) failed: %s", item_id, lookback, e)
                return 0, 0
            rows = []
            for p in points:
                ts = p.get("timestamp")
                if not isinstance(ts, int):
                    continue
                row = normalize_bucket_row(item_id, ts, p, "ts1d")
                if row:
                    rows.append(row)
            ins, skp = await self.repo.insert_price_rows(rows)
            self._long_backfilled_session.add((item_id, lookback))
            return ins, skp

    async def enforce_retention(self) -> int:
        now = int(time.time())
        cutoff = now - self.retention_days * 86400
        long_cutoff = (
            now - self.long_retention_days * 86400
            if self.long_retention_days > self.retention_days
            else None
        )
        deleted = await self.repo.delete_older_than(cutoff, long_cutoff)
        if deleted:
            log.info("Retention: deleted %d expired price rows", deleted)
        return deleted

    async def process_alerts(self, latest: dict) -> None:
        try:
            from win11toast import toast
        except ImportError:
            toast = None

        app_settings = await self.repo.get_settings(DEFAULT_SETTINGS)
        webhook_url = app_settings.get("discord_webhook_url", "").strip()

        alerts = await self.repo.get_active_alerts()
        now = int(time.time())
        vol_map: dict[int, int] | None = None

        for alert in alerts:
            iid = alert["item_id"]
            cooldown_min = int(alert.get("cooldown_minutes") or 0)
            last_trig = alert.get("last_triggered")
            if cooldown_min > 0 and last_trig and (now - int(last_trig)) < cooldown_min * 60:
                continue

            entry = latest.get(str(iid)) or latest.get(iid)
            if not entry or not isinstance(entry, dict):
                continue

            high_p = entry.get("high") or 0
            low_p = entry.get("low") or 0
            metric = alert.get("metric") or "either"

            if metric == "high":
                val = int(high_p)
                metric_label = "Instant Buy"
            elif metric == "low":
                val = int(low_p)
                metric_label = "Instant Sell"
            elif metric == "net_margin":
                if not high_p or not low_p:
                    continue
                tax = compute_ge_tax(high_p)
                val = int(high_p) - int(low_p) - tax
                metric_label = "Net Flip Margin"
            elif metric == "volume_24h":
                if vol_map is None:
                    vol_map = await self.repo.volume_since(now - 86400)
                val = int(vol_map.get(iid, 0))
                metric_label = "24h Volume"
            else:
                val = int(high_p or low_p or 0)
                metric_label = "Price"

            if val == 0 and metric != "net_margin":
                continue

            cond = alert["condition"]
            thresh = alert["threshold_price"]
            triggered = False
            if cond == ">" and val > thresh: triggered = True
            elif cond == "<" and val < thresh: triggered = True
            elif cond == ">=" and val >= thresh: triggered = True
            elif cond == "<=" and val <= thresh: triggered = True

            if triggered:
                item_name = alert.get("name") or f"Item {iid}"
                unit = "traded" if metric == "volume_24h" else "gp"
                msg = f"{item_name} {metric_label}: {val:,} {unit} ({cond} {thresh:,} {unit})"
                log.info("Alert triggered for %s (id=%d): %s", item_name, iid, msg)
                if toast is not None:
                    try:
                        toast("RS3 GE Tracker Alert", msg)
                    except Exception as e:
                        log.debug("Toast display failed: %s", e)
                if webhook_url:
                    await send_discord_webhook(
                        webhook_url,
                        title=f"🔔 GE Price Alert: {item_name}",
                        description=msg,
                    )

                deactivate = cooldown_min <= 0
                await self.repo.trigger_alert(alert["id"], now, deactivate=deactivate)

        slots = await self.repo.get_ge_slots()
        for slot in slots:
            if slot.get("empty") or slot.get("alerted_reset"):
                continue
            if slot.get("limit_remaining_seconds", 1) == 0:
                slot_idx = slot["slot_index"]
                item_name = slot.get("name") or f"Item {slot.get('item_id')}"
                msg = f"GE Slot #{slot_idx} ({item_name}) 4-hour buy limit has reset!"
                if toast is not None:
                    try:
                        toast("RS3 GE 4h Buy Limit Reset", msg)
                    except Exception:
                        pass
                if webhook_url:
                    await send_discord_webhook(
                        webhook_url,
                        title=f"⏱️ 4h Buy Limit Reset — Slot #{slot_idx}",
                        description=msg,
                        color=0x98C379,
                    )
                await self.repo.mark_ge_slot_alerted(slot_idx)

    async def run_cycle(self) -> dict:
        run_id = await self.repo.start_run()
        start_requests = self.client.request_count
        inserted = skipped = deleted = 0
        error: str | None = None
        try:
            await self.refresh_mapping_if_stale()

            latest = await self.client.latest()
            now_ts = int(time.time())
            await self.repo.upsert_latest(latest, now_ts)
            await self.repo.set_state("last_sync_at", str(now_ts))
            await self.repo.set_state("last_sync_ok", "1")
            await self.process_alerts(latest)

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
