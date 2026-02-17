# Portfolio Simulator — Architecture & Logic Flow

---

## System Overview

```
┌─────────────────────┐     HTTP/JSON      ┌──────────────────┐
│   Browser Frontend   │ ◄───────────────► │   FastAPI Server  │
│  (portfolio-sim.html)│   localhost:8000   │    (api.py)       │
└─────────────────────┘                    └────────┬─────────┘
                                                    │ SQLAlchemy ORM
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
                            │ Yahoo Finance  │             │   FRED (CSV)    │
                            │  (fetcher.py)  │             │(fred_fetcher.py)│
                            └───────────────┘             └─────────────────┘
```

---

## Frontend User Flow

```
User opens http://localhost:8000/portfolio-simulator.html
  → Auth overlay shown (z-index: 1000, blocks simulator)
  → User clicks "Log In with Auth0"
  → Redirected to Auth0 hosted login page (email/password or Google)
  → Auth0 redirects back with authorization code
  → initAuth() handles callback, gets user profile
  → onLoginSuccess():
      - Hide auth overlay
      - Show user email + Log Out button in header
      - Log login event to user_logins table via POST /api/auth/login-event
      - Show Welcome Guide overlay (z-index: 500)
  → User reads 4-section guide (what it does, how to use, what you'll see, tips)
  → Clicks "Got It — Let's Start"
  → dismissWelcomeGuide():
      - Hide welcome overlay
      - loadTickers() → populate dropdown → simulator ready
  → User configures simulation and clicks "Run Simulation"
```

**Overlay z-index layering:** Auth (1000) > Welcome Guide (500) > Result Modals (200)

---

## Database Schema (8 Tables)

**tickers** — Master list of ETF symbols (XLK, XLV, XLE, etc.)
Each ticker has: symbol, name, active flag, created/updated timestamps.

**monthly_prices** — One row per ticker per month. Stores open, high, low, close, volume. Linked to tickers via foreign key.

**dividends** — One row per dividend payment. Stores pay date, amount. Linked to tickers via foreign key.

**monthly_mm_rates** — Federal funds rate per month from FRED. Standalone table, no FK.

**annual_mm_rates** — Yearly average of monthly rates. Computed from monthly_mm_rates during load.

**user_logins** — One row per login event. Stores auth0_user_id, email, name, login_time, ip_address, user_agent. Used for audit trail and future per-user simulation storage.

**user_admin** — Whitelist of emails authorized to access the admin dashboard. Managed manually via SQL INSERT. Columns: email (PK), name.

**api_request_logs** — One row per API request. Stores request_id, user_email, method, path, status_code, response_time_ms, ip_address, user_agent, error_detail, created_at.

---

## Module Purpose

