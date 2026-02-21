# Portfolio Simulator

**What it does:** A historical backtesting and sector analytics suite. Simulate investing a fixed monthly amount (optionally growing each year) across any mix of securities over 1–20 years — using real Yahoo Finance prices and FRED rate data stored in SQL Server. Also includes a full suite of sector analytics tools: performance quilts, correlation matrix, drawdown analysis, sector rotation, dividend growth, $10K growth chart, and risk vs return scatter plot.

---

## Directory Structure

```
C:\Raj\python\portfolio-simulator\
│
├── backend\                        ← Python FastAPI backend
│   ├── app\                        ← Core application code
│   │   ├── api.py                  ← REST API endpoints (FastAPI) + static file serving
│   │   ├── auth.py                 ← Auth0 JWT/token verification (admin only)
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
├── frontend\                       ← Browser-based UI (all pages — no build tools)
│   ├── help.html                   ← Landing page: tool overview, guide, nav to all pages
│   ├── portfolio-simulator.html    ← Asset Allocation Simulator
│   ├── portfolio-simulator.css     ← Simulator styles (dark theme)
│   ├── portfolio-simulator.js      ← Simulation engine & UI
│   ├── sector-performance.html     ← Annual sector returns & dividends quilt
│   ├── sector-performance.css      ← Sector performance styles
│   ├── sector-performance.js       ← Sector performance logic
│   ├── correlation.html            ← Sector correlation matrix
│   ├── correlation.js
│   ├── drawdown.html               ← Peak-to-trough drawdown analysis
│   ├── drawdown.js
│   ├── sector-rotation.html        ← Year-by-year sector rankings
│   ├── sector-rotation.js
│   ├── dividend-growth.html        ← Year-over-year dividend growth by sector
│   ├── dividend-growth.js
│   ├── growth-chart.html           ← $10K growth chart by sector
│   ├── growth-chart.js
│   ├── risk-return.html            ← Risk vs return scatter plot
│   ├── risk-return.js
│   ├── shared-analytics.css        ← Shared styles for all analytics pages
│   ├── shared-analytics.js         ← Shared API layer, utilities, nav links
│   ├── admin.html                  ← Admin dashboard (Auth0 protected, isolated)
│   ├── CD-simulator.html           ← CD portfolio advisor (AI-powered)
│   ├── cdapp.js
│   └── cdstyles.css
│
├── tools\                          ← Utilities & verification
│   ├── generate_test_spreadsheet.py ← Generates Excel workbook from DB data
│   ├── spreadsheet_config.txt      ← Config file (tickers, amount, years, tax, growth)
│   ├── create_user_logins.sql      ← SQL script for manual user_logins table creation
│   └── Spreadsheet_Guide.md        ← One-page user guide for the Excel file
│
├── docs\                           ← Design & planning documents
│   ├── Auth0_Integration_Plan.md
│   └── Welcome_Guide_Plan.md
│
└── venv\                           ← Python virtual environment
```

---

## First-Time Setup

```bash
cd C:\Raj\python\portfolio-simulator
python -m venv venv
venv\Scripts\activate
pip install fastapi uvicorn sqlalchemy pyodbc pandas requests pytest openpyxl grip python-jose
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

**Step 2 — Open the app:**
Navigate to `http://localhost:8000` — serves the help/landing page automatically.

---

## Page Navigation

All public pages are open (no login required). Admin is completely separate.

| URL | Page | Auth |
|-----|------|------|
| `http://localhost:8000/` | Help & landing page | Public |
| `http://localhost:8000/help.html` | Help & landing page | Public |
| `http://localhost:8000/portfolio-simulator.html` | Asset Allocation Simulator | Public |
| `http://localhost:8000/sector-performance.html` | Sector annual returns & dividends | Public |
| `http://localhost:8000/correlation.html` | Sector correlation matrix | Public |
| `http://localhost:8000/drawdown.html` | Drawdown analysis | Public |
| `http://localhost:8000/sector-rotation.html` | Sector rotation rankings | Public |
| `http://localhost:8000/dividend-growth.html` | Dividend growth by sector | Public |
| `http://localhost:8000/growth-chart.html` | $10K growth chart | Public |
| `http://localhost:8000/risk-return.html` | Risk vs return scatter plot | Public |
| `http://localhost:8000/admin.html` | Admin dashboard | **Auth0 login required** |

**Navigation rules:**
- All public pages link to each other (Help, Simulator, and all analytics pages)
- Admin has no links to or from public pages — it is fully isolated
- Root `/` serves `help.html` as the landing page

---

## Authentication

**Public pages:** No login required. All analytics and simulation pages are freely accessible.

**Admin dashboard only** uses Auth0:
1. Navigate to `http://localhost:8000/admin.html`
2. A **lock screen** blocks access — click **"Log In with Auth0"**
3. Authenticate via Auth0 (email/password or social login)
4. Backend checks the `user_admin` database table — only whitelisted emails get in
5. Header shows your email and a **"Log Out"** button (no links back to other pages)

