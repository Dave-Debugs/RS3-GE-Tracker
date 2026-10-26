# RS3 Real-Time Prices API Notes

## Service Overview

- Provider: RuneScape Wiki (Weird Gloop)
- Reference page: <https://runescape.wiki/w/RuneScape:Real-time_Prices>
- Base URL (RS3): `https://prices.runescape.wiki/api/v2/rs`

## Endpoints Used

### 1. `GET /mapping`
Item reference data for all tradeable RS3 items (~7,300 items).

```json
[
  {
    "id": 4151,
    "name": "Abyssal whip",
    "examine": "A weapon from the Abyss.",
    "members": true,
    "lowalch": 72000,
    "highalch": 108000,
    "limit": 100,
    "value": 120001,
    "icon": "Abyssal whip.png"
  }
]
```

- `id` is the RS3 item ID (integer).
- `icon` is a wiki image filename rendered from `https://runescape.wiki/images/<name_with_underscores>`.
- Fetched at startup and refreshed at most once per 24 hours.

### 2. `GET /latest` and `GET /latest?id={itemId}`
Most recent instant buy (`high`) and sell (`low`) trade per item.

```json
{
  "data": {
    "4151": {
      "high": 73604,
      "highTime": 1700000197,
      "low": 71549,
      "lowTime": 1700000493
    }
  }
}
```

- Timestamps are Unix seconds (UTC).
- Prices are integer GP (`null` if an item has not traded on that side recently).

### 3. `GET /5m` and `GET /5m?timestamp={unix}`
5-minute average prices and volumes for all items that traded in that bucket.

```json
{
  "timestamp": 1700000100,
  "data": {
    "2": {
      "avgHighPrice": 800,
      "highPriceVolume": 6000,
      "avgLowPrice": 796,
      "lowPriceVolume": 3867
    }
  }
}
```

- `timestamp` must be aligned to a 300-second boundary; omitting it returns the most recent completed bucket.

### 4. `GET /1h` and `GET /1h?timestamp={unix}`
Same format as `/5m` but aggregated into hourly buckets (aligned to 3600 seconds). Used for market-wide 24h volume and Top Movers calculations.

### 5. `GET /timeseries?id={itemId}&lookback={window}`
Historical price series for a single item. Valid `lookback` values: `6h`, `24h`, `7d`, `30d`, `90d`, `6m`, `1y`.

```json
{
  "data": [
    {
      "timestamp": 1700000100,
      "avgHighPrice": 76235.5,
      "avgLowPrice": null,
      "highPriceVolume": 10,
      "lowPriceVolume": 0
    }
  ]
}
```

| Lookback | Bucket Size |
|----------|-------------|
| `6h`     | 5 min       |
| `24h`    | 5 min       |
| `7d`     | 1 hour      |
| `30d`    | 6 hours     |
| `90d`    | 6 hours     |
| `6m`     | 24 hours    |
| `1y`     | 24 hours    |

## Rate Limits & Usage Requirements

- The Wiki API blocks generic User-Agents (such as `python-requests/*`) with HTTP 400.
- Always configure a descriptive `User-Agent` header. By default, the app sends `RS3-GE-Tracker/1.3 (personal price tracker; +contact configured in settings)`.
- Requests are throttled to at least 1 second between calls, and bulk endpoints (`/latest`, `/5m`, `/1h`) are used instead of per-item polling loops.
