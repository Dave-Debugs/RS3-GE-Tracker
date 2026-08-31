from __future__ import annotations

import json
import time

import httpx
import pytest

from app.api_client.client import RS3PriceClient
from app.collector.collector import Collector
from app.db.database import Database
from app.db.repository import Repository

NOW = int(time.time())


def bucket(ts: int, size: int) -> int:
    return ts // size * size


class MockAPI:
    """Mock transport simulating the RS3 prices API (see docs/API.md)."""

    def __init__(self):
        self.fail_with: int | None = None   # HTTP status to force
        self.bad_json = False
        self.calls: list[str] = []
        self.mapping = [
            {"id": 4151, "name": "Abyssal whip", "examine": "A weapon from the Abyss.",
             "members": True, "limit": 100, "value": 120001, "highalch": 72000,
             "lowalch": 48000, "icon": "Abyssal whip.png"},
            {"id": 2, "name": "Cannonball", "examine": "Ammo for the Dwarf Cannon.",
             "members": True, "limit": 10000, "value": 5, "highalch": 3,
             "lowalch": 2, "icon": "Cannonball.png"},
            {"id": 1042, "name": "Blue partyhat", "examine": "A nice hat.",
             "members": False, "limit": 2, "value": 1, "highalch": 1,
             "lowalch": 1, "icon": "Blue partyhat.png"},
            {"id": 21787, "name": "Dragon scimitar", "examine": "A vicious curved sword.",
             "members": True, "limit": 100, "value": 60000, "highalch": 36000,
             "lowalch": 24000, "icon": "Dragon scimitar.png"},
        ]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        if self.fail_with:
            return httpx.Response(self.fail_with, text="forced failure")
        if self.bad_json:
            return httpx.Response(200, text="{not json!")
        path = request.url.path
        params = dict(request.url.params)
        if path.endswith("/mapping"):
            return httpx.Response(200, json=self.mapping)
        if path.endswith("/latest"):
            data = {"4151": {"high": 73604, "highTime": NOW - 60,
                             "low": 71549, "lowTime": NOW - 30},
                    "2": {"high": 800, "highTime": NOW - 10,
                          "low": 795, "lowTime": NOW - 20}}
            if "id" in params:
                data = {params["id"]: data.get(params["id"], {})}
            return httpx.Response(200, json={"data": data})
        if path.endswith("/5m") or path.endswith("/1h"):
            size = 300 if path.endswith("/5m") else 3600
            ts = int(params.get("timestamp", bucket(NOW, size) - size))
            return httpx.Response(200, json={
                "timestamp": ts,
                "data": {
                    "4151": {"avgHighPrice": 73000 + (ts % 1000),
                             "highPriceVolume": 20,
                             "avgLowPrice": 72000, "lowPriceVolume": 15},
                    "2": {"avgHighPrice": 801, "highPriceVolume": 5000,
                          "avgLowPrice": None, "lowPriceVolume": 0},
                    "notanid": {"avgHighPrice": 1, "highPriceVolume": 1,
                                "avgLowPrice": 1, "lowPriceVolume": 1},
                },
            })
        if path.endswith("/timeseries"):
            lookback = params.get("lookback")
            item_id = params.get("id")
            spans = {"24h": (86400, 300), "7d": (7 * 86400, 3600),
                     "30d": (30 * 86400, 21600)}
            span, step = spans.get(lookback, (86400, 300))
            points = []
            base = 70000 if item_id == "4151" else 800
            for i, ts in enumerate(range(bucket(NOW - span, step),
                                         bucket(NOW, step), step)):
                points.append({
                    "timestamp": ts,
                    "avgHighPrice": base + i * 3,
                    "avgLowPrice": base - 500 if i % 3 else None,
                    "highPriceVolume": 10, "lowPriceVolume": 5 if i % 3 else 0,
                })
            return httpx.Response(200, json={"data": points})
        return httpx.Response(404, text="not found")


@pytest.fixture
def mock_api() -> MockAPI:
    return MockAPI()


@pytest.fixture
async def client(mock_api) -> RS3PriceClient:
    c = RS3PriceClient(
        transport=httpx.MockTransport(mock_api.handler), min_interval=0
    )
    yield c
    await c.close()


@pytest.fixture
async def db(tmp_path) -> Database:
    d = Database(tmp_path / "test.db")
    await d.connect()
    yield d
    await d.close()


@pytest.fixture
def repo(db) -> Repository:
    return Repository(db)


@pytest.fixture
def collector(repo, client) -> Collector:
    return Collector(repo, client)


def make_points(start: int, step: int, prices: list[float],
                volume: int = 10, item_id: int = 0) -> list[dict]:
    return [
        {"item_id": item_id, "timestamp": start + i * step,
         "high_price": p + 50, "low_price": p - 50,
         "average_price": p, "volume": volume, "source": "5m"}
        for i, p in enumerate(prices)
    ]
