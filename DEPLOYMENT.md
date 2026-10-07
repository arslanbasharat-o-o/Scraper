# Ubuntu/Linux Deployment

Parts Extractor is designed to run as one application process because the
automation scheduler runs inside Flask. The deployment script creates a
single-worker Gunicorn systemd service and verifies `/readyz`.

## Requirements

- Ubuntu/Debian x86_64 server with systemd and sudo access.
- Python 3.10–3.12, or `uv` to provision Python 3.12.
- Google Chrome installed for browser fallback.
- A persistent, writable project directory for the SQLite databases.

## First Deployment

Clone the repository and run the deployment script from its root:

```bash
git clone https://github.com/arslanbasharat-o-o/Scraper.git
cd Scraper
bash deploy.sh
```

If `.env` does not exist, the script initializes it from
`.env.server-40gb.example` and generates a new `SECRET_KEY`. Review `.env` and
configure any supplier credentials and proxy before starting production jobs.
The script does not install operating-system packages or Google Chrome.

## Updates

Run this from the checkout on the server:

```bash
git pull origin main && bash deploy.sh
```

The script installs Python requirements, checks the environment and browser,
then creates or restarts `scraper.service`. It waits up to 60 seconds for the
readiness endpoint.

## Runtime

- Service: `scraper.service`
- Dashboard: `http://<server-address>:5000/`
- Readiness: `http://127.0.0.1:5000/readyz`
- Liveness: `http://127.0.0.1:5000/livez`
- SQLite data: `data/site_dbs/`
- Generated workbooks: `storage/exports/`

Keep exactly one Gunicorn worker. Threads handle concurrent requests while the
single process owns the scheduler. Back up `data/site_dbs/` before maintenance
or migrations. See [docs/OPERATIONS.md](docs/OPERATIONS.md) for routine
operations and [SECURITY.md](SECURITY.md) before exposing the dashboard.
