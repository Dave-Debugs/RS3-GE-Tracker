from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from .database import Database

log = logging.getLogger(__name__)

def _now() -> int:
    return int(time.time())

def compute_ge_tax(sell_price: int | float | None) -> int:
    if not sell_price or sell_price < 50:
        return 0
    return int(min(math.floor(float(sell_price) * 0.02), 50_000_000))

def compute_break_even_sell(buy_price: int | float | None) -> int:
    if not buy_price or buy_price <= 0:
        return 0
    if buy_price < 50:
        return int(buy_price)
    return int(math.ceil(float(buy_price) / 0.98))

def compute_liquidity_metrics(buy_limit: int | None, volume_24h: int) -> dict[str, Any]:
    """Compute estimated 4h buy-limit fill time (at 25% market capture) and 0-100 liquidity score."""
    lim = max(1, int(buy_limit or 1))
    vol = max(0, int(volume_24h or 0))
    if vol <= 0:
        return {
            "est_fill_hours": None,
            "liquidity_score": 0,
            "liquidity_rating": "Low",
        }
    hourly_capture = max(0.01, (vol / 24.0) * 0.25)
    est_hours = round(lim / hourly_capture, 1)
    ratio = vol / float(lim * 12)
    score = min(100, max(5, int(round(math.sqrt(min(ratio, 1.5)) * 82))))
    if score >= 70:
        rating = "High"
    elif score >= 40:
        rating = "Medium"
    else:
        rating = "Low"
    return {
        "est_fill_hours": est_hours,
        "liquidity_score": score,
        "liquidity_rating": rating,
    }

_CACHED_RECIPE_CATALOG: dict[int, list[dict[str, int]]] | None = None

def _load_recipe_catalog() -> dict[int, list[dict[str, int]]]:
    global _CACHED_RECIPE_CATALOG
    if _CACHED_RECIPE_CATALOG is not None:
        return _CACHED_RECIPE_CATALOG

    candidates: list[Path] = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "frontend" / "src" / "recipes.json")
        candidates.append(Path(sys._MEIPASS) / "recipes.json")
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    candidates.append(repo_root / "frontend" / "src" / "recipes.json")
    candidates.append(Path(__file__).resolve().parent.parent / "recipes.json")

    parsed: dict[int, list[dict[str, int]]] = {}
    for p in candidates:
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for out_id_str, ings in raw.items():
                        try:
                            out_id = int(out_id_str)
                            clean_ings = []
                            for ing in ings:
                                iid = int(ing.get("id", 0))
                                qty = int(float(ing.get("qty", 1)))
                                if iid > 0 and qty > 0:
                                    clean_ings.append({"item_id": iid, "qty": qty})
                            if clean_ings:
                                parsed[out_id] = clean_ings
                        except (ValueError, TypeError):
                            continue
                break
            except Exception as e:
                log.warning("Failed to parse recipe catalog from %s: %s", p, e)

    _CACHED_RECIPE_CATALOG = parsed
    return parsed


