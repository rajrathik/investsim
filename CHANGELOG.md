# Portfolio Simulator — Change History

---

## Project Specification

**What it does:** A historical backtesting tool that simulates investing a fixed monthly amount across securities (ETFs, mutual funds, stocks) over 1-20 years using real market data.

**Core rules:**
- Buys whole shares at the monthly high price (worst-case entry)
- Each ticker keeps its own accumulation bucket — unspent dollars stay until enough to buy a share
- Simulation runs through December of the prior complete calendar year (no partial-year data)
- Dividends tracked as cash (not reinvested), earn money market interest at the federal funds rate
- Side-by-side money market benchmark shows what risk-free investing would have returned

**Tech stack:** Python 3.12 / FastAPI / SQL Server / SQLAlchemy / vanilla HTML+CSS+JS / Auth0

**Data sources:** Yahoo Finance (prices, dividends), FRED (federal funds rate)

---

## Changelog

### Phase 1 — Database & Data Pipeline (Feb 7-8)

| Commit | Description |
|--------|-------------|
| `6fc2348` | Database models: Ticker, MonthlyPrice, Dividend tables with SQLAlchemy ORM, constraints, and unit tests |
| `5bf0b3a` | Revised models: separate dividends table, added adj_close column |
| `44c9458` | Yahoo Finance fetcher and loader: pulls 20 years of monthly OHLCV prices and dividends, batch runner CLI (`run_batch.py full/incremental`) |

### Phase 2 — REST API (Feb 9)

| Commit | Description |
|--------|-------------|
| `30de9f3` | FastAPI REST API: ticker CRUD, simulation-data endpoint (prices + dividends merged), money market rate endpoints, Pydantic validation, request ID middleware, CORS, global error handling, write-gate toggle, integration tests |

### Phase 3 — Money Market Rates (Feb 10)

| Commit | Description |
|--------|-------------|
| `e345148` | FRED federal funds rate integration: fetcher pulls CSV from FRED (no API key), computes annual averages, new MonthlyMoneyMarketRate and AnnualMoneyMarketRate models, API endpoints, batch runner (`run_fred_batch.py`) |

### Phase 4 — Frontend Build (Feb 14)

| Commit | Description |
|--------|-------------|
| `fd4e952` | Wildcard CORS for development |
| `65c9aff` | Initial frontend: single-page simulator with investment parameters, ticker selection, allocation sliders, simulation engine, results table |
| `bc8487e` | README.md and Architecture.md — project documentation |
| `bcb48e9` | Split monolith HTML into separate CSS/JS files. Added contextual cell click modals (per-ticker detail for any month) and column info tooltips |
| `508975d` | Clickable summary cards (6 tiles drill down to detail), table sort by date, equal-split button fix, multi-select checkbox dropdown with search |
| `3f89e77` | Money market interest on accumulated dividends (monthly compounding at fed funds rate), Div Value column, updated docs |
| `5cd4421` | Interactive charts: Growth Over Time (portfolio vs invested vs money market lines) and Dividend Earned chart. Hover tooltips with crosshair tracking. MM-only benchmark calculation |

### Phase 5 — UI Polish & Features (Feb 15 morning)

| Commit | Description |
|--------|-------------|
| `bf38bb2` | Label renames, remove cents display, fix multi-select behavior, year selector buttons |
| `12e0502` | Remove ETF-specific language (security-agnostic labels), year dropdown, multi-select fixes |
| `27e2488` | Total Invested running-total column, Tax Impact section (adjustable 0-60% rate with per-year breakdown), tile alignment fixes |
| `ce226ea` | Annual Return table: pre-tax returns per calendar year using DCA mid-year approximation (0.542 multiplier). Updated Architecture.md and README.md |
| `f7831e2` | Clickable calculation modals on annual return table (shows stock gain, avg invested capital, base capital, return formula). Sort newest-first |

### Phase 6 — Excel Verification Tool (Feb 15 mid-morning)

| Commit | Description |
|--------|-------------|
| `90c6e19` | Test spreadsheet generator (`generate_test_spreadsheet.py`): queries real DB data, builds 5-sheet Excel workbook (Setup, Monthly Simulation, Year Summary, Tax Impact, Annual Returns) with cross-sheet formulas mirroring the JS simulation logic |
| `c3fada6` | Fix Excel repair error in generated spreadsheet |
| `8e35c96` | Config file support: `spreadsheet_config.txt` for tickers, amount, years, tax rate (no interactive prompts needed) |
| `791c547` | Spreadsheet user guide (`Spreadsheet_Guide.md`): one-page walkthrough of all 5 sheets |
| `5f82ed8` | Updated README.md and Architecture.md with tools section documentation |

