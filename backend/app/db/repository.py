from __future__ import annotations

import logging
import time
from typing import Any, Iterable

from .database import Database

log = logging.getLogger(__name__)

def _now() -> int:
    return int(time.time())

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
        q = ",".join("?" * len(ids))
        cur = await self.db.conn.execute(
            f"SELECT * FROM items WHERE item_id IN ({q})", ids
        )
        rows = await cur.fetchall()
        return {r["item_id"]: dict(r) for r in rows}

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
        cur_before = await self.db.conn.execute("SELECT COUNT(*) FROM price_history")
        row_before = await cur_before.fetchone()
        before = row_before[0] if row_before else 0

        await self.db.conn.executemany(
            """INSERT OR IGNORE INTO price_history
               (item_id, timestamp, high_price, low_price, average_price,
                volume, source, created_at)
               VALUES (:item_id, :timestamp, :high_price, :low_price,
                       :average_price, :volume, :source, :created_at)""",
            [{**r, "created_at": now} for r in rows],
        )
        await self.db.conn.commit()

        cur_after = await self.db.conn.execute("SELECT COUNT(*) FROM price_history")
        row_after = await cur_after.fetchone()
        after = row_after[0] if row_after else 0

        inserted = after - before
        return inserted, len(rows) - inserted

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

    async def delete_older_than(self, cutoff: int) -> int:
        if not self.db.conn: return 0
        cur = await self.db.conn.execute(
            "DELETE FROM price_history WHERE timestamp < ?", (cutoff,)
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
            if isinstance(d, dict)
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
        q = ",".join("?" * len(ids))
        cur = await self.db.conn.execute(
            f"SELECT * FROM latest_prices WHERE item_id IN ({q})", ids
        )
        rows = await cur.fetchall()
        return {r["item_id"]: dict(r) for r in rows}

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

    async def create_alert(self, item_id: int, condition: str, threshold_price: int) -> int:
        if not self.db.conn: return 0
        cur = await self.db.conn.execute(
            "INSERT INTO alerts (item_id, condition, threshold_price) VALUES (?, ?, ?)",
            (item_id, condition, threshold_price),
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

    async def trigger_alert(self, alert_id: int, triggered_at: int) -> bool:
        if not self.db.conn: return False
        cur = await self.db.conn.execute(
            "UPDATE alerts SET active = 0, last_triggered = ? WHERE id = ?",
            (triggered_at, alert_id),
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
            return {"items": [], "total_cost": 0, "current_value": 0, "unrealized_profit": 0}
        query = """
            SELECT p.id, p.item_id, p.quantity, p.buy_price_per_item,
                   i.name, i.icon,
                   l.high as current_price
            FROM portfolio p
            JOIN items i ON p.item_id = i.item_id
            LEFT JOIN latest_prices l ON p.item_id = l.item_id
            ORDER BY p.id DESC
        """
        cur = await self.db.conn.execute(query)
        items = [dict(r) for r in await cur.fetchall()]
        total_cost = sum(item["quantity"] * item["buy_price_per_item"] for item in items)
        current_value = sum(item["quantity"] * (item["current_price"] or item["buy_price_per_item"]) for item in items)
        return {
            "items": items,
            "total_cost": total_cost,
            "current_value": current_value,
            "unrealized_profit": current_value - total_cost,
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
            cost = sum(ing["qty"] * (ing["input_buy_price"] or 0) for ing in ings)
            revenue = r["output_qty"] * (r["output_sell_price"] or 0)
            profit = revenue - cost
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
                "output_qty": r["output_qty"],
                "output_sell_price": r["output_sell_price"],
                "output_buy_price": r.get("output_buy_price"),
                "cost": cost,
                "revenue": revenue,
                "profit": profit,
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
        await self.db.conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        await self.db.conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
        await self.db.conn.commit()
        return True

    async def get_nature_rune_price(self) -> int:
        if not self.db.conn:
            return 350
        cur = await self.db.conn.execute(
            """SELECT l.high, l.low FROM latest_prices l
               LEFT JOIN items i USING (item_id)
               WHERE l.item_id = 561 OR LOWER(i.name) = 'nature rune'
               LIMIT 1"""
        )
        row = await cur.fetchone()
        if row:
            high, low = row["high"], row["low"]
            if high and low:
                return round((high + low) / 2)
            return high or low or 350
        return 350

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
            tax = int(min(sell_target * 0.02, 50_000_000)) if sell_target >= 50 else 0
            net_profit = margin - tax
            if net_profit <= 0:
                continue
            roi = round((net_profit / buy_offer) * 100, 2) if buy_offer > 0 else 0.0
            if roi > 60.0:
                continue
            buy_limit = r["buy_limit"] or 1
            limit_profit = net_profit * buy_limit
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
                "last_updated": r["fetched_at"],
            })

        sort_keys = {
            "limit_profit": lambda x: x["limit_profit_4h"],
            "net_profit": lambda x: x["net_profit"],
            "roi": lambda x: x["roi_pct"],
            "volume": lambda x: x["volume_24h"],
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
    ) -> dict[str, Any]:
        nat_price = await self.get_nature_rune_price()
        if not self.db.conn:
            return {"nature_rune_price": nat_price, "items": []}

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
            total_cost = buy_cost + nat_price
            net_profit = alch_val - total_cost
            if net_profit <= -500:
                continue
            roi = round((net_profit / total_cost) * 100, 2) if total_cost > 0 else 0.0
            buy_limit = r["buy_limit"] or 1
            limit_profit = net_profit * buy_limit
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
                "net_profit": net_profit,
                "roi_pct": roi,
                "limit_profit_4h": limit_profit,
                "volume_24h": int(vol),
                "last_updated": r["fetched_at"],
            })

        sort_keys = {
            "limit_profit": lambda x: x["limit_profit_4h"],
            "net_profit": lambda x: x["net_profit"],
            "roi": lambda x: x["roi_pct"],
            "volume": lambda x: x["volume_24h"],
        }
        key_fn = sort_keys.get(sort_by, sort_keys["limit_profit"])
        results.sort(key=key_fn, reverse=True)
        return {"nature_rune_price": nat_price, "items": results[:limit]}
