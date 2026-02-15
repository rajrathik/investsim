# Portfolio Simulator

**What it does:** A historical backtesting tool that lets you simulate investing a fixed monthly amount across securities (ETFs, mutual funds, stocks) over 1–20 years. It buys at the worst-case price each month (monthly high), tracks share accumulation, dividends earned, money market interest on accumulated cash, tax impact, and annual returns — all powered by real Yahoo Finance and FRED data stored in SQL Server.

---

## Directory Structure

```
C:\Raj\python\portfolio-simulator\
│
├── backend\                        ← Python FastAPI backend
│   ├── app\                        ← Core application code
│   │   ├── api.py                  ← REST API endpoints (FastAPI)
│   │   ├── config.py               ← Settings (DB connection, constants)
│   │   ├── database.py             ← SQLAlchemy engine & session
│   │   ├── models.py               ← DB models (Ticker, MonthlyPrice, Dividend)
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
│   └── portfolio-simulator.js      ← Application logic & simulation engine
│
└── venv\                           ← Python virtual environment
```

---

## First-Time Setup

```bash
cd C:\Raj\python\portfolio-simulator
python -m venv venv
venv\Scripts\activate
pip install fastapi uvicorn sqlalchemy pyodbc pandas requests pytest
```

Create tables and load historical data (one-time):

```bash
cd backend
python test_connection.py          # Creates all DB tables
python run_batch.py full           # Loads 20 years of ETF price/dividend data
python run_fred_batch.py full      # Loads 20 years of federal funds rate data
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
Double-click `frontend\portfolio-simulator.html` in your browser. It connects to the API on localhost:8000.

---

## Ongoing Data Updates

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

## Features

- **Dollar-cost averaging simulation** — invest a fixed monthly amount across multiple securities with custom allocation percentages
- **Worst-case entry pricing** — buys at the monthly high price each month (conservative backtesting)
- **Dividend tracking** — cash dividends accumulated separately (not reinvested into equities)
- **Money market interest** — accumulated dividends earn interest at the federal funds rate (monthly compounding)
- **MMF benchmark** — side-by-side comparison: what if the same investment went entirely into money market?
- **6 summary tiles** — Total Invested, Portfolio Value, Dividends Earned, Cash Accrual, Portfolio Balance, MMF Value (all clickable for drill-down)
- **Interactive charts** — Growth Over Time and Dividend Earned charts with hover tooltips and crosshair tracking
- **Monthly breakdown table** — clickable cells for per-ticker detail modals, sortable by date, with Total Invested running total
- **Tax impact analysis** — adjustable tax rate (0–60%) with yearly breakdown of taxes on dividends and MM interest
- **Annual return table** — pre-tax and after-tax returns per calendar year using DCA mid-year approximation
- **Multi-select ticker dropdown** — checkbox-based selection with search filtering
- **Proportional redistribution** — when a ticker has no data for a month, its allocation flows to available tickers

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | SQL Server (local), SQLAlchemy ORM |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Data Sources | Yahoo Finance (prices/dividends), FRED (federal funds rate) |
| Frontend | HTML + CSS + JS (vanilla, no build tools), Canvas charts |
| Tests | Pytest (read-only integration tests against real DB) |
