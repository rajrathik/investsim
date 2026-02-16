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

---

## Branch History

```
main
 └── feature/round-lot-shares  (Phase 8)
      └── feature/accumulate-then-buy  (Phase 9)
```

---

## Files Created/Modified (final state)

| File | Purpose |
|------|---------|
| `backend/app/config.py` | Settings: DB connection, Auth0, constants |
| `backend/app/database.py` | SQLAlchemy engine & session factory |
| `backend/app/models.py` | ORM models: Ticker, MonthlyPrice, Dividend, UserLogin |
| `backend/app/mm_rates.py` | Money market rate models & loaders |
| `backend/app/fetcher.py` | Yahoo Finance data fetcher |
| `backend/app/fred_fetcher.py` | FRED federal funds rate fetcher |
| `backend/app/loader.py` | Batch data loader (Yahoo to DB) |
| `backend/app/auth.py` | Auth0 token verification |
| `backend/app/api.py` | FastAPI endpoints + static file serving |
| `backend/run_batch.py` | CLI: load Yahoo Finance data |
| `backend/run_fred_batch.py` | CLI: load FRED rate data |
| `backend/test_connection.py` | Verify DB connection & create tables |
| `backend/tests/test_api.py` | API integration tests |
| `backend/tests/test_models.py` | ORM model tests |
| `backend/tests/test_fetcher.py` | Yahoo fetcher tests |
| `backend/tests/test_loader.py` | Loader logic tests |
| `backend/tests/test_mm_rates.py` | FRED/money market tests |
| `frontend/portfolio-simulator.html` | HTML structure + auth + welcome guide |
| `frontend/portfolio-simulator.css` | All styles |
| `frontend/portfolio-simulator.js` | Simulation engine + UI rendering |
| `tools/generate_test_spreadsheet.py` | Excel workbook generator |
| `tools/spreadsheet_config.txt` | Spreadsheet config (tickers, amount, years, tax) |
| `tools/Spreadsheet_Guide.md` | Spreadsheet user guide |
| `tools/create_user_logins.sql` | SQL script for user_logins table |
| `docs/Auth0_Integration_Plan.md` | Auth0 implementation plan |
| `docs/Welcome_Guide_Plan.md` | Welcome guide implementation plan |
| `README.md` | Project documentation |
| `Architecture.md` | Architecture & logic flow |
