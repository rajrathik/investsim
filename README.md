# Portfolio Simulator

**What it does:** A historical backtesting tool that lets you simulate investing a fixed monthly amount across securities (ETFs, mutual funds, stocks) over 1–20 years. It buys whole shares at the worst-case price each month (monthly high), carries unspent dollars to the next month, tracks share accumulation, dividends earned, money market interest on accumulated cash, tax impact, and annual returns — all powered by real Yahoo Finance and FRED data stored in SQL Server. Simulation period ends at the prior year's December (no partial-year data).

---

## Directory Structure

```
C:\Raj\python\portfolio-simulator\
│
├── backend\                        ← Python FastAPI backend
│   ├── app\                        ← Core application code
│   │   ├── api.py                  ← REST API endpoints (FastAPI) + static file serving
│   │   ├── auth.py                 ← Auth0 JWT/token verification
│   │   ├── config.py               ← Settings (DB connection, Auth0, constants)
│   │   ├── database.py             ← SQLAlchemy engine & session
│   │   ├── models.py               ← DB models (Ticker, MonthlyPrice, Dividend, UserLogin, UserAdmin, ApiRequestLog)
│   │   ├── mm_rates.py             ← Money market rate models & loaders
│   │   ├── fetcher.py              ← Yahoo Finance data fetcher
│   │   ├── fred_fetcher.py         ← FRED federal funds rate fetcher
│   │   └── loader.py               ← Batch data loader (Yahoo → DB)
│   │
│   ├── tests\                      ← Test suite (pytest)
│   │   ├── test_api.py             ← API integration tests (read-only, hits real DB)
│   │   ├── test_models.py          ← ORM model tests
│   │   ├── test_fetcher.py         ← Yahoo fetcher tests
│   │   ├── test_loader.py          ← Loader logic tests
│   │   └── test_mm_rates.py        ← FRED/money market tests
│   │
│   ├── run_batch.py                ← CLI: load Yahoo Finance data (full/incremental)
│   ├── run_fred_batch.py           ← CLI: load FRED rate data (full/incremental)
│   ├── test_connection.py          ← Verify DB connection & create tables
│   └── pytest.ini                  ← Pytest config
│
├── frontend\                       ← Browser-based UI
│   ├── portfolio-simulator.html    ← HTML structure
│   ├── portfolio-simulator.css     ← Styles
│   ├── portfolio-simulator.js      ← Application logic & simulation engine
│   └── admin.html                  ← Admin dashboard (manage tickers & data loads)
│
├── tools\                          ← Utilities & verification
│   ├── generate_test_spreadsheet.py ← Generates Excel workbook from DB data
│   ├── spreadsheet_config.txt      ← Config file (tickers, amount, years, tax, growth)
│   ├── create_user_logins.sql      ← SQL script for manual user_logins table creation
│   └── Spreadsheet_Guide.md        ← One-page user guide for the Excel file
│
├── docs\                           ← Design & planning documents
│   ├── Auth0_Integration_Plan.md   ← Auth0 implementation requirements
│   └── Welcome_Guide_Plan.md       ← Welcome guide implementation requirements
│
└── venv\                           ← Python virtual environment
```

---

## First-Time Setup

```bash
cd C:\Raj\python\portfolio-simulator
python -m venv venv
venv\Scripts\activate
pip install fastapi uvicorn sqlalchemy pyodbc pandas requests pytest openpyxl grip
```

Create tables and load historical data (one-time):

```bash
cd backend
python test_connection.py          # Creates all DB tables
python run_batch.py full           # Loads 30 years of ETF price/dividend data
python run_fred_batch.py full      # Loads 30 years of federal funds rate data
```

---

## Running the Project

**Step 1 — Start the API:**
```bash
cd C:\Raj\python\portfolio-simulator\backend
venv\Scripts\activate
uvicorn app.api:app --reload
```
API runs at `http://localhost:8000` (Swagger docs at `/docs`).

**Step 2 — Open the frontend:**
Navigate to `http://localhost:8000/portfolio-simulator.html` (served by the API).

---

## Authentication & Welcome Guide

The simulator requires Auth0 authentication. On first visit:

1. A **lock screen** overlay blocks the simulator
2. Click **"Log In with Auth0"** to authenticate (email/password or social login)
3. After login, a **Welcome Guide** overlay appears with a quick-start summary:
   - What the simulator does
   - How to use it (4 steps)
   - What results you'll see
   - Key things to know
4. Click **"Got It — Let's Start"** to proceed to the simulator
5. Header shows your email and a **"Log Out"** button

Auth0 configuration is stored in `backend/.env` (AUTH0_DOMAIN, AUTH0_CLIENT_ID). Auth0 Dashboard must have `http://localhost:8000/portfolio-simulator.html` and `http://localhost:8000/admin.html` in Allowed Callback URLs and Allowed Logout URLs, and `http://localhost:8000` in Allowed Web Origins.

---

## Admin Dashboard

A browser-based admin page for managing tickers and loading data.

**URL:** `http://localhost:8000/admin.html`

**Access:** Requires Auth0 login. Only users whose email is in the `user_admin` database table can access the dashboard. Add admin users via SQL: `INSERT INTO user_admin (email, name) VALUES ('you@example.com', 'Your Name')`.

**Setup:** Set `ENABLE_WRITE_API=True` in `backend/.env` and restart the server. Auth0 Dashboard must include `http://localhost:8000/admin.html` in Allowed Callback URLs and Allowed Logout URLs.

