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
- Admin dashboard: **http://localhost:8000/admin.html** (requires Auth0 login + email in `user_admin` table)
- Swagger API docs at: **http://localhost:8000/docs**
- Theme toggle: click the 🌙/☀️ button (bottom-right) on any page — persists across navigation

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

## 5. Update data (when needed)

```bash
cd C:\Raj\python\portfolio-simulator\backend
..\venv\Scripts\activate
python run_batch.py incremental
python run_fred_batch.py incremental
```

## 6. Run tests

```bash
cd C:\Raj\python\portfolio-simulator\backend
..\venv\Scripts\activate
pytest tests/ -v
```

## 7. Generate test spreadsheet

Edit `tools/spreadsheet_config.txt` then:

```bash
cd C:\Raj\python\portfolio-simulator
venv\Scripts\activate
venv\Scripts\python tools\generate_test_spreadsheet.py
```

Output: `tools/Portfolio_Simulator_Test.xlsx`

## 8. Convert Markdown files to PDF

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
