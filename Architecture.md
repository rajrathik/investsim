# Portfolio Simulator — Architecture & Logic Flow

---

## System Overview

```
┌──────────────────────────────────┐     HTTP/JSON      ┌──────────────────┐
│         Browser Frontend          │ ◄───────────────► │   FastAPI Server  │
│  help.html / simulator / analytics│   localhost:8000   │    (api.py)       │
│  admin.html (Auth0 protected)      │                    └────────┬─────────┘
└──────────────────────────────────┘                              │ SQLAlchemy ORM
                                                                  ▼
                                                        ┌──────────────────┐
                                                        │   SQL Server DB   │
                                                        │ REDACTED-DB-NAME │
                                                        └──────────────────┘
                                                                  ▲
                                            One-time & incremental loads
                                              ┌───────────────┴───────────────┐
                                              │                               │
                                      ┌───────┴───────┐             ┌────────┴────────┐
                                      │ Yahoo Finance  │             │      FRED       │
                                      │  (fetcher.py)  │             │(fred_fetcher.py)│
                                      └───────────────┘             └─────────────────┘
```

---

## Page Architecture & Navigation

```
http://localhost:8000/   →   help.html  (landing page — no auth)
                                │
                ┌───────────────┼───────────────────────────────┐
                ▼               ▼                               ▼
    portfolio-simulator.html  sector-performance.html    [all analytics pages]
         (no auth)              (no auth)               correlation, drawdown,
                │                    │                  rotation, div-growth,
                └────────────────────┘                  growth-chart, risk-return
                  all link to each other
                  via shared navLinks()

http://localhost:8000/admin.html  →  Auth0 lock screen
                                          │ login + user_admin check
                                          ▼
                                     Admin Dashboard
                                     (completely isolated — no links to/from public pages)
```

**Navigation rules:**
- All public pages share a consistent nav bar (Help, Simulator, Sector Returns, Correlation, Drawdowns, Rotation, Div Growth, $10K Growth, Risk vs Return)
- `shared-analytics.js` `navLinks()` generates nav HTML for analytics pages; `sector-performance.html` has it hardcoded
- Admin has no nav links — `admin.html` contains only a Logout button once authenticated
- Root `/` serves `help.html`

---

## Frontend User Flow

### Public Pages
```
User opens http://localhost:8000/
  → help.html served (landing/guide page)
  → User clicks any tool card or nav link
  → Page loads, fetches data from API (no auth required)
  → Simulator: loadTickers() on DOMContentLoaded → populate dropdown → ready
  → Analytics pages: load sector data on DOMContentLoaded → render
```

### Admin Dashboard
```
User opens http://localhost:8000/admin.html
  → Auth overlay shown (z-index: 1000, blocks entire page)
  → initAuth() fetches /api/auth/config → creates Auth0 SPA client
  → User clicks "Log In with Auth0"
  → Redirected to Auth0 hosted login page
  → Auth0 redirects back with authorization code
  → handleRedirectCallback() → getTokenSilently()
  → verifyAdmin() calls GET /api/admin/verify with Bearer token
      → Backend checks user_admin table
      → If authorized: hide overlay, show dashboard + user email + Logout
      → If denied: show error message, hide login button
  → Admin can add tickers, trigger batch loads, monitor status
  → All write calls use adminFetch() which injects Bearer token
  → Token auto-refreshed via getTokenSilently() on each request
```

---

## Database Schema (8 Tables)

**tickers** — Master list of asset symbols (XLK, XLV, XLE, etc.)
Each ticker has: symbol, name, active flag, created/updated timestamps.

**monthly_prices** — One row per ticker per month. Stores open, high, low, close, volume. Linked to tickers via foreign key.

**dividends** — One row per dividend payment. Stores pay date, amount. Linked to tickers via foreign key.

**monthly_mm_rates** — Federal funds rate per month from FRED. Standalone table, no FK.

**annual_mm_rates** — Yearly average of monthly rates. Computed from monthly_mm_rates during load.

**user_logins** — One row per login event. Stores auth0_user_id, email, name, login_time, ip_address, user_agent. Used for audit trail.

**user_admin** — Whitelist of emails authorized to access the admin dashboard. Managed manually via SQL INSERT. Columns: email (PK), name.

**api_request_logs** — One row per API request. Stores request_id, user_email, method, path, status_code, response_time_ms, ip_address, user_agent, error_detail, created_at.

---

## Module Purpose