class Repository:
    def __init__(self, db: Database):
        self.db = db

    async def upsert_items(self, items: Iterable[dict[str, Any]]) -> int:
        now = _now()
        rows = [
            (
                it["id"], it["name"], it.get("examine"),
                1 if it.get("members") else 0, it.get("icon"), None,
                it.get("limit"), it.get("value"), it.get("highalch"),
                it.get("lowalch"), now,
            )
            for it in items
            if isinstance(it.get("id"), int) and it.get("name")
        ]
        if not self.db.conn:
            return 0
        cur = await self.db.conn.executemany(
            """INSERT INTO items (item_id, name, description, members, icon,
                                  category, buy_limit, value, highalch, lowalch,
                                  last_updated)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(item_id) DO UPDATE SET
                 name=excluded.name, description=excluded.description,
                 members=excluded.members, icon=excluded.icon,
                 buy_limit=excluded.buy_limit, value=excluded.value,
                 highalch=excluded.highalch, lowalch=excluded.lowalch,
                 last_updated=excluded.last_updated""",
            rows,
        )
        await self.db.conn.commit()
        return cur.rowcount if cur.rowcount and cur.rowcount > 0 else len(rows)

    async def item_count(self) -> int:
        if not self.db.conn: return 0
        cur = await self.db.conn.execute("SELECT COUNT(*) FROM items")
        row = await cur.fetchone()
        return row[0] if row else 0

    async def get_item(self, item_id: int) -> dict | None:
        if not self.db.conn: return None
        cur = await self.db.conn.execute(
            "SELECT * FROM items WHERE item_id=?", (item_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def get_items(self, item_ids: Iterable[int]) -> dict[int, dict]:
        ids = list(item_ids)
        if not ids or not self.db.conn:
            return {}
        out: dict[int, dict] = {}
        chunk_size = 800
        for i in range(0, len(ids), chunk_size):
            chunk = ids[i : i + chunk_size]
            q = ",".join("?" * len(chunk))
            cur = await self.db.conn.execute(
                f"SELECT * FROM items WHERE item_id IN ({q})", chunk
            )
            rows = await cur.fetchall()
            for r in rows:
                out[r["item_id"]] = dict(r)
        return out

    async def search_items(self, pattern: str, limit: int = 25) -> list[dict]:
        if not self.db.conn: return []
        cur = await self.db.conn.execute(
            """SELECT * FROM items WHERE name LIKE ? COLLATE NOCASE
               ORDER BY CASE WHEN name LIKE ? COLLATE NOCASE THEN 0 ELSE 1 END,
                        LENGTH(name), name LIMIT ?""",
            (f"%{pattern}%", f"{pattern}%", limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def all_item_names(self) -> list[tuple[int, str]]:
        if not self.db.conn: return []
        cur = await self.db.conn.execute("SELECT item_id, name FROM items")
        rows = await cur.fetchall()
        return [(r["item_id"], r["name"]) for r in rows]

    async def insert_price_rows(self, rows: list[dict[str, Any]]) -> tuple[int, int]:
        if not rows or not self.db.conn:
            return 0, 0
        now = _now()
        before_changes = self.db.conn.total_changes

        await self.db.conn.executemany(
            """INSERT OR IGNORE INTO price_history
               (item_id, timestamp, high_price, low_price, average_price,
                volume, source, created_at)
               VALUES (:item_id, :timestamp, :high_price, :low_price,
                       :average_price, :volume, :source, :created_at)""",
            [{**r, "created_at": now} for r in rows],
        )
        await self.db.conn.commit()

        after_changes = self.db.conn.total_changes
        inserted = max(0, after_changes - before_changes)
        return inserted, max(0, len(rows) - inserted)

    async def get_price_history(
        self, item_id: int, since: int, until: int | None = None,
        sources: list[str] | None = None,
    ) -> list[dict]:
        if not self.db.conn: return []
        until = until or _now()
        sql = """SELECT timestamp, high_price, low_price, average_price,
                        volume, source
                 FROM price_history
                 WHERE item_id=? AND timestamp>=? AND timestamp<=?"""
        args: list[Any] = [item_id, since, until]
        if sources:
            sql += f" AND source IN ({','.join('?' * len(sources))})"
            args.extend(sources)
        sql += " ORDER BY timestamp"
        cur = await self.db.conn.execute(sql, args)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_price_history_batch(
        self, item_ids: Iterable[int], since: int, until: int | None = None
    ) -> dict[int, list[dict]]:
        ids = list(item_ids)
        if not ids or not self.db.conn:
            return {}
        until = until or _now()
        out: dict[int, list[dict]] = {iid: [] for iid in ids}
        chunk_size = 500
        for i in range(0, len(ids), chunk_size):
            chunk = ids[i : i + chunk_size]
            q = ",".join("?" * len(chunk))
            sql = f"""SELECT item_id, timestamp, high_price, low_price, average_price,
                             volume, source
                      FROM price_history
                      WHERE item_id IN ({q}) AND timestamp>=? AND timestamp<=?
                      ORDER BY item_id, timestamp"""
            cur = await self.db.conn.execute(sql, [*chunk, since, until])
            for r in await cur.fetchall():
                out[r["item_id"]].append(dict(r))
        return out

    async def delete_older_than(self, cutoff: int, long_cutoff: int | None = None) -> int:
        if not self.db.conn: return 0
        if long_cutoff is None:
            cur = await self.db.conn.execute(
                "DELETE FROM price_history WHERE timestamp < ?", (cutoff,)
            )
        else:
            cur = await self.db.conn.execute(
                """DELETE FROM price_history
                   WHERE (source IN ('5m', '1h') AND timestamp < ?)
                      OR (source NOT IN ('5m', '1h') AND timestamp < ?)""",
                (cutoff, long_cutoff),
            )
        await self.db.conn.commit()
        return cur.rowcount

    async def price_history_count(self) -> int:
        if not self.db.conn: return 0
        cur = await self.db.conn.execute("SELECT COUNT(*) FROM price_history")
        row = await cur.fetchone()
        return row[0] if row else 0

    async def data_coverage_days(self) -> float:
        if not self.db.conn: return 0.0
        cur = await self.db.conn.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM price_history"
        )
        row = await cur.fetchone()
        if not row or row[0] is None:
            return 0.0
        return round((row[1] - row[0]) / 86400, 1)

    async def earliest_timestamp(self, item_id: int) -> int | None:
        if not self.db.conn: return None
        cur = await self.db.conn.execute(
            "SELECT MIN(timestamp) FROM price_history WHERE item_id=?",
            (item_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else None

    async def avg_price_around(self, ts: int, window: int = 2 * 3600) -> dict[int, float]:
        if not self.db.conn: return {}
        cur = await self.db.conn.execute(
            """SELECT item_id, AVG(average_price) AS p
               FROM price_history
               WHERE source='1h' AND timestamp BETWEEN ? AND ?
                     AND average_price IS NOT NULL
               GROUP BY item_id""",
            (ts - window, ts + window),
        )
        rows = await cur.fetchall()
        return {r["item_id"]: r["p"] for r in rows}

    async def volume_since(self, since: int) -> dict[int, int]:
        if not self.db.conn: return {}
        cur = await self.db.conn.execute(
            """SELECT item_id, SUM(volume) AS v FROM price_history
               WHERE source='1h' AND timestamp>=? GROUP BY item_id""",
            (since,),
        )
        rows = await cur.fetchall()
        return {r["item_id"]: r["v"] or 0 for r in rows}

    async def upsert_latest(self, data: dict[str, dict], fetched_at: int) -> None:
        if not self.db.conn: return
        rows = [
            (int(iid), d.get("high"), d.get("highTime"),
             d.get("low"), d.get("lowTime"), fetched_at)
            for iid, d in data.items()
            if isinstance(d, dict) and str(iid).isdigit()
        ]
        await self.db.conn.executemany(
            """INSERT INTO latest_prices (item_id, high, high_time, low,
                                          low_time, fetched_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(item_id) DO UPDATE SET
                 high=excluded.high, high_time=excluded.high_time,
                 low=excluded.low, low_time=excluded.low_time,
                 fetched_at=excluded.fetched_at""",
            rows,
        )
        await self.db.conn.commit()

    async def get_latest(self, item_ids: Iterable[int]) -> dict[int, dict]:
        ids = list(item_ids)
        if not ids or not self.db.conn:
            return {}
        out: dict[int, dict] = {}
        chunk_size = 800
        for i in range(0, len(ids), chunk_size):
            chunk = ids[i : i + chunk_size]
            q = ",".join("?" * len(chunk))
            cur = await self.db.conn.execute(
                f"SELECT * FROM latest_prices WHERE item_id IN ({q})", chunk
            )
            for r in await cur.fetchall():
                out[r["item_id"]] = dict(r)
        return out

    async def get_all_latest(self) -> dict[int, dict]:
        if not self.db.conn:
            return {}
        cur = await self.db.conn.execute("SELECT * FROM latest_prices")
        return {r["item_id"]: dict(r) for r in await cur.fetchall()}

    async def add_tracked(self, item_id: int) -> bool:
        if not self.db.conn: return False
        cur = await self.db.conn.execute(
            "INSERT OR IGNORE INTO tracked_items (item_id, added_at, group_name) VALUES (?,?, 'Default')",
            (item_id, _now()),
        )
        await self.db.conn.commit()
        return cur.rowcount > 0

    async def remove_tracked(self, item_id: int) -> bool:
        if not self.db.conn: return False
        cur = await self.db.conn.execute(
            "DELETE FROM tracked_items WHERE item_id=?", (item_id,)
        )
        await self.db.conn.commit()
        return cur.rowcount > 0

    async def set_favorite(self, item_id: int, favorite: bool) -> None:
        if not self.db.conn: return
        await self.db.conn.execute(
            "UPDATE tracked_items SET favorite=? WHERE item_id=?",
            (1 if favorite else 0, item_id),
        )
        await self.db.conn.commit()

    async def set_group(self, item_id: int, group_name: str) -> None:
        if not self.db.conn: return
        await self.db.conn.execute(
            "UPDATE tracked_items SET group_name=? WHERE item_id=?",
            (group_name or 'Default', item_id),
        )
        await self.db.conn.commit()

    async def delete_group(self, group_name: str) -> int:
        if not self.db.conn or not group_name or group_name == 'Default': return 0
        cur = await self.db.conn.execute(
            "UPDATE tracked_items SET group_name='Default' WHERE group_name=?",
            (group_name,),
        )
        await self.db.conn.commit()
        return cur.rowcount

    async def set_backfilled(self, item_id: int) -> None:
        if not self.db.conn: return
        await self.db.conn.execute(
            "UPDATE tracked_items SET backfilled=1 WHERE item_id=?", (item_id,)
        )
        await self.db.conn.commit()

    async def tracked(self) -> list[dict]:
        if not self.db.conn: return []
        cur = await self.db.conn.execute(
            """SELECT t.*, i.name, i.icon, i.members, i.description,
                      i.buy_limit, i.highalch
               FROM tracked_items t LEFT JOIN items i USING (item_id)
               ORDER BY t.group_name ASC, t.favorite DESC, i.name"""
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def tracked_ids(self) -> list[int]:
        if not self.db.conn: return []
        cur = await self.db.conn.execute(
            "SELECT item_id FROM tracked_items"
        )
        rows = await cur.fetchall()
        return [r["item_id"] for r in rows]

    async def pending_backfill_ids(self) -> list[int]:
        if not self.db.conn: return []
        cur = await self.db.conn.execute(
            "SELECT item_id FROM tracked_items WHERE backfilled=0"
        )
        rows = await cur.fetchall()
        return [r["item_id"] for r in rows]

    async def get_state(self, key: str, default: str | None = None) -> str | None:
        if not self.db.conn: return default
        cur = await self.db.conn.execute(
            "SELECT value FROM sync_state WHERE key=?", (key,)
        )
        row = await cur.fetchone()
        return row["value"] if row else default

    async def set_state(self, key: str, value: str) -> None:
        if not self.db.conn: return
        await self.db.conn.execute(
            """INSERT INTO sync_state (key, value) VALUES (?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (key, value),
        )
        await self.db.conn.commit()

    async def get_settings(self, defaults: dict[str, str]) -> dict[str, str]:
        if not self.db.conn: return defaults
        cur = await self.db.conn.execute("SELECT key, value FROM settings")
        rows = await cur.fetchall()
        stored = {r["key"]: r["value"] for r in rows}
        return {**defaults, **stored}

    async def set_setting(self, key: str, value: str) -> None:
        if not self.db.conn: return
        await self.db.conn.execute(
            """INSERT INTO settings (key, value) VALUES (?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (key, value),
        )
        await self.db.conn.commit()

    async def start_run(self) -> int:
        if not self.db.conn: return 0
        cur = await self.db.conn.execute(
            "INSERT INTO collection_runs (started_at) VALUES (?)", (_now(),)
        )
        await self.db.conn.commit()
        return cur.lastrowid

    async def finish_run(self, run_id: int, ok: bool, inserted: int, skipped: int,
                   deleted: int, api_requests: int, error: str | None) -> None:
        if not self.db.conn: return
        await self.db.conn.execute(
            """UPDATE collection_runs
               SET finished_at=?, ok=?, inserted=?, skipped=?, deleted=?,
                   api_requests=?, error=? WHERE id=?""",
            (_now(), 1 if ok else 0, inserted, skipped, deleted,
             api_requests, error, run_id),
        )
        await self.db.conn.commit()

    async def last_run(self) -> dict | None:
        if not self.db.conn: return None
        cur = await self.db.conn.execute(
            "SELECT * FROM collection_runs WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def last_successful_run(self) -> dict | None:
        if not self.db.conn: return None
        cur = await self.db.conn.execute(
            "SELECT * FROM collection_runs WHERE ok=1 ORDER BY id DESC LIMIT 1"
        )
        row = await cur.fetchone()
        return dict(row) if row else None


    async def get_alerts(self) -> list[dict]:
        if not self.db.conn: return []
        cur = await self.db.conn.execute(
            """SELECT a.*, i.name, i.icon, l.high as latest_high, l.low as latest_low
               FROM alerts a
               JOIN items i ON a.item_id = i.item_id
               LEFT JOIN latest_prices l ON a.item_id = l.item_id
               ORDER BY a.id DESC"""
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_active_alerts(self) -> list[dict]:
        if not self.db.conn: return []
        cur = await self.db.conn.execute(
            """SELECT a.*, i.name
               FROM alerts a
               JOIN items i ON a.item_id = i.item_id
               WHERE a.active = 1"""
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def create_alert(
        self,
        item_id: int,
        condition: str,
        threshold_price: int,
        metric: str = "either",
        cooldown_minutes: int = 0,
    ) -> int:
        if not self.db.conn: return 0
        cur = await self.db.conn.execute(
            """INSERT INTO alerts (item_id, condition, threshold_price, metric, cooldown_minutes)
               VALUES (?, ?, ?, ?, ?)""",
            (item_id, condition, threshold_price, metric or "either", max(0, int(cooldown_minutes))),
        )
        await self.db.conn.commit()
        return cur.lastrowid or 0

    async def update_alert(self, alert_id: int, active: bool) -> bool:
        if not self.db.conn: return False
        cur = await self.db.conn.execute(
            "UPDATE alerts SET active = ? WHERE id = ?",
            (1 if active else 0, alert_id),
        )
        await self.db.conn.commit()
        return (cur.rowcount or 0) > 0

    async def trigger_alert(self, alert_id: int, triggered_at: int, deactivate: bool = True) -> bool:
        if not self.db.conn: return False
        new_active = 0 if deactivate else 1
        cur = await self.db.conn.execute(
            "UPDATE alerts SET active = ?, last_triggered = ? WHERE id = ?",
            (new_active, triggered_at, alert_id),
        )
        await self.db.conn.commit()
        return (cur.rowcount or 0) > 0

    async def delete_alert(self, alert_id: int) -> bool:
        if not self.db.conn: return False
        cur = await self.db.conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        await self.db.conn.commit()
        return (cur.rowcount or 0) > 0


    async def get_portfolio(self) -> dict:
        if not self.db.conn:
            return {
                "items": [],
                "total_cost": 0,
                "current_value": 0,
                "total_tax": 0,
                "net_liquidation_value": 0,
                "unrealized_profit": 0,
                "net_unrealized_profit": 0,
                "realized_profit": 0,
                "realized_count": 0,
            }
        query = """
            SELECT p.id, p.item_id, p.quantity, p.buy_price_per_item,
                   i.name, i.icon, i.buy_limit,
                   l.high as current_price, l.low as instant_sell_price
            FROM portfolio p
            JOIN items i ON p.item_id = i.item_id
            LEFT JOIN latest_prices l ON p.item_id = l.item_id
            ORDER BY p.id DESC
        """
        cur = await self.db.conn.execute(query)
        raw_items = [dict(r) for r in await cur.fetchall()]
        items = []
        total_cost = 0
        gross_value = 0
        total_tax = 0

        for item in raw_items:
            qty = int(item["quantity"] or 0)
            buy_px = int(item["buy_price_per_item"] or 0)
            cur_px = int(item["current_price"] or buy_px)
            tax_per_item = compute_ge_tax(cur_px)
            net_sell_per_item = cur_px - tax_per_item
            lot_cost = qty * buy_px
            lot_gross = qty * cur_px
            lot_tax = qty * tax_per_item
            lot_net = lot_gross - lot_tax
            lot_net_profit = lot_net - lot_cost

            total_cost += lot_cost
            gross_value += lot_gross
            total_tax += lot_tax

            items.append({
                **item,
                "current_price": cur_px,
                "tax_per_item": tax_per_item,
                "net_sell_price": net_sell_per_item,
                "break_even_price": compute_break_even_sell(buy_px),
                "lot_tax": lot_tax,
                "lot_net_value": lot_net,
                "lot_gross_profit": lot_gross - lot_cost,
                "lot_net_profit": lot_net_profit,
            })

        net_liquidation_value = gross_value - total_tax

        cur_hist = await self.db.conn.execute(
            "SELECT COALESCE(SUM(net_profit), 0) AS total_net, COUNT(*) AS cnt FROM flip_history"
        )
        hist_row = await cur_hist.fetchone()
        realized_profit = int(hist_row["total_net"] if hist_row else 0)
        realized_count = int(hist_row["cnt"] if hist_row else 0)

        return {
            "items": items,
            "total_cost": total_cost,
            "current_value": gross_value,
            "total_tax": total_tax,
            "net_liquidation_value": net_liquidation_value,
            "unrealized_profit": gross_value - total_cost,
            "net_unrealized_profit": net_liquidation_value - total_cost,
            "realized_profit": realized_profit,
            "realized_count": realized_count,
        }

    async def add_portfolio_item(self, item_id: int, quantity: int, buy_price_per_item: int) -> int:
        if not self.db.conn: return 0
        cur = await self.db.conn.execute(
            "INSERT INTO portfolio (item_id, quantity, buy_price_per_item) VALUES (?, ?, ?)",
            (item_id, quantity, buy_price_per_item),
        )
        await self.db.conn.commit()
        return cur.lastrowid or 0

    async def delete_portfolio_item(self, port_id: int) -> bool:
        if not self.db.conn: return False
        cur = await self.db.conn.execute("DELETE FROM portfolio WHERE id = ?", (port_id,))
        await self.db.conn.commit()
        return (cur.rowcount or 0) > 0

    async def close_portfolio_item(
        self,
        port_id: int,
        sell_price_per_item: int,
        quantity_sold: int | None = None,
        notes: str | None = None,
    ) -> dict | None:
        if not self.db.conn:
            return None
        cur = await self.db.conn.execute("SELECT * FROM portfolio WHERE id = ?", (port_id,))
        row = await cur.fetchone()
        if not row:
            return None
        lot = dict(row)
        avail_qty = int(lot["quantity"])
        sold_qty = avail_qty if quantity_sold is None else min(max(1, int(quantity_sold)), avail_qty)
        buy_px = int(lot["buy_price_per_item"])
        sell_px = max(0, int(sell_price_per_item))
        tax_per = compute_ge_tax(sell_px)
        total_tax = tax_per * sold_qty
        net_profit = (sell_px - tax_per - buy_px) * sold_qty
        now = _now()

        cur_flip = await self.db.conn.execute(
            """INSERT INTO flip_history
               (item_id, quantity, buy_price, sell_price, tax_paid, net_profit, closed_at, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (lot["item_id"], sold_qty, buy_px, sell_px, total_tax, net_profit, now, notes),
        )
        flip_id = cur_flip.lastrowid or 0

        remaining = avail_qty - sold_qty
        if remaining <= 0:
            await self.db.conn.execute("DELETE FROM portfolio WHERE id = ?", (port_id,))
        else:
            await self.db.conn.execute(
                "UPDATE portfolio SET quantity = ? WHERE id = ?", (remaining, port_id)
            )
        await self.db.conn.commit()
        return {
            "flip_id": flip_id,
            "item_id": lot["item_id"],
            "quantity_sold": sold_qty,
            "remaining_quantity": remaining,
            "buy_price": buy_px,
            "sell_price": sell_px,
            "tax_paid": total_tax,
            "net_profit": net_profit,
            "closed_at": now,
        }

    async def add_flip_history(
        self,
        item_id: int,
        quantity: int,
        buy_price: int,
        sell_price: int,
        notes: str | None = None,
    ) -> dict:
        if not self.db.conn:
            return {}
        qty = max(1, int(quantity))
        b_px = max(0, int(buy_price))
        s_px = max(0, int(sell_price))
        tax_per = compute_ge_tax(s_px)
        total_tax = tax_per * qty
        net_profit = (s_px - tax_per - b_px) * qty
        now = _now()
        cur = await self.db.conn.execute(
            """INSERT INTO flip_history
               (item_id, quantity, buy_price, sell_price, tax_paid, net_profit, closed_at, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, qty, b_px, s_px, total_tax, net_profit, now, notes),
        )
        await self.db.conn.commit()
        return {
            "id": cur.lastrowid or 0,
            "item_id": item_id,
            "quantity": qty,
            "buy_price": b_px,
            "sell_price": s_px,
            "tax_paid": total_tax,
            "net_profit": net_profit,
            "closed_at": now,
            "notes": notes,
        }

    async def get_flip_history(self, limit: int = 100) -> dict:
        if not self.db.conn:
            return {
                "flips": [],
                "total_realized_profit": 0,
                "total_tax_paid": 0,
                "trades_count": 0,
                "win_rate_pct": 0.0,
            }
        cur = await self.db.conn.execute(
            """SELECT f.*, i.name, i.icon
               FROM flip_history f
               LEFT JOIN items i ON f.item_id = i.item_id
               ORDER BY f.closed_at DESC, f.id DESC
               LIMIT ?""",
            (limit,),
        )
        flips = []
        for r in await cur.fetchall():
            d = dict(r)
            cost = d["buy_price"] * d["quantity"]
            d["roi_pct"] = round((d["net_profit"] / cost) * 100, 2) if cost > 0 else 0.0
            flips.append(d)

        cur_agg = await self.db.conn.execute(
            """SELECT COALESCE(SUM(net_profit), 0) AS total_profit,
                      COALESCE(SUM(tax_paid), 0) AS total_tax,
                      COUNT(*) AS cnt,
                      SUM(CASE WHEN net_profit > 0 THEN 1 ELSE 0 END) AS wins
               FROM flip_history"""
        )
        agg = await cur_agg.fetchone()
        cnt = int(agg["cnt"] or 0) if agg else 0
        wins = int(agg["wins"] or 0) if agg else 0
        win_rate = round((wins / cnt) * 100, 1) if cnt > 0 else 0.0
        return {
            "flips": flips,
            "total_realized_profit": int(agg["total_profit"] or 0) if agg else 0,
            "total_tax_paid": int(agg["total_tax"] or 0) if agg else 0,
            "trades_count": cnt,
            "win_rate_pct": win_rate,
        }

    async def delete_flip_history(self, flip_id: int) -> bool:
        if not self.db.conn:
            return False
        cur = await self.db.conn.execute("DELETE FROM flip_history WHERE id = ?", (flip_id,))
        await self.db.conn.commit()
        return (cur.rowcount or 0) > 0


    async def get_ge_slots(self) -> list[dict]:
        if not self.db.conn:
            return []
        cur = await self.db.conn.execute(
            """SELECT s.*, i.name, i.icon, i.buy_limit,
                      l.high AS market_buy, l.low AS market_sell
               FROM ge_slots s
               LEFT JOIN items i ON s.item_id = i.item_id
               LEFT JOIN latest_prices l ON s.item_id = l.item_id
               ORDER BY s.slot_index ASC"""
        )
        rows = {r["slot_index"]: dict(r) for r in await cur.fetchall()}
        now = _now()
        slots = []
        for idx in range(1, 9):
            row = rows.get(idx)
            if not row:
                slots.append({
                    "slot_index": idx,
                    "empty": True,
                })
                continue
            lim_start = row.get("limit_started_at") or row.get("started_at") or now
            limit_reset_at = lim_start + 4 * 3600
            remaining_sec = max(0, limit_reset_at - now)
            slots.append({
                "slot_index": idx,
                "empty": False,
                "item_id": row["item_id"],
                "name": row.get("name") or f"Item {row['item_id']}",
                "icon": row.get("icon"),
                "buy_limit": row.get("buy_limit"),
                "offer_type": row["offer_type"],
                "target_price": row["target_price"],
                "buy_cost_ref": row.get("buy_cost_ref"),
                "quantity": row["quantity"],
                "filled_qty": row["filled_qty"],
                "started_at": row["started_at"],
                "limit_started_at": lim_start,
                "limit_reset_at": limit_reset_at,
                "limit_remaining_seconds": remaining_sec,
                "alerted_reset": bool(row.get("alerted_reset")),
                "market_buy": row.get("market_buy"),
                "market_sell": row.get("market_sell"),
                "notes": row.get("notes"),
            })
        return slots

    async def upsert_ge_slot(
        self,
        slot_index: int,
        item_id: int,
        offer_type: str,
        target_price: int,
        quantity: int,
        filled_qty: int = 0,
        buy_cost_ref: int | None = None,
        reset_timer: bool = True,
        notes: str | None = None,
    ) -> dict:
        if not self.db.conn:
            return {}
        now = _now()
        cur_existing = await self.db.conn.execute(
            "SELECT * FROM ge_slots WHERE slot_index = ?", (slot_index,)
        )
        existing = await cur_existing.fetchone()
        started_at = now if (not existing or reset_timer) else existing["started_at"]
        limit_started_at = now if (not existing or reset_timer) else (existing["limit_started_at"] or now)
        alerted = 0 if (not existing or reset_timer) else existing["alerted_reset"]

        await self.db.conn.execute(
            """INSERT INTO ge_slots
               (slot_index, item_id, offer_type, target_price, buy_cost_ref, quantity,
                filled_qty, started_at, limit_started_at, alerted_reset, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(slot_index) DO UPDATE SET
                 item_id=excluded.item_id,
                 offer_type=excluded.offer_type,
                 target_price=excluded.target_price,
                 buy_cost_ref=excluded.buy_cost_ref,
                 quantity=excluded.quantity,
                 filled_qty=excluded.filled_qty,
                 started_at=excluded.started_at,
                 limit_started_at=excluded.limit_started_at,
                 alerted_reset=excluded.alerted_reset,
                 notes=excluded.notes""",
            (
                slot_index,
                item_id,
                offer_type if offer_type in ("buy", "sell") else "buy",
                max(0, int(target_price)),
                buy_cost_ref,
                max(1, int(quantity)),
                max(0, int(filled_qty)),
                started_at,
                limit_started_at,
                alerted,
                notes,
            ),
        )
        await self.db.conn.commit()
        slots = await self.get_ge_slots()
        return next((s for s in slots if s["slot_index"] == slot_index), {})

    async def mark_ge_slot_alerted(self, slot_index: int) -> None:
        if not self.db.conn:
            return
        await self.db.conn.execute(
            "UPDATE ge_slots SET alerted_reset = 1 WHERE slot_index = ?", (slot_index,)
        )
        await self.db.conn.commit()

    async def clear_ge_slot(self, slot_index: int) -> bool:
        if not self.db.conn:
            return False
        cur = await self.db.conn.execute("DELETE FROM ge_slots WHERE slot_index = ?", (slot_index,))
        await self.db.conn.commit()
        return (cur.rowcount or 0) > 0


    async def get_recipes(self) -> list[dict]:
        if not self.db.conn: return []
        cur_recipes = await self.db.conn.execute(
            """SELECT r.*, i.name as output_name, i.icon as output_icon,
                      i.description as output_description, i.members as output_members,
                      i.buy_limit as output_buy_limit, i.highalch as output_highalch,
                      l.low as output_sell_price, l.high as output_buy_price
               FROM recipes r
               JOIN items i ON r.output_item_id = i.item_id
               LEFT JOIN latest_prices l ON r.output_item_id = l.item_id
               ORDER BY r.id DESC"""
        )
        recipes_rows = [dict(r) for r in await cur_recipes.fetchall()]

        cur_ingredients = await self.db.conn.execute(
            """SELECT ri.*, i.name, i.icon, i.description, i.members,
                      i.buy_limit, i.highalch, l.high as input_buy_price, l.low as input_sell_price
               FROM recipe_ingredients ri
               JOIN items i ON ri.item_id = i.item_id
               LEFT JOIN latest_prices l ON ri.item_id = l.item_id"""
        )
        ingredients_rows = [dict(r) for r in await cur_ingredients.fetchall()]

        ings_by_recipe: dict[int, list[dict]] = {}
        for ing in ingredients_rows:
            rid = ing["recipe_id"]
            if rid not in ings_by_recipe:
                ings_by_recipe[rid] = []
            ings_by_recipe[rid].append(ing)

        out = []
        for r in recipes_rows:
            rid = r["id"]
            ings = ings_by_recipe.get(rid, [])
            out_qty = int(r["output_qty"] or 1)

            cost_instant = sum(
                ing["qty"] * (ing["input_buy_price"] or ing["input_sell_price"] or 0)
                for ing in ings
            )
            out_unit_instant = int(r["output_sell_price"] or r["output_buy_price"] or 0)
            tax_unit_instant = compute_ge_tax(out_unit_instant)
            revenue_instant = out_qty * out_unit_instant
            tax_instant = out_qty * tax_unit_instant
            profit_instant = revenue_instant - tax_instant - cost_instant

            cost_patient = sum(
                ing["qty"] * (ing["input_sell_price"] or ing["input_buy_price"] or 0)
                for ing in ings
            )
            out_unit_patient = int(r["output_buy_price"] or r["output_sell_price"] or 0)
            tax_unit_patient = compute_ge_tax(out_unit_patient)
            revenue_patient = out_qty * out_unit_patient
            tax_patient = out_qty * tax_unit_patient
            profit_patient = revenue_patient - tax_patient - cost_patient

            bottleneck_crafts = None
            for ing in ings:
                lim = ing.get("buy_limit")
                q = ing.get("qty") or 1
                if lim and lim > 0:
                    crafts = lim // q
                    if bottleneck_crafts is None or crafts < bottleneck_crafts:
                        bottleneck_crafts = crafts

            out.append({
                "id": rid,
                "name": r["name"],
                "output_item_id": r["output_item_id"],
                "output_name": r["output_name"],
                "output_icon": r["output_icon"],
                "output_description": r.get("output_description"),
                "output_members": bool(r.get("output_members")),
                "output_buy_limit": r.get("output_buy_limit"),
                "output_highalch": r.get("output_highalch"),
                "output_qty": out_qty,
                "output_sell_price": r["output_sell_price"],
                "output_buy_price": r.get("output_buy_price"),
                "cost": cost_instant,
                "revenue": revenue_instant,
                "tax": tax_instant,
                "profit": profit_instant,
                "patient_cost": cost_patient,
                "patient_revenue": revenue_patient,
                "patient_tax": tax_patient,
                "patient_profit": profit_patient,
                "max_crafts_4h": bottleneck_crafts,
                "limit_profit_instant_4h": (profit_instant * bottleneck_crafts) if bottleneck_crafts else None,
                "limit_profit_patient_4h": (profit_patient * bottleneck_crafts) if bottleneck_crafts else None,
                "ingredients": ings,
            })
        return out

    async def create_recipe(self, name: str, output_item_id: int, output_qty: int,
                            ingredients: list[dict]) -> int:
        if not self.db.conn: return 0
        cur = await self.db.conn.execute(
            "INSERT INTO recipes (name, output_item_id, output_qty) VALUES (?, ?, ?)",
            (name, output_item_id, output_qty),
        )
        recipe_id = cur.lastrowid or 0
        for ing in ingredients:
            await self.db.conn.execute(
                "INSERT INTO recipe_ingredients (recipe_id, item_id, qty) VALUES (?, ?, ?)",
                (recipe_id, ing["item_id"], ing["qty"]),
            )
        await self.db.conn.commit()
        return recipe_id

    async def delete_recipe(self, recipe_id: int) -> bool:
        if not self.db.conn: return False
        cur = await self.db.conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        await self.db.conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
        await self.db.conn.commit()
        return (cur.rowcount or 0) > 0


    async def _get_item_mid_price(self, item_id: int, fallback_name: str, default_price: int) -> int:
        if not self.db.conn:
            return default_price
        cur = await self.db.conn.execute(
            """SELECT l.high, l.low FROM latest_prices l
               LEFT JOIN items i USING (item_id)
               WHERE l.item_id = ? OR LOWER(i.name) = ?
               LIMIT 1""",
            (item_id, fallback_name.lower()),
        )
        row = await cur.fetchone()
        if row:
            high, low = row["high"], row["low"]
            if high and low:
                return round((high + low) / 2)
            return high or low or default_price
        return default_price

    async def get_nature_rune_price(self) -> int:
        return await self._get_item_mid_price(561, "nature rune", 350)

    async def get_fire_rune_price(self) -> int:
        return await self._get_item_mid_price(554, "fire rune", 60)

    async def get_divine_charge_price(self) -> int:
        return await self._get_item_mid_price(36390, "divine charge", 85000)

    async def _latest_history_ts(self) -> int:
        if not self.db.conn:
            return _now()
        cur = await self.db.conn.execute("SELECT MAX(timestamp) FROM price_history")
        row = await cur.fetchone()
        return int(row[0]) if row and row[0] else _now()

    async def scan_flips(
        self,
        min_price: int = 100,
        max_price: int | None = None,
        min_volume: int = 0,
        members: bool | None = None,
        limit: int = 50,
        sort_by: str = "limit_profit",
    ) -> list[dict]:
        if not self.db.conn:
            return []
        since_24h = (await self._latest_history_ts()) - 86400
        vol_map = await self.volume_since(since_24h)
        has_vol = len(vol_map) > 50

        sql = """
            SELECT i.item_id, i.name, i.icon, i.description, i.members,
                   i.buy_limit, i.highalch, l.high, l.low, l.high_time, l.low_time, l.fetched_at
            FROM latest_prices l
            JOIN items i ON l.item_id = i.item_id
            WHERE l.high IS NOT NULL AND l.low IS NOT NULL
              AND l.high > l.low AND l.low >= ?
        """
        params: list[Any] = [min_price]
        if max_price is not None and max_price > 0:
            sql += " AND l.low <= ?"
            params.append(max_price)
        if members is not None:
            sql += " AND i.members = ?"
            params.append(1 if members else 0)

        cur = await self.db.conn.execute(sql, params)
        rows = await cur.fetchall()

        results = []
        for r in rows:
            iid = r["item_id"]
            vol = vol_map.get(iid, 0)
            if has_vol and min_volume > 0 and vol < min_volume:
                continue
            ht, lt = r["high_time"], r["low_time"]
            if ht and lt and abs(int(ht) - int(lt)) > 86400:
                continue
            sell_target = int(r["high"])
            buy_offer = int(r["low"])
            margin = sell_target - buy_offer
            tax = compute_ge_tax(sell_target)
            net_profit = margin - tax
            if net_profit <= 0:
                continue
            roi = round((net_profit / buy_offer) * 100, 2) if buy_offer > 0 else 0.0
            if roi > 60.0:
                continue
            buy_limit = r["buy_limit"] or 1
            limit_profit = net_profit * buy_limit
            liq = compute_liquidity_metrics(buy_limit, int(vol))
            results.append({
                "item_id": iid,
                "name": r["name"],
                "icon": r["icon"],
                "description": r["description"],
                "members": bool(r["members"]),
                "buy_limit": r["buy_limit"],
                "highalch": r["highalch"],
                "buy_price": sell_target,
                "sell_price": buy_offer,
                "margin": margin,
                "tax": tax,
                "net_profit": net_profit,
                "roi_pct": roi,
                "limit_profit_4h": limit_profit,
                "volume_24h": int(vol),
                **liq,
                "last_updated": r["fetched_at"],
            })

        sort_keys = {
            "limit_profit": lambda x: x["limit_profit_4h"],
            "net_profit": lambda x: x["net_profit"],
            "roi": lambda x: x["roi_pct"],
            "volume": lambda x: x["volume_24h"],
            "liquidity": lambda x: (x["liquidity_score"], x["limit_profit_4h"]),
        }
        key_fn = sort_keys.get(sort_by, sort_keys["limit_profit"])
        results.sort(key=key_fn, reverse=True)
        return results[:limit]

    async def scan_alchemy(
        self,
        min_volume: int = 0,
        members: bool | None = None,
        limit: int = 50,
        sort_by: str = "limit_profit",
        mode: str = "manual",
    ) -> dict[str, Any]:
        nat_price = await self.get_nature_rune_price()
        fire_price = await self.get_fire_rune_price()
        div_charge_price = await self.get_divine_charge_price()
        machine_charge_per_alch = round(div_charge_price / 187.5)
        cast_cost = (
            nat_price + 5 * fire_price + machine_charge_per_alch
            if mode == "machine"
            else nat_price
        )

        if not self.db.conn:
            return {
                "mode": mode,
                "nature_rune_price": nat_price,
                "fire_rune_price": fire_price,
                "divine_charge_price": div_charge_price,
                "cast_cost": cast_cost,
                "items": [],
            }

        since_24h = (await self._latest_history_ts()) - 86400
        vol_map = await self.volume_since(since_24h)
        has_vol = len(vol_map) > 50

        sql = """
            SELECT i.item_id, i.name, i.icon, i.description, i.members,
                   i.buy_limit, i.highalch, l.high, l.low, l.fetched_at
            FROM items i
            JOIN latest_prices l ON i.item_id = l.item_id
            WHERE i.highalch IS NOT NULL AND i.highalch > 0
              AND (l.low IS NOT NULL OR l.high IS NOT NULL)
        """
        params: list[Any] = []
        if members is not None:
            sql += " AND i.members = ?"
            params.append(1 if members else 0)

        cur = await self.db.conn.execute(sql, params)
        rows = await cur.fetchall()

        results = []
        for r in rows:
            iid = r["item_id"]
            vol = vol_map.get(iid, 0)
            if has_vol and min_volume > 0 and vol < min_volume:
                continue
            buy_cost = int(r["low"] or r["high"] or 0)
            if buy_cost <= 0:
                continue
            alch_val = int(r["highalch"])
            total_cost = buy_cost + cast_cost
            net_profit = alch_val - total_cost
            if net_profit <= -500:
                continue
            roi = round((net_profit / total_cost) * 100, 2) if total_cost > 0 else 0.0
            buy_limit = r["buy_limit"] or 1
            limit_profit = net_profit * buy_limit
            machine_24h_profit = net_profit * 600
            liq = compute_liquidity_metrics(buy_limit, int(vol))
            results.append({
                "item_id": iid,
                "name": r["name"],
                "icon": r["icon"],
                "description": r["description"],
                "members": bool(r["members"]),
                "buy_limit": r["buy_limit"],
                "highalch": alch_val,
                "buy_price": int(r["high"] or buy_cost),
                "sell_price": int(r["low"] or buy_cost),
                "nature_rune_price": nat_price,
                "cast_cost": cast_cost,
                "net_profit": net_profit,
                "roi_pct": roi,
                "limit_profit_4h": limit_profit,
                "machine_profit_24h": machine_24h_profit,
                "volume_24h": int(vol),
                **liq,
                "last_updated": r["fetched_at"],
            })

        sort_keys = {
            "limit_profit": (
                (lambda x: x["machine_profit_24h"])
                if mode == "machine"
                else (lambda x: x["limit_profit_4h"])
            ),
            "net_profit": lambda x: x["net_profit"],
            "roi": lambda x: x["roi_pct"],
            "volume": lambda x: x["volume_24h"],
            "liquidity": lambda x: (x["liquidity_score"], x["limit_profit_4h"]),
        }
        key_fn = sort_keys.get(sort_by, sort_keys["limit_profit"])
        results.sort(key=key_fn, reverse=True)
        return {
            "mode": mode,
            "nature_rune_price": nat_price,
            "fire_rune_price": fire_price,
            "divine_charge_price": div_charge_price,
            "cast_cost": cast_cost,
            "items": results[:limit],
        }

    async def scan_crafting_arbitrage(
        self,
        execution_mode: str = "patient",
        min_volume: int = 0,
        limit: int = 50,
        sort_by: str = "limit_profit",
    ) -> list[dict]:
        if not self.db.conn:
            return []
        catalog = _load_recipe_catalog()
        if not catalog:
            return []

        since_24h = (await self._latest_history_ts()) - 86400
        vol_map = await self.volume_since(since_24h)
        has_vol = len(vol_map) > 50

        all_latest = await self.get_all_latest()
        if not all_latest:
            return []

        relevant_ids: set[int] = set()
        for out_id, ings in catalog.items():
            if out_id not in all_latest:
                continue
            if all(ing["item_id"] in all_latest for ing in ings):
                relevant_ids.add(out_id)
                for ing in ings:
                    relevant_ids.add(ing["item_id"])

        if not relevant_ids:
            return []

        items_map = await self.get_items(relevant_ids)
        results = []

        for out_id, ings in catalog.items():
            if out_id not in items_map or out_id not in all_latest:
                continue
            out_item = items_map[out_id]
            out_lp = all_latest[out_id]
            vol = vol_map.get(out_id, 0)
            if has_vol and min_volume > 0 and vol < min_volume:
                continue

            if execution_mode == "instant":
                out_sell = int(out_lp.get("low") or out_lp.get("high") or 0)
            else:
                out_sell = int(out_lp.get("high") or out_lp.get("low") or 0)

            if out_sell <= 0:
                continue

            total_cost = 0
            valid = True
            ing_details = []
            bottleneck_crafts: int | None = None

            for ing in ings:
                iid = ing["item_id"]
                qty = ing["qty"]
                ing_meta = items_map.get(iid)
                ing_lp = all_latest.get(iid)
                if not ing_meta or not ing_lp:
                    valid = False
                    break
                if execution_mode == "instant":
                    unit_cost = int(ing_lp.get("high") or ing_lp.get("low") or 0)
                else:
                    unit_cost = int(ing_lp.get("low") or ing_lp.get("high") or 0)
                if unit_cost <= 0:
                    valid = False
                    break
                total_cost += unit_cost * qty
                lim = ing_meta.get("buy_limit")
                if lim and lim > 0:
                    crafts = max(1, lim // qty)
                    if bottleneck_crafts is None or crafts < bottleneck_crafts:
                        bottleneck_crafts = crafts
                ing_details.append({
                    "item_id": iid,
                    "name": ing_meta["name"],
                    "icon": ing_meta.get("icon"),
                    "qty": qty,
                    "unit_cost": unit_cost,
                    "buy_limit": lim,
                })

            if not valid or total_cost <= 0:
                continue

            tax = compute_ge_tax(out_sell)
            net_profit = out_sell - tax - total_cost
            if net_profit <= 0:
                continue
            roi_pct = round((net_profit / total_cost) * 100, 2)
            if roi_pct > 150.0:
                continue

            crafts_4h = bottleneck_crafts or out_item.get("buy_limit") or 100
            limit_profit_4h = net_profit * crafts_4h
            liq = compute_liquidity_metrics(crafts_4h, int(vol))

            results.append({
                "output_item_id": out_id,
                "name": out_item["name"],
                "icon": out_item.get("icon"),
                "description": out_item.get("description"),
                "members": bool(out_item.get("members")),
                "buy_limit": out_item.get("buy_limit"),
                "output_price": out_sell,
                "total_cost": total_cost,
                "tax": tax,
                "net_profit": net_profit,
                "roi_pct": roi_pct,
                "max_crafts_4h": crafts_4h,
                "limit_profit_4h": limit_profit_4h,
                "volume_24h": int(vol),
                **liq,
                "execution_mode": execution_mode,
                "ingredients": ing_details,
            })

        sort_keys = {
            "limit_profit": lambda x: x["limit_profit_4h"],
            "net_profit": lambda x: x["net_profit"],
            "roi": lambda x: x["roi_pct"],
            "volume": lambda x: x["volume_24h"],
            "liquidity": lambda x: (x["liquidity_score"], x["limit_profit_4h"]),
        }
        key_fn = sort_keys.get(sort_by, sort_keys["limit_profit"])
        results.sort(key=key_fn, reverse=True)
        return results[:limit]


    async def export_workspace(self) -> dict[str, Any]:
        if not self.db.conn:
            return {}
        cur_tracked = await self.db.conn.execute("SELECT * FROM tracked_items")
        cur_port = await self.db.conn.execute("SELECT * FROM portfolio")
        cur_flips = await self.db.conn.execute("SELECT * FROM flip_history")
        cur_slots = await self.db.conn.execute("SELECT * FROM ge_slots")
        cur_alerts = await self.db.conn.execute("SELECT * FROM alerts")
        cur_recipes = await self.db.conn.execute("SELECT * FROM recipes")
        cur_ing = await self.db.conn.execute("SELECT * FROM recipe_ingredients")
        cur_settings = await self.db.conn.execute("SELECT * FROM settings")

        return {
            "version": "1.3.0",
            "exported_at": _now(),
            "tracked_items": [dict(r) for r in await cur_tracked.fetchall()],
            "portfolio": [dict(r) for r in await cur_port.fetchall()],
            "flip_history": [dict(r) for r in await cur_flips.fetchall()],
            "ge_slots": [dict(r) for r in await cur_slots.fetchall()],
            "alerts": [dict(r) for r in await cur_alerts.fetchall()],
            "recipes": [dict(r) for r in await cur_recipes.fetchall()],
            "recipe_ingredients": [dict(r) for r in await cur_ing.fetchall()],
            "settings": {r["key"]: r["value"] for r in await cur_settings.fetchall()},
        }

    async def import_workspace(self, payload: dict[str, Any]) -> dict[str, int]:
        if not self.db.conn:
            return {}
        counts = {
            "tracked_items": 0,
            "portfolio": 0,
            "flip_history": 0,
            "ge_slots": 0,
            "alerts": 0,
            "recipes": 0,
        }
        now = _now()

        for t in payload.get("tracked_items", []):
            if isinstance(t, dict) and t.get("item_id"):
                await self.db.conn.execute(
                    """INSERT INTO tracked_items (item_id, added_at, favorite, backfilled, group_name)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(item_id) DO UPDATE SET
                         favorite=excluded.favorite,
                         group_name=excluded.group_name""",
                    (
                        int(t["item_id"]),
                        int(t.get("added_at") or now),
                        1 if t.get("favorite") else 0,
                        1 if t.get("backfilled") else 0,
                        str(t.get("group_name") or "Default"),
                    ),
                )
                counts["tracked_items"] += 1

        if "portfolio" in payload and isinstance(payload["portfolio"], list):
            await self.db.conn.execute("DELETE FROM portfolio")
            for p in payload["portfolio"]:
                if isinstance(p, dict) and p.get("item_id"):
                    await self.db.conn.execute(
                        "INSERT INTO portfolio (item_id, quantity, buy_price_per_item) VALUES (?, ?, ?)",
                        (int(p["item_id"]), int(p.get("quantity", 1)), int(p.get("buy_price_per_item", 0))),
                    )
                    counts["portfolio"] += 1

        if "flip_history" in payload and isinstance(payload["flip_history"], list):
            await self.db.conn.execute("DELETE FROM flip_history")
            for f in payload["flip_history"]:
                if isinstance(f, dict) and f.get("item_id"):
                    await self.db.conn.execute(
                        """INSERT INTO flip_history
                           (item_id, quantity, buy_price, sell_price, tax_paid, net_profit, closed_at, notes)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            int(f["item_id"]),
                            int(f.get("quantity", 1)),
                            int(f.get("buy_price", 0)),
                            int(f.get("sell_price", 0)),
                            int(f.get("tax_paid", 0)),
                            int(f.get("net_profit", 0)),
                            int(f.get("closed_at") or now),
                            f.get("notes"),
                        ),
                    )
                    counts["flip_history"] += 1

        if "ge_slots" in payload and isinstance(payload["ge_slots"], list):
            await self.db.conn.execute("DELETE FROM ge_slots")
            for s in payload["ge_slots"]:
                if isinstance(s, dict) and s.get("slot_index") and s.get("item_id"):
                    await self.db.conn.execute(
                        """INSERT INTO ge_slots
                           (slot_index, item_id, offer_type, target_price, buy_cost_ref, quantity,
                            filled_qty, started_at, limit_started_at, alerted_reset, notes)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            int(s["slot_index"]),
                            int(s["item_id"]),
                            str(s.get("offer_type") or "buy"),
                            int(s.get("target_price", 0)),
                            s.get("buy_cost_ref"),
                            int(s.get("quantity", 1)),
                            int(s.get("filled_qty", 0)),
                            int(s.get("started_at") or now),
                            int(s.get("limit_started_at") or now),
                            1 if s.get("alerted_reset") else 0,
                            s.get("notes"),
                        ),
                    )
                    counts["ge_slots"] += 1

        if "alerts" in payload and isinstance(payload["alerts"], list):
            await self.db.conn.execute("DELETE FROM alerts")
            for a in payload["alerts"]:
                if isinstance(a, dict) and a.get("item_id"):
                    await self.db.conn.execute(
                        """INSERT INTO alerts
                           (item_id, condition, threshold_price, active, last_triggered, metric, cooldown_minutes)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            int(a["item_id"]),
                            str(a.get("condition") or ">"),
                            int(a.get("threshold_price", 0)),
                            1 if a.get("active", True) else 0,
                            a.get("last_triggered"),
                            str(a.get("metric") or "either"),
                            int(a.get("cooldown_minutes") or 0),
                        ),
                    )
                    counts["alerts"] += 1

        if "recipes" in payload and isinstance(payload["recipes"], list):
            await self.db.conn.execute("DELETE FROM recipes")
            await self.db.conn.execute("DELETE FROM recipe_ingredients")
            old_to_new_rid: dict[int, int] = {}
            for r in payload["recipes"]:
                if isinstance(r, dict) and r.get("output_item_id"):
                    cur_r = await self.db.conn.execute(
                        "INSERT INTO recipes (name, output_item_id, output_qty) VALUES (?, ?, ?)",
                        (str(r.get("name") or "Recipe"), int(r["output_item_id"]), int(r.get("output_qty", 1))),
                    )
                    if r.get("id") is not None and cur_r.lastrowid:
                        old_to_new_rid[int(r["id"])] = cur_r.lastrowid
                    counts["recipes"] += 1

            for ing in payload.get("recipe_ingredients", []):
                if isinstance(ing, dict) and ing.get("recipe_id") in old_to_new_rid:
                    await self.db.conn.execute(
                        "INSERT INTO recipe_ingredients (recipe_id, item_id, qty) VALUES (?, ?, ?)",
                        (old_to_new_rid[int(ing["recipe_id"])], int(ing["item_id"]), int(ing.get("qty", 1))),
                    )

        await self.db.conn.commit()
        return counts
