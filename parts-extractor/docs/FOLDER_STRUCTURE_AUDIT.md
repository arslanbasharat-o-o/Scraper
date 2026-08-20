# Folder Structure Audit

## Current Repository Directory Tree
```text
parts-extractor/
├── app.py (150 KB - Monolithic Flask App, routes & logic)
├── database.py (136 KB - Monolithic DB layer)
├── automation_service.py (31.5 KB - Automation orchestrator)
├── Dockerfile, pytest.ini, requirements.txt, start.bat, .env, .gitignore
├── server.log, server.log.1, server.stderr.log, server.stdout.log (Logs in root)
├── 13 Markdown files in project root (AUDIT_REPORT.md, UI_AUDIT_REPORT.md, etc.)
├── data/
│   ├── site_dbs/ (7 active SQLite DBs + 11 old backup DB files)
│   ├── backups/ (7 backup subdirectories, 228.26 MB)
│   └── browser_profiles/ (Automation profiles & cache)
├── scrapers/
│   ├── *.py (7 scraper engines + registry.py + browser_fetcher.py + botasaurus_wrapper.py)
│   └── menu_map/ (8 menu map scrapers)
├── scripts/ (4 execution scripts)
├── static/
│   ├── css/ (5 CSS stylesheets)
│   └── js/ (4 JS files)
├── templates/ (4 Jinja2 HTML templates)
├── tests/ (14 pytest files)
├── output/ (9 supplier directories with 112 export CSV/JSON/ZIP files)
└── error_logs/ (Debug HTML/snapshot logs)
```

## Identified Organizational Problems
1. **Monolithic Backend Core**: `app.py` (150 KB) and `database.py` (136 KB) contain all backend endpoints, business logic, scraping triggers, SQL queries, HTML generators, and comparison algorithms mixed together.
2. **Database Backup Clutter**: 11 database backup files (`.db.bak-*`, `.before-*`) totaling 62.97 MB are sitting inside `data/site_dbs/` alongside active production databases.
3. **Log Files in Project Root**: Active and rotated log files (`server.log`, `server.log.1`, `server.stderr.log`, `server.stdout.log`) are stored directly in root instead of a dedicated `logs/` directory.
4. **Root Documentation Sprawl**: 13 separate `.md` files are located in the project root without a structured `docs/` folder.
5. **Runtime Data Mixed with Storage**: `output/` (exports), `error_logs/`, `data/site_dbs/`, `data/backups/`, and `data/browser_profiles/` lack centralized storage configuration and boundaries.
6. **Hardcoded Relative Paths**: Paths to `data/site_dbs/`, `output/`, `templates/`, `static/` are hardcoded across `app.py`, `database.py`, scrapers, and scripts.

## Target Reorganization Tree (Proposed Framework Compliant Structure)
```text
parts-extractor/
├── backend/
│   ├── app.py (Main entry point / app factory)
│   ├── database.py (DB core)
│   ├── automation_service.py
│   ├── routes/ (Split endpoints if refactored later)
│   └── services/
├── scrapers/
│   ├── engines/
│   ├── menu_map/
│   └── utils/
├── data/
│   └── site_dbs/ (Active SQLite databases ONLY)
├── storage/
│   ├── uploads/
│   ├── exports/ (Moved from output/)
│   ├── backups/ (Moved from data/backups/ & site_dbs backup files)
│   ├── error_logs/ (Moved from root error_logs/)
│   └── temp/
├── static/
│   ├── css/
│   └── js/
├── templates/
├── scripts/
├── tests/
├── docs/ (All root markdown files except README.md)
├── logs/ (server.log, server.log.1)
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
├── Dockerfile
└── start.bat
```
