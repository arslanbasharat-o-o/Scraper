# Parts Extractor

A high-performance Flask dashboard and intelligent scraper for product extraction, automation history, and desktop menu-map discovery.

The architecture is **HTTP-first**: it uses high-speed, TLS-mimicking HTTP sessions for 95% of requests, safely falling back to local headless Botasaurus browser automation only when challenged by anti-bot systems (e.g. Cloudflare).

## Documentation

- **[Deployment Guide](DEPLOYMENT.md)** - How to run in production and worker constraints.
- **[Security Guide](SECURITY.md)** - Authentication setup, roles, and safety features.
- **[Audit Report](COMPLETE_PROJECT_TECHNICAL_AUDIT.md)** - Deep technical analysis of the system architecture.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cp .env.example .env
```

*Note: Python 3.13 is currently not supported due to `curl_cffi` dependencies. Please use Python 3.10-3.12.*

## Quick Start (Development)

```powershell
.\.venv\Scripts\python.exe -m flask --app app run --host=0.0.0.0 --port=5000 --debug
```

The dashboard is available at `/`, automation at `/automation`, history at `/history`, and menu-map discovery at `/menu-map`.

## Production Running (Windows)

Use Waitress to serve the application on Windows:
```powershell
waitress-serve --listen=0.0.0.0:5000 app:app
```

## Menu Map Discovery

The seven menu-map modules live under `scrapers/menu_map/`. Run one module or the combined runner:

```powershell
.\.venv\Scripts\python.exe -m scrapers.menu_map.xcellparts --headless
.\.venv\Scripts\python.exe -m scrapers.menu_map.parts4cells --headless --validate-urls
.\.venv\Scripts\python.exe scripts\run_menu_map_scrapers.py --all
.\.venv\Scripts\python.exe scripts\run_menu_map_scrapers.py --sites xcellparts parts4cells
```

Each site writes structured JSON, CSV, and XLSX results below `output/<site>/`. Inspection and diagnostic artifacts are only created when the corresponding command option requests them.

## Data Safety

Persistent scrape history and checkpoints are stored under `data/site_dbs/`. Recovery copies belong under `data/backups/`. Browser profiles under `data/browser_profiles/`, logs, caches, and temporary inspection output are disposable and must never be treated as scrape history.

Failed or paused automation runs preserve their latest partial history and checkpoint so the same run can resume after a fix.
