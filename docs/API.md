# RS3 Real-Time Prices API — Research Notes

*Verified live on 2026-08-09 against the actual service. Do not trust older
docs/examples that reference `api/v1` or OSRS-only endpoints — RuneScape 3 now
has a first-class **v2** API.*

## Service

- Provider: RuneScape Wiki (Weird Gloop), same infrastructure that powers the
  OSRS real-time prices project.
- Reference page: <https://runescape.wiki/w/RuneScape:Real-time_Prices>
- **Base URL (RS3): `https://prices.runescape.wiki/api/v2/rs`**
  (OSRS lives at a different prefix; everything below is RS3.)

## Endpoints used by this application

### 1. `GET /mapping`
Item reference data for **all tradeable RS3 items** (~7,300 items, ~1.4 MB).

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
- `icon` is a wiki image filename → renderable at
  `https://runescape.wiki/images/<name with spaces as underscores>`.
- Fetched at startup and refreshed at most once per 24 h (cached locally).

### 2. `GET /latest` and `GET /latest?id={itemId}`
Most recent instant buy ("high") and sell ("low") trade per item.

```json
{"data": {"4151": {"high": 73604, "highTime": 1786249197,
                    "low": 71549, "lowTime": 1786249493}}}
```

- Timestamps are **Unix seconds (UTC)**.
- Prices are integer GP.
- Fields can be `null` if an item hasn't traded on that side recently.

### 3. `GET /5m` and `GET /5m?timestamp={unix}`
5-minute average prices/volumes for **every item that traded in that bucket**
(one request returns them all — ~700-1,000 items per bucket).

```json
{"timestamp": 1786249200,
 "data": {"2": {"avgHighPrice": 800, "highPriceVolume": 6000,
                 "avgLowPrice": 796, "lowPriceVolume": 3867}}}
```

- `timestamp` param must be aligned to a 300 s boundary; omitting it returns
  the most recent **completed** bucket. The bucket's own timestamp is echoed
  at the top level.
- `avgHighPrice` / `avgLowPrice` may be `null` (no trades on that side);
  volumes are then `0`.

### 4. `GET /1h` and `GET /1h?timestamp={unix}`
Same shape as `/5m` but hourly buckets (~2,800 items per bucket, aligned to
3600 s). This is the workhorse for whole-market history (Top Movers).

### 5. `GET /timeseries?id={itemId}&lookback={window}`
Price history for one item. **`lookback` (not `timestep`) is the parameter in
v2** — valid values: `6h`, `24h`, `7d`, `30d`, `6m`, `1y`.

```json
{"data": [{"timestamp": 1786164900, "avgHighPrice": 76235.5,
           "avgLowPrice": null, "highPriceVolume": 10, "lowPriceVolume": 0}]}
```

Measured bucket resolution per lookback (verified empirically):

| lookback | bucket size |
|----------|-------------|
| `6h`     | 5 min       |
| `24h`    | 5 min       |
| `7d`     | 1 hour      |
| `30d`    | 6 hours     |

Buckets with zero trades are simply absent (sparse series).

## Formats

- **Item IDs**: integers, identical across all endpoints.
- **Timestamps**: Unix epoch seconds, UTC, bucket-aligned.
- **Prices**: integer or float GP; `null` = no trades on that side.
- **Volume**: `highPriceVolume` + `lowPriceVolume` = units traded in bucket.

## Rate limits & usage requirements

- No hard published rate limit, but the wiki **blocks abusive traffic** and
  explicitly **blocks generic User-Agents** — verified: sending
  `python-requests/2.31` returns **HTTP 400**.
- Required: a descriptive User-Agent with contact info. This app sends
  `RS3-GE-Tracker/1.0 (personal price tracker; +contact configured in settings)`.
- Be polite: this app throttles to ≥1 request/second, uses caching, and never
  loops `/latest?id=` per item (the bulk endpoints return everything at once).

## Historical data availability

- `timeseries` provides up to 1 year lookback, but at coarse resolution for
  long windows. For a rolling 30-day chart the best obtainable seed is:
  30d @ 6 h buckets + last 7d @ 1 h + last 24h @ 5 min.
- **Limitation discovered:** the v2 RS3 service is comparatively new; some
  items' 30d lookback currently returns less than a full 30 days of history
  (~16 days observed for some items on 2026-08-09). The app therefore builds
  its own local history forward in time and back-fills whatever the API has.
- Full historical dumps are not offered by this service; the wiki's separate
  `api.weirdgloop.org` exchange API offers daily (not intraday) history and is
  not used here.

## How the app maps endpoints to features

| Feature | Endpoint(s) |
|---|---|
| Item database & search | `/mapping` (cached 24 h) |
| Live price on cards/search | `/latest` (bulk, every cycle) |
| Tracked-item chart history | seed via `/timeseries`, then `/5m` forward |
| Whole-market history (Top Movers) | `/1h` (hourly, incl. missed buckets via `?timestamp=`) |
| Incremental sync / gap fill | `/5m?timestamp=`, `/1h?timestamp=`, `/timeseries` |
