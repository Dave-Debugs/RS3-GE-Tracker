"""Standalone collector — keeps collecting prices while the dashboard is
closed. Safe to run alongside the backend (SQLite WAL + idempotent inserts),
but normally you run EITHER this OR the backend, not both.

Usage:  python scripts/run_collector.py   (from the project root)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.api_client.client import RS3PriceClient  # noqa: E402
from app.collector.collector import Collector  # noqa: E402
from app.config import DATABASE_PATH, DEFAULT_SETTINGS  # noqa: E402
from app.db.database import Database  # noqa: E402
from app.db.repository import Repository  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402


def main() -> None:
    setup_logging()
    db = Database(DATABASE_PATH)
    repo = Repository(db)
    settings = repo.get_settings(DEFAULT_SETTINGS)
    client = RS3PriceClient(user_agent=settings["user_agent"])
    collector = Collector(repo, client)
    print(f"Collector running against {DATABASE_PATH}. Ctrl+C to stop.")
    try:
        while True:
            collector.run_cycle()
            settings = repo.get_settings(DEFAULT_SETTINGS)
            interval = max(1, int(settings.get("update_interval_minutes", "5"))) * 60
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Collector stopped.")
    finally:
        client.close()
        db.close()


if __name__ == "__main__":
    main()
