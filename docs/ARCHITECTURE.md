# Architecture

This document explains how the RS3 GE Tracker is put together, why it is built
that way, and where future features are meant to plug in. For what the app
does and how to run it, see the [README](../README.md); for the upstream data
source, see [API.md](API.md); for the local backend's endpoints, see
[REST-API.md](REST-API.md).

## Context and goals

The app exists to keep a reliable rolling 14-day local history of RuneScape 3
Grand Exchange prices and make it explorable through interactive charts. The
upstream service only offers coarse resolution for long lookbacks and (at the
time of writing) limited RS3 history, so the core job of this system is to
*accumulate* fine-grained data forward in time, politely and incrementally,
and never lose it to an API outage. Everything else — search, stats, trends,
movers — is derived read-side functionality on top of that store.

Design goals, in priority order: data collection must be reliable and
API-polite; the app must keep working (read-only) when the API is down; disk
usage must stay bounded; and the codebase must accept the planned v2 features
(alerts, flip tracking, portfolios) without restructuring.

## High-level design

```
                        ┌─────────────────────────────────────────────┐
                        │  RuneScape Wiki RS3 prices API (external)   │
                        │  prices.runescape.wiki/api/v2/rs            │
                        └──────────────────┬──────────────────────────┘
                                           │ HTTPS (throttled ≥1s/req,
                                           │ retries + backoff, UA required)
        backend process (uvicorn)          │
┌──────────────────────────────────────────┼─────────────────────────────┐
│                                          ▼                             │
│   app/api_client/client.py    RS3PriceClient — the ONLY code that      │
│                               talks to the wiki. TTL cache, request    │
│                               counting, error normalization (ApiError) │
│                                          │                             │
│   app/collector/collector.py  Collector.run_cycle() — mapping refresh, │
│   app/collector/scheduler.py  latest, incremental 5m/1h sync, item     │
│        (async task in the     backfill, 14-day retention, run stats    │
│         FastAPI lifespan)                │                             │
│                                          ▼                             │
│   app/db/database.py          SQLite, WAL mode, schema DDL             │
│   app/db/repository.py        ALL SQL lives here (no SQL elsewhere)    │
│                                          ▲                             │
│                                          │ reads                       │
│   app/services/               analytics (stats/trends/MA/merge),      │
│                               search (SQL + fuzzy), export (csv/json)  │
│                                          ▲                             │
│   app/routes/                 thin FastAPI routers: items, tracked,    │
│                               prices, stats, movers, settings, status, │
│                               export, icons                            │
└──────────────────────────────────────────┼─────────────────────────────┘
                                           │ HTTP :8000 (/api/*)
                                           ▼
                    frontend/ (Vite dev server :5173, proxies /api)
                    React + TypeScript, ECharts chart, App.tsx owns state
```

The dependency direction is strictly downward: routes → services →
repository → database, and collector → client + repository. Routes never
touch SQL or the wiki API; the client never touches the database. This is
what makes the pieces independently testable and replaceable.

## Data model

SQLite in WAL mode so the collector (single writer) and API handlers (many
readers) don't block each other. All timestamps are Unix seconds, UTC.

| Table | Purpose | Key design point |
|---|---|---|
| `items` | catalogue from `/mapping` (~7.3k rows) | refreshed ≤ once/24h |
| `price_history` | the time series | PK `(item_id, timestamp, source)`, `WITHOUT ROWID`; indexes on `item_id`, `timestamp`, `(item_id, timestamp)` |
| `latest_prices` | most recent instant buy/sell per item | overwritten each cycle, not history |
| `tracked_items` | watchlist | `backfilled` flag drives one-shot seeding |
| `sync_state` | key/value: last ingested bucket per resolution | the heart of incremental sync |
| `collection_runs` | per-cycle stats (inserted/skipped/deleted/requests/error) | powers the status endpoint and debugging |
| `settings` | user-tunable settings | defaults live in `config.py`, overrides here |

The `source` column (`5m`, `1h`, `ts6h`, plus the same values written by
backfill) is part of the primary key on purpose: the same wall-clock
timestamp legitimately exists at several resolutions, and `INSERT OR IGNORE`
against that key is the entire duplicate-prevention mechanism — idempotent by
construction, so re-fetching a bucket is always safe.

## Key decisions and trade-offs

**Storage budget: two tiers of resolution.** Storing 5-minute data for all
~7,300 items would be ~60M rows per 14 days — far too much for the value.
Instead, 5-minute rows are kept only for *tracked* items, while hourly rows
are kept for *every* item (~2M rows/14 days worst case). The hourly tier is
what makes market-wide features (Top Movers) possible; the 5-minute tier is
what makes tracked-item charts detailed. Trade-off: an item only gains
fine-grained history after you track it — mitigated by the timeseries
backfill, which immediately seeds 14d/7d/24h at the best resolution the API
offers.

