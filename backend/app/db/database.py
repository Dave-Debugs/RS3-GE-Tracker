from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import aiosqlite

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    item_id      INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT,
    members      INTEGER NOT NULL DEFAULT 0,
    icon         TEXT,
    category     TEXT,
    buy_limit    INTEGER,
    value        INTEGER,
    highalch     INTEGER,
    lowalch      INTEGER,
    last_updated INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS price_history (
    item_id       INTEGER NOT NULL,
    timestamp     INTEGER NOT NULL,
    high_price    REAL,
    low_price     REAL,
    average_price REAL,
    volume        INTEGER NOT NULL DEFAULT 0,
    source        TEXT NOT NULL,
    created_at    INTEGER NOT NULL,
    PRIMARY KEY (item_id, timestamp, source)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_price_ts ON price_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_price_source_ts ON price_history(source, timestamp);
CREATE TABLE IF NOT EXISTS latest_prices (
    item_id    INTEGER PRIMARY KEY,
    high       INTEGER,
    high_time  INTEGER,
    low        INTEGER,
    low_time   INTEGER,
    fetched_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS tracked_items (
    item_id    INTEGER PRIMARY KEY,
    added_at   INTEGER NOT NULL,
    favorite   INTEGER NOT NULL DEFAULT 0,
    backfilled INTEGER NOT NULL DEFAULT 0,
    group_name TEXT DEFAULT 'Default'
);
CREATE TABLE IF NOT EXISTS sync_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collection_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at        INTEGER NOT NULL,
    finished_at       INTEGER,
    ok                INTEGER NOT NULL DEFAULT 0,
    inserted          INTEGER NOT NULL DEFAULT 0,
    skipped           INTEGER NOT NULL DEFAULT 0,
    deleted           INTEGER NOT NULL DEFAULT 0,
    api_requests      INTEGER NOT NULL DEFAULT 0,
    error             TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id          INTEGER NOT NULL,
    condition        TEXT NOT NULL,
    threshold_price  INTEGER NOT NULL,
    active           INTEGER NOT NULL DEFAULT 1,
    last_triggered   INTEGER,
    metric           TEXT NOT NULL DEFAULT 'either',
    cooldown_minutes INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS portfolio (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id            INTEGER NOT NULL,
    quantity           INTEGER NOT NULL DEFAULT 0,
    buy_price_per_item INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS flip_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     INTEGER NOT NULL,
    quantity    INTEGER NOT NULL DEFAULT 1,
    buy_price   INTEGER NOT NULL DEFAULT 0,
    sell_price  INTEGER NOT NULL DEFAULT 0,
    tax_paid    INTEGER NOT NULL DEFAULT 0,
    net_profit  INTEGER NOT NULL DEFAULT 0,
    closed_at   INTEGER NOT NULL,
    notes       TEXT
);
CREATE TABLE IF NOT EXISTS ge_slots (
    slot_index       INTEGER PRIMARY KEY CHECK(slot_index BETWEEN 1 AND 8),
    item_id          INTEGER NOT NULL,
    offer_type       TEXT NOT NULL DEFAULT 'buy',
    target_price     INTEGER NOT NULL DEFAULT 0,
    buy_cost_ref     INTEGER,
    quantity         INTEGER NOT NULL DEFAULT 1,
    filled_qty       INTEGER NOT NULL DEFAULT 0,
    started_at       INTEGER NOT NULL,
    limit_started_at INTEGER,
    alerted_reset    INTEGER NOT NULL DEFAULT 0,
    notes            TEXT
);
CREATE TABLE IF NOT EXISTS recipes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    output_item_id INTEGER NOT NULL,
    output_qty     INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    item_id   INTEGER NOT NULL,
    qty       INTEGER NOT NULL DEFAULT 1
);
"""


class Database:

    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: aiosqlite.Connection | None = None
        self.write_lock = asyncio.Lock()

    async def connect(self) -> None:
        if self.conn is None:
            self.conn = await aiosqlite.connect(self.path, timeout=30)
            self.conn.row_factory = aiosqlite.Row
            await self.conn.execute("PRAGMA journal_mode=WAL")
            await self.conn.execute("PRAGMA synchronous=NORMAL")
            await self.conn.execute("PRAGMA busy_timeout=30000")
            await self.conn.execute("PRAGMA foreign_keys=ON")
            await self.init_schema()

    async def init_schema(self) -> None:
        if not self.conn:
            return
        await self.conn.executescript(SCHEMA)
        await self.conn.execute("DROP INDEX IF EXISTS idx_price_item")
        await self.conn.execute("DROP INDEX IF EXISTS idx_price_item_ts")
        await self.conn.commit()

        cursor = await self.conn.execute("PRAGMA table_info(tracked_items)")
        rows = await cursor.fetchall()
        columns = [row["name"] for row in rows]
        if "group_name" not in columns:
            await self.conn.execute("ALTER TABLE tracked_items ADD COLUMN group_name TEXT DEFAULT 'Default'")
            await self.conn.commit()

        cursor_alerts = await self.conn.execute("PRAGMA table_info(alerts)")
        alert_cols = [row["name"] for row in await cursor_alerts.fetchall()]
        if "metric" not in alert_cols:
            await self.conn.execute("ALTER TABLE alerts ADD COLUMN metric TEXT NOT NULL DEFAULT 'either'")
        if "cooldown_minutes" not in alert_cols:
            await self.conn.execute("ALTER TABLE alerts ADD COLUMN cooldown_minutes INTEGER NOT NULL DEFAULT 0")
        await self.conn.commit()
        log.debug("Database schema ensured at %s", self.path)

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()
            self.conn = None
