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
│   │   ├── models.py               ← DB models (Ticker, MonthlyPrice, Dividend, UserLogin, UserAdmin, ApiRequestLog, SavedSimulation)
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
│   ├── index.html                  ← Landing page: tool overview cards, nav to all pages
│   ├── simulator-guide.html        ← How It Works guide for the simulator
│   ├── portfolio-simulator.html    ← Asset Allocation Simulator
│   ├── portfolio-simulator.css     ← Simulator-specific styles (stepper controls, modals, cards)
│   ├── portfolio-simulator.js      ← Simulation engine & UI
│   ├── sector-performance.html     ← Annual sector returns & dividends quilt
│   ├── sector-performance.css      ← Sector performance styles (quilt, return/dividend colors)
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
│   ├── sp500-history.html          ← S&P 500 decade heatmap with methodology panel (Shiller data, 1871–today)
│   ├── sp500-history.js
│   ├── sp500-simulate.html         ← Historical DCA simulator: pick year range, starting amount, monthly contribution
│   ├── sp500-simulate.js
│   ├── stack-earn.html             ← Tiered savings calculator: ending balance or required monthly contribution to reach a goal
│   ├── stack-earn.js
│   ├── montecarlo.html             ← Monte Carlo portfolio simulator: 1,000 block-bootstrap futures from 150+ yrs of S&P 500 history; 5–30yr horizon; Market Cycle Sensitivity tooltip (Short/Medium/Long blocks); percentile table with Deposited column + plain-language tooltip
│   ├── montecarlo.js
│   ├── extreme-months.html         ← Monthly Market Extremes: ranked best & worst single months in S&P 500 history since 1871; shows $10K result per month; top-10/20 chip toggle; mini-bar magnitude indicators
│   ├── extreme-months.js
│   ├── shared-analytics.css        ← Single source of truth: CSS variables, reset, fonts, header, ← Home link styles, dark+light theme overrides, welcome bar styles, toggle button styles
│   ├── shared-analytics.js         ← Shared API layer, utilities, error handling, pageview tracking
│   ├── shared-auth.js              ← Auth0 public sign-in (IIFE): optional login/logout, welcome bar, _pubAuthFetch(), _pubIsSignedIn()
│   ├── theme-toggle.js             ← Dark/light theme toggle (IIFE + localStorage persistence)
│   ├── saved-simulations.html      ← View & delete saved portfolio simulations (auth-gated)
│   ├── robots.txt                  ← Search engine crawl directives
│   ├── sitemap.xml                 ← XML sitemap for Google Search Console
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
| `http://localhost:8000/` | Landing page (tool cards) | Public |
| `http://localhost:8000/simulator-guide.html` | Simulator guide (How It Works) | Public |
| `http://localhost:8000/portfolio-simulator.html` | Asset Allocation Simulator | Public |
| `http://localhost:8000/sector-performance.html` | Sector annual returns & dividends | Public |
| `http://localhost:8000/correlation.html` | Sector correlation matrix | Public |
| `http://localhost:8000/drawdown.html` | Drawdown analysis | Public |
| `http://localhost:8000/sector-rotation.html` | Sector rotation rankings | Public |
| `http://localhost:8000/dividend-growth.html` | Dividend growth by sector | Public |
| `http://localhost:8000/growth-chart.html` | $10K growth chart | Public |
| `http://localhost:8000/risk-return.html` | Risk vs return scatter plot | Public |
| `http://localhost:8000/sp500-history.html` | S&P 500 decade heatmap | Public |
| `http://localhost:8000/sp500-simulate.html` | S&P 500 historical DCA simulator | Public |
| `http://localhost:8000/stack-earn.html` | Tiered savings calculator (Stack & Earn) | Public |
| `http://localhost:8000/montecarlo.html` | Monte Carlo portfolio simulator (5–30yr horizon, withdrawal mode, lump sum, cycle sensitivity) | Public |
| `http://localhost:8000/extreme-months.html` | Monthly Market Extremes — best & worst single months, $10K result | Public |
| `http://localhost:8000/saved-simulations.html` | View & delete saved simulations | **Sign-in required** |
| `http://localhost:8000/admin.html` | Admin dashboard | **Auth0 login required** |

