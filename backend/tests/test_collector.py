import time

from app.collector.collector import normalize_bucket_row

NOW = int(time.time())


def test_normalize_bucket_row():
    row = normalize_bucket_row(1, 100, {"avgHighPrice": 110, "avgLowPrice": 90,
                                        "highPriceVolume": 3, "lowPriceVolume": 2}, "5m")
    assert row["average_price"] == 100 and row["volume"] == 5
    # one-sided
    row = normalize_bucket_row(1, 100, {"avgHighPrice": None, "avgLowPrice": 90,
                                        "highPriceVolume": 0, "lowPriceVolume": 2}, "5m")
    assert row["average_price"] == 90
    # empty / malformed
    assert normalize_bucket_row(1, 100, {"avgHighPrice": None, "avgLowPrice": None}, "5m") is None
    assert normalize_bucket_row(1, 100, "garbage", "5m") is None
    assert normalize_bucket_row(1, 100, {"avgHighPrice": "NaN?", "avgLowPrice": None}, "5m") is None


async def test_initial_cycle_populates_everything(collector, repo):
    result = await collector.run_cycle()
    assert result["ok"] is True
    assert await repo.item_count() == 4                      # mapping loaded
    latest = await repo.get_latest([4151])
    assert latest[4151]["high"] == 73604
    assert await repo.price_history_count() > 0              # 1h rows for all items
    assert await repo.get_state("last_1h_ts") is not None
    assert await repo.get_state("last_5m_ts") is not None
    last = await repo.last_run()
    assert last["ok"] == 1


async def test_incremental_sync_only_fetches_missing_buckets(collector, repo, mock_api):
    await collector.run_cycle()
    # Pretend last 1h sync was 3 hours ago -> expect ~3 bucket fetches, not 30 days
    last = int(await repo.get_state("last_1h_ts"))
    await repo.set_state("last_1h_ts", str(last - 3 * 3600))
    mock_api.calls.clear()
    await collector.run_cycle()
    hour_calls = [c for c in mock_api.calls if "/1h" in c]
    assert 1 <= len(hour_calls) <= 4
    # and they must be timestamped (incremental), not bare full fetches
    assert all("timestamp=" in c for c in hour_calls)


async def test_catchup_is_capped_after_long_downtime(collector, repo, mock_api):
    await collector.run_cycle()
    last_5m = int(await repo.get_state("last_5m_ts"))
    await repo.set_state("last_5m_ts", str(last_5m - 86400))
    mock_api.calls.clear()
    await collector.run_cycle()
    five_calls = [c for c in mock_api.calls if "/5m" in c]
    assert len(five_calls) <= 12  # MAX_CATCHUP_5M_BUCKETS


async def test_5m_rows_only_stored_for_tracked_items(collector, repo):
    await repo.upsert_items([{"id": 4151, "name": "Abyssal whip"},
                             {"id": 2, "name": "Cannonball"}])
    await repo.set_state("mapping_refreshed_at", str(NOW))
    await repo.add_tracked(4151)
    await repo.set_backfilled(4151)   # skip backfill; test 5m path in isolation
    await collector.run_cycle()
    rows_5m = await repo.get_price_history(2, NOW - 86400, sources=["5m"])
    assert rows_5m == []        # cannonball not tracked -> no 5m rows
    rows_1h = await repo.get_price_history(2, NOW - 86400, sources=["1h"])
    assert rows_1h              # but 1h rows exist for everyone


async def test_backfill_on_track(collector, repo):
    await collector.run_cycle()
    await repo.add_tracked(4151)
    await collector.run_cycle()
    pts = await repo.get_price_history(4151, NOW - 30 * 86400)
    sources = {p["source"] for p in pts}
    assert {"ts6h", "1h", "5m"} <= sources
    span_days = (pts[-1]["timestamp"] - pts[0]["timestamp"]) / 86400
    assert span_days >= 13
    assert await repo.pending_backfill_ids() == []


async def test_retention_enforced_in_cycle(collector, repo):
    await repo.insert_price_rows([{
        "item_id": 4151, "timestamp": NOW - 45 * 86400, "high_price": 1,
        "low_price": 1, "average_price": 1, "volume": 1, "source": "1h",
    }])
    result = await collector.run_cycle()
    assert result["deleted"] >= 1
    earliest = await repo.earliest_timestamp(4151)
    assert earliest is None or earliest >= NOW - 31 * 86400


async def test_api_failure_recovery(collector, repo, mock_api, monkeypatch):
    monkeypatch.setattr("app.api_client.client.RETRY_BACKOFF_BASE_SECONDS", 0.0)
    mock_api.fail_with = 503
    result = await collector.run_cycle()
    assert result["ok"] is False and result["error"]
    assert await repo.get_state("last_sync_ok") == "0"
    last = await repo.last_run()
    assert last["ok"] == 0
    # API comes back -> next cycle succeeds
    mock_api.fail_with = None
    result = await collector.run_cycle()
    assert result["ok"] is True
    assert await repo.get_state("last_sync_ok") == "1"


async def test_malformed_item_ids_skipped_not_fatal(collector, repo):
    # MockAPI 5m/1h data includes a "notanid" key
    await repo.add_tracked(4151)
    result = await collector.run_cycle()
    assert result["ok"] is True


async def test_first_run_seeds_24h_of_hourly_data(collector, repo, mock_api):
    await collector.run_cycle()
    hour_calls = [c for c in mock_api.calls if "/1h" in c]
    assert len(hour_calls) == 24  # market-wide seed for Top Movers
    rows = await repo.get_price_history(2, NOW - 2 * 86400, sources=["1h"])
    assert len(rows) >= 20
