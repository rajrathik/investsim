# Portfolio Simulator — Claude Context

## What This Is
A **live, deployed** historical backtesting + sector analytics suite at [Railway](https://railway.app).
Simulates DCA investing across securities using real Yahoo Finance + FRED data stored in SQL Server.

## Deployment (Railway)
- **Platform:** Railway (production, live)
- **Backend:** FastAPI served via Uvicorn, static files served from `frontend/`
- **DB on Railway:** PostgreSQL (Railway managed). Set `DB_TYPE=postgres` and `POSTGRES_URL=<railway-postgres-url>`
- **DB locally:** SQL Server. Set `DB_TYPE=sqlserver` (default in config.py)
- **Root `requirements.txt`** is what Railway installs from — this is intentional (Railway doesn't look in `backend/`)
- **`runtime.txt`** pins `python-3.12.3` — required so Railway builds with the right Python version
- **Railway start command** (set in Railway service settings — not a Procfile):
  ```
  sh -c "cd backend && uvicorn app.api:app --host 0.0.0.0 --port $PORT"
  ```
  Must `cd backend` first because `app.api` is a relative import path.

- **Railway service variables (exactly 6 set — confirmed):**

| Variable | Notes |
|----------|-------|
| `ALLOWED_ORIGINS` | Comma-separated allowed CORS origins (your Railway/Cloudflare domain) |
| `AUTH0_CLIENT_ID` | Auth0 application client ID |
| `AUTH0_DOMAIN` | Auth0 tenant domain |
| `DB_TYPE` | `postgres` |
| `ENABLE_WRITE_API` | `True` to allow admin write operations |
| `POSTGRES_URL` | Copy from Railway → PostgreSQL service → Connect tab |

> `AUTH0_AUDIENCE` is **not set** in Railway. The code supports it (`config.py` reads it via `os.getenv`), but when absent the backend automatically uses opaque token mode (validates via Auth0 `/userinfo`). Registered-user content gating is handled by `_pubIsSignedIn()` in `shared-auth.js`, not by audience.

- **Custom domain via Cloudflare:** Domain is managed in Cloudflare DNS. Railway generates a CNAME target; add it as a CNAME record in Cloudflare (subdomain → Railway CNAME). Railway handles SSL. Set `ALLOWED_ORIGINS` to the custom domain once DNS is live.

## Data Sync (Local SQL Server → Railway PostgreSQL)
When data is updated locally, sync to Railway using:
```bash
cd C:\Raj\python\portfolio-simulator
venv\Scripts\python tools\sync_sql_to_postgres.py           # sync core data tables
venv\Scripts\python tools\sync_sql_to_postgres.py --status  # compare row counts
venv\Scripts\python tools\sync_sql_to_postgres.py --dry-run # preview without writing
```
Requires `POSTGRES_URL` set in `backend\.env`. Syncs: tickers, monthly_prices, dividends, mm_rates, user_admin.

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Database | SQL Server, SQLAlchemy ORM |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Auth | Auth0 SPA SDK (admin + optional public sign-in), python-jose JWT |
| Rate Limiting | slowapi (per-IP, tiered) |
| Data Sources | Yahoo Finance (prices/dividends), FRED (federal funds rate) |
| Frontend | Vanilla HTML + CSS + JS, Canvas charts (no build tools, no framework) |

## Key Files
```
backend/app/api.py          ← All REST endpoints, CORS, rate limiting, static serving
backend/app/auth.py         ← Auth0 JWT verification
backend/app/config.py       ← Settings (DB, Auth0, constants) — reads .env
backend/app/models.py       ← ORM models (9 tables)
backend/app/fetcher.py      ← Yahoo Finance data fetcher
backend/app/fred_fetcher.py ← FRED federal funds rate fetcher
frontend/                   ← All HTML/CSS/JS (no build step)
frontend/shared-analytics.css  ← CSS single source of truth (vars, reset, header, ← Home link, themes)
frontend/shared-analytics.js   ← Shared API layer, utilities, pageview tracking
frontend/shared-auth.js        ← Public Auth0 sign-in IIFE
frontend/theme-toggle.js       ← Dark/light theme IIFE (no FOUC)
```

## Pages (all public except noted)
| Page | File |
|------|------|
| Landing (tool cards) | `index.html` |
| Asset Allocation Simulator | `portfolio-simulator.html` |
| Sector Returns Quilt | `sector-performance.html` |
| Correlation Matrix | `correlation.html` |
| Drawdown Analysis | `drawdown.html` |
| Sector Rotation Rankings | `sector-rotation.html` |
| Dividend Growth | `dividend-growth.html` |
| $10K Growth Chart | `growth-chart.html` |
| Risk vs Return | `risk-return.html` |
| S&P 500 History | `sp500-history.html` |
| S&P 500 Historical Simulator | `sp500-simulate.html` |
| Stack & Earn (Tiered Savings) | `stack-earn.html` (**sign-in required** — member content only, not in public tool grid) |
| Monte Carlo Simulator | `montecarlo.html` |
| Monthly Market Extremes | `extreme-months.html` |
| Annual Market Extremes | `extreme-years.html` |
| Saved Simulations | `saved-simulations.html` (**sign-in required**) |
| Admin Dashboard | `admin.html` (**Auth0 + user_admin table**) — tile on `index.html` visible only when `_admin_hint` localStorage flag set (cleared on admin logout) |
| CD Portfolio Advisor (AI) | `CD-simulator.html` + `cdapp.js` + `cdstyles.css` |

## Database (12 Tables)
`tickers`, `monthly_prices`, `dividends`, `monthly_mm_rates`, `annual_mm_rates`,
`user_logins`, `user_admin`, `api_request_logs`, `saved_simulations`, `shiller_market_data`,
`stack_earn_savings_tiers`, `stack_earn_goal_tiers`

> `shiller_market_data` — 1,863 rows, Jan 1871–Mar 2026. Loaded once via `backend/onetime/load_shiller_data.py`.
> 22 columns including `NominalTotalReturn` (calculated: monthly price return + dividend yield).
> Source: Robert Shiller / shillerdata.com — file `inputdata/ie_data.xls`.

## Untracked / In-Progress Files
- `backend/app/backend.py` — Flask-based CD portfolio recommendation engine (separate prototype, not integrated into FastAPI yet)

## Tools
- `tools/sync_sql_to_postgres.py` — Syncs local SQL Server data to Railway PostgreSQL (full replace per table, batched INSERT)
- `tools/generate_test_spreadsheet.py` — Generates 5-sheet Excel workbook from DB data to verify simulation calculations

## Auth Architecture
- **Public pages:** No login required. Optional Auth0 sign-in via `shared-auth.js` (welcome bar, save simulations)
- **All public pages use `/` as Auth0 callback** — adding new pages never requires Auth0 Dashboard changes
- **Admin:** Auth0 login + `user_admin` table whitelist + `ENABLE_WRITE_API=True` env flag (triple-gated)
- **Write endpoints:** Double-gated — Auth0 JWT token AND `ENABLE_WRITE_API=True`

## Simulation Logic (key rules)
- Buys at **monthly high** price (worst-case entry)
- **Whole shares only** — each ticker keeps its own accumulation bucket
- **Dividends as cash** (not reinvested) — earn FRED federal funds rate (monthly compounding)
- **MM-only benchmark** — parallel calculation for risk-free comparison
- Simulation ends **December of prior complete calendar year** (no partial year)
- Missing ticker data → allocation **redistributed proportionally** to available tickers

## Local Dev
```bash
cd backend && uvicorn app.api:app --reload
# API + static files at http://localhost:8000
```

## CSS/JS Conventions
- `shared-analytics.css` — single source for `:root` vars, reset, fonts, header, `.back-home`. Never duplicate in page CSS.
- Page CSS files contain **only overrides**
- Theme toggle loaded synchronously in `<head>` (IIFE) on all public pages — prevents FOUC
- Canvas charts re-render on `themechange` event; use `window.THEME.*` getters for colors
- Allocation controls use 5% stepper buttons (not sliders)

## Rate Limits (slowapi, per-IP)
- Default: 60/min | Heavy reads: 30/min | Writes: 10/min | Batch: 5/min

## Recent Commits
- Added **Worst 5-Year Periods & Recovery** section to `extreme-years.html`: non-overlapping 5-year crash windows ranked by total loss, with individual year pills, recovery Yr+1 / Yr+2 / combined columns, summary stat cards (worst period, avg Yr+1 recovery, avg Yr+2 recovery); new `GET /api/sp500-bad-streaks?n=` endpoint; both fetch calls parallel on page load
- Stack & Earn moved to member content: removed from public tool grid; card now appears in Member Content section of index.html (sign-in required); simulation logic fixed to split interest by running balance buckets (not monthly deposit amount); Google Search Console HTML file verification added (`frontend/googlefb699e7455843495.html`); Admin tile auto-detected on index.html via `/api/admin/verify` — shown when signed-in member is in user_admin table, hidden otherwise; `_admin_hint` localStorage flag set on verify, cleared on logout
- Stack & Earn: added `display_rate`, `display_upto`, `product_type` columns to both tier tables + migration script; `renderTiers()` respects flags; 6 new admin CRUD endpoints (`GET/PUT/POST /api/admin/stack-earn/savings-tiers` + goal-tiers); admin.html Rate Management card (editable table, Add New Tier form, product name display); Monte Carlo parameter guide added to `montecarlo.html`; renamed S&P 500 DCA Simulator → "S&P 500 Historical Simulator" across index.html and sp500-simulate.html; Stack & Earn card copy updated to remove tiered/split language
- Added Annual Market Extremes (`extreme-years.html/js`): ranked best & worst full calendar years in S&P 500 history since 1871; same side-by-side red/green panel layout as monthly extremes; compounded from monthly Shiller data; top-10/20 chip toggle; new `GET /api/sp500-extreme-years` endpoint
- Added Monthly Market Extremes (`extreme-months.html/js`): ranked best & worst single months in S&P 500 history since 1871; side-by-side red/green panels; $10K result per month; mini-bar magnitude indicators; top-10/20 chip toggle; new `GET /api/sp500-extreme-months` endpoint
- Monte Carlo refinements: added 5yr horizon chip; `?` tooltip on Market Cycle Sensitivity explaining Short/Medium/Long in plain terms; Deposited column + `?` tooltip on percentile table
- Added Monte Carlo Simulator (`montecarlo.html/js`): block-bootstrap 1,000-trial simulation from Shiller history; fan chart P10–P90 bands; withdrawal ruin-rate tracking; one-time lump sum events; new `GET /api/shiller-monthly-returns` endpoint
- Added Stack & Earn page (`stack-earn.html/js`): tiered savings calculator with split-bucket compounding + goal reverse-solve; two new DB tables seeded in SQL Server + PostgreSQL
- Replaced per-page nav bar with `← Home` link on all 12 tool pages; removed `navLinks()` from `shared-analytics.js`
- Added configurable `ALLOWED_ORIGINS` env var for CORS
- Pinned `python-jose[cryptography]==3.5.0`, added `runtime.txt` for Python 3.12.3
