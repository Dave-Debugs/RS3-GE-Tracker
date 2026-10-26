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

    await collector.run_cycle()
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

    r = await api.put("/api/tracked/4151/group", json={"group": "Flipping"})
    assert r.status_code == 200 and r.json()["group"] == "Flipping"
    r = await api.get("/api/tracked")
    assert r.json()["tracked"][0]["group_name"] == "Flipping"

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

    await repo.insert_price_rows(make_points(NOW - 60 * 86400, 3600, [1.0] * 5))
    await repo.insert_price_rows([{**p, "item_id": 4151} for p in
                                  make_points(NOW - 60 * 86400, 3600, [1.0] * 5)])
    r = await api.get("/api/prices/4151", params={"range": "14d"})
    assert r.status_code == 200
    points = r.json()["points"]
    assert points
    assert all(p["timestamp"] >= NOW - 14 * 86400 - 60 for p in points)

    r90 = await api.get("/api/prices/4151", params={"range": "90d"})
    assert r90.status_code == 200
    r1y = await api.get("/api/prices/4151", params={"range": "1y"})
    assert r1y.status_code == 200

    bad = await api.get("/api/prices/4151", params={"range": "2y"})
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
                                            "theme": "light",
                                            "default_chart_range": "90d"})
    assert r.status_code == 200
    assert r.json()["update_interval_minutes"] == "15"
    assert r.json()["default_chart_range"] == "90d"
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
    create_r = await api.post(
        "/api/alerts",
        json={
            "item_id": 4151,
            "condition": ">",
            "threshold_price": 75000,
            "metric": "high",
            "cooldown_minutes": 60,
        },
    )
    assert create_r.status_code == 201
    alert_id = create_r.json()["id"]
    r2 = await api.get("/api/alerts")
    alerts = r2.json()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["threshold_price"] == 75000
    assert alerts[0]["metric"] == "high"
    assert alerts[0]["cooldown_minutes"] == 60
    update_r = await api.put(f"/api/alerts/{alert_id}", json={"active": False})
    assert update_r.status_code == 200
    del_r = await api.delete(f"/api/alerts/{alert_id}")
    assert del_r.status_code == 200

async def test_portfolio_and_flip_ledger_routes(api):
    r = await api.get("/api/portfolio")
    assert r.status_code == 200
    assert r.json()["items"] == []
    add_r = await api.post("/api/portfolio", json={"item_id": 4151, "quantity": 5, "buy_price_per_item": 70000})
    assert add_r.status_code == 201
    port_id = add_r.json()["id"]
    r2 = await api.get("/api/portfolio")
    data = r2.json()
    assert len(data["items"]) == 1
    assert data["total_cost"] == 350000
    assert "net_liquidation_value" in data
    assert "total_tax" in data
    assert data["items"][0]["break_even_price"] > 70000

    close_r = await api.post(
        f"/api/portfolio/{port_id}/close",
        json={"sell_price_per_item": 75000, "quantity_sold": 2, "notes": "Partial flip"},
    )
    assert close_r.status_code == 200
    closed_data = close_r.json()
    assert closed_data["quantity_sold"] == 2
    assert closed_data["remaining_quantity"] == 3
    assert closed_data["tax_paid"] == 3000
    assert closed_data["net_profit"] == (75000 - 1500 - 70000) * 2

    hist_r = await api.get("/api/portfolio/history")
    assert hist_r.status_code == 200
    hist = hist_r.json()
    assert hist["trades_count"] == 1
    assert hist["total_realized_profit"] == closed_data["net_profit"]
    assert hist["win_rate_pct"] == 100.0

    del_r = await api.delete(f"/api/portfolio/{port_id}")
    assert del_r.status_code == 200

async def test_recipes_routes(api):
    r = await api.get("/api/recipes")
    assert r.status_code == 200
    assert r.json()["recipes"] == []
    create_r = await api.post("/api/recipes", json={
        "name": "Whip Dismantle",
        "output_item_id": 4151,
        "output_qty": 1,
        "ingredients": [{"item_id": 2, "qty": 50}]
    })
    assert create_r.status_code == 201
    rec_id = create_r.json()["id"]
    r2 = await api.get("/api/recipes")
    recipes = r2.json()["recipes"]
    assert len(recipes) == 1
    rec = recipes[0]
    assert "tax" in rec
    assert "patient_profit" in rec
    assert "patient_cost" in rec
    del_r = await api.delete(f"/api/recipes/{rec_id}")
    assert del_r.status_code == 200

async def test_scanner_routes(api):
    flips_r = await api.get("/api/scanner/flips", params={"min_price": 100, "sort_by": "limit_profit"})
    assert flips_r.status_code == 200
    data = flips_r.json()
    assert "items" in data and "count" in data
    assert data["count"] >= 1
    whip = next((i for i in data["items"] if i["item_id"] == 4151), None)
    assert whip is not None
    assert whip["net_profit"] > 0
    assert whip["limit_profit_4h"] == whip["net_profit"] * whip["buy_limit"]

    alch_r = await api.get("/api/scanner/alch", params={"sort_by": "limit_profit", "mode": "machine"})
    assert alch_r.status_code == 200
    alch_data = alch_r.json()
    assert alch_data["mode"] == "machine"
    assert "nature_rune_price" in alch_data
    assert "divine_charge_price" in alch_data
    assert "cast_cost" in alch_data
    assert isinstance(alch_data["items"], list)

    rec_scan = await api.get("/api/scanner/recipes", params={"execution_mode": "patient"})
    assert rec_scan.status_code == 200
    assert "items" in rec_scan.json()

async def test_ge_slots_and_backup_routes(api):
    slots_r = await api.get("/api/ge-slots")
    assert slots_r.status_code == 200
    assert len(slots_r.json()["slots"]) == 8

    put_r = await api.put(
        "/api/ge-slots/1",
        json={
            "item_id": 4151,
            "offer_type": "buy",
            "target_price": 71500,
            "quantity": 10,
            "filled_qty": 10,
        },
    )
    assert put_r.status_code == 200
    slot1 = put_r.json()["slot"]
    assert slot1["empty"] is False
    assert slot1["item_id"] == 4151
    assert slot1["limit_remaining_seconds"] > 0

    comp_r = await api.post("/api/ge-slots/1/complete", json={"action": "portfolio"})
    assert comp_r.status_code == 200
    assert comp_r.json()["action"] == "portfolio"

    exp_r = await api.get("/api/backup/export")
    assert exp_r.status_code == 200
    backup_payload = exp_r.json()
    assert backup_payload["version"] == "1.3.0"
    assert len(backup_payload["portfolio"]) >= 1

    imp_r = await api.post("/api/backup/import", json=backup_payload)
    assert imp_r.status_code == 200
    assert imp_r.json()["restored"]["portfolio"] >= 1

async def test_updater_routes(api):
    bad_apply = await api.post("/api/updater/apply", json={"download_url": "http://evil.example.com/setup.exe"})
    assert bad_apply.status_code == 400
    assert "Untrusted" in bad_apply.json()["detail"]
