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

## Database Schema (5 Tables)

**tickers** — Master list of ETF symbols (XLK, XLV, XLE, etc.)
Each ticker has: symbol, name, active flag, created/updated timestamps.

**monthly_prices** — One row per ticker per month. Stores open, high, low, close, volume. Linked to tickers via foreign key.

**dividends** — One row per dividend payment. Stores pay date, amount. Linked to tickers via foreign key.

**monthly_mm_rates** — Federal funds rate per month from FRED. Standalone table, no FK.

**annual_mm_rates** — Yearly average of monthly rates. Computed from monthly_mm_rates during load.

---

## Module Purpose

| Module | What It Does |
|--------|-------------|
| `config.py` | All settings: DB connection string, max tickers (50), history depth (20 yrs), write API toggle |
| `database.py` | Creates SQLAlchemy engine and session factory. `init_db()` ensures all tables exist at startup |
| `models.py` | ORM models for `Ticker`, `MonthlyPrice`, `Dividend` with constraints and relationships |
| `mm_rates.py` | ORM models for `MonthlyMoneyMarketRate`, `AnnualMoneyMarketRate` plus loader functions |
| `fetcher.py` | Pulls monthly OHLCV prices and dividend history from Yahoo Finance. Handles full (20 yr) and incremental (3 month) modes |
| `fred_fetcher.py` | Pulls federal funds rate from FRED public CSV endpoint. No API key needed. Computes annual averages |
| `loader.py` | Takes fetcher output DataFrames and upserts into SQL Server. Handles skip-if-exists (full) and update-if-exists (incremental) |
| `api.py` | FastAPI app with all REST endpoints, CORS, error handling, request IDs, input validation |
| `run_batch.py` | CLI entry point: `python run_batch.py full` or `incremental` — orchestrates fetcher → loader for Yahoo data |
| `run_fred_batch.py` | CLI entry point: same pattern for FRED data |
| `test_connection.py` | Quick script to verify DB connectivity and create tables |

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

---

## API Endpoint Flow

All endpoints live in `api.py`. Request flow:

```
HTTP Request
  → CORS middleware (allows all origins for dev)
  → Request ID middleware (generates UUID, adds X-Request-ID header)
  → Pydantic validation (symbol format, year/month ranges)
  → Route handler → SQLAlchemy query → JSON response
  → Global error handler catches exceptions → structured error JSON
```

Key endpoints the frontend uses:

| Endpoint | Frontend Usage |
|----------|---------------|
| `GET /api/tickers/active` | Populates ticker dropdown on page load |
| `GET /api/simulation-data/{symbol}?start_year&start_month&end_year&end_month` | Returns monthly prices + dividends merged for a ticker. Called once per allocated ticker when simulation runs |
| `GET /api/mm-rates/monthly?start_year&end_year` | Returns monthly federal funds rates. Used to compute money market interest on accumulated dividends |

Write endpoints (POST/PUT/DELETE) are disabled via `ENABLE_WRITE_API = False` in config.

---

## Frontend Simulation Logic

When user clicks "Run Simulation", the browser executes this flow:

**1. Fetch data** — For each allocated ticker, calls `/api/simulation-data/{symbol}` with the date range. Also fetches `/api/mm-rates/monthly` for money market rates. All fetches run in parallel via `Promise.all`.

**2. Build timeline** — Collects all unique year-month keys across all tickers, sorts chronologically.

**3. Redistribute allocation** — For each month, checks which tickers have valid price data. If a ticker has no data (e.g., ETF didn't exist yet), its allocation percentage is redistributed proportionally among available tickers. This ensures the full monthly amount is always invested.

**4. Buy shares** — For each ticker with data, calculates: `shares = (monthly_amount × effective_%) / high_price`. Uses the monthly high price (worst-case entry point). Accumulates shares in running total.

**5. Calculate dividends** — For each dividend payment in the month, calculates: `dividend_cash = dividend_per_share × total_shares_held`. Accumulated as cash (not reinvested into equities).

**6. Apply money market interest** — Prior month's accumulated dividend balance grows at that month's federal funds rate ÷ 12 (monthly compounding). New dividends are then added. This models parking dividends in a money market fund.

**7. Compute MM-only benchmark** — A separate running balance tracks what would happen if the entire monthly investment went into money market instead of ETFs. Each month: prior balance grows at MM rate ÷ 12, then the monthly investment is added. This provides a "what if you didn't invest in ETFs at all" comparison.

**8. Value portfolio** — At month end: `portfolio_value = Σ (shares_held × close_price)` across all tickers.

**9. Store snapshots** — Each month's per-ticker detail (shares bought, running totals, dividends, effective allocation, dividend balance with MM interest, MM-only balance) is stored for the drill-down modals.

**10. Render results** — Summary cards (6 tiles including Div + MM Interest and MM Only Benchmark), two interactive charts (Growth Over Time with portfolio/invested/MM-only lines, and Dividend Balance Growth), and clickable monthly breakdown table with Div Value and MM Only columns. Charts show tooltips on hover with values at that point in time.

---

## Key Design Decisions

- **Buy at monthly high**: Conservative — simulates worst-case dollar-cost averaging entry each month.
- **Dividends as cash**: Not reinvested into equities — tracked separately so user sees true cash generation.
- **Dividends earn money market interest**: Accumulated dividends are modeled as invested in a money market fund at the federal funds rate (monthly compounding). The "Div Value" column and summary tile show the impact.
- **MM-only benchmark**: A separate calculation shows what the same monthly investment would grow to if invested entirely in money market (no ETFs). Helps answer "was the ETF strategy worth the risk?"
- **Interactive charts**: Charts respond to mouse hover — a crosshair tracks position and a tooltip shows values at that point. No click needed, just hover.
- **Proportional redistribution**: When a ticker has no data for a month, its allocation flows to available tickers proportionally, ensuring 100% of monthly investment is always deployed.
- **Read-only API**: Write endpoints disabled by default. Data loads only through CLI batch scripts.
- **Split frontend**: HTML, CSS, and JS in separate files — no build tools, no Node.js — just open the HTML file in a browser.
