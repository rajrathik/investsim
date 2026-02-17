# Plan: Admin Dashboard HTML

## Context
Adding tickers and loading Yahoo Finance/FRED data currently requires CLI commands. The user wants a simple browser-based admin page to manage tickers and trigger data loads — no auth, just a utility page.

## Branch
Same branch: `feature/annual-deposit-growth`

## Changes

### 1. New: `frontend/admin.html`
Self-contained HTML file (inline CSS/JS, dark theme matching simulator) with:

| Section | Controls | API Call |
|---------|----------|----------|
| **Add Ticker** | Symbol input + name input + Add button | `POST /api/tickers` |
| **Active Tickers** | Auto-loaded list with ticker symbols/names | `GET /api/tickers/active` (no auth) |
| **Full Data Load** | Button — loads all history (prices + dividends) | `POST /api/batch/full` |
| **Incremental Update** | Button + months input (default 2) | `POST /api/batch/incremental` |
| **FRED Rates** | Full + Incremental buttons | `POST /api/batch/fred-full`, `POST /api/batch/fred-incremental` |
| **Batch Status** | Auto-polling status display | `GET /api/batch/status` |
| **Write API Warning** | Banner if ENABLE_WRITE_API is disabled | `GET /api/health` check |

### 2. `backend/app/api.py`
- Add `@app.get("/admin")` route to serve admin.html (before static files mount)
- Add `months` field to `BatchRequest` model (optional int, default None)
- Pass `months` to `fetch_all_tickers()` in incremental handler
- Add FRED batch endpoints: `POST /api/batch/fred-full` and `POST /api/batch/fred-incremental`
- Remove auth requirement from `GET /api/tickers/active` so admin page can list tickers without login

### 3. `backend/app/fetcher.py`
- Add `months` parameter to `fetch_all_tickers()` (default None = use existing 2-month logic)
- When `months` is provided in incremental mode, use that instead of hardcoded 2

### 4. Documentation
- `README.md` — Add admin page section
- `Architecture.md` — Add admin.html to module table
- `CHANGELOG.md` — Update Phase 10 entry
- `QUICKSTART.md` — Add admin URL

## Verification
1. Set `ENABLE_WRITE_API=True` in `backend/.env`
2. Restart uvicorn
3. Open http://localhost:8000/admin.html
4. Add a ticker → verify it appears in list
5. Run full load → verify batch status updates
6. Run incremental with 6 months → verify it fetches correct range
7. Run FRED loads → verify
