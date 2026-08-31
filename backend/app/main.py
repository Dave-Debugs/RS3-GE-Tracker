"""FastAPI application entry point.

Run with:  uvicorn app.main:app --port 8000   (from the backend/ directory)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import sys
import os

from .api_client.client import RS3PriceClient
from .collector.collector import Collector
from .collector.scheduler import CollectorScheduler
from .config import DATABASE_PATH, DEFAULT_SETTINGS
from .db.database import Database
from .db.repository import Repository
from .logging_config import setup_logging
from .routes import (
    export, icons, items, movers, prices, settings, stats, status, tracked, alerts, portfolio, recipes,
)

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    log.info("RS3 GE Tracker backend starting (db=%s)", DATABASE_PATH)

    db = Database(DATABASE_PATH)
    await db.connect()
    repo = Repository(db)
    app_settings = await repo.get_settings(DEFAULT_SETTINGS)
    client = RS3PriceClient(user_agent=app_settings["user_agent"])
    collector = Collector(repo, client)
    scheduler = CollectorScheduler(repo, collector)

    app.state.db = db
    app.state.repo = repo
    app.state.client = client
    app.state.collector = collector
    app.state.scheduler = scheduler

    if app_settings.get("collector_autostart", "true") == "true":
        scheduler.start()
    else:
        log.info("Collector autostart disabled in settings")

    yield

    log.info("RS3 GE Tracker backend shutting down")
    await scheduler.stop()
    await client.close()
    await db.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="RS3 Grand Exchange Tracker",
        version="0.5.5",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (items, tracked, prices, stats, movers, settings, status,
                   export, icons):
        app.include_router(module.router)
    app.include_router(alerts.router)
    app.include_router(portfolio.router)
    app.include_router(recipes.router)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    def get_frontend_dist() -> str:
        if getattr(sys, 'frozen', False):
            base_path = os.path.join(sys._MEIPASS, "frontend")
        else:
            base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend")
        return os.path.join(base_path, "dist")

    dist_dir = get_frontend_dist()
    if os.path.exists(dist_dir):
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")
    else:
        log.warning(f"Frontend dist not found at {dist_dir}. Serving API only.")

    return app


app = create_app()
