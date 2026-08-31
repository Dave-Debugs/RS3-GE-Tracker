# RS3 Grand Exchange Tracker

A local, lightweight market tracker and flipping toolkit for **RuneScape 3** Grand Exchange prices. It pulls live price data directly from the RuneScape Wiki API, stores up to **30 days** of history locally in SQLite, and provides an interactive dashboard with multi-item charts, flipping margin calculators, crafting recipes, and portfolio tracking.

---

## Features

- **Multi-Dashboard Item Groups** — Organize items into dedicated dashboards (e.g. *Flipping*, *Herblore*, *Boss Drops*, *High Alch*) to isolate charts and watchlists without visual clutter.
- **Interactive Price Charts** — Zoomable charts with 1H, 6H, 24H, 7D, 14D, and 30D ranges, instant buy/sell bands, volume bars, moving averages, and normalized % change comparison.
- **Crafting & Flipping Recipes** — Calculate real profit margins for potions, smithing, and processing with auto-populating ingredients, 2% GE tax calculations, and in-game examine tooltips with direct Wiki guides.
- **Portfolio Tracker** — Log your held items, purchase prices, and quantities to track total portfolio value and unrealized profit in real time.
- **Price Alerts** — Set custom price thresholds with Windows desktop notifications when targets are hit.
- **Top Movers & Market Trends** — Discover biggest 24H and weekly gainers, losers, and highest-volume items across the entire tradeable RS3 item catalog (~7,300 items).
- **Offline & Local First** — Everything is stored locally in SQLite (`rs3_tracker.db`). If your internet drops or the Wiki API is temporarily unreachable, your existing charts and data remain instantly viewable.

---

## Quick Start (Windows)

### Option 1: Run the Standalone App
Download the compiled `RS3Tracker.exe` from the [Releases](https://github.com/DaveDebugs/rs3-ge-tracker/releases) tab and double-click to run.

### Option 2: Run from Source

**Prerequisites**:
- [Python 3.11+](https://python.org) (make sure "Add to PATH" is checked)
- [Node.js 18+](https://nodejs.org)

```bat
:: 1. Install dependencies
scripts\setup.bat

:: 2. Launch backend & frontend
scripts\start_all.bat
```

Once running, open your browser to **http://localhost:5173**.

---

## Manual Startup

```bash
# Terminal 1: Backend
cd backend
python -m uvicorn app.main:app --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

---

## Testing

Run the automated backend test suite:

```bash
cd backend
python -m pytest
```

---

## Data & Attribution

Price data is provided by the [RuneScape Wiki real-time prices project](https://runescape.wiki/w/RuneScape:Real-time_prices). This project is not affiliated with or endorsed by Jagex.