**Navigation rules:**
- All public tool pages have a `← Home` link (top-left of header) pointing back to the landing page
- `index.html` is the hub — users navigate out via tool cards and back via `← Home`
- Admin has no links to or from public pages — it is fully isolated
- Root `/` serves `index.html` as the landing page

---

## Authentication

**Public pages:** No login required for viewing. All analytics and simulation pages are freely accessible without an account.

**Optional public sign-in** (via `shared-auth.js`):
- Users can optionally sign in on any public page via a **"Sign In"** link in the header
- Signing in shows a **welcome bar** across all pages with the user's email and a Sign Out button
- Signed-in users unlock **member content** on the landing page (e.g., Saved Simulations tile)
- Signed-in users can **save up to 3 portfolio simulations** from the simulator and view/delete them on the Saved Simulations page
- All public pages redirect to `/` after Auth0 login — only one callback URL needed for all public pages
- Auth state cached in `localStorage` (`pub_auth_user` key) for instant welcome bar across pages

**Admin dashboard** uses separate Auth0 flow:
1. Navigate to `http://localhost:8000/admin.html`
2. A **lock screen** blocks access — click **"Log In with Auth0"**
3. Authenticate via Auth0 (email/password or social login)
4. Backend checks the `user_admin` database table — only whitelisted emails get in
5. Header shows your email and a **"Log Out"** button (no links back to other pages)

**Auth0 setup:**
- Configure `AUTH0_DOMAIN` and `AUTH0_CLIENT_ID` in `backend/.env`
- Auth0 Dashboard settings:
  - **Allowed Callback URLs:** `http://localhost:8000/, http://localhost:8000/admin.html`
  - **Allowed Logout URLs:** `http://localhost:8000/, http://localhost:8000/admin.html`
  - **Allowed Web Origins:** `http://localhost:8000`
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
- **6 summary tiles** — Total Invested, Equity Value, Dividends Earned, Cash Accrual, Portfolio Balance, MMF Value (all clickable for drill-down). Each tile has a **?** info icon with hover tooltip explaining the metric
- **Save simulation results** — signed-in users can save up to 3 simulation results (inputs + all 6 tile values + total return). Saved simulations viewable and deletable on a dedicated page (`saved-simulations.html`)
- **Interactive charts** — Growth Over Time and Dividend Earned charts with hover crosshair and tooltips
- **Monthly breakdown table** — clickable cells for per-ticker detail modals
- **Tax impact analysis** — adjustable tax rate (0–60%) with yearly breakdown of taxes on dividends and MM interest
- **Annual return table** — pre-tax returns per calendar year with clickable calculation modals
- **Proportional redistribution** — when a ticker has no data for a month, its allocation flows to available tickers
- **5% stepper allocation controls** — −/+ buttons in 5% increments replace sliders; tickers at 0% are silently excluded from simulation
- **Equal Split rounds to 5%** — distributes allocations in clean 5% multiples

### Sector Analytics Tools
- **Sector Performance** — annual total returns and dividends for all 11 S&P 500 sector ETFs plus VTI; color-coded quilt table; summary stats (CAGR, best/worst year, positive years, total/avg dividends)
- **Correlation Matrix** — Pearson correlation between sectors over selected year range; color-coded by strength
- **Drawdown Analysis** — peak-to-trough loss analysis; recovery time; comparison against VTI
- **Sector Rotation** — year-by-year sector rankings #1–#12 by performance; leadership count (top 3, bottom 3)
- **Dividend Growth** — year-over-year dividend growth by sector; identify consistent payers vs cutters
- **$10K Growth Chart** — cumulative growth of $10,000 invested in each sector; interactive canvas chart
- **Risk vs Return** — scatter plot of annual volatility (X) vs total return (Y); return/risk ratio
- **S&P 500 History** — 155 years of annual returns from Shiller data; decade heatmap (muted green/red color scale); methodology panel explaining formula, columns used, and assumptions; summary stats (median, best/worst year)
- **Monthly Market Extremes** — ranked best and worst single months in S&P 500 history since 1871; side-by-side panels (red/green); shows what each month did to $10,000; proportional mini-bar magnitude indicators; chip toggle for top-10 vs top-20

