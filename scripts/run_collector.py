"""Standalone background price collector."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.api_client.client import RS3PriceClient  # noqa: E402
from app.collector.collector import Collector  # noqa: E402
from app.config import DATABASE_PATH, DEFAULT_SETTINGS  # noqa: E402
from app.db.database import Database  # noqa: E402
from app.db.repository import Repository  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402


async def run() -> None:
    setup_logging()
    db = Database(DATABASE_PATH)
    await db.init_db()
    repo = Repository(db)
    settings = await repo.get_settings(DEFAULT_SETTINGS)
    client = RS3PriceClient(user_agent=settings["user_agent"])
    collector = Collector(repo, client)
    print(f"Collector running against {DATABASE_PATH}. Ctrl+C to stop.")
    try:
        while True:
            await collector.run_cycle()
            settings = await repo.get_settings(DEFAULT_SETTINGS)
            interval = max(1, int(settings.get("update_interval_minutes", "5"))) * 60
            await asyncio.sleep(interval)
    finally:
        await client.close()
        await db.close()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Collector stopped.")


if __name__ == "__main__":
    main()
