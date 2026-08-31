# Deployment Guide — Parts Extractor

## Single-User Desktop / Server Deployment

This application uses an embedded SQLite database and an in-process background scheduler for automation tasks. It is designed to be run as a single instance.

### Prerequisites

- Python 3.10, 3.11, or 3.12 (do not use 3.13 due to `curl_cffi` compatibility).
- Chrome or Chromium installed (for Botasaurus browser fallback).
- Windows (supported), Linux, or macOS.

### Installation

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
   cp .env.example .env
   # Edit .env with your credentials and SECRET_KEY
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