**Incremental sync via bucket timestamps, not row diffing.** The API's `/5m`
and `/1h` accept a `?timestamp=` for any past bucket. `sync_state` remembers
the last ingested bucket per resolution; a cycle fetches exactly the missing
buckets and nothing else. Catch-up after downtime is capped (12 five-minute,
6 hourly buckets per cycle) so a laptop waking from a week of sleep produces
a handful of requests, not a storm; tracked items heal older gaps through
backfill instead. Trade-off: untracked items simply have a gap for extended
downtime — accepted, since nothing user-visible depends on complete hourly
history for untracked items.

**Collector lives inside the FastAPI process.** An async task started from
the lifespan hook, running cycles in a thread (`asyncio.to_thread`) because
SQLite and httpx-sync are blocking. This gives "start one thing and
everything works" — no service manager, no IPC. The standalone
`scripts/run_collector.py` reuses the identical `Collector` for headless
collection. Trade-off: running both at once would double-poll the API; since
inserts are idempotent this corrupts nothing, but the README tells users to
run one or the other.

**Merged read-side series.** Chart queries pull all sources in the window and
`merge_sources()` collapses same-timestamp rows preferring the finest
resolution (5m > 1h > ts6h), then `downsample()` thins to ~1,100 points.
Trade-off: mixed-density series (6h buckets early, 5m recent) — visually
fine, and honest about what data actually exists.

**Icons proxied, not hotlinked.** Browsers can be blocked by the wiki's CDN
protections; `/api/icon/{item_id}` fetches once with the proper User-Agent
and caches on disk forever. The frontend never talks to the wiki at all —
the backend is the single egress point for the whole app.

**SQLite over a server database.** Zero-install, single-file backup, WAL
concurrency is plenty for one writer + local readers. Revisit only if
multiple machines must share one database (a v2 cloud-sync concern).

**Descriptive trends, not predictions.** The trend score is
`0.7 × regression slope (%/day) + 0.3 × MA-crossover gap (%)`, thresholded at
±0.35 / ±2.0 into five classes. The API exposes every input number
(slope, R², momentum, volatility, MAs) so the UI can show its work. This is
deliberately simple and labeled descriptive; ML experiments are a v2 item.

## A collection cycle, step by step

`Collector.run_cycle()` (see `backend/app/collector/collector.py`):

1. Refresh `/mapping` if older than 24h.
2. One bulk `/latest` request → overwrite `latest_prices`.
3. Backfill any tracked item with `backfilled=0` from `/timeseries`
   (14d→`ts6h`, 7d→`1h`, 24h→`5m`), then set the flag.
4. Fetch missed 5-minute buckets (capped), keep rows for tracked items only.
5. Fetch missed hourly buckets (capped; first run ever seeds 24 buckets so
   Top Movers works on day one), keep rows for all items.
6. Delete `price_history` rows older than 14 days.
7. Write a `collection_runs` row and update `sync_state`.

Failures at any step are caught, logged, recorded on the run row, and the
next cycle starts clean — an API outage can never kill the scheduler loop.

## Frontend state model

`App.tsx` is the single owner of cross-component state (tracked list,
selected chart items, focused item, range/mode/overlay toggles, settings,
status). Children are presentational and call back up. Data flows are
poll-based: status + tracked refresh every 60s; chart/stats refetch on
selection or range change. No state library — at this component count,
lifting state to one component is simpler than introducing Redux/Zustand;
revisit if the component tree deepens materially in v2.

## Extension points (v2 roadmap)

The seams where planned features attach, with no restructuring expected:

*Price alerts / notifications* — new `alerts` table + repository methods; a
check at the end of `run_cycle()` (all fresh prices are in hand there);
delivery adapters (desktop toast, Discord webhook) as a new
`services/notify.py`; CRUD router in `routes/`.

*Flip/profit/portfolio tracking* — pure additions: `trades` table, a
`services/portfolio.py` computing P&L against `price_history`, new routes and
a frontend panel. GE tax math belongs in `services/` beside analytics.

*More indicators (RSI, Bollinger, …)* — add functions in
`services/analytics.py` following `moving_average()`'s shape
(`points → [{timestamp, value}]`), expose via the existing `ma=`-style query
parameter pattern on `/api/prices/{id}`.

*Cloud sync / multiple accounts* — the repository interface is the boundary:
everything above `db/repository.py` is storage-agnostic, so a remote-capable
implementation can replace it wholesale.

## What to revisit as it grows

The 60-second full-refresh polling in the frontend is wasteful once panels
multiply — switch to server-sent events pushed at cycle end. `merge_sources`
and stats run per request with no cache — fine at 6 tracked items; add a
small TTL cache keyed on `(item, range)` if watchlists reach hundreds.
`collection_runs` grows ~288 rows/day and is never pruned — harmless for
years, but retention there is a one-line addition to step 6.
