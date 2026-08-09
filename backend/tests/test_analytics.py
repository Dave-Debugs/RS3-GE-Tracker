import time

from app.services.analytics import (
    analyze_trend,
    compute_stats,
    downsample,
    linear_regression,
    merge_sources,
    moving_average,
    pct_change,
)
from tests.conftest import make_points

NOW = int(time.time())


def test_pct_change():
    assert pct_change(100, 110) == 10.0
    assert pct_change(100, 90) == -10.0
    assert pct_change(None, 100) is None
    assert pct_change(0, 100) is None


def test_compute_stats_basic():
    # 14 days of daily points rising 100 -> 129
    points = make_points(NOW - 30 * 86400 + 3600, 86400, list(range(100, 130)))
    stats = compute_stats(points, NOW)
    assert stats["current_price"] == 129
    assert stats["high_7d"] == 129 and stats["low_7d"] == 100
    assert stats["average_7d"] == 114.5
    assert stats["median_7d"] == 114.5
    assert stats["change_24h"] is not None and stats["change_24h"] > 0
    assert stats["change_7d"] is not None
    assert stats["total_volume"] == 300
    assert stats["volatility_7d"] > 0


def test_compute_stats_empty():
    stats = compute_stats([], NOW)
    assert stats["current_price"] is None and stats["points"] == 0


def test_linear_regression_perfect_line():
    slope, intercept, r2 = linear_regression([0, 1, 2, 3], [10, 12, 14, 16])
    assert abs(slope - 2) < 1e-9 and abs(intercept - 10) < 1e-9 and r2 > 0.999


def test_trend_classifications():
    rising = make_points(NOW - 7 * 86400, 3600, [100 + i * 0.5 for i in range(168)])
    assert analyze_trend(rising).classification == "Strongly Rising"

    falling = make_points(NOW - 7 * 86400, 3600, [200 - i * 0.5 for i in range(168)])
    assert analyze_trend(falling).classification == "Strongly Falling"

    flat = make_points(NOW - 7 * 86400, 3600, [100 + (i % 2) * 0.1 for i in range(168)])
    assert analyze_trend(flat).classification == "Neutral"

    too_few = make_points(NOW - 600, 300, [100, 101])
    assert analyze_trend(too_few).classification == "Neutral"


def test_trend_exposes_calculation_details():
    t = analyze_trend(make_points(NOW - 7 * 86400, 3600,
                                  [100 + i * 0.2 for i in range(168)]))
    d = t.to_dict()
    for key in ("slope_pct_per_day", "short_ma", "long_ma", "momentum_pct",
                "volatility_pct", "r_squared", "points_used"):
        assert key in d


def test_moving_average_trailing_window():
    points = make_points(0, 3600, [10, 20, 30, 40])
    ma = moving_average(points, 2 * 3600)
    assert [p["value"] for p in ma] == [10, 15, 20, 30]


def test_merge_sources_prefers_finer_resolution():
    coarse = {"timestamp": 1000, "average_price": 50, "source": "ts6h"}
    fine = {"timestamp": 1000, "average_price": 55, "source": "5m"}
    merged = merge_sources([coarse, fine])
    assert len(merged) == 1 and merged[0]["average_price"] == 55


def test_downsample_keeps_endpoints():
    points = make_points(0, 300, list(range(5000)))
    thinned = downsample(points, max_points=1000)
    assert len(thinned) <= 1001
    assert thinned[0] == points[0] and thinned[-1] == points[-1]
