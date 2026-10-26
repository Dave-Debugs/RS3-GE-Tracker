# RS3 Grand Exchange Tracker (v1.3)

A local desktop market tracker, flipping scanner, crafting arbitrage engine, and 8-slot GE offer manager for **RuneScape 3** Grand Exchange prices. It pulls live price data from the RuneScape Wiki real-time prices API, stores rolling history locally in SQLite, and runs entirely on your machine.

---

## Features

- **Smart Flip Finder & Liquidity Scoring**: Scans the tradeable RS3 item catalog for active buy/sell spreads after deducting the 2% Grand Exchange tax (capped at 50M gp per item) and ranks flips by 4-hour buy limit profit, liquidity & fill speed (`0-100` score + estimated hours to fill a 4h limit), profit per item, ROI %, or 24-hour volume.
- **Crafting, Potion & Combination Arbitrage Scanner**: Evaluates multi-ingredient crafting and herblore recipes against live GE prices in both **Patient Mode** (slow-buy inputs, slow-sell output minus 2% tax) and **Instant Mode** (insta-buy inputs, insta-sell output minus 2% tax).
- **High Level Alchemy & Auto-Alcher Mk. II Scanner**: Supports both **Manual Cast** (`1x Nature rune`) and **Invention Auto-Alchemiser Mk. II** (`1x Nature rune + 5x Fire rune + Divine charge / 187.5`, with 600x daily passive machine profit).
- **8-Slot Active GE Offer & 4-Hour Buy Limit Timer Board**: Track live Buy/Sell offers across all 8 GE slots with live 4-hour buy limit reset countdowns, desktop/Discord alerts on reset, 1-click slot assignment from the Scanner, and 1-click completion into your Portfolio or Realized Flip Ledger.
- **Portfolio Lifecycle & Realized Flip Ledger**: Track net liquidation value after the 2% GE tax, close full or partial positions via **Sell / Close**, and review lifetime realized profit, total GE tax paid, and win-rate % in the **Realized Flip Ledger**.
- **Interactive Price Charts (`1H` to `1Y`) & Quantitative Overlays**: Zoomable LTTB-downsampled charts across `1H`, `6H`, `24H`, `7D`, `14D`, `30D`, `90D`, `6M`, and `1Y` with **Bollinger Bands (±2σ)**, **VWAP**, moving averages, and automatic reference lines for your **Portfolio Avg Buy**, **Break-Even (+2% Tax)**, and **Active Price Alerts**.
- **Alerts, Discord Webhooks & Workspace Backup**: Set price, net-margin, or 24h-volume alerts with recurring cooldowns, optional Discord Webhook embeds, RS3 shorthand inputs (`10k`, `2.5m`, `1.2b`), 4 RS3 themes (*Grand Exchange Gold*, *Noxious Abyss*, *Prifddinas Crystal*, *GE Parchment Light*), and 1-click JSON workspace backup/restore.

---

## Installation (Windows)

### Option 1: Windows Installer (Recommended)
Download and run **`RS3-GE-Tracker-Setup-1.3.exe`** (or the standalone `RS3Tracker.exe`) from the [Releases](https://github.com/dave-debugs/rs3-ge-tracker/releases) page. Once launched, the app runs in your system tray and opens the dashboard in your default browser.

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

To compile the frontend bundle, standalone executable, and Inno Setup installer (`v1.3`):

```bat
cd frontend && npm run build
cd ..\backend && python -m PyInstaller RS3Tracker.spec --noconfirm
iscc ..\installer\RS3-GE-Tracker.iss
```

---

## Data & Attribution

Price and item data is provided by the [RuneScape Wiki Real-Time Prices API](https://runescape.wiki/w/RuneScape:Real-time_prices). Created by [dave-debugs](https://github.com/dave-debugs). This project is not affiliated with or endorsed by Jagex.