**Features:**
- **Add Ticker** — enter symbol + optional name, adds to database
- **Active Tickers** — see all tickers currently in the system
- **Load New Tickers** — fetches full history (30 yrs) only for tickers with no data yet (newly added tickers)
- **Refresh Recent Data** — fetches the last N months (default 2, configurable) for all tickers and merges with existing
- **Reload All Tickers** — re-downloads full history for every ticker (with confirmation dialog; existing data is skipped, not overwritten)
- **FRED Rates** — load federal funds rate data (full history or incremental)
- **Batch Status** — auto-polling display shows running/completed/failed status with summary

---

## Ongoing Data Updates

**Option 1 — Admin Dashboard (recommended):**

Open `http://localhost:8000/admin.html` and click the buttons.

**Option 2 — CLI:**

```bash
cd backend
python run_batch.py incremental       # Fetches latest months from Yahoo
python run_fred_batch.py incremental  # Fetches latest months from FRED
```

---

## Running Tests

```bash
cd backend
pytest tests/ -v                          # All tests (needs API/DB running)
pytest tests/test_api.py -v -s            # API tests with output
pytest tests/test_mm_rates.py -v -m "not network"  # Offline unit tests only
```

---

## Git Workflow

```bash
cd C:\Raj\python\portfolio-simulator
git add .
git commit -m "Your commit message"
```

---

## Test Spreadsheet (Verify Calculations)

Generate an Excel workbook that mirrors the website's simulation logic with real DB data and Excel formulas.

**Setup:** Edit `tools/spreadsheet_config.txt`:
```
tickers = XLK:60, XLV:40
monthly_amount = 1000
years = 3
tax_rate = 30
annual_growth = 0
```

**Generate:**
```bash
cd C:\Raj\python\portfolio-simulator
venv\Scripts\python tools\generate_test_spreadsheet.py
```

Opens as `tools/Portfolio_Simulator_Test.xlsx` with 5 sheets: Setup, Monthly Simulation, Year Summary, Tax Impact, Annual Returns. All cells are Excel formulas — change any input on Setup and everything recalculates. See `tools/Spreadsheet_Guide.md` for a walkthrough.

---

## Viewing Markdown Files Locally

Use [Grip](https://github.com/joeyespo/grip) to render `.md` files in your browser (GitHub-style):

```bash
venv\Scripts\pip install grip
venv\Scripts\grip README.md
```
Opens at `http://localhost:6419`. Press Ctrl+C to stop. Works for any `.md` file:
```bash
venv\Scripts\grip Architecture.md
venv\Scripts\grip tools\Spreadsheet_Guide.md
```

---

## Features

- **Dollar-cost averaging simulation** — invest a monthly amount across multiple securities with custom allocation percentages
- **Annual deposit growth** — optionally increase your monthly investment by a fixed $ amount each year (e.g., $1000/month growing by $100/year)
- **Worst-case entry pricing** — buys at the monthly high price each month (conservative backtesting)
- **Round-lot (integer) share buying** — buys whole shares only: floor(bucket ÷ price). Each ticker accumulates unspent dollars in its own bucket until enough to buy a share
- **Prior year-end cutoff** — simulation runs through December of the last complete calendar year (never into the current partial year)
- **Dividend tracking** — cash dividends accumulated separately (not reinvested into equities)
- **Money market interest** — accumulated dividends earn interest at the federal funds rate (monthly compounding)
- **MMF benchmark** — side-by-side comparison: what if the same investment went entirely into money market?
- **6 summary tiles** — Total Invested, Equity Value, Dividends Earned, Cash Accrual, Portfolio Balance, MMF Value (all clickable for drill-down)
- **Interactive charts** — Growth Over Time and Dividend Earned charts with hover tooltips and crosshair tracking
- **Monthly breakdown table** — clickable cells for per-ticker detail modals, sortable by date, with Total Invested running total and Total Shares column
- **Tax impact analysis** — adjustable tax rate (0–60%) with yearly breakdown of taxes on dividends and MM interest
- **Annual return table** — pre-tax returns per calendar year using DCA mid-year approximation
- **Clickable calculation modals** — click any highlighted cell in monthly or annual tables to see full calculation breakdown
- **Multi-select ticker dropdown** — checkbox-based selection with search filtering
- **Proportional redistribution** — when a ticker has no data for a month, its allocation flows to available tickers
- **Excel test spreadsheet** — generate a multi-sheet workbook with real data and Excel formulas to verify every calculation
- **Auth0 authentication** — login required before accessing the simulator; supports email/password and social login providers; expired tokens automatically redirect to login screen
- **API request logging** — every API call logged to database with user, method, path, status code, response time, and IP address
- **Welcome guide** — after login, a concise training overlay explains the simulator's purpose, how to use it, and what results mean
- **Admin dashboard** — browser-based page to add tickers and trigger Yahoo Finance/FRED data loads without CLI; configurable incremental month range; auto-polling batch status; secured by Auth0 login + `user_admin` table whitelist

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | SQL Server (local), SQLAlchemy ORM |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Data Sources | Yahoo Finance (prices/dividends), FRED (federal funds rate) |
| Frontend | HTML + CSS + JS (vanilla, no build tools), Canvas charts |
| Tests | Pytest (read-only integration tests against real DB) |
