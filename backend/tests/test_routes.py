import time

import httpx
import pytest

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
async def api(repo, collector, client, mock_api):
    """AsyncClient wired to the mock API + temp DB (no background tasks)."""
    await collector.run_cycle()  # seed items/latest/1h data
    app = create_app()
    scheduler = DummyScheduler()
    app.state.db = repo.db
    app.state.repo = repo
    app.state.client = client
    app.state.collector = collector
    app.state.scheduler = scheduler

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(_app):
        yield

    app.router.lifespan_context = noop_lifespan
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.scheduler = scheduler
        yield ac


async def test_health(api):
    r = await api.get("/api/health")
    assert r.json() == {"status": "ok"}


async def test_search_route(api):
    r = await api.get("/api/items/search", params={"q": "whip"})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["name"] == "Abyssal whip"
    assert results[0]["current_price"] is not None
    assert results[0]["icon_url"] == "/api/icon/4151"


async def test_track_untrack_flow(api):
    r = await api.post("/api/tracked", json={"item_id": 4151})
    assert r.status_code == 201 and r.json()["added"] is True
    assert api.scheduler.triggered is True
    r = await api.get("/api/tracked")
    tracked = r.json()["tracked"]
    assert len(tracked) == 1 and tracked[0]["item_id"] == 4151
    assert "trend" in tracked[0] and "change_24h" in tracked[0]
    r = await api.put("/api/tracked/4151/favorite", json={"favorite": True})
    assert r.json()["favorite"] is True
    
    # Test setting group
    r = await api.put("/api/tracked/4151/group", json={"group": "Flipping"})
    assert r.status_code == 200 and r.json()["group"] == "Flipping"
    r = await api.get("/api/tracked")
    assert r.json()["tracked"][0]["group_name"] == "Flipping"
    
    # Test deleting group (resets group to Default)
    r = await api.delete("/api/tracked/groups/Flipping")
    assert r.status_code == 200 and r.json()["items_moved_to_default"] == 1
    r = await api.get("/api/tracked")
    assert r.json()["tracked"][0]["group_name"] == "Default"

    r = await api.delete("/api/tracked/4151")
    assert r.json()["removed"] is True
    del_again = await api.delete("/api/tracked/4151")
    assert del_again.status_code == 404


async def test_track_unknown_item_404(api):
    r = await api.post("/api/tracked", json={"item_id": 999999})
    assert r.status_code == 404


async def test_prices_route_and_14day_filter(api, repo):
    # insert data older than the 14d window; it must not appear for range=14d
    await repo.insert_price_rows(make_points(NOW - 60 * 86400, 3600, [1.0] * 5))
    await repo.insert_price_rows([{**p, "item_id": 4151} for p in
                                  make_points(NOW - 60 * 86400, 3600, [1.0] * 5)])
    r = await api.get("/api/prices/4151", params={"range": "14d"})
    assert r.status_code == 200
    points = r.json()["points"]
    assert points
    assert all(p["timestamp"] >= NOW - 14 * 86400 - 60 for p in points)
    # bad range rejected
    bad = await api.get("/api/prices/4151", params={"range": "90d"})
    assert bad.status_code == 422


async def test_prices_moving_averages(api):
    r = await api.get("/api/prices/4151", params={"range": "24h", "ma": "1h,24h"})
    body = r.json()
    assert set(body["moving_averages"].keys()) == {"1h", "24h"}
    bad = await api.get("/api/prices/4151", params={"range": "24h", "ma": "3d"})
    assert bad.status_code == 422


async def test_stats_and_trends_routes(api):
    await api.post("/api/tracked", json={"item_id": 4151})
    r = await api.get("/api/stats/4151")
    assert r.status_code == 200
    body = r.json()
    for key in ("current_price", "change_24h", "high_7d", "low_7d",
                "average_7d", "median_7d", "volatility_7d", "total_volume"):
        assert key in body
    r = await api.get("/api/trends/4151")
    assert r.json()["classification"] in {
        "Strongly Rising", "Rising", "Neutral", "Falling", "Strongly Falling"}


async def test_movers_route(api):
    r = await api.get("/api/movers", params={"period": "24h"})
    assert r.status_code == 200
    body = r.json()
    assert {"gainers", "losers", "highest_volume"} <= set(body.keys())
    bad = await api.get("/api/movers", params={"period": "1y"})
    assert bad.status_code == 422


async def test_settings_roundtrip(api):
    r = await api.get("/api/settings")
    assert r.json()["update_interval_minutes"] == "5"
    r = await api.put("/api/settings", json={"update_interval_minutes": "15",
                                            "theme": "light"})
    assert r.status_code == 200
    assert r.json()["update_interval_minutes"] == "15"
    bad = await api.put("/api/settings", json={"update_interval_minutes": "7"})
    assert bad.status_code == 422
    empty = await api.put("/api/settings", json={})
    assert empty.status_code == 422


async def test_status_route(api):
    r = await api.get("/api/status")
    body = r.json()
    assert body["api_online"] is True
    assert body["collector_running"] is True
    assert body["database_records"] > 0
    assert body["item_count"] == 4


async def test_export_csv_and_json(api):
    await api.post("/api/tracked", json={"item_id": 4151})
    r = await api.get("/api/export/4151", params={"format": "csv", "range": "14d"})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    assert lines[0] == "timestamp,item_id,item_name,high_price,low_price,average_price,volume"
    r = await api.get("/api/export/4151", params={"format": "json"})
    body = r.json()
    assert body["item_name"] == "Abyssal whip"
    bad = await api.get("/api/export/4151", params={"format": "xml"})
    assert bad.status_code == 422


async def test_alerts_routes(api):
    r = await api.get("/api/alerts")
    assert r.status_code == 200
    assert r.json() == {"alerts": []}
    create_r = await api.post("/api/alerts", json={"item_id": 4151, "condition": ">", "threshold_price": 75000})
    assert create_r.status_code == 201
    alert_id = create_r.json()["id"]
    r2 = await api.get("/api/alerts")
    alerts = r2.json()["alerts"]
    assert len(alerts) == 1 and alerts[0]["threshold_price"] == 75000
    update_r = await api.put(f"/api/alerts/{alert_id}", json={"active": False})
    assert update_r.status_code == 200
    del_r = await api.delete(f"/api/alerts/{alert_id}")
    assert del_r.status_code == 200


async def test_portfolio_routes(api):
    r = await api.get("/api/portfolio")
    assert r.status_code == 200
    assert r.json()["items"] == []
    add_r = await api.post("/api/portfolio", json={"item_id": 4151, "quantity": 5, "buy_price_per_item": 70000})
    assert add_r.status_code == 201
    port_id = add_r.json()["id"]
    r2 = await api.get("/api/portfolio")
    assert len(r2.json()["items"]) == 1
    assert r2.json()["total_cost"] == 350000
    del_r = await api.delete(f"/api/portfolio/{port_id}")
    assert del_r.status_code == 200


async def test_recipes_routes(api):
    r = await api.get("/api/recipes")
    assert r.status_code == 200
    assert r.json()["recipes"] == []
    create_r = await api.post("/api/recipes", json={
        "name": "Whip Dismantle",
        "output_item_id": 2,
        "output_qty": 100,
        "ingredients": [{"item_id": 4151, "qty": 1}]
    })
    assert create_r.status_code == 201
    rec_id = create_r.json()["id"]
    r2 = await api.get("/api/recipes")
    assert len(r2.json()["recipes"]) == 1
    del_r = await api.delete(f"/api/recipes/{rec_id}")
    assert del_r.status_code == 200
