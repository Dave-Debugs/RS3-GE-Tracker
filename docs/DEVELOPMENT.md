# Developer Guide

How to find your way around the codebase, make changes safely, and test them.
Assumes you've read the [README](../README.md) quick start. Companion docs:
[ARCHITECTURE.md](ARCHITECTURE.md) for the *why* behind the structure,
[REST-API.md](REST-API.md) for the backend's endpoints, and
[API.md](API.md) for the upstream wiki API.

## Environment setup

```bash
# backend
cd backend
pip install -r requirements.txt
python -m pytest tests -q          # 53 tests, ~1s, no network needed
python -m uvicorn app.main:app --port 8000 --reload

# frontend (second terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173, proxies /api → :8000
```

`--reload` gives backend hot-reload; Vite hot-reloads the frontend. The
SQLite file appears at `database/rs3_tracker.db` on first backend start. To
develop against a scratch database, set `RS3_DB_PATH=/tmp/dev.db` before
starting. Delete the DB file any time — everything re-syncs.

## Codebase tour

```
backend/app/
  config.py             constants + user-setting defaults. Change knobs here.
  main.py               app factory + lifespan (wires db/client/collector)
  deps.py               FastAPI dependencies (repo, scheduler from app.state)
  api_client/client.py  the ONLY code that calls the wiki API
  collector/collector.py  sync logic (cycle steps, backfill, retention)
  collector/scheduler.py  async loop that runs cycles on the interval
  db/database.py        connection + schema DDL (add new tables here)
  db/repository.py      ALL SQL (add new queries here, nowhere else)
  services/analytics.py stats, regression, trend classes, MAs, merge/downsample
  services/search.py    search ranking + fuzzy fallback
  services/export.py    CSV/JSON serialization
  routes/*.py           one thin router per feature area
backend/tests/
  conftest.py           MockAPI transport + db/repo/collector/client fixtures
  test_*.py             one file per layer
frontend/src/
  App.tsx               all cross-component state + data fetching
  api.ts                typed fetch wrappers (mirror of REST-API.md)
  types.ts              TS mirrors of backend response shapes
  lib/format.ts         GP/percent/time formatting
  components/           presentational components (chart, lists, panels)
```

The layering rule that keeps this maintainable: **routes call services and
the repository; services call the repository; only `api_client` touches the
wiki; only `repository` contains SQL.** If you find yourself writing SQL in a
route or an HTTP call in a service, you're in the wrong file.

## Common tasks

### Add a backend endpoint

Worked example — "average daily volume" endpoint:

