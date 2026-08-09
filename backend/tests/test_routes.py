import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_points

NOW = int(time.time())


class DummyScheduler:
    running = True
    next_run_at = NOW + 300

    def __init__(self):
        self.triggered = False

    def trigger_now(self):
        self.triggered = True


@pytest.fixture
def api(repo, collector, mock_api):
    """TestClient wired to the mock API + temp DB (no real lifespan)."""
    collector.run_cycle()  # seed items/latest/1h data
    app = create_app()
    app.router.lifespan_context = None  # replaced below
    scheduler = DummyScheduler()
    app.state.repo = repo
    app.state.scheduler = scheduler

    # Bypass the production lifespan entirely
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(_app):
        yield

    app.router.lifespan_context = noop_lifespan
    with TestClient(app) as client:
        client.scheduler = scheduler
        yield client


def test_health(api):
    assert api.get("/api/health").json() == {"status": "ok"}


def test_search_route(api):
    r = api.get("/api/items/search", params={"q": "whip"})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["name"] == "Abyssal whip"
    assert results[0]["current_price"] is not None
    assert results[0]["icon_url"] == "/api/icon/4151"


def test_track_untrack_flow(api):
    r = api.post("/api/tracked", json={"item_id": 4151})
    assert r.status_code == 201 and r.json()["added"] is True
    assert api.scheduler.triggered is True
    r = api.get("/api/tracked")
    tracked = r.json()["tracked"]
    assert len(tracked) == 1 and tracked[0]["item_id"] == 4151
    assert "trend" in tracked[0] and "change_24h" in tracked[0]
    r = api.put("/api/tracked/4151/favorite", json={"favorite": True})
    assert r.json()["favorite"] is True
    r = api.delete("/api/tracked/4151")
    assert r.json()["removed"] is True
    assert api.delete("/api/tracked/4151").status_code == 404


def test_track_unknown_item_404(api):
    assert api.post("/api/tracked", json={"item_id": 999999}).status_code == 404


def test_prices_route_and_30day_filter(api, repo):
    # insert data older than the 30d window; it must not appear for range=30d
    repo.insert_price_rows(make_points(NOW - 60 * 86400, 3600, [1.0] * 5))
    repo.insert_price_rows([{**p, "item_id": 4151} for p in
                            make_points(NOW - 60 * 86400, 3600, [1.0] * 5)])
    r = api.get("/api/prices/4151", params={"range": "30d"})
    assert r.status_code == 200
    points = r.json()["points"]
    assert points
    assert all(p["timestamp"] >= NOW - 30 * 86400 - 60 for p in points)
    # bad range rejected
    assert api.get("/api/prices/4151", params={"range": "90d"}).status_code == 422


def test_prices_moving_averages(api):
    r = api.get("/api/prices/4151", params={"range": "24h", "ma": "1h,24h"})
    body = r.json()
    assert set(body["moving_averages"].keys()) == {"1h", "24h"}
    assert api.get("/api/prices/4151",
                   params={"range": "24h", "ma": "3d"}).status_code == 422


def test_stats_and_trends_routes(api):
    api.post("/api/tracked", json={"item_id": 4151})
    r = api.get("/api/stats/4151")
    assert r.status_code == 200
    body = r.json()
    for key in ("current_price", "change_24h", "high_30d", "low_30d",
                "average_30d", "median_30d", "volatility_30d", "total_volume"):
        assert key in body
    r = api.get("/api/trends/4151")
    assert r.json()["classification"] in {
        "Strongly Rising", "Rising", "Neutral", "Falling", "Strongly Falling"}


def test_movers_route(api):
    r = api.get("/api/movers", params={"period": "24h"})
    assert r.status_code == 200
    body = r.json()
    assert {"gainers", "losers", "highest_volume"} <= set(body.keys())
    assert api.get("/api/movers", params={"period": "1y"}).status_code == 422


def test_settings_roundtrip(api):
    r = api.get("/api/settings")
    assert r.json()["update_interval_minutes"] == "5"
    r = api.put("/api/settings", json={"update_interval_minutes": "15",
                                       "theme": "light"})
    assert r.status_code == 200
    assert r.json()["update_interval_minutes"] == "15"
    assert api.put("/api/settings",
                   json={"update_interval_minutes": "7"}).status_code == 422
    assert api.put("/api/settings", json={}).status_code == 422


def test_status_route(api):
    body = api.get("/api/status").json()
    assert body["api_online"] is True
    assert body["collector_running"] is True
    assert body["database_records"] > 0
    assert body["item_count"] == 4


def test_export_csv_and_json(api):
    api.post("/api/tracked", json={"item_id": 4151})
    r = api.get("/api/export/4151", params={"format": "csv", "range": "30d"})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    assert lines[0] == "timestamp,item_id,item_name,high_price,low_price,average_price,volume"
    r = api.get("/api/export/4151", params={"format": "json"})
    body = r.json()
    assert body["item_name"] == "Abyssal whip"
    assert api.get("/api/export/4151",
                   params={"format": "xml"}).status_code == 422
