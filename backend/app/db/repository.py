"""All SQL lives here. Higher layers never write raw SQL."""
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

    # ------------------------------------------------------------------ items
    def upsert_items(self, items: Iterable[dict[str, Any]]) -> int:
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
        cur = self.db.conn.executemany(
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
        self.db.conn.commit()
        return cur.rowcount if cur.rowcount and cur.rowcount > 0 else len(rows)

    def item_count(self) -> int:
        return self.db.conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    def get_item(self, item_id: int) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM items WHERE item_id=?", (item_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_items(self, item_ids: Iterable[int]) -> dict[int, dict]:
        ids = list(item_ids)
        if not ids:
            return {}
        q = ",".join("?" * len(ids))
        rows = self.db.conn.execute(
            f"SELECT * FROM items WHERE item_id IN ({q})", ids
        ).fetchall()
        return {r["item_id"]: dict(r) for r in rows}

    def search_items(self, pattern: str, limit: int = 25) -> list[dict]:
        """LIKE search; fuzzy layer sits above in services.search."""
        rows = self.db.conn.execute(
            """SELECT * FROM items WHERE name LIKE ? COLLATE NOCASE
               ORDER BY CASE WHEN name LIKE ? COLLATE NOCASE THEN 0 ELSE 1 END,
                        LENGTH(name), name LIMIT ?""",
            (f"%{pattern}%", f"{pattern}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def all_item_names(self) -> list[tuple[int, str]]:
        rows = self.db.conn.execute("SELECT item_id, name FROM items").fetchall()
        return [(r["item_id"], r["name"]) for r in rows]

    # ---------------------------------------------------------------- prices
    def insert_price_rows(self, rows: list[dict[str, Any]]) -> tuple[int, int]:
        """Insert price rows, ignoring duplicates.

        Returns (inserted, skipped). Rows must have keys:
        item_id, timestamp, high_price, low_price, average_price, volume, source.
        """
        if not rows:
            return 0, 0
        now = _now()
        before = self.db.conn.execute(
            "SELECT COUNT(*) FROM price_history"
        ).fetchone()[0]
        self.db.conn.executemany(
            """INSERT OR IGNORE INTO price_history
               (item_id, timestamp, high_price, low_price, average_price,
                volume, source, created_at)
               VALUES (:item_id, :timestamp, :high_price, :low_price,
                       :average_price, :volume, :source, :created_at)""",
            [{**r, "created_at": now} for r in rows],
        )
        self.db.conn.commit()
        after = self.db.conn.execute(
            "SELECT COUNT(*) FROM price_history"
        ).fetchone()[0]
        inserted = after - before
        return inserted, len(rows) - inserted

    def get_price_history(
        self, item_id: int, since: int, until: int | None = None,
        sources: list[str] | None = None,
    ) -> list[dict]:
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
        return [dict(r) for r in self.db.conn.execute(sql, args).fetchall()]

    def delete_older_than(self, cutoff: int) -> int:
        cur = self.db.conn.execute(
            "DELETE FROM price_history WHERE timestamp < ?", (cutoff,)
        )
        self.db.conn.commit()
        return cur.rowcount

    def price_history_count(self) -> int:
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM price_history"
        ).fetchone()[0]

    def data_coverage_days(self) -> float:
        row = self.db.conn.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM price_history"
        ).fetchone()
        if not row or row[0] is None:
            return 0.0
        return round((row[1] - row[0]) / 86400, 1)

    def earliest_timestamp(self, item_id: int) -> int | None:
        row = self.db.conn.execute(
            "SELECT MIN(timestamp) FROM price_history WHERE item_id=?",
            (item_id,),
        ).fetchone()
        return row[0]

    # -------- market-wide snapshot queries (Top Movers), based on 1h data ---
    def avg_price_around(self, ts: int, window: int = 2 * 3600) -> dict[int, float]:
        """Average price per item in [ts-window, ts+window] from hourly rows."""
        rows = self.db.conn.execute(
            """SELECT item_id, AVG(average_price) AS p
               FROM price_history
               WHERE source='1h' AND timestamp BETWEEN ? AND ?
                     AND average_price IS NOT NULL
               GROUP BY item_id""",
            (ts - window, ts + window),
        ).fetchall()
        return {r["item_id"]: r["p"] for r in rows}

    def volume_since(self, since: int) -> dict[int, int]:
        rows = self.db.conn.execute(
            """SELECT item_id, SUM(volume) AS v FROM price_history
               WHERE source='1h' AND timestamp>=? GROUP BY item_id""",
            (since,),
        ).fetchall()
        return {r["item_id"]: r["v"] or 0 for r in rows}

    # -------------------------------------------------------------- latest
    def upsert_latest(self, data: dict[str, dict], fetched_at: int) -> None:
        rows = [
            (int(iid), d.get("high"), d.get("highTime"),
             d.get("low"), d.get("lowTime"), fetched_at)
            for iid, d in data.items()
            if isinstance(d, dict)
        ]
        self.db.conn.executemany(
            """INSERT INTO latest_prices (item_id, high, high_time, low,
                                          low_time, fetched_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(item_id) DO UPDATE SET
                 high=excluded.high, high_time=excluded.high_time,
                 low=excluded.low, low_time=excluded.low_time,
                 fetched_at=excluded.fetched_at""",
            rows,
        )
        self.db.conn.commit()

    def get_latest(self, item_ids: Iterable[int]) -> dict[int, dict]:
        ids = list(item_ids)
        if not ids:
            return {}
        q = ",".join("?" * len(ids))
        rows = self.db.conn.execute(
            f"SELECT * FROM latest_prices WHERE item_id IN ({q})", ids
        ).fetchall()
        return {r["item_id"]: dict(r) for r in rows}

    # ------------------------------------------------------------- tracked
    def add_tracked(self, item_id: int) -> bool:
        cur = self.db.conn.execute(
            "INSERT OR IGNORE INTO tracked_items (item_id, added_at, group_name) VALUES (?,?, 'Default')",
            (item_id, _now()),
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    def remove_tracked(self, item_id: int) -> bool:
        cur = self.db.conn.execute(
            "DELETE FROM tracked_items WHERE item_id=?", (item_id,)
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    def set_favorite(self, item_id: int, favorite: bool) -> None:
        self.db.conn.execute(
            "UPDATE tracked_items SET favorite=? WHERE item_id=?",
            (1 if favorite else 0, item_id),
        )
        self.db.conn.commit()

    def set_group(self, item_id: int, group_name: str) -> None:
        self.db.conn.execute(
            "UPDATE tracked_items SET group_name=? WHERE item_id=?",
            (group_name or 'Default', item_id),
        )
        self.db.conn.commit()

    def set_backfilled(self, item_id: int) -> None:
        self.db.conn.execute(
            "UPDATE tracked_items SET backfilled=1 WHERE item_id=?", (item_id,)
        )
        self.db.conn.commit()

    def tracked(self) -> list[dict]:
        rows = self.db.conn.execute(
            """SELECT t.*, i.name, i.icon, i.members, i.description
               FROM tracked_items t LEFT JOIN items i USING (item_id)
               ORDER BY t.group_name ASC, t.favorite DESC, i.name"""
        ).fetchall()
        return [dict(r) for r in rows]

    def tracked_ids(self) -> list[int]:
        rows = self.db.conn.execute(
            "SELECT item_id FROM tracked_items"
        ).fetchall()
        return [r["item_id"] for r in rows]

    def pending_backfill_ids(self) -> list[int]:
        rows = self.db.conn.execute(
            "SELECT item_id FROM tracked_items WHERE backfilled=0"
        ).fetchall()
        return [r["item_id"] for r in rows]

    # ------------------------------------------------------------ sync state
    def get_state(self, key: str, default: str | None = None) -> str | None:
        row = self.db.conn.execute(
            "SELECT value FROM sync_state WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        self.db.conn.execute(
            """INSERT INTO sync_state (key, value) VALUES (?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (key, value),
        )
        self.db.conn.commit()

    # -------------------------------------------------------------- settings
    def get_settings(self, defaults: dict[str, str]) -> dict[str, str]:
        rows = self.db.conn.execute("SELECT key, value FROM settings").fetchall()
        stored = {r["key"]: r["value"] for r in rows}
        return {**defaults, **stored}

    def set_setting(self, key: str, value: str) -> None:
        self.db.conn.execute(
            """INSERT INTO settings (key, value) VALUES (?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (key, value),
        )
        self.db.conn.commit()

    # -------------------------------------------------------- collection log
    def start_run(self) -> int:
        cur = self.db.conn.execute(
            "INSERT INTO collection_runs (started_at) VALUES (?)", (_now(),)
        )
        self.db.conn.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, ok: bool, inserted: int, skipped: int,
                   deleted: int, api_requests: int, error: str | None) -> None:
        self.db.conn.execute(
            """UPDATE collection_runs
               SET finished_at=?, ok=?, inserted=?, skipped=?, deleted=?,
                   api_requests=?, error=? WHERE id=?""",
            (_now(), 1 if ok else 0, inserted, skipped, deleted,
             api_requests, error, run_id),
        )
        self.db.conn.commit()

    def last_run(self) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM collection_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def last_successful_run(self) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM collection_runs WHERE ok=1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