### Infrastructure
- **Dark/light theme toggle** — 🌙/☀️ button on every page; persists via localStorage; no FOUC (synchronous IIFE in `<head>`); Canvas charts re-render on toggle
- **CSS consolidation** — `shared-analytics.css` is the single source of truth for `:root` variables, reset, fonts, header, and shared component styles; page-specific CSS files contain only overrides
- **Optional public Auth0 sign-in** — `shared-auth.js` loaded on all 11 public pages; provides optional sign-in link, welcome bar, `_pubAuthFetch()` for authenticated API calls, `_pubIsSignedIn()` for checking login state; all pages use single `/` callback URL
- **Member content section** — landing page shows member-only tiles (Saved Simulations, Newsletters, Watchlists) when signed in
- **Public pages, isolated admin** — all public pages are open (no login required); admin is Auth0-protected and completely separate with no cross-links
- **Landing page with tool cards** — root URL serves `index.html` with clickable cards for each tool; separate `simulator-guide.html` for the How It Works walkthrough
- **Admin dashboard** — Auth0 login + `user_admin` table whitelist; two-layer security; no links to/from public pages
- **Smart batch loading** — Load New Tickers (full history for new tickers only), Refresh Recent Data (incremental, configurable months), or Reload All Tickers
- **API request logging** — every API call logged to DB with user, method, path, status code, response time, and IP
- **Self-hosted pageview tracking** — `navigator.sendBeacon()` on all 12 pages fires `POST /api/track/pageview` (zero cost, no third-party analytics)
- **Error handling** — try/catch with user-facing error messages on all analytics page `loadData()` functions; `resp.ok` checks in shared API layer
- **Rate limiting** — slowapi (60/min default, 30/min for heavy reads, 10/min for writes, 5/min for batch loads); returns HTTP 429 when exceeded
- **Write endpoint auth** — all POST/PUT/DELETE endpoints require Auth0 JWT token + `ENABLE_WRITE_API=True` config flag (double-gated)
- **SEO foundations** — meta descriptions on all 11 pages, Open Graph + Twitter Card tags, canonical links, robots.txt, sitemap.xml, JSON-LD structured data (WebSite, WebApplication, BreadcrumbList)
- **Excel verification tool** — generate a 5-sheet workbook with real data and Excel formulas to verify every calculation step

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | SQL Server (local dev) / PostgreSQL (Railway production), SQLAlchemy ORM |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Auth | Auth0 SPA SDK (admin + optional public sign-in), python-jose for JWT verification |
| Rate Limiting | slowapi (per-IP, tiered limits by endpoint category) |
| Data Sources | Yahoo Finance (prices/dividends), FRED (federal funds rate) |
| Frontend | HTML + CSS + JS (vanilla, no build tools), Canvas charts |
| Deployment | Railway (production), configurable via environment variables |
| SEO | Meta descriptions, Open Graph, Twitter Cards, canonical links, robots.txt, sitemap.xml, JSON-LD structured data |
| Tests | Pytest (read-only integration tests against real DB) |

---

## Shiller Historical Data

