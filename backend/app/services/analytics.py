from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass


@dataclass
class TrendResult:
    classification: str
    slope_pct_per_day: float
    short_ma: float | None
    long_ma: float | None
    momentum_pct: float
    volatility_pct: float
    r_squared: float
    points_used: int

    def to_dict(self) -> dict:
        return asdict(self)


def pct_change(old: float | None, new: float | None) -> float | None:
    if old is None or new is None or old == 0:
        return None
    return round((new - old) / old * 100, 2)


def price_at_or_before(points: list[dict], ts: int) -> float | None:
    best = None
    for p in points:
        if p["timestamp"] <= ts and p.get("average_price") is not None:
            best = p["average_price"]
        elif p["timestamp"] > ts:
            break
    return best


def compute_vwap(points: list[dict]) -> float | None:
    """Compute Volume-Weighted Average Price (VWAP) across points with positive volume."""
    weighted_sum = 0.0
    total_vol = 0
    fallback_prices: list[float] = []
    for p in points:
        price = p.get("average_price")
        if price is None:
            continue
        fallback_prices.append(float(price))
        vol = int(p.get("volume") or 0)
        if vol > 0:
            weighted_sum += float(price) * vol
            total_vol += vol
    if total_vol > 0:
        return round(weighted_sum / total_vol, 2)
    if fallback_prices:
        return round(statistics.fmean(fallback_prices), 2)
    return None


def detect_anomalies(points: list[dict], z_threshold: float = 2.0) -> dict:
    """Detect statistical price & volume anomalies using Z-scores against the window baseline."""
    prices = [float(p["average_price"]) for p in points if p.get("average_price") is not None]
    vols = [float(p.get("volume") or 0) for p in points if (p.get("volume") or 0) > 0]

    price_zscore = 0.0
    if len(prices) >= 5:
        mean_p = statistics.fmean(prices)
        std_p = statistics.pstdev(prices)
        if std_p > 0:
            price_zscore = round((prices[-1] - mean_p) / std_p, 2)

    vol_zscore = 0.0
    if len(vols) >= 5:
        mean_v = statistics.fmean(vols)
        std_v = statistics.pstdev(vols)
        if std_v > 0:
            vol_zscore = round((vols[-1] - mean_v) / std_v, 2)

    anomaly_label: str | None = None
    if price_zscore >= z_threshold and vol_zscore >= 1.5:
        anomaly_label = "Breakout Surge"
    elif price_zscore <= -z_threshold and vol_zscore >= 1.5:
        anomaly_label = "Panic Dump"
    elif price_zscore >= z_threshold:
        anomaly_label = "Price Surge (+2σ)"
    elif price_zscore <= -z_threshold:
        anomaly_label = "Price Dip (-2σ)"
    elif vol_zscore >= z_threshold:
        anomaly_label = "Volume Spike"

    return {
        "price_zscore": price_zscore,
        "volume_zscore": vol_zscore,
        "anomaly_label": anomaly_label,
    }


def compute_stats(points: list[dict], now: int) -> dict:
    prices = [p["average_price"] for p in points if p.get("average_price") is not None]
    if not prices:
        return {
            "current_price": None, "change_24h": None, "change_7d": None,
            "high_7d": None, "low_7d": None,
            "average_7d": None, "median_7d": None, "vwap_7d": None,
            "volatility_7d": None,
            "price_zscore": 0.0, "volume_zscore": 0.0, "anomaly_label": None,
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
    anomalies = detect_anomalies(points)
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
        "vwap_7d": compute_vwap(points),
        "volatility_7d": volatility,
        "price_zscore": anomalies["price_zscore"],
        "volume_zscore": anomalies["volume_zscore"],
        "anomaly_label": anomalies["anomaly_label"],
        "total_volume": int(sum(p.get("volume") or 0 for p in points)),
        "points": len(points),
    }


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
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


def bollinger_bands(points: list[dict], window_seconds: int, num_std: float = 2.0) -> list[dict]:
    """Compute rolling Bollinger Bands (middle SMA, upper +2σ, lower -2σ)."""
    out = []
    values: list[tuple[int, float]] = [
        (p["timestamp"], float(p["average_price"]))
        for p in points if p.get("average_price") is not None
    ]
    start = 0
    for i, (ts, _) in enumerate(values):
        while values[start][0] < ts - window_seconds:
            start += 1
        window_slice = [v for _, v in values[start : i + 1]]
        mean = sum(window_slice) / len(window_slice)
        std = statistics.pstdev(window_slice) if len(window_slice) > 1 else 0.0
        upper = round(mean + num_std * std, 2)
        lower = round(max(0.0, mean - num_std * std), 2)
        out.append({
            "timestamp": ts,
            "middle": round(mean, 2),
            "upper": upper,
            "lower": lower,
        })
    return out


def analyze_trend(points: list[dict]) -> TrendResult:
    series = [
        (p["timestamp"], float(p["average_price"]))
        for p in points if p.get("average_price") is not None
    ]
    if len(series) < 3:
        return TrendResult("Neutral", 0.0, None, None, 0.0, 0.0, 0.0, len(series))

    ts0 = series[0][0]
    xs = [(t - ts0) / 86400 for t, _ in series]
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
    priority = {"5m": 0, "1h": 1, "ts6h": 2, "ts1d": 3}
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
    """Largest-Triangle-Three-Buckets (LTTB) downsampling preserving endpoints and peaks."""
    n = len(points)
    if max_points <= 2 or n <= max_points:
        return points

    sampled = [points[0]]
    every = (n - 2) / (max_points - 2)
    a = 0

    for i in range(max_points - 2):
        avg_range_start = int(math.floor((i + 1) * every)) + 1
        avg_range_end = int(math.floor((i + 2) * every)) + 1
        if avg_range_end >= n:
            avg_range_end = n
        avg_range_length = max(1, avg_range_end - avg_range_start)

        avg_x = 0.0
        avg_y = 0.0
        for idx in range(avg_range_start, avg_range_end):
            pt = points[idx]
            avg_x += float(pt.get("timestamp") or idx)
            avg_y += float(pt.get("average_price") or pt.get("high_price") or pt.get("low_price") or 0.0)
        avg_x /= avg_range_length
        avg_y /= avg_range_length

        range_offs = int(math.floor(i * every)) + 1
        range_to = int(math.floor((i + 1) * every)) + 1
        if range_to >= n:
            range_to = n - 1

        pt_a = points[a]
        pt_a_x = float(pt_a.get("timestamp") or a)
        pt_a_y = float(pt_a.get("average_price") or pt_a.get("high_price") or pt_a.get("low_price") or 0.0)

        max_area = -1.0
        next_a = range_offs
        for idx in range(range_offs, max(range_offs + 1, range_to)):
            pt = points[idx]
            px = float(pt.get("timestamp") or idx)
            py = float(pt.get("average_price") or pt.get("high_price") or pt.get("low_price") or 0.0)
            area = abs(
                (pt_a_x - avg_x) * (py - pt_a_y)
                - (pt_a_x - px) * (avg_y - pt_a_y)
            ) * 0.5
            if area > max_area:
                max_area = area
                next_a = idx

        sampled.append(points[next_a])
        a = next_a

    sampled.append(points[-1])
    return sampled
