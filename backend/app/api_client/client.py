"""HTTP client for the RS3 real-time prices API.

Responsibilities: throttling, retries with exponential backoff, timeout
handling, response validation, and a tiny in-memory TTL cache. See
docs/API.md for the verified endpoint contract.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx

from ..config import (
    API_BASE_URL,
    DEFAULT_USER_AGENT,
    MAX_RETRIES,
    MIN_REQUEST_INTERVAL_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    RETRY_BACKOFF_BASE_SECONDS,
)

log = logging.getLogger(__name__)


class ApiError(Exception):
    """Raised when the RS3 price API cannot be reached or returns bad data."""


class RS3PriceClient:
    def __init__(
        self,
        base_url: str = API_BASE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval: float = MIN_REQUEST_INTERVAL_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last_request = 0.0
        self._cache: dict[str, tuple[float, Any]] = {}
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=REQUEST_TIMEOUT_SECONDS,
            transport=transport,
        )
        self.request_count = 0

    # ------------------------------------------------------------------ core
    def _throttle(self) -> None:
        with self._lock:
            wait = self._last_request + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    def _get(self, path: str, params: dict | None = None,
             cache_ttl: float = 0.0) -> Any:
        url = f"{self.base_url}{path}"
        cache_key = f"{url}?{sorted((params or {}).items())}"
        if cache_ttl > 0:
            hit = self._cache.get(cache_key)
            if hit and time.monotonic() - hit[0] < cache_ttl:
                log.debug("cache hit %s", cache_key)
                return hit[1]

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt:
                backoff = RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                log.warning("Retrying %s in %.1fs (attempt %d/%d): %s",
                            path, backoff, attempt, MAX_RETRIES, last_error)
                time.sleep(backoff)
            self._throttle()
            self.request_count += 1
            try:
                resp = self._client.get(url, params=params)
                if resp.status_code == 429:
                    last_error = ApiError("rate limited (HTTP 429)")
                    continue
                if resp.status_code >= 500:
                    last_error = ApiError(f"server error (HTTP {resp.status_code})")
                    continue
                if resp.status_code != 200:
                    raise ApiError(
                        f"HTTP {resp.status_code} for {path}: {resp.text[:200]}"
                    )
                try:
                    data = resp.json()
                except ValueError as e:
                    raise ApiError(f"invalid JSON from {path}: {e}") from e
                if cache_ttl > 0:
                    self._cache[cache_key] = (time.monotonic(), data)
                log.debug("GET %s params=%s -> ok", path, params)
                return data
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_error = e
        raise ApiError(f"API request failed after retries: {path}: {last_error}")

    # ------------------------------------------------------------- endpoints
    def mapping(self) -> list[dict]:
        data = self._get("/mapping", cache_ttl=3600)
        if not isinstance(data, list):
            raise ApiError("mapping: expected a list")
        return data

    def latest(self, item_id: int | None = None) -> dict[str, dict]:
        params = {"id": item_id} if item_id else None
        data = self._get("/latest", params=params)
        payload = data.get("data") if isinstance(data, dict) else None
        if not isinstance(payload, dict):
            raise ApiError("latest: malformed response")
        return payload

    def five_minute(self, timestamp: int | None = None) -> tuple[int, dict[str, dict]]:
        params = {"timestamp": timestamp} if timestamp else None
        data = self._get("/5m", params=params)
        return self._bucket_response(data, "5m", timestamp)

    def one_hour(self, timestamp: int | None = None) -> tuple[int, dict[str, dict]]:
        params = {"timestamp": timestamp} if timestamp else None
        data = self._get("/1h", params=params)
        return self._bucket_response(data, "1h", timestamp)

    @staticmethod
    def _bucket_response(data: Any, name: str,
                         requested_ts: int | None) -> tuple[int, dict[str, dict]]:
        if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
            raise ApiError(f"{name}: malformed response")
        ts = data.get("timestamp") or requested_ts
        if not isinstance(ts, int):
            raise ApiError(f"{name}: missing bucket timestamp")
        return ts, data["data"]

    def timeseries(self, item_id: int, lookback: str) -> list[dict]:
        if lookback not in {"6h", "24h", "7d", "30d", "6m", "1y"}:
            raise ValueError(f"invalid lookback {lookback!r}")
        data = self._get("/timeseries", params={"id": item_id, "lookback": lookback})
        points = data.get("data") if isinstance(data, dict) else None
        if not isinstance(points, list):
            raise ApiError("timeseries: malformed response")
        return points

    def close(self) -> None:
        self._client.close()
