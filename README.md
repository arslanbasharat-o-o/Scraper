# Parts Extractor

Parts Extractor is a Flask dashboard for supplier catalog scraping, scheduled product extraction, price-change history, and menu-map discovery.

Version: `8.4.5`

## Features

- Supplier-specific scrapers for MobileSentrix, XCell Parts, Parts4Cells, Phone LCD Parts, TX Parts, and GadgetFix.
- Scheduled automation with durable checkpoints and resumable runs.
- Product detail enrichment for SKUs, stock status, descriptions, images, and pricing.
- History comparison for changed, added, and removed products.
- Admin authentication with user and role management.
- Menu-map discovery tools for supplier category navigation.

## Requirements

- Python `3.10`, `3.11`, or `3.12`
- Chrome or Chromium for browser fallback
- SQLite, bundled with Python on standard installations

Python `3.13` is not recommended because some HTTP/TLS dependencies may not support it yet.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.local-10gb.example .env  # local 10 GB workstation
# Hostinger 40 GB deployments should use .env.server-40gb.example instead.
```

Edit `.env` before running in production. At minimum, set a strong `SECRET_KEY` and admin credentials.

## Development

```powershell
.\.venv\Scripts\python.exe -m flask --app app run --host=0.0.0.0 --port=5000 --debug
```

Open `http://127.0.0.1:5000`.

## Production

Run exactly one application process. The automation scheduler runs inside the Flask process, so multiple worker processes can create duplicate scheduled jobs.

Windows:

```powershell
waitress-serve --listen=0.0.0.0:5000 app:app
```

Linux:

```bash
gunicorn -w 1 --threads 4 -b 0.0.0.0:5000 app:app
```

## Project Layout

```text
.
├── app.py
├── database.py
├── automation_service.py
├── scrapers/
├── scripts/
├── static/
├── templates/
├── tests/
├── docs/
├── requirements.txt
├── Dockerfile
└── start.bat
```

## Data

Runtime data is intentionally excluded from Git.

- Supplier databases: `data/site_dbs/`
- Browser profiles: `data/browser_profiles/`
- Logs and temporary files: `logs/`, `.tmp/`, `storage/temp/`
- Exports: `storage/exports/`

Keep persistent database directories on durable storage when deploying to a server.

## Checks

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py database.py automation_service.py scripts\resume_automation_run.py
.\.venv\Scripts\python.exe -m pytest tests
```

## License

See [LICENSE](LICENSE).