| Module | What It Does |
|--------|-------------|
| `config.py` | All settings: DB connection string, max tickers (50), history depth (20 yrs), write API toggle |
| `database.py` | Creates SQLAlchemy engine and session factory. `init_db()` ensures all tables exist at startup |
| `models.py` | ORM models for `Ticker`, `MonthlyPrice`, `Dividend`, `UserLogin`, `UserAdmin`, `ApiRequestLog` with constraints and relationships |
| `mm_rates.py` | ORM models for `MonthlyMoneyMarketRate`, `AnnualMoneyMarketRate` plus loader functions |
| `fetcher.py` | Pulls monthly OHLCV prices and dividend history from Yahoo Finance. Handles full (20 yr) and incremental (3 month) modes |
| `fred_fetcher.py` | Pulls federal funds rate from FRED public CSV endpoint. No API key needed. Computes annual averages |
| `loader.py` | Takes fetcher output DataFrames and upserts into SQL Server. Handles skip-if-exists (full) and update-if-exists (incremental) |
| `auth.py` | Auth0 token verification (opaque tokens via /userinfo endpoint), `get_current_user` FastAPI dependency, auth failure logging |
| `api.py` | FastAPI app with all REST endpoints, auth protection, static file serving, CORS, error handling, request IDs, API request logging to DB, FRED batch endpoints, admin write-status endpoint |
| `run_batch.py` | CLI entry point: `python run_batch.py full` or `incremental` — orchestrates fetcher → loader for Yahoo data |
| `run_fred_batch.py` | CLI entry point: same pattern for FRED data |
| `test_connection.py` | Quick script to verify DB connectivity and create tables |
| **tools/** | |
| `generate_test_spreadsheet.py` | Reads `spreadsheet_config.txt` (or interactive prompts), queries DB for prices/dividends/MM rates, generates 5-sheet Excel workbook with formulas mirroring the JS simulation logic |
| `spreadsheet_config.txt` | User-editable config: tickers + allocations, monthly amount, years, tax rate, annual deposit growth |
| `Spreadsheet_Guide.md` | One-page walkthrough for users navigating the Excel workbook |
| **frontend/** | |
| `portfolio-simulator.html` | Main simulator page (Auth0 login required) |
| `portfolio-simulator.css` | Simulator styles (dark theme) |
| `portfolio-simulator.js` | Simulation engine + UI rendering |
| `admin.html` | Admin dashboard — manage tickers and trigger data loads (Auth0 login + user_admin whitelist) |

---

## Data Load Flow

```
run_batch.py full
  → fetcher.get_monthly_prices(ticker, 20 years)    ← Yahoo Finance HTTP
  → fetcher.get_dividends(ticker, 20 years)          ← Yahoo Finance HTTP
  → loader.load_monthly_prices(db, dataframe)        ← INSERT, skip duplicates
  → loader.load_dividends(db, dataframe)             ← INSERT, skip duplicates
  → repeat for each ticker in DB

run_fred_batch.py full
  → fred_fetcher.get_monthly_rates(20 years)         ← FRED CSV download
  → fred_fetcher.compute_annual_averages(dataframe)
  → mm_rates.load_all_rates(db, dataframe)           ← INSERT/UPSERT
```

Incremental mode is identical but fetches only the last 3 months and upserts (update existing, insert new).

**Spreadsheet generation** (tools/generate_test_spreadsheet.py):
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
  → CORS middleware (localhost:8000)
  → Request ID middleware (generates UUID, adds X-Request-ID header)
  → Auth0 token verification (Bearer token → get_current_user dependency)
  → Pydantic validation (symbol format, year/month ranges)
  → Route handler → SQLAlchemy query → JSON response
  → Global error handler catches exceptions → structured error JSON
```

Key endpoints the frontend uses:

| Endpoint | Auth | Frontend Usage |
|----------|------|---------------|
| `GET /api/auth/config` | No | Returns Auth0 domain + clientId for SPA SDK initialization |
| `POST /api/auth/login-event` | Yes | Logs login to user_logins table (auth0_user_id, email, IP, user agent) |
| `GET /api/tickers/active` | Yes | Populates ticker dropdown on page load |
| `GET /api/simulation-data/{symbol}?start_year&start_month&end_year&end_month` | Yes | Returns monthly prices + dividends merged for a ticker |
| `GET /api/mm-rates/monthly?start_year&end_year` | Yes | Returns monthly federal funds rates for MM interest calculation |

Most data endpoints require a valid Auth0 Bearer token. The frontend's `authFetch()` wrapper injects the token automatically. Static files (HTML, CSS, JS) are served via FastAPI's `StaticFiles` mount at `/`.

**Admin/batch endpoints (no auth — gated by ENABLE_WRITE_API):**

| Endpoint | Auth | Usage |
|----------|------|-------|
| `GET /api/admin/write-status` | No | Returns whether write API is enabled |
| `GET /api/admin/verify` | Yes | Checks logged-in user's email against user_admin table |
| `GET /api/tickers/active` | No | Lists active tickers (used by admin page and simulator) |
| `POST /api/tickers` | No | Add a new ticker (requires ENABLE_WRITE_API=True) |
| `POST /api/batch/full` | No | Trigger full Yahoo Finance data load (requires ENABLE_WRITE_API=True) |
| `POST /api/batch/incremental` | No | Trigger incremental Yahoo load with optional months param (requires ENABLE_WRITE_API=True) |
| `POST /api/batch/fred-full` | No | Trigger full FRED rate load (requires ENABLE_WRITE_API=True) |
| `POST /api/batch/fred-incremental` | No | Trigger incremental FRED load (requires ENABLE_WRITE_API=True) |
| `GET /api/batch/status` | No | Check batch job status |

Write endpoints are disabled by default (`ENABLE_WRITE_API=False` in config). Set `ENABLE_WRITE_API=True` in `backend/.env` to enable.

---

## Frontend Simulation Logic

When user clicks "Run Simulation", the browser executes this flow:

**1. Fetch data** — For each allocated ticker, calls `/api/simulation-data/{symbol}` with the date range. Also fetches `/api/mm-rates/monthly` for money market rates. All fetches run in parallel via `Promise.all`.

**2. Build timeline** — Collects all unique year-month keys across all tickers, sorts chronologically.

**3. Redistribute allocation** — For each month, checks which tickers have valid price data. If a ticker has no data (e.g., ETF didn't exist yet), its allocation percentage is redistributed proportionally among available tickers. This ensures the full monthly amount is always invested.

**4. Compute month budget** — The investable amount each month is: `base_monthly_amount + (year_offset × annual_growth)`. Year 1 uses the base amount; each subsequent year adds the growth amount. Default growth is $0 (flat — existing behavior). No aggregate carryover between months.

**5. Accumulate-then-buy (round lot)** — Each ticker maintains its own accumulation bucket. For each ticker with data: `allocated = month_budget × effective_%`, then the allocated amount is added to that ticker's bucket. `shares = floor(bucket / high_price)` (integer shares only). Actual cost = shares × high price. The remainder stays in that ticker's bucket for next month. No money crosses between tickers — each ticker's unspent dollars are earmarked for that ticker only.

**6. Calculate dividends** — For each dividend payment in the month, calculates: `dividend_cash = dividend_per_share × total_shares_held`. Accumulated as cash (not reinvested into equities).

**7. Apply money market interest** — Prior month's accumulated dividend balance grows at that month's federal funds rate ÷ 12 (monthly compounding). New dividends are then added. This models parking dividends in a money market fund.

**8. Compute MM-only benchmark** — A separate running balance tracks what would happen if the entire monthly investment went into money market instead of equities. Each month: prior balance grows at MM rate ÷ 12, then the same growing month budget is added (matching the equity simulation's annual growth schedule). This provides a "what if you didn't invest in equities at all" comparison.

**9. Value portfolio** — At month end: `portfolio_value = Σ (shares_held × close_price)` across all tickers.

**10. Store snapshots** — Each month's per-ticker detail (integer shares bought, actual $ spent, accumulation bucket balance, running totals, dividends, effective allocation, dividend balance with MM interest, MM-only balance) is stored for the drill-down modals.

**11. Render results** — Summary cards (6 tiles: Total Invested, Equity Value, Dividends Earned, Cash Accrual, Portfolio Balance, MMF Value), two interactive charts (Growth Over Time with portfolio/invested/money market lines, and Dividend Earned), clickable monthly breakdown table (with Total Invested running total, Total Shares, Cash Accrual, Equity Value, and MMF Value columns), tax impact section, and annual return table. Charts show tooltips on hover with crosshair tracking.

**12. Compute tax impact** — User-adjustable tax rate (0–60%) applied per year to dividends and MM interest separately. Renders a Tax Liability by Year table showing dividends, tax on dividends, MM interest, tax on interest, and total taxes per year.

**13. Compute annual returns** — For each calendar year, calculates pre-tax returns using a DCA mid-year approximation. Stock value = shares × December close price. Portfolio value = stock value + accumulated dividend balance. Average invested capital ≈ year's new contributions × 0.542 (reflects that monthly DCA dollars are invested ~6.5 months on average). Pre-tax return = (stock gain + dividends + MM interest) ÷ (beginning stock value + avg invested capital). Beginning stock value is the prior year's ending stock value (0 for the first year).

---

## Key Design Decisions

- **Buy at monthly high**: Conservative — simulates worst-case dollar-cost averaging entry each month.
- **Round-lot (integer) share buying with per-ticker accumulation**: Only whole shares are purchased: `floor(bucket / high_price)`. No fractional shares. Each ticker keeps its own accumulation bucket — unspent dollars stay earmarked for that ticker until enough accumulates to buy a whole share. Example: $100/month budget, XLRE at 10% = $10/month, share price $40 → accumulates $10, $20, $30, $40 → buys 1 share in month 4. This preserves the user's allocation intent even at low dollar amounts.
- **Prior year-end cutoff**: Simulation runs from January of (current year − N) through December of the prior complete calendar year. This avoids partial-year data for the current year.
- **Dividends as cash**: Not reinvested into equities — tracked separately so user sees true cash generation.
- **Dividends earn money market interest**: Accumulated dividends are modeled as invested in a money market fund at the federal funds rate (monthly compounding). The "Cash Accrual" column and summary tile show the impact.
- **MM-only benchmark**: A separate calculation shows what the same monthly investment would grow to if invested entirely in money market (no securities). Helps answer "was the investment strategy worth the risk?"
- **Interactive charts**: Charts respond to mouse hover — a crosshair tracks position and a tooltip shows values at that point. No click needed, just hover.
- **Proportional redistribution**: When a ticker has no data for a month, its allocation flows to available tickers proportionally, ensuring 100% of monthly investment is always deployed.
- **Tax impact analysis**: User-adjustable tax rate (0–60%) applied to dividends and MM interest per year. Shows yearly tax liability breakdown and after-tax portfolio values.
- **Annual return calculation**: Pre-tax returns per calendar year using DCA mid-year approximation (contributions × 0.542). Returns computed against beginning stock value + average invested capital.
- **Security-agnostic labeling**: UI avoids ETF-specific language — supports ETFs, mutual funds, individual stocks, or any ticker in the database.
- **Read-only API by default**: Write endpoints disabled by default (`ENABLE_WRITE_API=False`). Set `ENABLE_WRITE_API=True` in `.env` to enable ticker creation and data loading via the admin dashboard or API.
- **Split frontend**: HTML, CSS, and JS in separate files — no build tools, no Node.js — just open the HTML file in a browser.
- **Excel verification tool**: A Python script generates a multi-sheet workbook that mirrors the JS simulation using Excel formulas. Users edit a plain-text config file, re-run the script, and open the spreadsheet to trace every calculation step. The spreadsheet reads real data from the same SQL Server DB used by the API.
- **Clickable calculation modals**: Both the monthly breakdown table and annual return table have clickable cells that show full calculation breakdowns (numerator/denominator for returns, per-ticker share purchases, dividend sources, etc.).
- **Auth0 authentication**: All API endpoints (except `/api/health` and `/api/auth/config`) require a valid Bearer token. Frontend injects the token via `authFetch()` wrapper. Auth0 SPA SDK handles login/logout with PKCE flow (no client secret in browser). Login events logged to `user_logins` table for audit and future per-user features.
- **Opaque token verification**: With no Auth0 audience configured, Auth0 issues opaque tokens instead of JWTs. Backend validates these by calling Auth0's `/userinfo` endpoint. Simpler setup — no Custom API registration needed in Auth0 Dashboard.
- **Welcome guide overlay**: Shown after login and before simulator loads. Uses the same overlay pattern as the auth screen (fixed position, backdrop blur, hidden via CSS class toggle). Content is concise — four sections with icons covering what the tool does, how to use it, what results show, and key tips. Single button dismisses the guide and triggers ticker loading.
- **Frontend served by FastAPI**: HTML, CSS, and JS are served via FastAPI's `StaticFiles` mount. Required because Auth0 SPA SDK needs HTTP origin (not `file://`) for PKCE redirects. Access via `http://localhost:8000/portfolio-simulator.html`.
- **Admin dashboard**: Self-contained HTML page at `/admin.html` for managing tickers and triggering data loads (Yahoo Finance prices+dividends and FRED rates). Two layers of security: (1) Auth0 login required, (2) logged-in user's email must exist in the `user_admin` database table. Write operations additionally gated by `ENABLE_WRITE_API` config flag. Supports custom incremental month range (default 2 months). Auto-polls batch status during loads.
