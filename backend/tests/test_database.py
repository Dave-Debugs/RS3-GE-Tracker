import time

from tests.conftest import make_points

NOW = int(time.time())


async def test_upsert_items_and_search(repo, mock_api):
    await repo.upsert_items(mock_api.mapping)
    assert await repo.item_count() == 4
    item = await repo.get_item(4151)
    assert item["name"] == "Abyssal whip"
    # upsert again -> no duplicates
    await repo.upsert_items(mock_api.mapping)
    assert await repo.item_count() == 4


async def test_insert_prices_and_duplicate_prevention(repo):
    rows = make_points(NOW - 3600, 300, [100, 101, 102])
    ins, skip = await repo.insert_price_rows(rows)
    assert (ins, skip) == (3, 0)
    ins, skip = await repo.insert_price_rows(rows)
    assert (ins, skip) == (0, 3)
    assert await repo.price_history_count() == 3


async def test_same_timestamp_different_source_not_duplicate(repo):
    row = make_points(NOW, 300, [100])[0]
    await repo.insert_price_rows([row])
    ins, _ = await repo.insert_price_rows([{**row, "source": "1h"}])
    assert ins == 1


async def test_price_history_window_query(repo):
    await repo.insert_price_rows(make_points(NOW - 40 * 86400, 86400, list(range(40))))
    pts = await repo.get_price_history(0, NOW - 10 * 86400)
    assert all(p["timestamp"] >= NOW - 10 * 86400 for p in pts)
    assert len(pts) == 10


async def test_delete_older_than_30_days(repo):
    old = make_points(NOW - 35 * 86400, 300, [1, 2, 3])
    new = make_points(NOW - 3600, 300, [4, 5])
    await repo.insert_price_rows(old + new)
    deleted = await repo.delete_older_than(NOW - 30 * 86400)
    assert deleted == 3
    assert await repo.price_history_count() == 2


async def test_tracked_lifecycle(repo, mock_api):
    await repo.upsert_items(mock_api.mapping)
    assert await repo.add_tracked(4151) is True
    assert await repo.add_tracked(4151) is False  # idempotent
    assert await repo.tracked_ids() == [4151]
    assert await repo.pending_backfill_ids() == [4151]
    await repo.set_backfilled(4151)
    assert await repo.pending_backfill_ids() == []
    await repo.set_favorite(4151, True)
    tracked = await repo.tracked()
    assert tracked[0]["favorite"] == 1
    assert await repo.remove_tracked(4151) is True
    assert await repo.remove_tracked(4151) is False


async def test_settings_and_state(repo):
    assert await repo.get_settings({"a": "1"}) == {"a": "1"}
    await repo.set_setting("a", "2")
    settings = await repo.get_settings({"a": "1"})
    assert settings["a"] == "2"
    assert await repo.get_state("missing") is None
    await repo.set_state("last_5m_ts", "123")
    assert await repo.get_state("last_5m_ts") == "123"


async def test_collection_run_log(repo):
    run_id = await repo.start_run()
    await repo.finish_run(run_id, True, 10, 2, 1, 4, None)
    last = await repo.last_run()
    assert last["ok"] == 1 and last["inserted"] == 10
    succ = await repo.last_successful_run()
    assert succ["id"] == run_id
