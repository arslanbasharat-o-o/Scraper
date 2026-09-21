# Deployment Guide — Parts Extractor

## Single-User Desktop / Server Deployment

This application uses an embedded SQLite database and an in-process background scheduler for automation tasks. It is designed to be run as a single instance.

### Prerequisites

- Python 3.10, 3.11, or 3.12 (do not use 3.13 due to `curl_cffi` compatibility).
- Chrome or Chromium installed (for Botasaurus browser fallback).
- Windows (supported), Linux, or macOS.

### Quick Setup on Ubuntu / Linux Server (Recommended)

Run the automated setup script to install dependencies, official Google Chrome (`.deb`), and run the pre-flight verification:
```bash
bash scripts/setup_server.sh
```
This script will:
1. Automatically download and install official Google Chrome if missing (avoiding broken Ubuntu Snap packages).
2. Create and configure `.venv` with Python 3.10–3.12.
3. Install all Python dependencies from `requirements.txt`.
4. Initialize `.env` from `.env.server-40gb.example` with a secure random `SECRET_KEY`.
5. Run the pre-flight readiness audit (`python -m scrapers.system_check`).

---

### Manual Installation (Alternative)

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```

2. Activate the virtual environment:
   - Windows: `.venv\Scripts\activate`
   - Linux/Mac: `source .venv/bin/activate`

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the environment:
   ```bash
   cp .env.server-40gb.example .env
   # Edit .env with your credentials and SECRET_KEY
   ```

5. Verify system readiness:
   ```bash
   python -m scrapers.system_check
   ```

### Running the Application

**CRITICAL CONSTRAINT:** The background scheduler runs within the Flask process. You **MUST** run the application with exactly **one worker process** to avoid duplicate schedule executions.

#### Using Waitress (Windows)
Waitress is multi-threaded but single-process, which is perfectly safe.
```bash
waitress-serve --listen=0.0.0.0:5000 app:app
```

#### Using Gunicorn (Linux/Mac)
You must specify exactly one worker (`-w 1`) and use threads (`--threads 4`) for concurrency.
```bash
gunicorn -w 1 --threads 4 -b 0.0.0.0:5000 app:app
```

#### During Development
```bash
python -m flask --app app run --host=0.0.0.0 --port=5000 --debug
```
*(Do not use `--debug` in production)*

### Data Storage

All state is stored in `data/site_dbs/`. Ensure this directory is mounted as a persistent volume if deploying via Docker.
- `mobilesentrix.db`: The main database.
- Database runs in WAL mode for safe concurrent reads.

### Observability

- `/api/health`: Provides detailed system status.
- `/livez`: Liveness probe (HTTP 200 if process is up).
- `/readyz`: Readiness probe (HTTP 200 if DB is accessible).

### Updating an Existing Server

When updates are pushed to GitHub, the server does not need to reinstall Chrome or re-run the full installer. Simply run:

```bash
# 1. Pull updates
git pull origin main

# 2. Restart service
sudo systemctl restart scraper

# 3. Verify readiness & version
curl -s http://localhost:5000/readyz
```