### Phase 7 — Authentication (Feb 15 afternoon)

| Commit | Description |
|--------|-------------|
| `98af634` | Auth0 integration: SPA SDK (PKCE flow), lock screen overlay, JWT/opaque token verification via `/userinfo`, `authFetch()` wrapper injects Bearer token on all API calls, login event logging to `user_logins` table, header shows email + logout button |
| `70924b5` | Welcome guide overlay: 4-section training manual shown after login (What It Does, How to Use It, What You'll See, Key Things to Know). Single dismiss button triggers simulator load. Updated docs |

### Phase 8 — Round-Lot Share Buying (Feb 15 evening)

| Commit | Description |
|--------|-------------|
| `ecfde48` | Integer share buying: `Math.floor()` replaces fractional shares. Renamed Portfolio Value to Equity Value. Added Total Shares column. Removed After-Tax columns from monthly table. Updated Excel generator, modals, tooltips, docs. Branch: `feature/round-lot-shares` |

### Phase 9 — Per-Ticker Accumulate-Then-Buy (Feb 15 evening)

| Commit | Description |
|--------|-------------|
| `3cb8dff` | Replaced aggregate carryover with per-ticker accumulation buckets. Each ticker keeps its own unspent dollars — money never crosses between tickers. Monthly budget is flat (no carryover addition). Excel generator expanded to 9 columns per ticker (Accum In, Allocated, Accum Bal, Shares, Spent, Accum Out, Cum Shares, Divs, Value). Updated welcome guide, Architecture.md, README.md, Spreadsheet_Guide.md. Branch: `feature/accumulate-then-buy` |

### Phase 10 — Annual Deposit Growth & Admin Dashboard (Feb 16-17)

| Commit | Description |
|--------|-------------|
| `88e8dea` | Annual deposit growth feature: optional $ increase to monthly investment each year. Year 1 uses base amount, each subsequent year adds the growth amount. New UI input field in Investment Parameters card. MM-only benchmark uses same growing schedule. Spreadsheet generator reads `annual_growth` from config file |
| `127f535` | Deposit column added to monthly breakdown table |
| `082929f` | Auth token expiry now redirects to login screen (not generic error). API request logging to `api_request_logs` table (method, path, user, response time, status). Auth failure logging with IP and path |
| `e275c55` | Admin dashboard (`admin.html`): browser-based ticker management and data loading (Yahoo Finance + FRED) with Auth0 login + `user_admin` table whitelist. `UserAdmin` model maps `user_admin` table (email PK, name). `GET /api/admin/verify` endpoint checks logged-in user against admin whitelist. FRED batch API endpoints (`POST /api/batch/fred-full`, `POST /api/batch/fred-incremental`). `ENABLE_WRITE_API` now configurable via `.env`. `fetcher.py` accepts custom `months` parameter for incremental loads. Fix `.env` load order (load before config imports). Updated `.gitignore` to exclude `.env` files. Updated docs |
| `4ac9f0c` | Smart batch loading: `POST /api/batch/full-new` loads full history only for tickers with no price data. Admin UI now has 3 clear options — Load New Tickers (primary), Refresh Recent Data, Reload All Tickers (with confirmation). `get_tickers_without_data()` helper in loader.py. Branch: `feature/smart-batch-loading` |

### Phase 11 — Sector Analytics, UI Restructure, Theme Toggle & Stepper Controls (Feb 18-21)

| Commit | Description |
|--------|-------------|
| `871833f..b5abad2` | Full frontend overhaul on `feature/no-auth` branch (multiple commits merged to main). Key changes: |
| | **Sector analytics suite** — 8 new pages: sector-performance, correlation, drawdown, sector-rotation, dividend-growth, growth-chart, risk-return, plus shared-analytics.css/js. Each page fetches from new `/api/sector-performance` and `/api/sector-monthly` endpoints |
| | **UI restructure** — `help.html` renamed to `index.html` (tool card grid). Simulator guide extracted to standalone `simulator-guide.html`. NYT-style centered header layout across all pages. Auth removed from all public endpoints |
| | **CSS consolidation** — `shared-analytics.css` is now single source of truth for `:root` variables, reset, fonts, header/nav. Duplicate rules stripped from `sector-performance.css` and `portfolio-simulator.css` |
| | **Dark/light theme toggle** — New `theme-toggle.js` loaded in `<head>` on all 10 public pages. IIFE prevents FOUC via `data-theme` attribute on `<html>`. Floating 🌙/☀️ button persists theme via localStorage. Light-mode CSS variable overrides in shared-analytics.css, sector-performance.css, portfolio-simulator.css. Canvas hex colors replaced with `THEME.*` getters; `themechange` event triggers chart re-render |
| | **Stepper allocation controls** — Replaced range input sliders with −/+ button pair (5% increments). `eqSplit()` rounds to nearest 5%. Tickers at 0% silently excluded from simulation |
| | **Inline hex → CSS var()** — Replaced hardcoded hex colors (`#10b981`, `#ef4444`, `#f59e0b`) with `var(--accent)`, `var(--red)`, `var(--gold)` across 7 JS files for theme adaptability |

### Phase 12 — Public Auth0 Sign-In, Saved Simulations & Tile Tooltips (Feb 21)

| Commit | Description |
|--------|-------------|
| `cbc10e4` | **Optional Auth0 sign-in for public pages** — `shared-auth.js` IIFE loaded on all 10 public pages. Sign-in link in header, welcome bar with email + sign out. Auth state cached in localStorage for instant cross-page display. All pages use single `/` callback URL (no Auth0 config changes when adding pages). `POST /api/auth/login-event` now writes to `user_logins` table. Member content section on `index.html` with 3 tiles (Newsletters, Saved Simulations, Watchlists) visible only when signed in |
| `cbc10e4` | **Saved portfolio simulations** — `SavedSimulation` model (9th DB table). `POST /api/simulations` (save, max 3 per user, 409 if full), `GET /api/simulations` (list by user), `DELETE /api/simulations/{id}` (delete own). Save button on simulator results (signed-in only). New `saved-simulations.html` page: auth-gated, displays simulation cards with ticker tags, 6 value tiles, total return %, MMF comparison, delete buttons. Sequential display numbering via array index (DB IDs may have gaps) |
| `25c0927` | **Tile info tooltips** — Each of the 6 summary result tiles (Total Invested, Equity Value, Dividends Earned, Cash Accrual, Portfolio Balance, MMF Value) now shows a `?` icon with hover tooltip explaining the metric. Applied to both simulator results and saved simulations page. CSS-only hover with z-index elevation on parent card so tooltips overlay adjacent tiles |

### Phase 13 — Error Handling, Pageview Tracking, SEO & API Security (Feb 22)

| Commit | Description |
|--------|-------------|
| `bfe98ea` | **Growth chart light theme fix** — Tooltip background changed from hardcoded `rgba(10,14,23,0.9)` to `var(--card)` so year heading is visible in light theme. Crosshair line changed from hardcoded white to `THEME.text2` |
| `5a59688` | **Error handling** — All 6 analytics JS files wrap `loadData()` in try/catch with user-facing error message div. `shared-analytics.js` API functions check `resp.ok` and throw on HTTP errors. No more silent failures |
| `5a59688` | **Self-hosted pageview tracking** — `POST /api/track/pageview` endpoint writes to `api_request_logs` with `method=PAGEVIEW`. `navigator.sendBeacon()` on all 12 public pages (6 via `shared-analytics.js`, 5 via inline script, 1 via both). Zero cost, no third-party analytics |
| `5a59688` | **SEO foundations** — `<meta name="description">` on all 11 public HTML pages. `robots.txt` (allows crawlers, blocks admin + API). `sitemap.xml` with all 11 public URLs and priorities. FastAPI routes for `/robots.txt` and `/sitemap.xml` |
| `17443bc` | **Full Google SEO** — Canonical `<link>` tags on all 11 pages. Open Graph (`og:title`, `og:description`, `og:url`, `og:type`) on all 11 pages. Twitter Card (`twitter:card`, `twitter:title`, `twitter:description`) on all 11 pages. `sitemap.xml` fixed to use absolute URLs (Google requires this). JSON-LD structured data: `WebSite` on index, `WebApplication` on simulator, `BreadcrumbList` on guide. All URLs use `investsim.claritycapitaltools.com` placeholder for find-and-replace at deploy time |
| `a488dbf` | **Rate limiting** — `slowapi` library: 60/min default per IP, 30/min for expensive sector queries, 10/min for ticker CRUD + simulation saves + login events, 5/min for batch load endpoints, 30/min for pageview tracking. Returns HTTP 429 when exceeded |
| `a488dbf` | **Write endpoint auth** — `POST /api/tickers` and all 5 batch POST endpoints now require Auth0 JWT token (were previously config-flag only). All write endpoints are double-gated: Auth0 token + `ENABLE_WRITE_API=True`. Frontend `adminFetch()` already sent auth — no frontend changes needed |

### Phase 14 — Railway Deployment: PostgreSQL Support & Data Sync Tool (Feb 23)

| Commit | Description |
|--------|-------------|
| `0f11c79` | **DB_TYPE switch** — `config.py` now supports `DB_TYPE=sqlserver` (local) or `DB_TYPE=postgres` (Railway). Default is `postgres`. SQL Server connection built from `DB_SERVER/DB_NAME/DB_USER/DB_PASSWORD` env vars; PostgreSQL connection from `POSTGRES_URL`. Both resolved at startup — flip a single env var to switch databases entirely |
| `d435b11` | **SQL Server → PostgreSQL sync tool** — `tools/sync_sql_to_postgres.py`: reads from local SQL Server, writes to Railway PostgreSQL. Creates tables if they don't exist. Truncates + bulk inserts in batches of 1000. Resets auto-increment sequences. Supports `--tables`, `--all`, `--dry-run`, `--status` modes. Data tables synced: `tickers`, `monthly_prices`, `dividends`, `monthly_mm_rates`, `annual_mm_rates`, `user_admin`. Log tables (`user_logins`, `api_request_logs`, `saved_simulations`) synced only with `--all` flag |
| `ebd0906` | **Remove duplicate backend/requirements.txt** — root `requirements.txt` is what Railway installs from (Railway doesn't install from subdirectories). Removed the duplicate in `backend/` to avoid confusion |

### Phase 22 — Member gating, admin tile, SEO verification, simulation fix (Mar 2026)

| Change | Description |
|--------|-------------|
| `frontend/index.html` | Stack & Earn removed from public tool grid; added to Member Content section (sign-in required). Admin tile added at bottom — shown only when signed-in member's token passes `/api/admin/verify`; `_admin_hint` localStorage flag cached to avoid re-checking on every page load |
| `frontend/admin.html` | Set `_admin_hint` in localStorage on successful admin verification; clear it on logout |
| `frontend/stack-earn.js` | Fixed tier interest calculation: splits running balance across tier buckets (amounts below T1 max earn T1 rate, amounts above earn T2/T3), not the monthly deposit amount |
| `frontend/googlefb699e7455843495.html` | Google Search Console HTML file verification (placed at root of frontend so served at `/googlefb699e7455843495.html`) |

### Phase 21 — Stack & Earn columns, admin rate management, UX copy (Mar 2026)

| Change | Description |
|--------|-------------|
| `backend/app/models.py` | Added 3 nullable columns to both `StackEarnSavingsTier` and `StackEarnGoalTier`: `display_rate` (Integer, default 1 — set to 0 to hide rate in UI), `display_upto` (Integer, default 0 — set to 1 to format range as "Upto $X"), `product_type` (String(100), default `'PurposeSaving'` — product identifier for future extensibility) |
| `backend/onetime/migrate_stack_earn_add_columns.py` | One-time migration script: ALTER TABLE on both tier tables for SQL Server (IF NOT EXISTS guard) and PostgreSQL (ADD COLUMN IF NOT EXISTS); backfills NULLs with defaults |
| `backend/app/api.py` | Refactored `get_stack_earn_savings_tiers` / `get_stack_earn_goal_tiers` to use shared `_serialize_tier()` returning all 8 fields (with `getattr` fallbacks for pre-migration rows). Added `TierUpsert` Pydantic model and 6 new admin-gated CRUD endpoints: `GET /api/admin/stack-earn/savings-tiers`, `PUT /api/admin/stack-earn/savings-tiers/{n}`, `POST /api/admin/stack-earn/savings-tiers`, and equivalents for goal-tiers |
| `frontend/stack-earn.js` | `renderTiers()` now shows product name above the table, hides rate cell when `display_rate=0` (collapses Rate column if no tier shows rates), and uses "Upto $X" range format when `display_upto=1` |
| `frontend/admin.html` | New **Stack & Earn — Rate Management** card: Savings / Goal tab switcher, editable table (label, min, max, rate %, Show Rate checkbox, Upto Format checkbox) with per-row Save button, Add New Tier form with product name field. Loads on `adminInit()` via new admin endpoints |
| `frontend/montecarlo.html` | Added page-level layman parameter guide below methodology note: plain-English descriptions of Starting Amount, Monthly Cash Flow, Investment Horizon, and Market Cycle Sensitivity with guidance on defaults |
| `frontend/index.html` | Stack & Earn card: removed `$500/mo` reference and "tiered/split" language; new copy describes recurring deposits accumulating with interest over time. S&P 500 card: renamed from "S&P 500 DCA Simulator" to "S&P 500 Historical Simulator" |
| `frontend/sp500-simulate.html` | Removed "DCA" from `<title>`, `og:title`, `twitter:title`, JSON-LD `name`, and `<h1>` — now "S&P 500 Historical Simulator" throughout |

### Phase 20 — Annual Market Extremes (Mar 2026)

| Change | Description |
|--------|-------------|
| `GET /api/sp500-extreme-years` | New endpoint: returns the N best and N worst full calendar years from Shiller data. Annual returns compounded from 12 monthly NominalTotalReturn values (partial years skipped). Each row: rank, year (string), return_pct, end_value ($10K result). Default N=20, max 50. 60/min rate limit |
| `frontend/extreme-years.html` | New page: identical layout to Monthly Market Extremes. Side-by-side panels (Worst Years / Best Years) with summary cards. "Year" column header instead of "Month". Chip toggle for top-10 vs top-20 |
| `frontend/extreme-years.js` | IIFE: fetches n=20 once (cached), re-renders sliced table on chip toggle. Same render logic as extreme-months.js |
| `frontend/index.html` | Added Annual Market Extremes tool card (📅) after the monthly extremes card |

### Phase 19 — Monthly Market Extremes (Mar 2026)

| Change | Description |
|--------|-------------|
| `GET /api/sp500-extreme-months` | New endpoint: returns the N best and N worst single months from Shiller data. Each row includes rank, date label (e.g. "Sep 1931"), return_pct, and end_value ($10K result). Default N=20, max 50. 60/min rate limit |
| `frontend/extreme-months.html` | New page: side-by-side panels (Worst Months / Best Months) with summary cards showing the single all-time worst and best monthly result. Chip toggle for top-10 vs top-20. Inline mini-bars show relative magnitude. Red/green color coding with dark-mode aware CSS vars |
| `frontend/extreme-months.js` | IIFE: fetches n=20 once (cached), re-renders sliced table on chip toggle. Bars scale to #1 entry in each list |
| `frontend/index.html` | Added Monthly Market Extremes tool card |
| `frontend/sitemap.xml` | Added `extreme-months.html` URL entry |

### Phase 18 — Monte Carlo Portfolio Simulator (Mar 2026)

| Change | Description |
|--------|-------------|
| `GET /api/shiller-monthly-returns` | New endpoint: returns all ~1,850 monthly nominal total returns as a flat float array. One small fetch; all simulation work is client-side |
| `frontend/montecarlo.html` | New page: controls card (starting amount, monthly cash flow, horizon chips 5–30yr, market cycle chips 1/3/5yr with ? tooltip explaining each option in plain terms, optional one-time cash event panel), fan chart, stat strip, percentile table with Deposited column and ? tooltip |
| `frontend/montecarlo.js` | Block-bootstrap Monte Carlo: draws random N-year return blocks from Shiller history, runs 1,000 trials client-side. Fan chart draws P10/P25/P50/P75/P90 bands. Withdrawal mode tracks ruin rate (% of simulations that ran out of money). One-time lump sum injected at specified year |
| `frontend/index.html` | Added Monte Carlo tool card |
| `frontend/sitemap.xml` | Added `montecarlo.html` URL entry |
| `frontend/extreme-months.html` | New page — see Phase 19 |

### Phase 17 — Stack & Earn Tiered Savings Calculator (Mar 2026)

| Change | Description |
|--------|-------------|
| `stack_earn_savings_tiers` | New DB table: tiered interest rates for savings calculator. Three tiers: T1 $0–$1K/mo @ 5%, T2 $1K–$10K/mo @ 3%, T3 $10K+/mo @ 1% |
| `stack_earn_goal_tiers` | New DB table: same structure as savings tiers, independent dataset so rates can diverge later |
| `backend/app/models.py` | Added `StackEarnSavingsTier` and `StackEarnGoalTier` ORM models |
| `backend/app/api.py` | Added `GET /api/stack-earn/savings-tiers` and `GET /api/stack-earn/goal-tiers` endpoints (60/min rate limit, no auth) |
| `backend/onetime/seed_stack_earn_tiers.py` | One-time seeder: creates tables and inserts 3 tiers into both SQL Server and PostgreSQL |
| `tools/sync_sql_to_postgres.py` | Added both tier tables to `DATA_TABLES` for sync to Railway |
| `frontend/stack-earn.html` | New page: two-tab layout (Savings Calculator / Goal Calculator), tier rates table, period chips, hero result card, year-by-year breakdown table |
| `frontend/stack-earn.js` | Calculator logic: split-bucket forward simulation (t1/t2/t3 balance each compounds independently), binary search reverse-solve for goal calculator (60 iterations → penny accuracy) |
| `frontend/index.html` | Added Stack & Earn tool card to landing page grid |
| `frontend/sitemap.xml` | Added `stack-earn.html` URL entry |

### Phase 16 — Navigation Simplification (Mar 2026)

| Change | Description |
|--------|-------------|
| Nav bar removed | Replaced full navigation bar (9 links per page) on all 12 public tool pages with a single `← Home` link (top-left, absolutely positioned in header). `index.html` landing page is the hub — users navigate between tools via card grid and return via `← Home` |
| `shared-analytics.css` | Removed `.nav-links` rules; added `.back-home` style (absolute top-left, `var(--text3)`, hover → `var(--accent)`); updated `.header` bottom padding |
| `shared-analytics.js` | Removed `navLinks()` function |
| 6 analytics JS files | Removed `$('navLinks').innerHTML = navLinks()` call from `correlation.js`, `dividend-growth.js`, `drawdown.js`, `growth-chart.js`, `risk-return.js`, `sector-rotation.js` |
| 12 HTML files | Replaced `<nav class="nav-links">` blocks with `<a href="/" class="back-home">← Home</a>` on all tool pages |

### Phase 15 — Railway Build Fixes (Feb 23)

| Commit | Description |
|--------|-------------|
| `d4de646` | **Pin python-jose + runtime.txt** — Railway was failing to build due to python-jose version conflicts. Pinned `python-jose[cryptography]==3.5.0` in `requirements.txt`. Added `runtime.txt` with `python-3.12.3` so Railway picks the correct Python version (Railway defaults to an older version without this file) |
| `51c1fb5` | **python-jose[cryptography]** — intermediate fix attempt (superseded by `d4de646`) |
| `e0185c0` | **Configurable CORS origins** — `ALLOWED_ORIGINS` env var added to `config.py`. Comma-separated list of allowed origins; defaults to `*` if not set. Set to your Railway domain in production. No more editing `api.py` to lock down CORS |

---

## Branch History

```
main
 └── feature/round-lot-shares  (Phase 8)
      └── feature/accumulate-then-buy  (Phase 9)
 └── feature/annual-deposit-growth  (Phase 10)
 └── feature/smart-batch-loading  (Phase 10 — smart batch UI)
 └── feature/no-auth  (Phase 11 — analytics, UI restructure, theme, stepper)
```

---

## Files Created/Modified (final state)

| File | Purpose |
|------|---------|
| `backend/app/config.py` | Settings: DB connection, Auth0, constants |
| `backend/app/database.py` | SQLAlchemy engine & session factory |
| `backend/app/models.py` | ORM models: Ticker, MonthlyPrice, Dividend, UserLogin, UserAdmin, ApiRequestLog, SavedSimulation |
| `backend/app/mm_rates.py` | Money market rate models & loaders |
| `backend/app/fetcher.py` | Yahoo Finance data fetcher |
| `backend/app/fred_fetcher.py` | FRED federal funds rate fetcher |
| `backend/app/loader.py` | Batch data loader (Yahoo to DB) |
| `backend/app/auth.py` | Auth0 token verification |
| `backend/app/api.py` | FastAPI endpoints + rate limiting (slowapi) + auth on all writes + pageview tracking + robots/sitemap routes + static file serving |
| `backend/run_batch.py` | CLI: load Yahoo Finance data |
| `backend/run_fred_batch.py` | CLI: load FRED rate data |
| `backend/test_connection.py` | Verify DB connection & create tables |
| `backend/tests/test_api.py` | API integration tests |
| `backend/tests/test_models.py` | ORM model tests |
| `backend/tests/test_fetcher.py` | Yahoo fetcher tests |
| `backend/tests/test_loader.py` | Loader logic tests |
| `backend/tests/test_mm_rates.py` | FRED/money market tests |
| `frontend/index.html` | Landing page: tool overview cards. Served at `/` |
| `frontend/simulator-guide.html` | How It Works guide for the simulator |
| `frontend/portfolio-simulator.html` | Asset Allocation Simulator |
| `frontend/portfolio-simulator.css` | Simulator-specific styles (stepper controls, modals, cards, tile info tooltips, light-mode overrides) |
| `frontend/portfolio-simulator.js` | Simulation engine + UI rendering (Canvas uses THEME.* getters, tile tooltips, save simulation) |
| `frontend/sector-performance.html` | Annual sector returns & dividends quilt |
| `frontend/sector-performance.css` | Quilt table, return/dividend color scales, light-mode overrides |
| `frontend/sector-performance.js` | Sector performance logic |
| `frontend/correlation.html/js` | Sector correlation matrix (Pearson) |
| `frontend/drawdown.html/js` | Peak-to-trough drawdown analysis |
| `frontend/sector-rotation.html/js` | Year-by-year sector performance rankings |
| `frontend/dividend-growth.html/js` | Year-over-year dividend growth by sector |
| `frontend/growth-chart.html/js` | $10K cumulative growth chart (Canvas, THEME.* getters) |
| `frontend/risk-return.html/js` | Risk vs return scatter plot (Canvas, THEME.* getters) |
| `frontend/shared-analytics.css` | Single source of truth: CSS variables, reset, fonts, header, `← Home` link styles, welcome bar styles, dark+light theme overrides, toggle button styles |
| `frontend/shared-analytics.js` | Shared API layer (with error handling + resp.ok checks), pageview tracking beacon, utilities, sector constants |
| `frontend/shared-auth.js` | Public Auth0 sign-in IIFE: optional login/logout, welcome bar, _pubAuthFetch(), _pubIsSignedIn(), pubauth event |
| `frontend/theme-toggle.js` | Dark/light theme toggle (IIFE + localStorage + THEME palette + themechange event) |
| `frontend/saved-simulations.html` | View & delete saved simulations (auth-gated, tile info tooltips) |
| `frontend/robots.txt` | Search engine crawl directives (allows crawlers, blocks admin + API) |
| `frontend/sitemap.xml` | XML sitemap for Google — all public URLs with priorities |
| `frontend/extreme-months.html/js` | Monthly Market Extremes — see Phase 19 |
| `frontend/extreme-years.html/js` | Annual Market Extremes — see Phase 20 |
| `frontend/admin.html` | Admin dashboard (Auth0 login + user_admin whitelist, isolated). Phase 21: added Stack & Earn Rate Management card |
| `backend/onetime/migrate_stack_earn_add_columns.py` | One-time migration: adds display_rate, display_upto, product_type columns to both tier tables — see Phase 21 |
| `frontend/CD-simulator.html` | CD portfolio advisor (AI-powered) |
| `tools/generate_test_spreadsheet.py` | Excel workbook generator |
| `tools/sync_sql_to_postgres.py` | Sync local SQL Server data to Railway PostgreSQL |
| `tools/spreadsheet_config.txt` | Spreadsheet config (tickers, amount, years, tax, annual growth) |
| `tools/Spreadsheet_Guide.md` | Spreadsheet user guide |
| `tools/create_user_logins.sql` | SQL script for user_logins table |
| `docs/Auth0_Integration_Plan.md` | Auth0 implementation plan |
| `docs/Welcome_Guide_Plan.md` | Welcome guide implementation plan |
| `requirements.txt` | Root-level dependencies — Railway installs from here |
| `runtime.txt` | Pins Python 3.12.3 for Railway builds |
| `README.md` | Project documentation |
| `Architecture.md` | Architecture & logic flow |
| `CHANGELOG.md` | Change history |
| `QUICKSTART.md` | Quick start guide |
| `CLAUDE.md` | Claude AI context file — auto-loaded at session start |
