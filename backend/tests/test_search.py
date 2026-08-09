import pytest

from app.services.search import search_items


@pytest.fixture
def loaded_repo(repo, mock_api):
    repo.upsert_items(mock_api.mapping)
    return repo


def test_exact_name(loaded_repo):
    results = search_items(loaded_repo, "Abyssal whip")
    assert results and results[0]["item_id"] == 4151


def test_partial_case_insensitive(loaded_repo):
    results = search_items(loaded_repo, "scim")
    assert any(r["name"] == "Dragon scimitar" for r in results)
    results = search_items(loaded_repo, "PARTY")
    assert any(r["item_id"] == 1042 for r in results)


def test_search_by_item_id(loaded_repo):
    results = search_items(loaded_repo, "4151")
    assert results[0]["item_id"] == 4151


def test_fuzzy_typo(loaded_repo):
    results = search_items(loaded_repo, "abysal whyp")
    assert any(r["item_id"] == 4151 for r in results)


def test_empty_and_no_match(loaded_repo):
    assert search_items(loaded_repo, "") == []
    assert search_items(loaded_repo, "zzzzqqqq") == []


def test_prefix_ranked_before_substring(loaded_repo):
    loaded_repo.upsert_items([{"id": 9999, "name": "Off-hand dragon whip"}])
    results = search_items(loaded_repo, "dragon")
    assert results[0]["name"].lower().startswith("dragon")
