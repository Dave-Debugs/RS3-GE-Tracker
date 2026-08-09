import time

from tests.conftest import make_points

NOW = int(time.time())


def test_upsert_items_and_search(repo, mock_api):
    repo.upsert_items(mock_api.mapping)
    assert repo.item_count() == 4
    assert repo.get_item(4151)["name"] == "Abyssal whip"
    # upsert again -> no duplicates
    repo.upsert_items(mock_api.mapping)
    assert repo.item_count() == 4


def test_insert_prices_and_duplicate_prevention(repo):
    rows = make_points(NOW - 3600, 300, [100, 101, 102])
    ins, skip = repo.insert_price_rows(rows)
    assert (ins, skip) == (3, 0)
    ins, skip = repo.insert_price_rows(rows)
    assert (ins, skip) == (0, 3)
    assert repo.price_history_count() == 3


def test_same_timestamp_different_source_not_duplicate(repo):
    row = make_points(NOW, 300, [100])[0]
    repo.insert_price_rows([row])
    ins, _ = repo.insert_price_rows([{**row, "source": "1h"}])
    assert ins == 1


def test_price_history_window_query(repo):
    repo.insert_price_rows(make_points(NOW - 40 * 86400, 86400, list(range(40))))
    pts = repo.get_price_history(0, NOW - 10 * 86400)
    assert all(p["timestamp"] >= NOW - 10 * 86400 for p in pts)
    assert len(pts) == 10


def test_delete_older_than_30_days(repo):
    old = make_points(NOW - 35 * 86400, 300, [1, 2, 3])
    new = make_points(NOW - 3600, 300, [4, 5])
    repo.insert_price_rows(old + new)
    deleted = repo.delete_older_than(NOW - 30 * 86400)
    assert deleted == 3
    assert repo.price_history_count() == 2


def test_tracked_lifecycle(repo, mock_api):
    repo.upsert_items(mock_api.mapping)
    assert repo.add_tracked(4151) is True
    assert repo.add_tracked(4151) is False  # idempotent
    assert repo.tracked_ids() == [4151]
    assert repo.pending_backfill_ids() == [4151]
    repo.set_backfilled(4151)
    assert repo.pending_backfill_ids() == []
    repo.set_favorite(4151, True)
    assert repo.tracked()[0]["favorite"] == 1
    assert repo.remove_tracked(4151) is True
    assert repo.remove_tracked(4151) is False


def test_settings_and_state(repo):
    assert repo.get_settings({"a": "1"}) == {"a": "1"}
    repo.set_setting("a", "2")
    assert repo.get_settings({"a": "1"})["a"] == "2"
    assert repo.get_state("missing") is None
    repo.set_state("last_5m_ts", "123")
    assert repo.get_state("last_5m_ts") == "123"


def test_collection_run_log(repo):
    run_id = repo.start_run()
    repo.finish_run(run_id, True, 10, 2, 1, 4, None)
    last = repo.last_run()
    assert last["ok"] == 1 and last["inserted"] == 10
    assert repo.last_successful_run()["id"] == run_id
