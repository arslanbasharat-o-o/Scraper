# Railway Deployment

This project is ready for Railway using the included Dockerfile and `railway.toml`.

## What Railway Uses

- `Dockerfile` to build runtime dependencies (Chromium, chromedriver, Python, Pillow)
- `railway.toml` for health checks and restart policy
- `PORT` from Railway runtime (defaults to `3001` locally)

## Option 1: Deploy from GitHub (Recommended)

1. Push your repository to GitHub.
2. In Railway, create a new project and select **Deploy from GitHub repo**.
3. Select this repository and branch.
4. Railway will build using the Dockerfile automatically.
5. After deploy, open service logs and confirm:
   - `Scraper API running at http://localhost:<PORT>`
   - `GET /health` returns `{"status":"healthy"...}`

## Option 2: Deploy with Railway CLI

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

## Suggested Railway Variables

Set these in Railway service variables:

- `PERSIST_JOBS=false`
- `MAX_ACTIVE_SCRAPES=3`
- `JOB_MAX_RUNTIME_MS=2700000`
- `CHROME_HEADLESS=true`

You can copy additional defaults from `.env.example`.

## GitHub Actions CD Setup

The repository includes `.github/workflows/cd-railway.yml`.

Configure these GitHub repository secrets to enable automatic deploys on `main`:

- `RAILWAY_TOKEN`
- `RAILWAY_PROJECT_ID`
- `RAILWAY_SERVICE_ID`
- `RAILWAY_ENVIRONMENT_ID` (optional)

## Verify Deployment

```bash
curl https://<your-railway-domain>/health
```

Expected fields include:
- `success: true`
- `status: healthy`
- `memory.heap_usage_percent`
- `jobs.active_scrapes`
