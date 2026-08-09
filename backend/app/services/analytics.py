"""Price statistics and basic statistical trend analysis.

These are descriptive statistics over recorded history — not predictions.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass


@dataclass
class TrendResult:
    classification: str          # Strongly Rising|Rising|Neutral|Falling|Strongly Falling
    slope_pct_per_day: float     # linear regression slope, % of mean price/day
    short_ma: float | None       # mean of last ~24h of points
    long_ma: float | None        # mean of last ~7d of points
    momentum_pct: float          # % change over the last quarter of the window
    volatility_pct: float        # stdev of per-point returns, %
    r_squared: float
    points_used: int

    def to_dict(self) -> dict:
        return asdict(self)


def pct_change(old: float | None, new: float | None) -> float | None:
    if old is None or new is None or old == 0:
        return None
    return round((new - old) / old * 100, 2)


def price_at_or_before(points: list[dict], ts: int) -> float | None:
    """Latest average_price at or before ts (points sorted by timestamp)."""
    best = None
    for p in points:
        if p["timestamp"] <= ts and p.get("average_price") is not None:
            best = p["average_price"]
        elif p["timestamp"] > ts:
            break
    return best


def compute_stats(points: list[dict], now: int) -> dict:
    """Stats over a (≤14-day) window of price rows sorted by timestamp."""
    prices = [p["average_price"] for p in points if p.get("average_price") is not None]
    if not prices:
        return {
            "current_price": None, "change_24h": None, "change_7d": None,
            "high_7d": None, "low_7d": None,
            "average_7d": None, "median_7d": None, "volatility_7d": None,
            "total_volume": 0, "points": 0,
        }
    current = prices[-1]
    day = 86400
    returns = [
        (b - a) / a for a, b in zip(prices, prices[1:]) if a
    ]
    volatility = (
        round(statistics.pstdev(returns) * 100, 3) if len(returns) > 1 else 0.0
    )
    return {
        "current_price": current,
        "change_24h": pct_change(price_at_or_before(points, now - day), current),
        "change_7d": pct_change(
            price_at_or_before(points, now - 7 * day) or prices[0], current
        ),
        "high_7d": max(prices),
        "low_7d": min(prices),
        "average_7d": round(statistics.fmean(prices), 2),
        "median_7d": round(statistics.median(prices), 2),
        "volatility_7d": volatility,
        "total_volume": int(sum(p.get("volume") or 0 for p in points)),
        "points": len(points),
    }


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Least squares fit -> (slope, intercept, r_squared)."""
    n = len(xs)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0, 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    if sxx == 0:
        return 0.0, mean_y, 0.0
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    syy = sum((y - mean_y) ** 2 for y in ys)
    r2 = (sxy ** 2) / (sxx * syy) if syy else 0.0
    return slope, intercept, r2


def moving_average(points: list[dict], window_seconds: int) -> list[dict]:
    """Trailing moving average series over average_price."""
    out = []
    values: list[tuple[int, float]] = [
        (p["timestamp"], p["average_price"])
        for p in points if p.get("average_price") is not None
    ]
    start = 0
    running = 0.0
    for i, (ts, price) in enumerate(values):
        running += price
        while values[start][0] < ts - window_seconds:
            running -= values[start][1]
            start += 1
        out.append({"timestamp": ts, "value": round(running / (i - start + 1), 2)})
    return out


def analyze_trend(points: list[dict]) -> TrendResult:
    """Classify the current trend from recorded history (descriptive only)."""
    series = [
        (p["timestamp"], float(p["average_price"]))
        for p in points if p.get("average_price") is not None
    ]
    if len(series) < 3:
        return TrendResult("Neutral", 0.0, None, None, 0.0, 0.0, 0.0, len(series))

    ts0 = series[0][0]
    xs = [(t - ts0) / 86400 for t, _ in series]        # days
    ys = [v for _, v in series]
    mean_price = sum(ys) / len(ys)
    slope, _, r2 = linear_regression(xs, ys)
    slope_pct = (slope / mean_price * 100) if mean_price else 0.0

    last_ts = series[-1][0]
    short = [v for t, v in series if t >= last_ts - 86400]
    long_ = [v for t, v in series if t >= last_ts - 7 * 86400]
    short_ma = round(sum(short) / len(short), 2) if short else None
    long_ma = round(sum(long_) / len(long_), 2) if long_ else None

    quarter = max(1, len(series) // 4)
    old_q = ys[-quarter - 1] if len(ys) > quarter else ys[0]
    momentum = ((ys[-1] - old_q) / old_q * 100) if old_q else 0.0

    returns = [(b - a) / a for a, b in zip(ys, ys[1:]) if a]
    vol = (statistics.pstdev(returns) * 100) if len(returns) > 1 else 0.0

    # Classification: combine regression slope with MA crossover confirmation.
    score = slope_pct
    if short_ma and long_ma and long_ma:
        ma_gap_pct = (short_ma - long_ma) / long_ma * 100
        score = 0.7 * slope_pct + 0.3 * ma_gap_pct

    if score >= 2.0:
        cls = "Strongly Rising"
    elif score >= 0.35:
        cls = "Rising"
    elif score <= -2.0:
        cls = "Strongly Falling"
    elif score <= -0.35:
        cls = "Falling"
    else:
        cls = "Neutral"

    return TrendResult(
        classification=cls,
        slope_pct_per_day=round(slope_pct, 3),
        short_ma=short_ma,
        long_ma=long_ma,
        momentum_pct=round(momentum, 2),
        volatility_pct=round(vol, 3),
        r_squared=round(r2, 3),
        points_used=len(series),
    )


def merge_sources(points: list[dict]) -> list[dict]:
    """Collapse rows from multiple sources into one series.

    When several sources cover the same timestamp, prefer the finest
    resolution (5m > 1h > ts6h). Output sorted by timestamp.
    """
    priority = {"5m": 0, "1h": 1, "ts6h": 2}
    best: dict[int, dict] = {}
    for p in points:
        ts = p["timestamp"]
        cur = best.get(ts)
        if cur is None or priority.get(p.get("source", ""), 9) < priority.get(
            cur.get("source", ""), 9
        ):
            best[ts] = p
    return sorted(best.values(), key=lambda p: p["timestamp"])


def downsample(points: list[dict], max_points: int = 1100) -> list[dict]:
    """Return points directly. LTTB downsampling is handled by the frontend."""
    return points
