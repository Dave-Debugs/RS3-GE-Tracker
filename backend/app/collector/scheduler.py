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
        self._interval_seconds = 300

    async def update_interval(self) -> None:
        settings = await self.repo.get_settings(DEFAULT_SETTINGS)
        try:
            minutes = int(settings["update_interval_minutes"])
        except (KeyError, ValueError):
            minutes = 5
        self._interval_seconds = max(1, minutes) * 60

    @property
    def next_run_at(self) -> float | None:
        if not self.running or self.last_cycle_at is None:
            return None
        return self.last_cycle_at + self._interval_seconds

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.get_event_loop().create_task(self._loop())
            self.running = True
            log.info("Collector scheduler started")

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
                await self.collector.run_cycle()
            except Exception:
                log.exception("Scheduler cycle crashed")

            await self.update_interval()

            try:
                await asyncio.wait_for(self._wake.wait(),
                                       timeout=self._interval_seconds)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()
