# Backend REST API Reference

The local FastAPI backend serves everything under `http://localhost:8000/api`.
Interactive Swagger docs are always available at
[http://localhost:8000/docs](http://localhost:8000/docs) — this page is the
stable reference with real examples. (For the *upstream* RuneScape Wiki API
the app consumes, see [API.md](API.md).)

All responses are JSON unless noted. There is no authentication — the server
binds to localhost and is intended for local use only. Timestamps are Unix
seconds (UTC). All example responses below were captured from a running
instance.

## Conventions and errors

Validation failures return `422` and unknown items return `404`, both shaped
like FastAPI's standard error body:

```json
{ "detail": "Unknown item id 999999" }
```

| Status | Meaning |
|---|---|
| 200 / 201 | success |
| 404 | unknown `item_id`, or item not tracked |
| 422 | invalid parameter (bad range, period, interval, format…) |
| 500 | unexpected server error (check `logs/rs3_tracker.log`) |

`range` parameters accept exactly `24h`, `7d`, `14d`, `30d`.

---

## Health and status

### `GET /api/health`

Liveness probe. → `{ "status": "ok" }`

### `GET /api/status`

Dashboard header data: API/collector state, sync times, database counters.

```json
{
  "api_online": true,
  "collector_running": true,
  "last_update": 1786251349,
  "next_update": 1786251648,
  "last_run_ok": true,
  "last_run_error": null,
  "tracked_items": 6,
  "database_records": 67692,
  "data_coverage_days": 16.7,
  "item_count": 7310,
  "server_time": 1786251448
}
```

`api_online` means the most recent collection cycle succeeded within the last
2 hours. When `false`, the UI shows its "displaying cached data" banner —
every read endpoint keeps working from the local database.

### `POST /api/status/collect-now`

Wakes the collector immediately (also used internally after tracking an
item). → `{ "triggered": true }`, or
`{ "triggered": false, "reason": "collector not running" }`.

---

## Items and search

### `GET /api/items/search?q={query}&limit={n}`

Search by partial name, exact name, item ID, or fuzzy match (typo-tolerant),
in that ranking order. `limit` defaults to 25, max 100. Empty/short queries
return an empty result set rather than an error.

`GET /api/items/search?q=whip&limit=2`:

```json
{
  "query": "whip",
  "results": [
    {
      "item_id": 21369,
      "name": "Whip vine",
      "description": "Use on an abyssal whip for added oomph!",
      "members": true,
      "icon_url": "/api/icon/21369",
      "buy_limit": 1,
      "current_price": 225000
    },
    {
      "item_id": 4151,
      "name": "Abyssal whip",
      "description": "A weapon from the Abyss.",
      "members": true,
      "icon_url": "/api/icon/4151",
      "buy_limit": 10,
      "current_price": 71978
    }
  ]
}
```

`current_price` is the midpoint of the latest instant buy/sell, `null` if the
item hasn't traded recently.

### `GET /api/items/{item_id}`

Single item summary (same shape as a search result, minus `current_price`).
`404` if the ID is unknown.

### `GET /api/icon/{item_id}`

The item's icon as `image/png`, proxied from the wiki once and cached on disk
(`database/icon_cache/`). Always returns an image — a transparent 1×1 PNG if
the icon can't be fetched — so `<img>` tags never break.

---

## Tracked items

### `GET /api/tracked`

The watchlist with per-item live stats, sorted favorites-first then by name.

```json
{
  "tracked": [
    {
      "item_id": 4151,
      "name": "Abyssal whip",
      "icon_url": "/api/icon/4151",
      "members": true,
      "favorite": false,
      "current_price": 71978,
      "change_24h": -5.58,
      "change_7d": -3.73,
      "change_30d": -7.72,
      "trend": "Neutral",
      "volume_24h": 1337,
      "last_updated": 1786251005,
      "backfilled": true
    }
  ]
}
```

`backfilled: false` means history seeding is still pending (it completes on
the next collector kick, typically within seconds of tracking). Change fields
are percentages and may be `null` when there is no reference price that far
back.

### `POST /api/tracked` — body `{ "item_id": 4151 }`

Starts tracking. Returns `201` with `{ "item_id": 4151, "added": true }`
(`"added": false` if it was already tracked — idempotent). Triggers an
immediate collection cycle so backfill starts right away. `404` for unknown
IDs.

### `DELETE /api/tracked/{item_id}`

Stops tracking. → `{ "item_id": 4151, "removed": true }`; `404` if not
tracked. Collected history rows are kept until retention ages them out.

### `PUT /api/tracked/{item_id}/favorite` — body `{ "favorite": true }`

Pins the item to the top of the list. `404` if not tracked.

---

## Prices and charts

### `GET /api/prices/{item_id}?range={range}&ma={list}`

The chart series. Sources are merged (finest resolution wins per timestamp)
and downsampled to ≤ ~1,100 points. `ma` is an optional comma list from
`1h`, `6h`, `24h`, `7d`; each requested moving average comes back as its own
series, computed over full history so the first charted points already have
context.

`GET /api/prices/4151?range=24h&ma=1h` (truncated):

```json
{
  "item_id": 4151,
  "name": "Abyssal whip",
  "range": "24h",
  "points": [
    {
      "timestamp": 1786165200,
      "high_price": 78682.6,
      "low_price": 75000.0,
      "average_price": 76841.3,
      "volume": 9
    },
    {
      "timestamp": 1786165500,
      "high_price": 74471.0,
      "low_price": null,
      "average_price": 74471.0,
      "volume": 1
    }
  ],
  "moving_averages": {
    "1h": [
      { "timestamp": 1786165200, "value": 76946.54 },
      { "timestamp": 1786165500, "value": 75849.27 }
    ]
  }
}
```

`high_price`/`low_price` are the average instant-buy/instant-sell for the
bucket; either can be `null` when only one side traded (then
`average_price` equals the side that exists). `422` for a bad `range` or an
unknown `ma` key.

---

## Statistics and trends

### `GET /api/stats/{item_id}`

Descriptive statistics over the item's recorded 30-day window.

```json
{
  "item_id": 4151,
  "current_price": 70352.0,
  "change_24h": -7.72,
  "change_7d": -5.9,
  "change_30d": -9.8,
  "high_30d": 95000.0,
  "low_30d": 37353.18,
  "average_30d": 77212.88,
  "median_30d": 77133.96,
  "volatility_30d": 8.207,
  "total_volume": 15980,
  "points": 368
}
```

`volatility_30d` is the standard deviation of point-to-point returns, in
percent. All price fields are `null` and `points` is `0` for an item with no
recorded history yet.

### `GET /api/trends/{item_id}`

The trend classification plus every number behind it (see
[ARCHITECTURE.md](ARCHITECTURE.md) for the scoring formula — this is
descriptive, not predictive).

```json
{
  "item_id": 4151,
  "classification": "Neutral",
  "slope_pct_per_day": -0.206,
  "short_ma": 76769.55,
  "long_ma": 76927.33,
  "momentum_pct": 17.25,
  "volatility_pct": 8.207,
  "r_squared": 0.008,
  "points_used": 368
}
```

`classification` is one of `Strongly Rising`, `Rising`, `Neutral`,
`Falling`, `Strongly Falling`.

---

## Top Movers

### `GET /api/movers?period={24h|7d|30d}&limit={n}`

Market-wide gainers, losers, and highest 24h volume, computed from hourly
whole-market data. Items are filtered for liquidity (price ≥ 100 gp at both
endpoints of the comparison, ≥ 2,000 units traded in 24h) so dead-item
manipulation spikes don't dominate. `limit` defaults 10, max 50.

`GET /api/movers?period=24h&limit=1` (truncated):

```json
{
  "period": "24h",
  "gainers": [
    {
      "item_id": 25800,
      "name": "Black dragonhide shield",
      "icon_url": "/api/icon/25800",
      "current_price": 256679,
      "previous_price": 8715,
      "change_pct": 2845.4,
      "volume_24h": 80218
    }
  ],
  "losers": [
    {
      "item_id": 199,
      "name": "Grimy guam",
      "current_price": 256,
      "previous_price": 46563,
      "change_pct": -99.45,
      "volume_24h": 37086
    }
  ],
  "highest_volume": [
    {
      "item_id": 12183,
      "name": "Spirit shards",
      "current_price": 24,
      "volume_24h": 324887352
    }
  ]
}
```

`7d`/`30d` periods need the app to have been collecting hourly data that far
back; until then their lists are short or empty (24h works from first run).

---

## Settings

### `GET /api/settings`

```json
{
  "update_interval_minutes": "5",
  "theme": "dark",
  "default_chart_range": "30d",
  "user_agent": "RS3-GE-Tracker/1.0 (personal price tracking app; ...)",
  "collector_autostart": "true",
  "database_path": ".../database/rs3_tracker.db"
}
```

All values are strings. `database_path` is informational (read-only; set via
the `RS3_DB_PATH` environment variable before startup).

### `PUT /api/settings`

Partial update — send only the keys you're changing; returns the full merged
settings. Validation per key: `update_interval_minutes` ∈
`5|10|15|30|60`, `theme` ∈ `dark|light`, `default_chart_range` ∈
`24h|7d|14d|30d`, `collector_autostart` ∈ `true|false`, `user_agent` length
10–300. Invalid values → `422`; an empty body → `422`. A changed interval
takes effect from the next cycle; `collector_autostart` takes effect at next
startup.

---

## Export

### `GET /api/export/{item_id}?format={csv|json}&range={range}`

Downloads the item's merged history as a file
(`Content-Disposition: attachment`).

CSV columns (Excel / Google Sheets / pandas-friendly, CRLF line endings,
ISO-8601 UTC timestamps):

```csv
timestamp,item_id,item_name,high_price,low_price,average_price,volume
2026-08-02 05:00:00,4151,Abyssal whip,77370.95,72001.0,74685.975,23
```

JSON shape: `{ "item_id", "item_name", "points": [{ "timestamp",
"datetime_utc", "high_price", "low_price", "average_price", "volume" }] }`.

`format` other than `csv`/`json` → `422`. Load into pandas with
`pd.read_csv(url_or_file, parse_dates=["timestamp"])`.
