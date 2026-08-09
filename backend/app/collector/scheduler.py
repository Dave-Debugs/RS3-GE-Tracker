"""Async background scheduler that runs collection cycles at the configured
interval. Runs inside the FastAPI process (started from the lifespan hook) so
no separate service is needed; `scripts/run_collector.py` can also run it
standalone so collection continues while the dashboard is closed.
"""
from __future__ import annotations

import asyncio
import logging
import time

from ..config import DEFAULT_SETTINGS
from ..db.repository import Repository
from .collector import Collector

log = logging.getLogger(__name__)


class CollectorScheduler:
    def __init__(self, repo: Repository, collector: Collector):
        self.repo = repo
        self.collector = collector
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()
        self.last_cycle_at: float | None = None
        self.running = False

    @property
    def interval_seconds(self) -> int:
        settings = self.repo.get_settings(DEFAULT_SETTINGS)
        try:
            minutes = int(settings["update_interval_minutes"])
        except (KeyError, ValueError):
            minutes = 5
        return max(1, minutes) * 60

    @property
    def next_run_at(self) -> float | None:
        if not self.running or self.last_cycle_at is None:
            return None
        return self.last_cycle_at + self.interval_seconds

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.get_event_loop().create_task(self._loop())
            self.running = True
            log.info("Collector scheduler started (interval %ds)",
                     self.interval_seconds)

    async def stop(self) -> None:
        self.running = False
        self._stop.set()
        self._wake.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except asyncio.TimeoutError:
                self._task.cancel()
        log.info("Collector scheduler stopped")

    def trigger_now(self) -> None:
        self._wake.set()

    async def _loop(self) -> None:
        while not self._stop.is_set():
            self.last_cycle_at = time.time()
            try:
                # run_cycle is blocking (sqlite + httpx sync) -> thread pool
                await asyncio.to_thread(self.collector.run_cycle)
            except Exception:  # pragma: no cover - collector already logs
                log.exception("Scheduler cycle crashed")
            # Sleep until next interval, but wake early on trigger/stop.
            try:
                await asyncio.wait_for(self._wake.wait(),
                                       timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()
