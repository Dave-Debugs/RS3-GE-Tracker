# RS3 Grand Exchange Tracker (v1.2)

A local desktop market tracker, flipping scanner, and alchemy calculator for **RuneScape 3** Grand Exchange prices. It pulls live price data from the RuneScape Wiki real-time prices API, stores rolling history locally in SQLite, and runs entirely on your machine.

---

## What's in v1.2

- **Smart Flip Finder & 4h Limit Matrix** — Scans the tradeable RS3 item catalog for active buy/sell spreads after deducting the 2% Grand Exchange tax (capped at 50M gp per item) and ranks flips by 4-hour buy limit profit, profit per item, ROI %, or 24-hour volume.
- **High Level Alchemy Scanner** — Automatically pulls the live Nature rune price and ranks items by net profit per alch and 4-hour buy limit profit.
- **GE Tax & Flip Calculator** — Built-in calculator for checking break-even sell prices, 2% tax deductions, required capital, and total flip profit for any custom quantity or 4-hour limit.
- **Item Group Dashboards** — Organize your watchlist into separate item groups (such as *Flipping*, *PvM Gear*, *Herblore*, or *High Alch*) so your charts and KPI summary cards stay focused.
- **Interactive Price Charts** — Zoomable price and volume charts across 1H, 6H, 24H, 7D, 14D, and 30D windows with instant buy/sell bands, moving averages, and % change comparison mode.
- **Crafting & Processing Recipes** — Track input costs and output margins for potions, smithing, and item combinations with automatic ingredient lookup and hover examine tooltips.
- **Portfolio Tracker & Price Alerts** — Log your current holdings to track unrealized profit and set desktop notifications when items cross your target price.
- **Built-in Auto-Updater** — Check for new releases and install updates directly from the Settings menu or the system tray icon with SHA-256 checksum verification.

---

## Installation (Windows)

### Option 1: Windows Installer (Recommended)
Download and run **`RS3-GE-Tracker-Setup-1.2.exe`** (or the standalone `RS3Tracker.exe`) from the [Releases](https://github.com/dave-debugs/rs3-ge-tracker/releases) page. Once launched, the app runs in your system tray and opens the dashboard in your default browser.

### Option 2: Run from Source

**Prerequisites**:
- [Python 3.11+](https://python.org)
- [Node.js 18+](https://nodejs.org)

```bat
scripts\setup.bat
scripts\start_all.bat
```

Once started, open **http://localhost:5173** in your browser.

---

## Manual Development Startup

```bash
# Backend (Port 8000)
cd backend
python -m uvicorn app.main:app --port 8000

# Frontend (Port 5173)
cd frontend
npm run dev
```

---

## Building the Installer

To compile the frontend bundle, standalone executable, and Inno Setup installer (`v1.2`):

```bat
cd frontend && npm run build
cd ..\backend && python -m PyInstaller RS3Tracker.spec --noconfirm
iscc ..\installer\RS3-GE-Tracker.iss
```

---

## Data & Attribution

Price and item data is provided by the [RuneScape Wiki Real-Time Prices API](https://runescape.wiki/w/RuneScape:Real-time_prices). Created by [dave-debugs](https://github.com/dave-debugs). This project is not affiliated with or endorsed by Jagex.
