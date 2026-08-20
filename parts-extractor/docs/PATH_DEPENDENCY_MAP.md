# Path Dependency Map

## Key Hardcoded & Dynamic Path Dependencies Identified

### 1. Database Connections (`database.py` & `app.py`)
- `data/site_dbs/mobilesentrix.db`
- `data/site_dbs/xcellparts.db`
- `data/site_dbs/gadgetfix.db`
- `data/site_dbs/mobilesentrix_ca.db`
- `data/site_dbs/parts4cells.db`
- `data/site_dbs/phonelcdparts.db`
- `data/site_dbs/txparts.db`
- *Dynamic Path Generator*: `database.py:get_db_path(site_key)` computes `data/site_dbs/{site_key}.db`.

### 2. Output and Export Files (`app.py`, `automation_service.py`, scrapers)
- Output Root: `output/{supplier_name}/`
- Export Files: `output/{supplier_name}/export_{timestamp}.csv`, `.zip`, `.json`
- *Dynamic Path Generator*: `os.path.join("output", supplier)`

### 3. Server Logging & Error Logs (`app.py`, `scrapers/browser_fetcher.py`)
- Main log file: `server.log`, `server.log.1` (written in project root)
- Error snapshots: `error_logs/{timestamp}/` (created dynamically on scraper failure)

### 4. Static & Template Routes (`app.py`, HTML files)
- Static files served from `static/css/*.css` and `static/js/*.js`
- Jinja2 templates loaded from `templates/*.html`

### 5. Script & Execution Paths (`start.bat`, `scripts/`)
- `start.bat`: Calls `.\.venv\Scripts\python.exe app.py`
- `scripts/resume_automation_run.py`: References `data/site_dbs/` and `app.py` logic.

## Risk Assessment
- High Risk: Changing database paths without updating `database.py:get_db_path()`.
- Medium Risk: Moving `output/` without updating export endpoints in `app.py`.
- Low Risk: Moving documentation files into `docs/` and log files into `logs/`.
