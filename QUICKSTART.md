# Quick Start (run after every reboot)

## 1. Start SQL Server (requires admin terminal)

```bash
net start MSSQLSERVER
```

Right-click terminal -> "Run as administrator" if needed.

## 2. Start the API server

```bash
cd C:\Raj\python\portfolio-simulator\backend
..\venv\Scripts\activate
uvicorn app.api:app --reload
```

Leave this terminal open.

## 3. Open the website

Go to: **http://localhost:8000/**

- Landing page with tool cards — click any card to launch
- Simulator: **http://localhost:8000/portfolio-simulator.html** (no login required)
- Saved simulations: **http://localhost:8000/saved-simulations.html** (requires sign-in)
- Admin dashboard: **http://localhost:8000/admin.html** (requires Auth0 login + email in `user_admin` table)
- Swagger API docs at: **http://localhost:8000/docs**
- Theme toggle: click the 🌙/☀️ button (bottom-right) on any page — persists across navigation
- Optional sign-in: click "Sign In" link in any page header — unlocks member content and saved simulations

## 4. View any Markdown file in the browser

Open a second terminal:

```bash
cd C:\Raj\python\portfolio-simulator
venv\Scripts\activate
venv\Scripts\grip README.md
```

Opens at: **http://localhost:6419**

Press Ctrl+C to stop, then view another file:

```bash
venv\Scripts\grip Architecture.md
venv\Scripts\grip CHANGELOG.md
venv\Scripts\grip tools\Spreadsheet_Guide.md
```

## 5. One-time DB migrations (run once per DB after pulling new code)

_None outstanding._

## 7. Update data (when needed)

```bash
cd C:\Raj\python\portfolio-simulator\backend
..\venv\Scripts\activate
python run_batch.py incremental
python run_fred_batch.py incremental
```

## 8. Run tests

```bash
cd C:\Raj\python\portfolio-simulator\backend
..\venv\Scripts\activate
pytest tests/ -v
```

## 9. Generate test spreadsheet

Edit `tools/spreadsheet_config.txt` then:

```bash
cd C:\Raj\python\portfolio-simulator
venv\Scripts\activate
venv\Scripts\python tools\generate_test_spreadsheet.py
```

Output: `tools/Portfolio_Simulator_Test.xlsx`

## 10. Convert Markdown files to PDF

When a `.md` file is new or changed, regenerate its PDF:

```bash
cd C:\Raj\python\portfolio-simulator
venv\Scripts\activate
venv\Scripts\mdpdf -o README.pdf README.md
venv\Scripts\mdpdf -o Architecture.pdf Architecture.md
venv\Scripts\mdpdf -o CHANGELOG.pdf CHANGELOG.md
venv\Scripts\mdpdf -o QUICKSTART.pdf QUICKSTART.md
venv\Scripts\mdpdf -o tools\Spreadsheet_Guide.pdf tools\Spreadsheet_Guide.md
venv\Scripts\mdpdf -o docs\Auth0_Integration_Plan.pdf docs\Auth0_Integration_Plan.md
venv\Scripts\mdpdf -o docs\Welcome_Guide_Plan.pdf docs\Welcome_Guide_Plan.md
```

Or convert any single file:

```bash
venv\Scripts\mdpdf -o <output>.pdf <input>.md
```

## 11. Railway deployment (reference)

### One-time: Replace domain placeholder in SEO tags

```bash
# In your editor — find and replace across all files:
Find:    investsim.claritycapitaltools.com
Replace: your-actual-domain.railway.app   (or your custom domain)
```

Files affected: `frontend/sitemap.xml`, `frontend/robots.txt`, all 17 HTML files (canonical + OG tags).

### Railway start command (set in Railway service settings — not a Procfile)

```
sh -c "cd backend && uvicorn app.api:app --host 0.0.0.0 --port $PORT"
```

Must `cd backend` first — Railway runs from the repo root but `app.api` is a relative path inside `backend/`.

### Railway service variables (exactly 6 set)

| Variable | Value |
|----------|-------|
| `ALLOWED_ORIGINS` | Your custom domain (e.g. `https://yoursubdomain.yourdomain.com`) |
| `AUTH0_CLIENT_ID` | Your Auth0 client ID |
| `AUTH0_DOMAIN` | Your Auth0 tenant domain |
| `DB_TYPE` | `postgres` |
| `ENABLE_WRITE_API` | `True` (for admin write access) |
| `POSTGRES_URL` | Paste from Railway → PostgreSQL service → Connect tab |

> `AUTH0_AUDIENCE` is not set — backend uses opaque token mode (validates via Auth0 `/userinfo`). The code supports it but it is not needed.

### Custom domain via Cloudflare

1. In Railway dashboard: add your custom domain to the service → Railway gives you a CNAME target
2. In Cloudflare DNS: add a CNAME record — subdomain → Railway CNAME target
3. Railway handles SSL automatically
4. Update `ALLOWED_ORIGINS` env var to the custom domain once DNS propagates

### Sync local data to Railway PostgreSQL (run after loading new data locally)

```bash
cd C:\Raj\python\portfolio-simulator
venv\Scripts\python tools\sync_sql_to_postgres.py --status   # check counts first
venv\Scripts\python tools\sync_sql_to_postgres.py            # sync all core data tables
```

Requires `POSTGRES_URL` in `backend\.env`.
