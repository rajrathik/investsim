# Portfolio Simulator — Architecture & Logic Flow

---

## System Overview

```
┌──────────────────────────────────┐     HTTP/JSON      ┌──────────────────┐
│         Browser Frontend          │ ◄───────────────► │   FastAPI Server  │
│ index.html / simulator / analytics│   localhost:8000   │    (api.py)       │
│  admin.html (Auth0 protected)      │                    └────────┬─────────┘
└──────────────────────────────────┘                              │ SQLAlchemy ORM
                                                                  ▼
                                                        ┌──────────────────────────────────┐
                                                        │  Database                         │
                                                        │  SQL Server (local dev)            │
                                                        │  PostgreSQL  (Railway production)  │
                                                        │  DB_TYPE env var selects which     │
                                                        └──────────────────────────────────┘
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
http://localhost:8000/   →   index.html  (landing page — tool cards, no auth)
                                │
                ┌───────────────┼───────────────────────────────┐
                ▼               ▼                               ▼
    portfolio-simulator.html  sector-performance.html    [all analytics pages]
    simulator-guide.html        (no auth)               correlation, drawdown,
         (no auth)                                      rotation, div-growth,
                                                        growth-chart, risk-return,
                                                        sp500-history, sp500-simulate,
                                                        stack-earn, extreme-months,
                                                        extreme-years, bad-streaks,
                                                        sp500-rolling-returns

                  all tool pages have a ← Home link back to index.html

http://localhost:8000/saved-simulations.html  →  Saved Simulations (sign-in required)

http://localhost:8000/admin.html  →  Auth0 lock screen
                                          │ login + user_admin check
                                          ▼
                                     Admin Dashboard
                                     (completely isolated — no links to/from public pages)
```

**Navigation rules:**
- All public tool pages have a `← Home` link (top-left of header) pointing back to `index.html`
- `index.html` is the hub — no nav bar needed; users navigate out via tool cards and back via `← Home`
- Admin has no nav links — `admin.html` contains only a Logout button once authenticated
- Root `/` serves `index.html`
- Every page loads `theme-toggle.js` in `<head>` for dark/light theme switching with localStorage persistence
- Every public page loads Auth0 SPA SDK + `shared-auth.js` for optional sign-in (welcome bar, sign-in link)
- Signed-in users see member content on the landing page (Saved Simulations) and can access `saved-simulations.html`. `stack-earn.html` is fully built but not linked from the landing page — accessible via direct URL only
- Signed-in members who are admins also see an Admin tile — auto-detected via `GET /api/admin/verify` using `_pubAuthFetch` on page load; `_admin_hint` flag cached in localStorage

---

## Frontend User Flow

### Public Pages
```
User opens http://localhost:8000/
  → index.html served (landing page with tool cards)
  → theme-toggle.js IIFE runs in <head> — reads localStorage('theme'), sets data-theme on <html> (no flash)
  → DOMContentLoaded: toggle button injected at bottom-right
  → shared-auth.js IIFE runs:
      → Checks localStorage('pub_auth_user') for cached user
      → If cached: injects welcome bar immediately (no flash)
      → Inits Auth0 SPA client, handles redirect callback if returning from Auth0
      → If authenticated: shows welcome bar, caches user, dispatches 'pubauth' event
      → If not authenticated: shows "Sign In" link in header
      → Exposes window._pubAuthFetch() and window._pubIsSignedIn() globally
  → index.html listens for 'pubauth' event → shows/hides member content section
  → calls /api/admin/verify → if admin, shows Admin tile and sets _admin_hint in localStorage
  → User clicks any tool card or nav link
  → Page loads, fetches data from API (no auth required)
  → Simulator: loadTickers() on DOMContentLoaded → populate dropdown → ready
  → Analytics pages: load sector data on DOMContentLoaded → render
```

