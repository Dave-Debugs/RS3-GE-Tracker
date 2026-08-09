"""Application configuration.

Static config lives here (paths, API constants). User-tunable settings
(update interval, theme, user agent, ...) are persisted in the SQLite
`settings` table and exposed via the settings API; defaults are below.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Paths -----------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATABASE_DIR = Path(os.environ.get("RS3_DB_DIR", PROJECT_ROOT / "database"))
DATABASE_PATH = Path(os.environ.get("RS3_DB_PATH", DATABASE_DIR / "rs3_tracker.db"))
LOG_DIR = Path(os.environ.get("RS3_LOG_DIR", PROJECT_ROOT / "logs"))

# --- RS3 real-time prices API (see docs/API.md) ----------------------------
API_BASE_URL = "https://prices.runescape.wiki/api/v2/rs"
DEFAULT_USER_AGENT = (
    "RS3-GE-Tracker/1.0 (personal price tracking app; "
    "https://github.com/local/rs3-price-tracker)"
)

# Politeness / robustness
MIN_REQUEST_INTERVAL_SECONDS = 1.0   # global throttle between API requests
REQUEST_TIMEOUT_SECONDS = 25
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_SECONDS = 2.0     # 2s, 4s, 8s

# Bucket sizes (seconds)
BUCKET_5M = 300
BUCKET_1H = 3600

# Incremental-sync catch-up caps per collection cycle (avoid hammering after
# long downtime; older gaps for tracked items are healed via /timeseries).
MAX_CATCHUP_5M_BUCKETS = 12
MAX_CATCHUP_1H_BUCKETS = 6

# Mapping refresh
MAPPING_REFRESH_SECONDS = 24 * 3600

# --- Retention -------------------------------------------------------------
# The UI is built around 14 days; retention is configurable internally.
RETENTION_DAYS = int(os.environ.get("RS3_RETENTION_DAYS", "14"))

# --- User-tunable defaults (persisted in DB `settings` table) --------------
DEFAULT_SETTINGS: dict[str, str] = {
    "update_interval_minutes": "5",           # 5|10|15|30|60
    "theme": "dark",                          # dark|light
    "default_chart_range": "24h",             # 1h|6h|24h|7d|14d
    "user_agent": DEFAULT_USER_AGENT,
    "collector_autostart": "true",            # start collector with backend
    "database_path": str(DATABASE_PATH),      # informational (read-only in UI)
}

ALLOWED_INTERVALS = {"5", "10", "15", "30", "60"}
ALLOWED_RANGES = {"1h", "6h", "24h", "7d", "14d"}
CHART_RANGE_SECONDS = {
    "1h": 3600,
    "6h": 6 * 3600,
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
    "14d": 14 * 24 * 3600,
}