**Source:** [shillerdata.com](https://shillerdata.com/) — Robert Shiller's S&P 500 monthly data since 1871.
**Table:** `shiller_market_data` (1,863 rows, Jan 1871 – present)

### How to download the file

1. Go to **[shillerdata.com](https://shillerdata.com/)**
2. Download the Excel file — it is named **`ie_data.xls`**
3. Save it to **`C:\Raj\python\portfolio-simulator\inputdata\ie_data.xls`**

### Load into database

```bash
cd C:\Raj\python\portfolio-simulator

# First time — load into both SQL Server and PostgreSQL
venv\Scripts\python backend\onetime\load_shiller_data.py --db both

# Updated file downloaded — reload from scratch (wipes existing rows first)
venv\Scripts\python backend\onetime\load_shiller_data.py --db both --truncate

# SQL Server only (start SQL Server first: net start MSSQLSERVER as admin)
venv\Scripts\python backend\onetime\load_shiller_data.py --db sqlserver

# PostgreSQL only
venv\Scripts\python backend\onetime\load_shiller_data.py --db postgres

# Preview without writing anything
venv\Scripts\python backend\onetime\load_shiller_data.py --dry-run
```

Data dictionary is in the script docstring: `backend/onetime/load_shiller_data.py`

---

## Railway Deployment

The app is deployed and live on [Railway](https://railway.app).

### How Railway Builds It

- **`requirements.txt`** (project root) — Railway installs from this file. The root-level file is intentional; Railway doesn't look inside `backend/`.
- **`runtime.txt`** (project root) — Pins `python-3.12.3` so Railway uses the correct Python version.
- **Start command** (set in Railway service settings — not a Procfile):
  ```
  sh -c "cd backend && uvicorn app.api:app --host 0.0.0.0 --port $PORT"
  ```
  Must `cd backend` first — Railway runs from repo root but `app.api` is a relative path inside `backend/`.

### Railway Service Variables (6 configured)

| Variable | Description |
|----------|-------------|
| `ALLOWED_ORIGINS` | Your custom domain (e.g. `https://yoursubdomain.yourdomain.com`) |
| `AUTH0_CLIENT_ID` | Auth0 application client ID |
| `AUTH0_DOMAIN` | Your Auth0 tenant domain |
| `DB_TYPE` | `postgres` |
| `ENABLE_WRITE_API` | `True` to allow admin write operations |
| `POSTGRES_URL` | Copy from Railway → PostgreSQL service → Connect tab |

> `AUTH0_AUDIENCE` is not set in Railway. The backend falls back to opaque token mode (validates via Auth0 `/userinfo`). Supported by the code but not required.

### Custom Domain via Cloudflare

1. In Railway service settings: add your custom domain → Railway gives you a **CNAME target**
2. In Cloudflare DNS: add a **CNAME record** — your subdomain → Railway's CNAME target
3. Railway handles SSL/TLS automatically
4. Update `ALLOWED_ORIGINS` env var to your custom domain once DNS propagates

### Syncing Data to Railway PostgreSQL

All market data lives in local SQL Server. Use the sync tool to push it to Railway:

```bash
cd C:\Raj\python\portfolio-simulator

# Sync core data tables (tickers, prices, dividends, MM rates, user_admin)
venv\Scripts\python tools\sync_sql_to_postgres.py

# Check row counts on both sides first
venv\Scripts\python tools\sync_sql_to_postgres.py --status

# Dry run (preview without writing)
venv\Scripts\python tools\sync_sql_to_postgres.py --dry-run

# Sync specific tables only
venv\Scripts\python tools\sync_sql_to_postgres.py --tables tickers monthly_prices dividends
```

Requires `POSTGRES_URL` set in `backend\.env`. Full replace strategy per table (TRUNCATE + bulk INSERT).

### DB Type Switch

The backend supports both SQL Server (local) and PostgreSQL (Railway) via a single env var:

```
DB_TYPE=sqlserver   # local development (default fallback)
DB_TYPE=postgres    # Railway production (default in config.py)
```

Set in `backend\.env` locally, or in Railway environment variables for production.