### Saved Simulations (signed-in users)
```
User clicks "Save Simulation" on portfolio-simulator.html results
  → saveSimulation() builds payload from window._lastResults
  → Calls POST /api/simulations via window._pubAuthFetch() (Bearer token)
  → Server validates (max 3 per user), saves to saved_simulations table → 201
  → User navigates to saved-simulations.html (via member section tile or nav)
  → Page checks sign-in state → if signed in, calls GET /api/simulations
  → Renders simulation cards with ticker tags, values grid, ? tooltips, delete buttons
  → Delete calls DELETE /api/simulations/{id} → refreshes list
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

## Database Schema (10 Tables)

**tickers** — Master list of asset symbols (XLK, XLV, XLE, etc.)
Each ticker has: symbol, name, active flag, created/updated timestamps.

**monthly_prices** — One row per ticker per month. Stores open, high, low, close, volume. Linked to tickers via foreign key.

**dividends** — One row per dividend payment. Stores pay date, amount. Linked to tickers via foreign key.

**monthly_mm_rates** — Federal funds rate per month from FRED. Standalone table, no FK.

**annual_mm_rates** — Yearly average of monthly rates. Computed from monthly_mm_rates during load.

**user_logins** — One row per login event. Stores auth0_user_id, email, name, login_time, ip_address, user_agent. Used for audit trail.

**user_admin** — Whitelist of emails authorized to access the admin dashboard. Managed manually via SQL INSERT. Columns: email (PK), name.

**api_request_logs** — One row per API request. Stores request_id, user_email, method, path, status_code, response_time_ms, ip_address, user_agent, error_detail, created_at.

**saved_simulations** — User's saved portfolio simulation results (max 3 per user). Stores auth0_user_id, email, tickers_json (allocation map), start/end year, monthly_amount, annual_growth, 6 result values (total_invested, equity_value, dividends_earned, cash_accrual, mm_earned, portfolio_balance), total_return_pct, mmf_value, created_at. Auto-increment ID with gap management (display numbering handled by frontend).

**shiller_market_data** — Monthly S&P 500 historical data from Robert Shiller (shillerdata.com). 1,863 rows, Jan 1871–present. 22 columns: DataDate, Year, Month, SpPrice, Dividend, Earnings, Cpi, LongInterestRate, real/total-return series, Cape, TrCape, ExcessCapeYield, bond returns, 10-year forward returns, and `NominalTotalReturn` (calculated: monthly price return + dividend yield). Loaded once via `backend/onetime/load_shiller_data.py`. Not in the core ORM (models.py) — queried via raw SQL in the API.

---

## Module Purpose

| Module | What It Does |
|--------|-------------|
| `config.py` | All settings: `DB_TYPE` switch (sqlserver/postgres), `POSTGRES_URL`, SQL Server connection params, Auth0 config, max tickers (50), history depth (30 yrs), `ENABLE_WRITE_API` toggle, `ALLOWED_ORIGINS` for CORS. All values from env vars / `.env` |
| `database.py` | Creates SQLAlchemy engine and session factory. `init_db()` ensures all tables exist at startup |
| `models.py` | ORM models for `Ticker`, `MonthlyPrice`, `Dividend`, `UserLogin`, `UserAdmin`, `ApiRequestLog`, `SavedSimulation` with constraints and relationships |
| `mm_rates.py` | ORM models for `MonthlyMoneyMarketRate`, `AnnualMoneyMarketRate` plus loader functions |
| `fetcher.py` | Pulls monthly OHLCV prices and dividend history from Yahoo Finance. Handles full (30 yr) and incremental (configurable months, default 2) modes |
| `fred_fetcher.py` | Pulls federal funds rate from FRED public CSV endpoint. No API key needed. Computes annual averages |
| `loader.py` | Takes fetcher output DataFrames and upserts into the configured DB. `get_tickers_without_data()` identifies new tickers needing initial load |
| `auth.py` | Auth0 token verification. Two modes: JWT via JWKS (when audience is set) or opaque token via `/userinfo` endpoint. `get_current_user` FastAPI dependency. Auth failure logging with IP and path. |
| `api.py` | FastAPI app: all REST endpoints, Auth0 protection on write/admin routes, rate limiting (slowapi), public access on read endpoints, static file serving, CORS, request ID middleware, API request logging to DB, pageview tracking, serves robots.txt and sitemap.xml |
| `run_batch.py` | CLI entry point: `python run_batch.py full` or `incremental` — orchestrates fetcher → loader for Yahoo data |
| `run_fred_batch.py` | CLI entry point: same pattern for FRED data |
| `test_connection.py` | Quick script to verify DB connectivity and create tables |
| **tools/** | |
| `generate_test_spreadsheet.py` | Reads `spreadsheet_config.txt`, queries DB for prices/dividends/MM rates, generates 5-sheet Excel workbook with formulas mirroring the JS simulation logic |
| `sync_sql_to_postgres.py` | Syncs local SQL Server data to Railway PostgreSQL. Full replace per table. Supports `--status`, `--dry-run`, `--tables`, `--all` modes. Requires `POSTGRES_URL` in `backend\.env` |
| **frontend/** | |
| `index.html` | Landing page: tool overview cards, member content section (shown when signed in), nav to all public pages. Served at `/` |
| `simulator-guide.html` | How It Works guide for the simulator (standalone page linked from simulator header) |
| `portfolio-simulator.html/css/js` | Asset Allocation Simulator — stepper allocation controls (5% increments), save simulation button (signed in), tile info tooltips, loads tickers on DOMContentLoaded |
| `sector-performance.html/css/js` | Annual sector returns & dividends quilt, summary stats |
| `correlation.html/js` | Sector correlation matrix (Pearson) |
| `drawdown.html/js` | Peak-to-trough drawdown analysis |
| `sector-rotation.html/js` | Year-by-year sector performance rankings |
| `dividend-growth.html/js` | Year-over-year dividend growth by sector |
| `growth-chart.html/js` | $10K cumulative growth chart (interactive canvas) |
| `risk-return.html/js` | Risk vs return scatter plot |
| `sp500-history.html/js` | S&P 500 decade heatmap. Compounds monthly `NominalTotalReturn` values into annual returns; renders a color-interpolated decade grid (muted green/red); methodology panel explains columns used, formula, and assumptions |
| `sp500-simulate.html/js` | S&P 500 Historical Simulator. Pick year range (1872–2024), starting amount, monthly contribution → final balance, stat strip, area chart (balance vs invested), year-by-year table with inline return bars. API: `GET /api/sp500-simulate` |
| `stack-earn.html/js` | Stack & Earn savings calculator. Two tabs: Savings (forward simulation with split-bucket compounding) and Goal (binary-search reverse solve). Loads tier rates from `GET /api/stack-earn/savings-tiers` and `GET /api/stack-earn/goal-tiers`. Three independent balance buckets (T1/T2/T3) compound at their own monthly rate. Tier table respects `display_rate`, `display_upto`, and `product_type` fields from the API |
| `montecarlo.html/js` | Monte Carlo portfolio simulator. Block-bootstrap: draws random N-year return blocks from Shiller history, 1,000 trials client-side. Horizon 5–30yr. Fan chart (P10/P25/P50/P75/P90 bands). Supports withdrawal mode (tracks ruin rate) and optional one-time lump sum event. Market Cycle Sensitivity selector (Short·1yr / Medium·3yr / Long·5yr) with plain-language `?` tooltip. Percentile table includes Deposited column and `?` tooltip explaining each column. API: `GET /api/shiller-monthly-returns` |
| `extreme-months.html/js` | Monthly Market Extremes. Fetches `GET /api/sp500-extreme-months?n=20` once (cached). Renders side-by-side panels: worst months (red) and best months (green). Summary cards show all-time worst and best. Table rows: rank, date, return%, $10K result, mini-bar (width proportional to magnitude, scales to #1 entry). Chip toggle for top-10/top-20 slices from cached 20 with no re-fetch |
| `extreme-years.html/js` | Annual Market Extremes. Fetches `GET /api/sp500-extreme-years?n=20` once (cached). Same layout as extreme-months. Annual returns compounded from monthly Shiller data server-side. Chip toggle for top-10/top-20 |
| `bad-streaks.html/js` | 5-Year Crash Periods & Recovery. Fetches `GET /api/sp500-bad-streaks?n=10` once (cached). Renders worst non-overlapping 5-year windows in a single panel table: rank, period dates, 5-yr return, $10K result, year-by-year color pills, recovery Yr+1/Yr+2/combined columns. 3 summary stat cards. 5/10 period chip toggle re-renders from cached data with no re-fetch |
| `sp500-rolling-returns.html/js` | S&P 500 Rolling Returns. Fetches `GET /api/damodaran-forward-returns` once (all 98 years, cached client-side). Table columns: Year, 1Y, 3Y, 5Y, 7Y, 10Y — all computed server-side as geometric mean (CAGR) of that year's return and the following N-1 years, null when the window runs past the last year on record. From/To year selectors filter the cached data client-side; default sort newest-first. Source: `damodaran_annual_returns` table |
| `saved-simulations.html` | View & delete saved simulations — auth-gated (shows sign-in prompt if not logged in), fetches via `_pubAuthFetch()`, renders cards with ticker tags, value tiles with ? tooltips, delete buttons |
| `shared-analytics.css` | Single source of truth for CSS: `:root` variables, reset, fonts, header, `← Home` link styles, welcome bar styles, dark+light theme overrides, toggle button styles. All page-specific CSS files contain only overrides |
| `shared-analytics.js` | Shared API utilities (authFetch, getSectorPerformance, getMonthlyPrices) with error handling (try/catch, resp.ok checks), pageview tracking beacon, chart tooltip helpers, sector constants |
| `shared-auth.js` | Public Auth0 sign-in IIFE: inits Auth0 SPA client, handles login/logout, injects welcome bar + sign-in link, caches user in localStorage, exposes `window._pubAuthFetch()` (authenticated fetch) and `window._pubIsSignedIn()`, dispatches `pubauth` CustomEvent. Skips admin.html. All pages redirect to `/` for Auth0 callback |
| `theme-toggle.js` | Dark/light theme: synchronous IIFE sets `data-theme` before render (no FOUC), injects toggle button, exposes `window.THEME` getters for Canvas, dispatches `themechange` event, persists via localStorage |
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
  → Rate limiter (slowapi — per-IP limits, returns 429 when exceeded)
  → Request ID middleware (generates UUID, logs method/path, adds X-Request-ID header)
  → Route handler:
      Public endpoints  → no auth check → SQLAlchemy query → JSON response
      Write endpoints   → get_current_user dependency → Auth0 JWT + ENABLE_WRITE_API check → handler
      Admin endpoints   → get_current_user dependency → Auth0 token verification → handler
  → API request logged to DB (api_request_logs table)
  → Global error handlers catch exceptions → structured error JSON (never leaks stack traces)
```

