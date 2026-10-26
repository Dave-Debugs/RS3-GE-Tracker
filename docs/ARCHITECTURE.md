# Architecture

This document outlines the structure of **RS3 GE Tracker**, how price data is collected and stored locally, and how the backend and frontend modules interact.

## Overview

The application runs a local FastAPI backend paired with a SQLite database (`WAL` mode) and a React + TypeScript frontend. A background collector task runs inside the FastAPI lifespan to sync Grand Exchange item metadata, live instant-buy/sell quotes, 5-minute buckets for tracked items, and hourly buckets for market-wide volume and movers.

Layer responsibilities:
- `backend/app/api_client/client.py`: `RS3PriceClient` handles all HTTP communication with `prices.runescape.wiki/api/v2/rs`, including rate limiting, retries, and User-Agent headers.
- `backend/app/collector/collector.py` & `scheduler.py`: Runs periodic sync cycles, backfills newly tracked items and long-horizon chart windows (`90d`, `6m`, `1y`), evaluates price/margin/volume alerts and 4-hour GE slot timers, and dispatches desktop or Discord Webhook notifications.
- `backend/app/db/database.py` & `repository.py`: Manages the SQLite connection, schema migrations, and all SQL queries (prices, watchlist, portfolio, flip history, 8-slot GE board, recipes, alerts, scanners, and backups).
- `backend/app/services/`: Contains pure domain logic for statistical indicators (`analytics.py`), fuzzy search (`search.py`), CSV/JSON export (`export.py`), and GitHub release updates (`updater.py`).
- `backend/app/routes/`: FastAPI route handlers under `/api/*`.
- `frontend/src/`: React + TypeScript SPA using `@tanstack/react-query` for polling and caching and Apache ECharts for interactive charts.

## Data Model

All timestamps are stored as UTC Unix seconds.

| Table | Purpose | Notes |
|---|---|---|
| `items` | Item catalog from `/mapping` (~7.3k rows) | Refreshed once per 24h |
| `price_history` | Historical time series | `PRIMARY KEY (item_id, timestamp, source) WITHOUT ROWID` |
| `latest_prices` | Most recent instant buy (`high`) and sell (`low`) | Updated every collection cycle |
| `tracked_items` | User watchlist and item groups | `backfilled` flag triggers initial history seed |
| `portfolio` | Active item holdings | Tracks quantity and buy cost per item |
| `flip_history` | Realized flip ledger | Stores completed flips, 2% GE tax paid, and net profit |
| `ge_slots` | 8-slot Grand Exchange offer board | Tracks active buy/sell offers and 4-hour limit reset timestamps |
| `recipes` & `recipe_ingredients` | Custom crafting/potion recipes | Evaluated in both Patient and Instant execution modes |
| `alerts` | Price, net-margin, and volume alerts | Supports recurring cooldowns and Discord webhooks |
| `sync_state` | Last ingested bucket timestamp per resolution | Drives incremental `/5m` and `/1h` syncing |
| `collection_runs` | Per-cycle audit log | Records inserted/skipped/deleted row counts and errors |
| `settings` | User preferences | Stored as key/value pairs |

## Collection Cycle

Each `Collector.run_cycle()` performs the following steps:
1. Refresh `/mapping` if the local item catalog is older than 24 hours.
2. Fetch bulk `/latest` quotes and update `latest_prices`.
3. Backfill any newly tracked items (`backfilled = 0`) using `/timeseries`.
4. Fetch missed `/5m` buckets (capped per cycle) and store rows for tracked items.
5. Fetch missed `/1h` buckets (capped per cycle) and store rows across all items.
6. Evaluate active alerts (`either`, `high`, `low`, `net_margin`, `volume_24h`) and 8-slot GE 4-hour buy limit timers.
7. Prune expired intraday rows while retaining daily history up to 370 days for `90d`, `6m`, and `1y` charts.
8. Record run metrics in `collection_runs`.