**Auth0 setup** (for admin access):
- Configure `AUTH0_DOMAIN` and `AUTH0_CLIENT_ID` in `backend/.env`
- Auth0 Dashboard must have `http://localhost:8000/admin.html` in:
  - Allowed Callback URLs
  - Allowed Logout URLs
  - Allowed Web Origins
- Add admin users via SQL: `INSERT INTO user_admin (email, name) VALUES ('you@example.com', 'Your Name')`

---

## Admin Dashboard

**URL:** `http://localhost:8000/admin.html`

**Access:** Auth0 login + `user_admin` table whitelist. Completely isolated — no links to or from any other page.

**Setup:** Set `ENABLE_WRITE_API=True` in `backend/.env` and restart the server before using write operations.

**Features:**
- **Add Ticker** — enter symbol + optional name, adds to database
- **Active Tickers** — see all tickers currently in the system
- **Load New Tickers** — fetches full history (30 yrs) only for tickers with no data yet
- **Refresh Recent Data** — fetches the last N months (configurable, default 2) for all tickers and merges with existing
- **Reload All Tickers** — re-downloads full history for every ticker (with confirmation dialog)
- **FRED Rates** — load federal funds rate data (full history or incremental 3 months)
- **Batch Status** — live auto-polling display of running/completed/failed batch jobs

---

## Ongoing Data Updates

**Option 1 — Admin Dashboard (recommended):**

Open `http://localhost:8000/admin.html`, log in, and click the appropriate buttons.

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

## Test Spreadsheet (Verify Calculations)

Generate an Excel workbook that mirrors the simulator's logic with real DB data and Excel formulas.

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
venv\Scripts\grip README.md
```
Opens at `http://localhost:6419`. Press Ctrl+C to stop.

---

## Features

### Asset Allocation Simulator
- **Dollar-cost averaging simulation** — invest a monthly amount across multiple securities with custom allocation percentages
- **Annual deposit growth** — optionally increase monthly investment by a fixed $ amount each year (e.g., $1,000/month growing by $100/year)
- **Worst-case entry pricing** — buys at the monthly high price (conservative backtesting)
- **Round-lot (integer) share buying with per-ticker accumulation** — whole shares only; each ticker keeps its own cash bucket until enough accumulates to buy a share
- **Prior year-end cutoff** — simulation runs through December of the last complete calendar year
- **Dividend tracking** — cash dividends accumulated separately (not reinvested into equities)
- **Money market interest** — accumulated dividends earn interest at the FRED federal funds rate (monthly compounding)
- **MMF benchmark** — side-by-side: what if the same investment went entirely into money market?
- **6 summary tiles** — Total Invested, Equity Value, Dividends Earned, Cash Accrual, Portfolio Balance, MMF Value (all clickable for drill-down)
- **Interactive charts** — Growth Over Time and Dividend Earned charts with hover crosshair and tooltips
- **Monthly breakdown table** — clickable cells for per-ticker detail modals
- **Tax impact analysis** — adjustable tax rate (0–60%) with yearly breakdown of taxes on dividends and MM interest
- **Annual return table** — pre-tax returns per calendar year with clickable calculation modals
- **Proportional redistribution** — when a ticker has no data for a month, its allocation flows to available tickers

### Sector Analytics Tools
- **Sector Performance** — annual total returns and dividends for all 11 S&P 500 sector ETFs plus VTI; color-coded quilt table; summary stats (CAGR, best/worst year, positive years, total/avg dividends)
- **Correlation Matrix** — Pearson correlation between sectors over selected year range; color-coded by strength
- **Drawdown Analysis** — peak-to-trough loss analysis; recovery time; comparison against VTI
- **Sector Rotation** — year-by-year sector rankings #1–#12 by performance; leadership count (top 3, bottom 3)
- **Dividend Growth** — year-over-year dividend growth by sector; identify consistent payers vs cutters
- **$10K Growth Chart** — cumulative growth of $10,000 invested in each sector; interactive canvas chart
- **Risk vs Return** — scatter plot of annual volatility (X) vs total return (Y); return/risk ratio

### Infrastructure
- **Public pages, isolated admin** — all public pages are open (no login); admin is Auth0-protected and completely separate with no cross-links
- **Help landing page** — root URL serves a guide page with tool cards, simulator how-to, and nav to all tools
- **Admin dashboard** — Auth0 login + `user_admin` table whitelist; two-layer security; no links to/from public pages
- **Smart batch loading** — Load New Tickers (full history for new tickers only), Refresh Recent Data (incremental, configurable months), or Reload All Tickers
- **API request logging** — every API call logged to DB with user, method, path, status code, response time, and IP
- **Excel verification tool** — generate a 5-sheet workbook with real data and Excel formulas to verify every calculation step

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | SQL Server (local), SQLAlchemy ORM |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Auth | Auth0 SPA SDK (admin only), python-jose for JWT verification |
| Data Sources | Yahoo Finance (prices/dividends), FRED (federal funds rate) |
| Frontend | HTML + CSS + JS (vanilla, no build tools), Canvas charts |
| Tests | Pytest (read-only integration tests against real DB) |
