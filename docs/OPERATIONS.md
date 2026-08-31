# Operations

## Runtime Storage

Parts Extractor keeps runtime state outside version control.

```text
data/site_dbs/        Supplier SQLite databases
data/browser_profiles Browser profiles for fallback scraping
logs/                 Application logs
storage/exports/      Generated exports
storage/temp/         Temporary files
```

Back up `data/site_dbs/` before deployments, schema changes, or manual data maintenance.

## Health Checks

- `GET /livez` confirms the process is running.
- `GET /readyz` confirms the app can access its database.
- `GET /api/health` returns detailed application health.

## Automation

Run one application process only. The scheduler runs inside the Flask process.

Use threads for request concurrency, not multiple worker processes:

```bash
gunicorn -w 1 --threads 4 -b 0.0.0.0:5000 app:app
```

Paused, failed, or interrupted automation runs preserve checkpoints where possible and can be resumed from the Automation screen.

## Deployment Checklist

1. Pull the latest `main` branch.
2. Install dependencies from `requirements.txt`.
3. Confirm `.env` contains production credentials and a strong `SECRET_KEY`.
4. Back up `data/site_dbs/`.
5. Run syntax checks and tests.
6. Restart the single application process.
7. Confirm `/readyz` returns HTTP 200.