| Module | What It Does |
|--------|-------------|
| `config.py` | All settings: DB connection string, Auth0 config, max tickers (50), history depth (30 yrs), write API toggle (reads from `.env`) |
| `database.py` | Creates SQLAlchemy engine and session factory. `init_db()` ensures all tables exist at startup |
| `models.py` | ORM models for `Ticker`, `MonthlyPrice`, `Dividend`, `UserLogin`, `UserAdmin`, `ApiRequestLog` with constraints and relationships |
| `mm_rates.py` | ORM models for `MonthlyMoneyMarketRate`, `AnnualMoneyMarketRate` plus loader functions |
| `fetcher.py` | Pulls monthly OHLCV prices and dividend history from Yahoo Finance. Handles full (30 yr) and incremental (configurable months, default 2) modes |
| `fred_fetcher.py` | Pulls federal funds rate from FRED public CSV endpoint. No API key needed. Computes annual averages |
| `loader.py` | Takes fetcher output DataFrames and upserts into SQL Server. `get_tickers_without_data()` identifies new tickers needing initial load |
| `auth.py` | Auth0 token verification. Two modes: JWT via JWKS (when audience is set) or opaque token via `/userinfo` endpoint. `get_current_user` FastAPI dependency. Auth failure logging with IP and path. |
| `api.py` | FastAPI app: all REST endpoints, Auth0 protection on admin routes, public access on all data/analytics endpoints, static file serving, CORS, request ID middleware, API request logging to DB |
| `run_batch.py` | CLI entry point: `python run_batch.py full` or `incremental` — orchestrates fetcher → loader for Yahoo data |
| `run_fred_batch.py` | CLI entry point: same pattern for FRED data |
| `test_connection.py` | Quick script to verify DB connectivity and create tables |
| **tools/** | |
| `generate_test_spreadsheet.py` | Reads `spreadsheet_config.txt`, queries DB for prices/dividends/MM rates, generates 5-sheet Excel workbook with formulas mirroring the JS simulation logic |
| **frontend/** | |
| `help.html` | Landing page: tool overview cards, simulator how-to guide, nav to all public pages. Served at `/` |
| `portfolio-simulator.html/css/js` | Asset Allocation Simulator — no auth required, loads tickers on DOMContentLoaded |
| `sector-performance.html/css/js` | Annual sector returns & dividends quilt, summary stats |
| `correlation.html/js` | Sector correlation matrix (Pearson) |
| `drawdown.html/js` | Peak-to-trough drawdown analysis |
| `sector-rotation.html/js` | Year-by-year sector performance rankings |
| `dividend-growth.html/js` | Year-over-year dividend growth by sector |
| `growth-chart.html/js` | $10K cumulative growth chart (interactive canvas) |
| `risk-return.html/js` | Risk vs return scatter plot |
| `shared-analytics.css/js` | Shared dark theme styles, API utilities (authFetch, getSectorPerformance, getMonthlyPrices), nav link generator, chart tooltip helpers |
| `admin.html` | Admin dashboard — Auth0 protected, isolated, no cross-links to public pages |

---

## Data Load Flow

```
run_batch.py full
  → fetcher.get_monthly_prices(ticker, 30 years)    ← Yahoo Finance HTTP
  → fetcher.get_dividends(ticker, 30 years)          ← Yahoo Finance HTTP
  → loader.load_monthly_prices(db, dataframe)        ← INSERT, skip duplicates
  → loader.load_dividends(db, dataframe)             ← INSERT, skip duplicates
  → repeat for each ticker in DB

run_batch.py full-new  (via API: POST /api/batch/full-new)
  → loader.get_tickers_without_data(db)              ← only tickers with zero price rows
  → same fetch+load flow as above, skipped if all have data

run_batch.py incremental  (via API: POST /api/batch/incremental)
  → fetcher fetches only last N months (configurable, default 2)
  → loader upserts — updates existing rows, inserts new ones

run_fred_batch.py full
  → fred_fetcher.get_monthly_rates(30 years)         ← FRED CSV download
  → mm_rates.load_all_rates(db, dataframe)           ← INSERT/UPSERT
```

Spreadsheet generation (tools/generate_test_spreadsheet.py):
```
Read spreadsheet_config.txt (tickers, amount, years, tax rate, annual growth)
  → Query DB: Ticker, MonthlyPrice, Dividend, MonthlyMoneyMarketRate
  → Build 5 Excel sheets with cross-sheet formula references:
      Setup (raw data) → Monthly Sim (formulas) → Year Summary (SUMIFS)
      → Tax Impact (rates from Setup) → Annual Returns (detail blocks)
  → Save Portfolio_Simulator_Test.xlsx
```

---

## API Endpoint Flow

All endpoints live in `api.py`. Request flow:

```
HTTP Request
  → CORS middleware (allow all origins for development)
  → Request ID middleware (generates UUID, logs method/path, adds X-Request-ID header)
  → Route handler:
      Public endpoints  → no auth check → SQLAlchemy query → JSON response
      Admin endpoints   → get_current_user dependency → Auth0 token verification → handler
  → API request logged to DB (api_request_logs table)
  → Global error handlers catch exceptions → structured error JSON (never leaks stack traces)
```

### Public endpoints (no auth required)

| Endpoint | Usage |
|----------|-------|
| `GET /api/health` | Health check — DB connectivity + record counts |
| `GET /api/auth/config` | Returns Auth0 domain + clientId for admin SPA SDK |
| `GET /api/admin/write-status` | Returns whether write API is enabled |
| `GET /api/tickers/active` | Lists active tickers (used by simulator dropdown) |
| `GET /api/tickers` | Lists all tickers (requires auth token) |
| `GET /api/simulation-data/{symbol}` | Combined monthly prices + dividends for simulation |
| `GET /api/mm-rates/monthly` | Monthly FRED federal funds rates |
| `GET /api/mm-rates/annual` | Annual average FRED rates |
| `GET /api/mm-rates/annual/{year}` | Rate for a specific year |
| `GET /api/sector-performance` | Annual returns + dividends for 12 sector ETFs |
| `GET /api/sector-monthly` | Monthly close prices + dividends for sector analytics |
| `GET /api/batch/status` | Status of last batch job |

### Admin endpoints (Auth0 Bearer token required)

| Endpoint | Usage |
|----------|-------|
| `GET /api/admin/verify` | Checks token + `user_admin` table — grants or denies admin access |
| `POST /api/tickers` | Add new ticker (also requires ENABLE_WRITE_API=True) |
| `PUT /api/tickers/{symbol}` | Update ticker name/active |
| `DELETE /api/tickers/{symbol}` | Delete ticker + all data |
| `POST /api/batch/full` | Full Yahoo data load for all tickers (async, background thread) |
| `POST /api/batch/full-new` | Full load for new tickers only (skips those with data) |
| `POST /api/batch/incremental` | Incremental load — configurable months param (default 2) |
| `POST /api/batch/fred-full` | Full FRED rate history load (async) |
| `POST /api/batch/fred-incremental` | Incremental FRED load — last 3 months (async) |

Write endpoints additionally gated by `ENABLE_WRITE_API=True` in `.env`.

---

## Frontend Simulation Logic

When user clicks "Run Simulation":

**1. Fetch data** — For each allocated ticker, calls `/api/simulation-data/{symbol}` with date range. Also fetches `/api/mm-rates/monthly`. All fetches run in parallel via `Promise.all`.

**2. Build timeline** — Collects all unique year-month keys across all tickers, sorts chronologically.

**3. Redistribute allocation** — Each month, checks which tickers have valid price data. If a ticker has no data (e.g., ETF didn't exist yet), its allocation % is redistributed proportionally to available tickers — full monthly amount is always deployed.

**4. Compute month budget** — `base_monthly_amount + (year_offset × annual_growth)`. Year 1 = base; each subsequent year adds the growth amount. Default growth = $0 (flat).

**5. Accumulate-then-buy (round lot)** — Each ticker has its own accumulation bucket. Each month: `allocated = month_budget × effective_%`, added to that ticker's bucket. `shares = floor(bucket / high_price)` — whole shares only. Cost = shares × high price. Remainder stays in bucket for next month. No money crosses between tickers.

**6. Calculate dividends** — `dividend_cash = dividend_per_share × total_shares_held`. Accumulated as cash, not reinvested.

**7. Apply money market interest** — Prior month's dividend balance grows at `FRED_rate ÷ 12` (monthly compounding). New dividends added after interest. Models parking dividends in a money market fund.

**8. MM-only benchmark** — Separate running balance: each month prior balance grows at MM rate ÷ 12, then same growing month budget is added. Answers "what if you skipped equities entirely?"

**9. Value portfolio** — `portfolio_value = Σ (shares_held × close_price)` across all tickers at month end.

**10. Store snapshots** — Per-ticker detail per month stored for drill-down modals (shares bought, $ spent, bucket balance, running totals, dividends, effective allocation, dividend balance, MM balance).

**11. Render results** — 6 summary tiles, two interactive canvas charts, monthly breakdown table (clickable cells → per-ticker modals), tax impact section, annual returns table.

**12. Tax impact** — User-adjustable tax rate (0–60%) applied per year to dividends and MM interest separately. Shows yearly tax liability breakdown.

**13. Annual returns** — Pre-tax returns per calendar year using DCA mid-year approximation (contributions × 0.542 ≈ 6.5 months average hold). Return = (stock gain + dividends + MM interest) ÷ (beginning stock value + avg invested capital).

---

## Sector Analytics Logic

All analytics pages share `shared-analytics.js` which provides:

- `authFetch()` — plain fetch (no auth needed for public pages)
- `getSectorPerformance()` — cached call to `/api/sector-performance` (annual returns + dividends)
- `getMonthlyPrices()` — cached call to `/api/sector-monthly` (monthly closes + monthly dividends)
- `pearsonCorrelation()`, `stdDev()`, `totalReturn()` — shared math utilities
- `navLinks()` — nav HTML injected into `#navLinks` div on each page
- Tooltip helpers, sector color/order constants

Individual page logic:

| Page | Data Used | Key Calculation |
|------|-----------|----------------|
| `sector-performance.js` | Annual returns + dividends | Quilt table colored by return magnitude; CAGR, best/worst year, dividend stats per sector |
| `correlation.js` | Monthly prices | Pearson correlation matrix between all sector pairs over selected year range |
| `drawdown.js` | Monthly prices | Max peak-to-trough % loss; time to recovery for each sector |
| `sector-rotation.js` | Annual returns | Year-by-year rank ordering; leadership count (top 1, top 3, bottom 3) |
| `dividend-growth.js` | Annual dividends | YoY % change in dividends per sector |
| `growth-chart.js` | Monthly prices + annual dividends | Cumulative growth of $10K invested; interactive canvas with sector toggles |
| `risk-return.js` | Annual returns | StdDev of annual returns (X) vs average total return (Y); scatter plot |

---

## Key Design Decisions

- **Buy at monthly high**: Conservative worst-case dollar-cost averaging entry.
- **Round-lot accumulation per ticker**: Only whole shares; each ticker keeps its own bucket. Preserves allocation intent even at low dollar amounts or high share prices.
- **Prior year-end cutoff**: Simulation ends December of last complete year — no partial-year data.
- **Dividends as cash**: Not reinvested into equities — tracked separately for true cash generation visibility.
- **Dividends earn MM interest**: Accumulated dividends modeled as parked in a money market fund at the FRED rate (monthly compounding).
- **MM-only benchmark**: Parallel calculation showing the same contributions in money market only — answers "was equity risk worth it?"
- **Public pages, isolated admin**: All analytics and simulation pages are freely accessible. Admin is Auth0-protected with zero navigation overlap — you cannot reach admin from any public page, and admin has no links out.
- **Help as landing page**: Root URL serves `help.html` — a guide with tool cards and full simulator how-to. Simulator loads directly to the simulation UI (welcome overlay removed).
- **Auth0 admin only**: `auth.py` provides full JWT/JWKS + opaque token `/userinfo` verification. `get_current_user` dependency used only on admin-relevant routes. All data/analytics endpoints are public.
- **Two-layer admin security**: (1) Auth0 login, (2) email checked against `user_admin` DB table. Write operations additionally gated by `ENABLE_WRITE_API` config flag.
- **Opaque token support**: With no Auth0 audience configured, Auth0 issues opaque tokens. Backend validates via `/userinfo` endpoint — simpler setup, no Custom API registration needed.
- **Smart batch loading**: Three modes — full-new (only new tickers), incremental (configurable months, default 2), full (all tickers, rare). Background threads keep the API responsive during long loads.
- **Read-only API by default**: `ENABLE_WRITE_API=False` in config. Write endpoints return 403 until explicitly enabled in `.env`.
- **No build tools**: Vanilla HTML/CSS/JS. No Node.js, no webpack, no framework. All static files served by FastAPI's `StaticFiles` mount.
- **Shared analytics layer**: `shared-analytics.js` and `shared-analytics.css` provide a single source of truth for API calls (with caching), math utilities, nav links, and dark theme styles across all analytics pages.
- **Interactive canvas charts**: Custom canvas rendering with crosshair and hover tooltip. No chart library dependency.
- **Excel verification tool**: Python script generates a 5-sheet Excel workbook from real DB data using formulas that mirror the JS simulation. Users can trace every calculation step. Reads from a plain-text config file.
- **API request logging**: Every API call (path starting with `/api`) logged to `api_request_logs` table. Static file requests skipped to avoid noise.
- **Structured error responses**: Global exception handlers catch all errors — never leaks stack traces. Returns consistent `{error, detail, request_id}` JSON. Request IDs in headers for correlation.
