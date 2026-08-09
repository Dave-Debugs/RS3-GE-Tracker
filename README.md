# RS3 Grand Exchange Tracker

A local, self-hosted market analytics app for **RuneScape 3** Grand Exchange
prices. It automatically collects price data from the RuneScape Wiki's
real-time prices API, keeps a rolling **30-day** history in SQLite, and gives
you an interactive dark-themed dashboard with multi-item comparison charts,
statistics, trend classification, and Top Movers.

> Not affiliated with Jagex. Price data © the RuneScape Wiki real-time prices
> project — please keep the descriptive User-Agent so their service can
> identify this app.

---

## What it does

- **Automatic collection** — a background collector polls the RS3 price API on
  a configurable interval (5/10/15/30/60 min) with throttling, retries,
  exponential backoff, caching, and duplicate prevention.
- **Rolling 30-day history** — new data in, data older than 30 days out, on
  every cycle. The database never grows unbounded.
- **Incremental sync** — only *missing* 5-minute / hourly buckets are fetched
  (the API's `?timestamp=` parameters), never the whole history again. Newly
  tracked items are seeded from the API's own timeseries (30d/7d/24h).
- **Item search** — partial, exact, item-ID, and fuzzy (typo-tolerant) search
  across all ~7,300 tradeable RS3 items.
- **Tracked items** — watchlist with live price, 24H/7D/30D change, trend
  badge, 24H volume, favorites, and per-row chart toggles.
- **Interactive chart** — zoom, pan, hover tooltips with exact timestamp/GP,
  ranges 24H/7D/14D/30D, optional volume bars, instant buy/sell bands, and
  1h/6h/24h/7d moving averages.
- **Two comparison modes** — *Actual Price* (GP) and *% Change* (all items
  normalized to 0% at the window start, so an 800 gp Cannonball and a 120M gp
  Bond can be compared on one chart).
- **Statistics & trends** — 30D high/low/average/median/volatility, volume,
  and a descriptive trend classification (Strongly Rising → Strongly Falling)
  built from linear regression + moving-average crossover, with the underlying
  numbers shown. It describes history; it does not predict the future.
- **Top Movers** — market-wide biggest gainers/losers (24H/7D/30D) and highest
  volume, from hourly whole-market data; click any item to chart it.
- **Export** — CSV (Excel/Sheets/pandas-friendly) and JSON per item.
- **Graceful degradation** — if the API is down you see
  "API temporarily unavailable — displaying cached data", never a crash.

## Documentation

| Doc | Read it when you want… |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | the system design, data model, key decisions, and where v2 features plug in |
| [docs/REST-API.md](docs/REST-API.md) | the local backend's endpoints with real request/response examples |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | a codebase tour, add-a-feature walkthroughs, and testing patterns |
| [docs/API.md](docs/API.md) | the upstream RuneScape Wiki price API research (endpoints, formats, limits) |

## Architecture

```
RuneScape Wiki RS3 price API  (prices.runescape.wiki/api/v2/rs — see docs/API.md)
        │  polled by
        ▼
backend/app/collector      background scheduler + incremental sync + retention
        │  writes
        ▼
database/rs3_tracker.db    SQLite (WAL): items, price_history, latest_prices,
        │                  tracked_items, sync_state, collection_runs, settings
        ▼
backend/app (FastAPI)      REST API: search, tracked, prices, stats, trends,
        │                  movers, settings, status, export, icon proxy
        ▼
frontend/ (React + TS)     Vite dev server → dashboard with ECharts graphs
```

Layers are cleanly separated: `api_client` (HTTP), `db` (schema + all SQL),
`collector` (sync logic), `services` (analytics/search/export), `routes`
(HTTP endpoints), `frontend` (UI). Future features (alerts, flip tracking,
portfolios…) plug in as new services/routes without touching the collector.

## Requirements

- **Python 3.11+** (3.10 works) — https://python.org (check "Add to PATH")
- **Node.js 18+** — https://nodejs.org
- Windows, macOS, or Linux. No database server needed (SQLite is embedded).

## Installation (Windows)

```bat
scripts\setup.bat        :: installs Python + Node dependencies
scripts\start_all.bat    :: starts backend + frontend, opens the dashboard
```

That's it. The dashboard is at **http://localhost:5173**, the API at
http://localhost:8000 (interactive docs at http://localhost:8000/docs).

### Manual start

```bash
# backend (from backend/):
python -m uvicorn app.main:app --port 8000
# frontend (from frontend/):
npm run dev
```

### Docker (optional)

```bash
docker compose up
```

## First run

1. On startup the collector downloads the item catalogue (~7,300 items) and
   seeds the last 24 h of market-wide hourly data (~25 API requests, once).
2. Search an item → **+ Track**. Tracking triggers an immediate backfill of
   that item's history from the API's timeseries (up to 30 days at the best
   available resolution).
3. From then on everything updates automatically at your chosen interval.

## How the collector works

Every cycle it: refreshes the item mapping (≤1×/day) → fetches `/latest`
(bulk, one request) → fetches only the **missed** 5-minute buckets (stored for
tracked items) → fetches only the missed hourly buckets (stored for **all**
items — powers Top Movers) → backfills any newly tracked items via
`/timeseries` → deletes rows older than 30 days → records run statistics.
Catch-up after downtime is capped per cycle so it can never hammer the API;
older gaps for tracked items heal via timeseries backfill.

Collection continues while the dashboard is closed as long as the backend is
running. To collect without the web server at all:
`python scripts/run_collector.py` (or `scripts\start_collector.bat`).
"Start collector automatically" can be toggled in Settings.

## Database

SQLite file at **`database/rs3_tracker.db`** (created automatically; override
with the `RS3_DB_PATH` env var). Tables: `items`, `price_history` (PK
`item_id+timestamp+source` prevents duplicates; indexed on `item_id`,
`timestamp`, and both), `latest_prices`, `tracked_items`, `sync_state`,
`collection_runs`, `settings`. Retention is 30 days (internally configurable
via `RS3_RETENTION_DAYS`; the UI is designed around 30).

## API configuration

The app uses the RuneScape Wiki real-time prices API for RS3 —
**`https://prices.runescape.wiki/api/v2/rs`** — endpoints `/mapping`,
`/latest`, `/5m`, `/1h`, `/timeseries`. Full research notes, verified response
shapes, and rate-limit/User-Agent requirements: **[docs/API.md](docs/API.md)**.
The User-Agent is editable in Settings — keep it descriptive; the API returns
HTTP 400 to generic agents (verified).

## Testing

```bash
cd backend
python -m pytest tests -v
```

53 tests cover the API client (mocked transport — no live API needed),
database (insert/dedupe/retention/30-day filtering), collector (initial +
incremental sync, catch-up caps, backfill, failure recovery), analytics
(price changes, stats, regression, trend classes, moving averages), search
(partial/exact/ID/fuzzy), and every REST route including export and error
paths.

## Building for Windows (production)

```bash
cd frontend && npm run build      # outputs frontend/dist
```

Serve `frontend/dist` with any static server (or add a StaticFiles mount to
FastAPI) and run the backend with
`python -m uvicorn app.main:app --port 8000`. For auto-start on login, put a
shortcut to `scripts\start_backend.bat` in `shell:startup`.

## Troubleshooting

- **"API OFFLINE" in the header** — the wiki API is unreachable or the last
  cycle failed. The dashboard keeps serving cached data; check
  `logs/rs3_tracker.log` for the exact error. The collector retries
  automatically each interval.
- **HTTP 400 from the API** — your User-Agent is too generic. Restore a
  descriptive one in Settings.
- **No chart after tracking an item** — backfill happens on the next
  collector kick (triggered automatically within seconds). Low-volume items
  (e.g. party hats) genuinely have very few data points.
- **Top Movers looks thin for 7D/30D** — market-wide history accumulates
  from the moment you first run the app (the API's timeseries endpoint is
  per-item, so whole-market history can't be backfilled in bulk politely).
  24H movers work from day one.
- **Port already in use** — something else is on 8000/5173; stop it or change
  the port in `scripts/start_backend.bat` and `frontend/vite.config.ts`
  (proxy target too).
- **Windows says "python not found"** — reinstall Python with
  "Add python.exe to PATH" checked, or use `py -m uvicorn ...`.

## Known limitations (v1)

- The RS3 real-time price service is newer than the OSRS one; at the time of
  writing its `30d` timeseries returned ~16 days of history for many items, so
  a brand-new install may show less than a full 30 days until the app has run
  long enough to build its own.
- Prices are 5-minute/hourly *averages* of instant-buy/sell trades (that's
  what the API provides), not the exact guide price shown in-game.
- Top Movers 7D/30D need the app to have been collecting for that long.
- One collector at a time: run either the backend (which embeds it) or
  `run_collector.py`, not both simultaneously.