1. Query in `db/repository.py` (if the data isn't already reachable):

```python
def daily_volume(self, item_id: int, since: int) -> list[dict]:
    rows = self.db.conn.execute(
        """SELECT timestamp/86400*86400 AS day, SUM(volume) AS v
           FROM price_history WHERE item_id=? AND source='1h' AND timestamp>=?
           GROUP BY day ORDER BY day""", (item_id, since)).fetchall()
    return [dict(r) for r in rows]
```

2. Route in the matching `routes/` module (or a new module — then register it
   in the router loop in `main.py`):

```python
@router.get("/volume/{item_id}")
def volume(item_id: int, repo: Repository = Depends(get_repo)) -> dict:
    if not repo.get_item(item_id):
        raise HTTPException(404, f"Unknown item id {item_id}")
    return {"days": repo.daily_volume(item_id, int(time.time()) - 30*86400)}
```

3. Test in `tests/test_routes.py` using the `api` fixture (it seeds a mock
   database — see "Testing patterns" below), and a repository test if the
   query has any logic worth pinning.

4. Frontend: add the wrapper in `api.ts`, the response type in `types.ts`,
   then consume it from a component.

### Add a chart overlay or indicator

Implement the series function in `services/analytics.py` with the same shape
as `moving_average()` (`points → [{"timestamp", "value"}]`), expose it from
`routes/prices.py` (either extend the `ma=` list or add a parameter), pass it
through `PriceChart.tsx`'s `buildOption()` as another line series. Follow how
`maKeys` flows from `App.tsx` → `PriceChart` for the toggle.

### Add a stat to the stats panel

One line in `compute_stats()` (`services/analytics.py`), assert it in
`test_analytics.py`, add the field to `ItemStats` in `frontend/src/types.ts`,
and a row in `StatsPanel.tsx`'s `rows` array. The route needs no change.

### Add a setting

Add the default in `config.py` `DEFAULT_SETTINGS`, a validator in
`routes/settings.py` `VALIDATORS`, the field in `SettingsUpdate`, the TS type
in `types.ts`, and a control in `SettingsPanel.tsx`. Read it wherever needed
via `repo.get_settings(DEFAULT_SETTINGS)` — settings are read fresh each
cycle, so most take effect without restart.

### Add a table

Append the DDL to `SCHEMA` in `db/database.py` (`CREATE TABLE IF NOT EXISTS`
makes it self-migrating on next start for additive changes), then repository
methods + tests. For *destructive* schema changes there is no migration
framework — v1's stance is that `price_history` is rebuildable, so document
"delete the DB" as the migration when unavoidable.

### Touch the collector

Collector changes deserve extra care — this is the code that must never
wedge. Keep the invariants: every fetch goes through `RS3PriceClient` (so
throttling/retries apply), every insert is `INSERT OR IGNORE` against the
`(item_id, timestamp, source)` key (so re-runs are safe), and any new step
inside `run_cycle()` must catch its own recoverable errors so one bad step
doesn't abort the cycle. Test both the happy path and the failure path — see
`test_api_failure_recovery` for the pattern.

## Testing patterns

Tests never hit the live API or the real database. Two fixtures from
`tests/conftest.py` do the heavy lifting:

**`MockAPI`** is a fake wiki API behind an `httpx.MockTransport` — it serves
a 4-item catalogue and generated price data in the exact v2 response shapes,
and can be flipped into failure modes mid-test:

```python
def test_my_feature_survives_api_outage(collector, repo, mock_api, monkeypatch):
    monkeypatch.setattr("app.api_client.client.RETRY_BACKOFF_BASE_SECONDS", 0.0)
    mock_api.fail_with = 503          # every request now returns HTTP 503
    result = collector.run_cycle()
    assert result["ok"] is False
```

`mock_api.calls` records every requested URL — assert against it to pin
*request behavior* (e.g. "incremental sync fetched only 3 buckets"), which is
how the politeness guarantees stay tested.

**`api`** (in `test_routes.py`) is a FastAPI `TestClient` wired to a
temp-file database seeded by one mock collector cycle, with the production
lifespan bypassed — so route tests exercise real SQL against real (mock)
data:

```python
def test_my_route(api):
    r = api.get("/api/stats/4151")
    assert r.status_code == 200
```

House rules: every bug fix lands with a test that fails without it; anything
touching sync or retention asserts row counts and `mock_api.calls`, not just
"no exception"; keep the suite fast (it's currently ~1s — no sleeps, use
`monkeypatch` to zero out backoffs).

There is no frontend test suite in v1; `npx tsc --noEmit` is the merge gate
for type safety, and the manual smoke check is: search → track → chart
renders → % mode → untrack.

## Debugging

`logs/rs3_tracker.log` (rotating, also mirrored to console) records every
cycle: mapping refreshes, buckets fetched, rows inserted/skipped/deleted,
and full tracebacks for unexpected errors. The `collection_runs` table is the
structured version of the same story — `SELECT * FROM collection_runs ORDER
BY id DESC LIMIT 5` is the first thing to check when data looks stale, and
`GET /api/status` surfaces the latest run's error text. To force a cycle
without waiting: `curl -X POST localhost:8000/api/status/collect-now`. To
re-seed an item's history, set its `backfilled` flag back to 0 (or untrack →
retrack).

If the wiki API starts returning 400s, your User-Agent got too generic —
check the `user_agent` setting. If SQLite reports the database is locked,
you're almost certainly running the backend and `run_collector.py`
simultaneously with a long write in flight; stop one.

## Conventions

Python: stdlib-first (the whole backend uses four runtime deps), type hints
on public functions, `log = logging.getLogger(__name__)` per module, no
prints. Timestamps are Unix seconds UTC everywhere; convert only at the
display edge (`format.ts`, `export.py`). Frontend: components stay
presentational — fetching and state live in `App.tsx`; anything shown to the
user goes through the formatters in `lib/format.ts` (never raw
`toLocaleString` in components). Keep new work aligned with the extension
points listed in [ARCHITECTURE.md](ARCHITECTURE.md) so v2 features land as
additions, not rewrites.