### Rate Limits (per IP)

| Category | Limit | Endpoints |
|----------|-------|-----------|
| Default | 60/min | All endpoints not listed below |
| Heavy reads | 30/min | `/api/sector-performance`, `/api/sector-monthly` |
| Writes | 10/min | Ticker CRUD, simulation saves, login events |
| Batch | 5/min | All `/api/batch/*` POST endpoints |
| Tracking | 30/min | `/api/track/pageview` |

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
| `POST /api/auth/login-event` | Logs public user login event to `user_logins` table |
| `POST /api/track/pageview` | Records page view (fire-and-forget, self-hosted analytics) |
| `GET /api/sp500-extreme-months` | Returns N best and N worst single months from Shiller data (rank, date, return_pct, end_value). Default N=20 |
| `GET /api/sp500-extreme-years` | Returns N best and N worst full calendar years by compounded NominalTotalReturn (rank, date as year string, return_pct, end_value). Default N=20, max 50. 60/min rate limit |
| `GET /api/sp500-bad-streaks` | Returns N worst non-overlapping 5-year windows. Each period includes rank, start/end year, return_pct, end_value ($10K result), years_detail (per-year pills), recovery_yr1, recovery_yr2, recovery_combined_pct. Default N=10, max 20. 60/min rate limit |
| `GET /api/damodaran-forward-returns` | Returns 1/3/5/7/10-year rolling forward CAGR for every year in `damodaran_annual_returns`. Each entry: year, r1, r3, r5, r7, r10 (null when the dataset doesn't have enough future years to fill the window). 30/min rate limit |
| `GET /api/stack-earn/savings-tiers` | Tier rates for the savings calculator. Returns 8 fields: tier_number, tier_label, min_amount, max_amount, annual_rate, display_rate, display_upto, product_type |
| `GET /api/stack-earn/goal-tiers` | Tier rates for the goal calculator. Same 8-field response |

### Authenticated endpoints (Auth0 Bearer token required — public sign-in)

| Endpoint | Usage |
|----------|-------|
| `POST /api/simulations` | Save a simulation result (max 3 per user, returns 409 if full) |
| `GET /api/simulations` | List saved simulations for the current user (sorted by created_at) |
| `DELETE /api/simulations/{sim_id}` | Delete a saved simulation (user can only delete their own) |

### Admin endpoints (Auth0 Bearer token + ENABLE_WRITE_API required)

| Endpoint | Usage |
|----------|-------|
| `GET /api/admin/verify` | Checks token + `user_admin` table — grants or denies admin access |
| `POST /api/tickers` | Add new ticker (requires Auth0 token + ENABLE_WRITE_API) |
| `PUT /api/tickers/{symbol}` | Update ticker name/active (requires Auth0 token + ENABLE_WRITE_API) |
| `DELETE /api/tickers/{symbol}` | Delete ticker + all data (requires Auth0 token + ENABLE_WRITE_API) |
| `POST /api/batch/full` | Full Yahoo data load for all tickers (requires Auth0 token + ENABLE_WRITE_API) |
| `POST /api/batch/full-new` | Full load for new tickers only (requires Auth0 token + ENABLE_WRITE_API) |
| `POST /api/batch/incremental` | Incremental load — configurable months (requires Auth0 token + ENABLE_WRITE_API) |
| `POST /api/batch/fred-full` | Full FRED rate history load (requires Auth0 token + ENABLE_WRITE_API) |
| `POST /api/batch/fred-incremental` | Incremental FRED load — last 3 months (requires Auth0 token + ENABLE_WRITE_API) |
| `GET /api/admin/stack-earn/savings-tiers` | List savings tiers (admin-only) |
| `PUT /api/admin/stack-earn/savings-tiers/{n}` | Update a savings tier (rate, label, display flags) |
| `POST /api/admin/stack-earn/savings-tiers` | Add a new savings tier (auto-assigns next tier_number) |
| `GET /api/admin/stack-earn/goal-tiers` | List goal tiers (admin-only) |
| `PUT /api/admin/stack-earn/goal-tiers/{n}` | Update a goal tier |
| `POST /api/admin/stack-earn/goal-tiers` | Add a new goal tier |

All write endpoints are **double-gated**: Auth0 JWT token + `ENABLE_WRITE_API=True` in `.env`. Rate limited to 10/min (ticker CRUD) or 5/min (batch loads).

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

**11. Render results** — 6 summary tiles (each with ? info tooltip), save simulation button (if signed in), two interactive canvas charts, monthly breakdown table (clickable cells → per-ticker modals), tax impact section, annual returns table.

**12. Tax impact** — User-adjustable tax rate (0–60%) applied per year to dividends and MM interest separately. Shows yearly tax liability breakdown.

**13. Annual returns** — Pre-tax returns per calendar year using DCA mid-year approximation (contributions × 0.542 ≈ 6.5 months average hold). Return = (stock gain + dividends + MM interest) ÷ (beginning stock value + avg invested capital).

---

## Sector Analytics Logic

All analytics pages share `shared-analytics.js` which provides:

- `authFetch()` — plain fetch (no auth needed for public pages)
- `getSectorPerformance()` — cached call to `/api/sector-performance` (annual returns + dividends)
- `getMonthlyPrices()` — cached call to `/api/sector-monthly` (monthly closes + monthly dividends)
- `pearsonCorrelation()`, `stdDev()`, `totalReturn()` — shared math utilities
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
| `sp500-history.js` | `shiller_market_data.NominalTotalReturn` | Compounds monthly returns into annual returns; renders decade heatmap with muted color interpolation (dark green/dark red poles); hover tooltip; re-colors on theme change |
| `sp500-simulate.js` | `GET /api/sp500-simulate` | Historical simulation: each month balance = (balance + monthly) × (1 + NominalTotalReturn); renders stat strip, area chart with hover crosshair, year-by-year table with color-coded return bars |
| `stack-earn.js` | `GET /api/stack-earn/savings-tiers`, `GET /api/stack-earn/goal-tiers` | Savings: 3-bucket split compounding (t1/t2/t3 each earn their rate independently). Goal: 60-iteration binary search to find monthly contribution → renders hero result + year-by-year table. `renderTiers()` respects display_rate / display_upto / product_type flags |
| `montecarlo.js` | `GET /api/shiller-monthly-returns` | Fetches ~1,850 monthly returns once (cached). Block-bootstrap: each trial draws random N-year blocks (1/3/5yr cycles), runs 1,000 trials. Horizon selectable 5–30yr. Computes P10/P25/P50/P75/P90 per year. Fan chart draws two filled bands + median line + optional deposits line. Percentile table with Deposited column. Ruin tracking for withdrawal mode. Optional one-time lump sum event |
| `extreme-months.js` | `GET /api/sp500-extreme-months` | Fetches n=20 worst+best once (cached). Chip toggle re-renders sliced table (top-10 or top-20) without re-fetching. Mini-bars scale to the #1 entry in each list. Red/green color classes adapt to dark-mode via CSS `[data-theme="dark"]` overrides |
| `extreme-years.js` | `GET /api/sp500-extreme-years` | Same pattern as extreme-months. Annual returns compounded server-side from monthly Shiller data. Chip toggle, mini-bars, dark-mode CSS |
| `bad-streaks.js` | `GET /api/sp500-bad-streaks` | Fetches n=10 once (cached). Greedy non-overlapping 5-year window selection done server-side. Client computes summary card averages (avg Yr+1, avg Yr+2 across all shown periods). Chip toggle (5/10) re-slices cached data. Year pills colored red/green by sign. Recovery columns use green/red with `c-rec-pos`/`c-rec-neg` classes. Combined recovery = compounded Yr+1 × Yr+2 |
| `sp500-rolling-returns.js` | `GET /api/damodaran-forward-returns` | Fetches all 98 years once (cached). N-year CAGR windows computed server-side. From/To year `<select>`s (populated from actual min/max years in the response) filter the cached array client-side and re-render sorted newest-first. Null cells render as a muted em-dash |

---

## Key Design Decisions

- **Buy at monthly high**: Conservative worst-case dollar-cost averaging entry.
- **Round-lot accumulation per ticker**: Only whole shares; each ticker keeps its own bucket. Preserves allocation intent even at low dollar amounts or high share prices.
- **Prior year-end cutoff**: Simulation ends December of last complete year — no partial-year data.
- **Dividends as cash**: Not reinvested into equities — tracked separately for true cash generation visibility.
- **Dividends earn MM interest**: Accumulated dividends modeled as parked in a money market fund at the FRED rate (monthly compounding).
- **MM-only benchmark**: Parallel calculation showing the same contributions in money market only — answers "was equity risk worth it?"
- **Public pages, isolated admin**: All analytics and simulation pages are freely accessible. Admin is Auth0-protected with zero navigation overlap — you cannot reach admin from any public page, and admin has no links out.
- **Landing page with tool cards**: Root URL serves `index.html` with clickable cards for each tool. Separate `simulator-guide.html` for the How It Works walkthrough. Simulator loads directly to the simulation UI.
- **Auth0 admin only**: `auth.py` provides full JWT/JWKS + opaque token `/userinfo` verification. `get_current_user` dependency used only on admin-relevant routes. All data/analytics endpoints are public.
- **Two-layer admin security**: (1) Auth0 login, (2) email checked against `user_admin` DB table. Write operations additionally gated by `ENABLE_WRITE_API` config flag.
- **Opaque token support**: With no Auth0 audience configured, Auth0 issues opaque tokens. Backend validates via `/userinfo` endpoint — simpler setup, no Custom API registration needed.
- **Smart batch loading**: Three modes — full-new (only new tickers), incremental (configurable months, default 2), full (all tickers, rare). Background threads keep the API responsive during long loads.
- **Read-only API by default**: `ENABLE_WRITE_API=False` in config. Write endpoints return 403 until explicitly enabled in `.env`.
- **Optional public sign-in**: `shared-auth.js` IIFE loaded on all public pages. Handles Auth0 init, login/logout, welcome bar injection, and exposes `_pubAuthFetch()` for authenticated API calls. Completely separate from admin auth. Skips `admin.html`. Uses `localStorage` cache (`pub_auth_user`) for instant welcome bar display across pages.
- **Single callback URL for all public pages**: All public pages use `window.location.origin + '/'` as the Auth0 redirect URI. Only two URLs ever needed in Auth0 Dashboard: `/` (public) and `/admin.html` (admin). Adding new pages never requires Auth0 config changes.
- **Saved simulations**: Max 3 per user enforced server-side (409 Conflict). Auto-increment DB IDs with gaps after deletions — frontend uses array index + 1 for sequential display numbering (Portfolio #1, #2, #3).
- **Tile info tooltips**: Each of the 6 summary result tiles has a `?` icon that reveals a description tooltip on hover. Uses CSS-only hover with `.tile-info:hover .tile-tooltip` (no JS). Parent card uses `z-index` elevation on hover so tooltips overlay adjacent cards.
- **No build tools**: Vanilla HTML/CSS/JS. No Node.js, no webpack, no framework. All static files served by FastAPI's `StaticFiles` mount.
- **CSS consolidation**: `shared-analytics.css` is the single source of truth for `:root` variables, reset, fonts, header, and shared component styles. `sector-performance.css` and `portfolio-simulator.css` contain only page-specific overrides — no duplicate `:root`, reset, or body rules.
- **Dark/light theme toggle**: `theme-toggle.js` loaded synchronously in `<head>` on all public pages. IIFE reads localStorage and sets `data-theme` attribute on `<html>` before body renders (prevents flash). DOMContentLoaded injects floating toggle button. Dispatches `themechange` CustomEvent for Canvas re-rendering. Exposes `window.THEME` getter object so Canvas-drawing JS can read computed CSS variable values.
- **5% stepper allocation controls**: Replaced range sliders with −/+ button pairs that increment/decrement by 5%. Equal Split rounds to nearest 5%. Tickers at 0% are silently excluded from the simulation (filtered at `active` array before any API calls).
- **Interactive canvas charts**: Custom canvas rendering with crosshair and hover tooltip. No chart library dependency. Canvas structural colors use `THEME.*` getters that re-read CSS variables on theme change.
- **Excel verification tool**: Python script generates a 5-sheet Excel workbook from real DB data using formulas that mirror the JS simulation. Users can trace every calculation step. Reads from a plain-text config file.
- **API request logging**: Every API call (path starting with `/api`) logged to `api_request_logs` table. Static file requests skipped to avoid noise.
- **Self-hosted pageview tracking**: `navigator.sendBeacon()` on all 13 pages fires `POST /api/track/pageview` writing to existing `api_request_logs` table with `method=PAGEVIEW`. Zero cost, no third-party analytics.
- **Error handling**: All analytics pages wrap `loadData()` in try/catch with user-facing error div. Shared API layer checks `resp.ok` and throws on HTTP errors. No silent failures.
- **Rate limiting**: slowapi library with per-IP limits. Default 60/min for all endpoints. Tighter limits on expensive reads (30/min), writes (10/min), and batch operations (5/min). Returns HTTP 429 Too Many Requests.
- **Write endpoint double-gating**: All POST/PUT/DELETE endpoints require both a valid Auth0 JWT token AND `ENABLE_WRITE_API=True` config flag. Neither alone is sufficient.
- **SEO foundations**: All 12 public HTML pages have `<meta name="description">`, canonical links, Open Graph tags, and Twitter Card tags. `robots.txt` allows crawlers but blocks `/admin.html` and `/api/`. `sitemap.xml` lists all public pages with priorities. JSON-LD structured data on key pages (WebSite, WebApplication, BreadcrumbList). All URLs use `investsim.claritycapitaltools.com` placeholder — global find-and-replace at deploy time.
- **Structured error responses**: Global exception handlers catch all errors — never leaks stack traces. Returns consistent `{error, detail, request_id}` JSON. Request IDs in headers for correlation.
