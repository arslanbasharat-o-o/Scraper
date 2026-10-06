# Deployment Guide — Parts Extractor

## Single-User Desktop / Server Deployment

This application uses an embedded SQLite database and an in-process background scheduler for automation tasks. It is designed to be run as a single instance.

### Local Windows startup

From the project directory, run the local launcher:

```bat
start.bat
```

It prepares `.venv`, installs requirements, preserves an existing `.env`, creates
the runtime directories, and starts the dashboard locally. A `.bat` file is a
Windows command script; Ubuntu/Linux uses `deploy.sh` below.

### Prerequisites

- Python 3.12 for the Windows launcher; Python 3.10–3.12 on Ubuntu/Linux (do not use 3.13 due to `curl_cffi` compatibility).
- Chrome or Chromium installed (for Botasaurus browser fallback).
- Windows (supported), Linux, or macOS.

### Ubuntu / Linux deployment

From the project checkout on the server, run:

```bash
bash deploy.sh
```

The script prepares Python 3.10–3.12 and dependencies, creates `.env` from the
40 GB template only when absent, creates runtime directories, and runs the
readiness check. Install Chrome and configure credentials/proxy separately.
On systemd hosts, it creates and enables `scraper.service` if needed, restarts
the service, and waits for `/readyz`. On hosts without systemd, it prints the
single-worker Gunicorn command.

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

Pull the desired revision, then run the deployment check:

```bash
git pull origin main
bash deploy.sh
```
