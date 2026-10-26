from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "RS3 GE Tracker"
else:
    PROJECT_ROOT = BACKEND_DIR.parent
DATABASE_DIR = Path(os.environ.get("RS3_DB_DIR", PROJECT_ROOT / "database"))
DATABASE_PATH = Path(os.environ.get("RS3_DB_PATH", DATABASE_DIR / "rs3_tracker.db"))
LOG_DIR = Path(os.environ.get("RS3_LOG_DIR", PROJECT_ROOT / "logs"))

APP_VERSION = "1.3.0"
GITHUB_RELEASE_URLS = [
    "https://api.github.com/repos/Dave-Debugs/RS3-GE-Tracker/releases/latest",
    "https://api.github.com/repos/dave-debugs/rs3-ge-tracker/releases/latest",
]

API_BASE_URL = "https://prices.runescape.wiki/api/v2/rs"
DEFAULT_USER_AGENT = (
    "RS3-GE-Tracker/1.3 (personal price tracking app; "
    "https://github.com/Dave-Debugs/RS3-GE-Tracker)"
)

MIN_REQUEST_INTERVAL_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 25
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_SECONDS = 2.0

BUCKET_5M = 300
BUCKET_1H = 3600

MAX_CATCHUP_5M_BUCKETS = 12
MAX_CATCHUP_1H_BUCKETS = 6

MAPPING_REFRESH_SECONDS = 24 * 3600

RETENTION_DAYS = int(os.environ.get("RS3_RETENTION_DAYS", "35"))
LONG_RETENTION_DAYS = int(os.environ.get("RS3_LONG_RETENTION_DAYS", "370"))

DEFAULT_SETTINGS: dict[str, str] = {
    "update_interval_minutes": "5",
    "theme": "dark",
    "default_chart_range": "24h",
    "show_item_tooltips": "true",
    "user_agent": DEFAULT_USER_AGENT,
    "collector_autostart": "true",
    "discord_webhook_url": "",
    "database_path": str(DATABASE_PATH),
}

ALLOWED_INTERVALS = {"5", "10", "15", "30", "60"}
ALLOWED_RANGES = {"1h", "6h", "24h", "7d", "14d", "30d", "90d", "6m", "1y"}
CHART_RANGE_SECONDS = {
    "1h": 3600,
    "6h": 6 * 3600,
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
    "14d": 14 * 24 * 3600,
    "30d": 30 * 24 * 3600,
    "90d": 90 * 24 * 3600,
    "6m": 180 * 24 * 3600,
    "1y": 365 * 24 * 3600,
}
