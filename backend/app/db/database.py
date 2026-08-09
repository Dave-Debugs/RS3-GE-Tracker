"""SQLite connection management and schema.

SQLite is used in WAL mode so the background collector (writer) and the API
(readers) can work concurrently. All timestamps are Unix epoch seconds (UTC).
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

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
CREATE INDEX IF NOT EXISTS idx_price_item ON price_history(item_id);
CREATE INDEX IF NOT EXISTS idx_price_ts ON price_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_price_item_ts ON price_history(item_id, timestamp);

CREATE TABLE IF NOT EXISTS latest_prices (
    item_id    INTEGER PRIMARY KEY,
    high       INTEGER,
    high_time  INTEGER,
    low        INTEGER,
    low_time   INTEGER,
    fetched_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tracked_items (
    item_id  INTEGER PRIMARY KEY,
    added_at INTEGER NOT NULL,
    favorite INTEGER NOT NULL DEFAULT 0,
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
"""


class Database:
    """Thread-safe SQLite wrapper (one connection per thread)."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._local = threading.local()
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @property
    def conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        # Migration: Add group_name if missing
        cursor = self.conn.execute("PRAGMA table_info(tracked_items)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "group_name" not in columns:
            self.conn.execute("ALTER TABLE tracked_items ADD COLUMN group_name TEXT DEFAULT 'Default'")
            self.conn.commit()
        log.debug("Database schema ensured at %s", self.path)

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
