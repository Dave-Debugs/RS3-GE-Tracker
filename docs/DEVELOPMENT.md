# Developer Guide

## Local Development Setup

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m pytest -v
python -m uvicorn app.main:app --port 8000 --reload

# Frontend (second terminal)
cd frontend
npm install
npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies `/api` requests to `http://localhost:8000`. The SQLite database is created automatically at `database/rs3_tracker.db` on startup (override with the `RS3_DB_PATH` environment variable if needed).

## Project Layout

```text
backend/
  app/
    api_client/client.py     HTTP client for the RuneScape Wiki RS3 API
    collector/collector.py   Incremental sync, backfill, retention, and alerts
    collector/scheduler.py   Async background scheduler loop
    db/database.py           SQLite connection, pragmas, and schema DDL
    db/repository.py         Database queries for all domain tables
    services/analytics.py    VWAP, Bollinger Bands, Z-score anomalies, LTTB downsampling
    services/search.py       Exact, prefix, substring, and fuzzy item search
    services/export.py       CSV and JSON history export
    services/updater.py      GitHub release checker and installer launcher
    routes/*.py              FastAPI routers mounted under /api
  tests/
    conftest.py              MockAPI transport and temporary SQLite fixtures
    test_*.py                Unit and integration test suites (59 tests)
frontend/
  src/
    App.tsx                  Main layout, KPI strip, and tab navigation
    hooks.ts                 React Query hooks for API endpoints
    api.ts                   Typed fetch wrappers
    types.ts                 TypeScript interfaces
    lib/format.ts            GP shorthand parser and number/time formatters
    components/              UI views and modals
```

## Testing

Run the backend test suite from the `backend/` directory:

```bash
cd backend
python -m pytest -v
```

Tests run against an isolated temporary SQLite database and a mocked Wiki API transport (`MockAPI` in `tests/conftest.py`), requiring no network access.

To verify the frontend TypeScript types and production bundle:

```bash
cd frontend
npm run build
```
