import httpx
import pytest

from app.api_client.client import ApiError, RS3PriceClient


def test_mapping(client):
    items = client.mapping()
    assert len(items) == 4
    assert items[0]["id"] == 4151


def test_latest_bulk_and_single(client):
    data = client.latest()
    assert "4151" in data and data["4151"]["high"] == 73604
    single = client.latest(4151)
    assert list(single.keys()) == ["4151"]


def test_five_minute_and_one_hour(client):
    ts, data = client.five_minute()
    assert ts % 300 == 0
    assert data["2"]["avgLowPrice"] is None
    ts_h, data_h = client.one_hour()
    assert ts_h % 3600 == 0
    assert "4151" in data_h


def test_timeseries_validates_lookback(client):
    with pytest.raises(ValueError):
        client.timeseries(4151, "3d")
    points = client.timeseries(4151, "24h")
    assert points and "timestamp" in points[0]


def test_http_error_raises_apierror(mock_api, client):
    mock_api.fail_with = 400
    with pytest.raises(ApiError):
        client.latest()


def test_server_error_retries_then_fails(mock_api, client, monkeypatch):
    monkeypatch.setattr("app.api_client.client.RETRY_BACKOFF_BASE_SECONDS", 0.0)
    mock_api.fail_with = 503
    with pytest.raises(ApiError):
        client.latest()
    assert len(mock_api.calls) == 4  # initial + 3 retries


def test_invalid_json_raises(mock_api, client):
    mock_api.bad_json = True
    with pytest.raises(ApiError, match="invalid JSON"):
        client.latest()


def test_mapping_cached(mock_api, client):
    client.mapping()
    client.mapping()
    assert len([c for c in mock_api.calls if "mapping" in c]) == 1


def test_descriptive_user_agent_sent(mock_api):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers["user-agent"]
        return httpx.Response(200, json={"data": {}})

    c = RS3PriceClient(transport=httpx.MockTransport(handler), min_interval=0)
    c.latest()
    c.close()
    assert "RS3-GE-Tracker" in seen["ua"]
    assert "python-requests" not in seen["ua"]
