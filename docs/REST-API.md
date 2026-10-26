# Backend REST API Reference

The local FastAPI backend serves endpoints under `http://localhost:8000/api`. Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

## Conventions

- All responses are JSON unless otherwise noted (such as `/api/icon/{item_id}` and `/api/export/{item_id}`).
- Timestamps are UTC Unix seconds.
- `range` parameters accept `1h`, `6h`, `24h`, `7d`, `14d`, `30d`, `90d`, `6m`, and `1y`.

---

## Health & Status

### `GET /api/health`
Returns `{ "status": "ok" }`.

### `GET /api/status`
Returns collector health, sync timestamps, and database row counts:

```json
{
  "api_online": true,
  "collector_running": true,
  "last_update": 1700001349,
  "next_update": 1700001648,
  "last_run_ok": true,
  "last_run_error": null,
  "tracked_items": 6,
  "database_records": 67692,
  "data_coverage_days": 30.0,
  "item_count": 7310,
  "server_time": 1700001448
}
```

### `POST /api/status/collect-now`
Triggers an immediate background collection cycle.

---

## Items & Search

### `GET /api/items/search?q={query}&limit={n}`
Searches the item catalog by exact name, item ID, prefix, substring, or typo-tolerant fuzzy match.

### `GET /api/items/{item_id}`
Returns metadata for a single item (`404` if unknown).

### `GET /api/icon/{item_id}`
Proxies and caches the item's PNG icon in `database/icon_cache/`.

---

## Tracked Watchlist

### `GET /api/tracked`
Returns all tracked items with live buy/sell quotes, net profit after the 2% GE tax, 4h limit profit, 24h/7d percentage changes, and trend classification.

### `POST /api/tracked`
Body: `{ "item_id": 4151 }`. Adds an item to the watchlist and triggers historical backfill.

### `DELETE /api/tracked/{item_id}`
Removes an item from the watchlist.

### `PUT /api/tracked/{item_id}/favorite`
Body: `{ "favorite": true }`. Pins or unpins a tracked item.

### `PUT /api/tracked/{item_id}/group`
Body: `{ "group_name": "PvM Gear" }`. Assigns a tracked item to a custom group.

---

## Prices, Statistics & Trends

### `GET /api/prices/{item_id}?range={range}&ma={list}`
Returns merged, LTTB-downsampled price points, optional moving averages (`1h`, `6h`, `24h`, `7d`), Bollinger Bands (`±2σ`), VWAP, and Z-score price/volume anomalies. Automatically backfills long ranges (`90d`, `6m`, `1y`) on demand.

### `GET /api/stats/{item_id}`
Returns descriptive statistics for the item (`current_price`, `change_24h`, `change_7d`, `high_7d`, `low_7d`, `average_7d`, `median_7d`, `vwap_7d`, `volatility_7d`, `total_volume`, and `anomalies`).

### `GET /api/trends/{item_id}`
Returns the regression slope, short/long moving averages, momentum, volatility, $R^2$, and trend classification (`Strongly Rising`, `Rising`, `Neutral`, `Falling`, `Strongly Falling`).

---

## Market Scanners

### `GET /api/scanner/flips`
Query params: `min_price`, `max_price`, `min_volume`, `members`, `sort_by` (`limit_profit`, `net_profit`, `roi`, `volume`, `liquidity`), `limit`.

### `GET /api/scanner/alch`
Query params: `min_volume`, `members`, `mode` (`manual` or `machine`), `sort_by`, `limit`.

### `GET /api/scanner/recipes`
Query params: `execution_mode` (`patient` or `instant`), `min_volume`, `sort_by`, `limit`.

---

## Portfolio, Flip Ledger & 8-Slot GE Board

- `GET /api/portfolio`: Returns active holdings with gross value, 2% GE tax, and net liquidation P&L.
- `POST /api/portfolio`: Adds a holding (`item_id`, `quantity`, `buy_price_per_item`).
- `POST /api/portfolio/{port_id}/close`: Closes a full or partial position and logs the realized trade into `flip_history`.
- `GET /api/portfolio/history` & `POST /api/portfolio/history`: Lists or logs completed flips in the Realized Flip Ledger.
- `GET /api/ge-slots`, `PUT /api/ge-slots/{slot_index}`, `POST /api/ge-slots/{slot_index}/complete`, `DELETE /api/ge-slots/{slot_index}`: Manages the 8 active Grand Exchange slots and 4-hour buy limit timers.

---

## Recipes, Alerts, Settings & Backup

- `GET /api/recipes`, `POST /api/recipes`, `DELETE /api/recipes/{id}`: Custom crafting/combination recipes with Patient and Instant mode margins.
- `GET /api/alerts`, `POST /api/alerts`, `PUT /api/alerts/{id}`, `DELETE /api/alerts/{id}`: Price, net-margin, and 24h-volume alerts with cooldowns.
- `GET /api/settings` & `PUT /api/settings`: Reads or updates application settings (`update_interval_minutes`, `theme`, `default_chart_range`, `user_agent`, `collector_autostart`, `show_tooltips`, `discord_webhook_url`).
- `GET /api/backup/export` & `POST /api/backup/import`: Exports or restores a JSON snapshot of the user's workspace (`tracked_items`, `portfolio`, `flip_history`, `ge_slots`, `recipes`, `alerts`, `settings`).
