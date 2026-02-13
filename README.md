# MobileSentrix Scraper API

Production-oriented scraper service for product pages and category pages, with Selenium extraction, Python image conversion, and ZIP export.

[![Node.js](https://img.shields.io/badge/Node.js-v20+-green?logo=node.js)](https://nodejs.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)
[![CI](https://github.com/arslanbasharat-o-o/Scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/arslanbasharat-o-o/Scraper/actions/workflows/ci.yml)
[![CD - Railway](https://github.com/arslanbasharat-o-o/Scraper/actions/workflows/cd-railway.yml/badge.svg)](https://github.com/arslanbasharat-o-o/Scraper/actions/workflows/cd-railway.yml)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [API Overview](#api-overview)
- [Configuration](#configuration)
- [Railway Deployment](#railway-deployment)
- [CI/CD](#cicd)
- [Project Structure](#project-structure)
- [Documentation](#documentation)

## Features

- Concurrent scrape queue (`MAX_ACTIVE_SCRAPES`)
- Single-product and category scraping
- Multiple image extraction fallbacks
- Python-based image conversion (`convert_image.py`)
- Python ZIP creation with Node.js fallback (`create_zip.py`)
- Job APIs for status, images, ZIP downloads, and cleanup
- Health and memory monitoring endpoints

## Requirements

- Node.js 20+
- Python 3.11+ (recommended)
- Chrome/Chromium runtime for Selenium

## Quick Start

```bash
git clone https://github.com/arslanbasharat-o-o/Scraper.git
cd Scraper
npm install
python3 -m pip install -r requirements.txt
```

Start server:

```bash
npm start

# Startup checks + server boot
npm run start:check
```

Server default: `http://localhost:3001`

Health check:

```bash
curl http://localhost:3001/health
```

## API Overview

### Start scrape job

`GET /scrape` and `POST /scrape` are both supported. The URL is passed as query parameter.

```bash
curl -G "http://localhost:3001/scrape" \
  --data-urlencode "url=https://www.mobilesentrix.ca/replacement-parts/motorola/g-series/moto-g06-power-xt2535-10-2025"
```

Optional idempotency key:

```bash
curl -G "http://localhost:3001/scrape" \
  --data-urlencode "url=https://example.com/category" \
  --data-urlencode "job_id=my-stable-job-id"
```

### Job endpoints

- `GET /jobs` - list jobs
- `GET /jobs/:id` - job summary
- `GET /jobs/:id?include_products=true` - include product payload
- `POST /jobs/:id/stop` - stop a running job
- `DELETE /jobs/:id` - delete job and files
- `POST /jobs/reset` - reset all jobs

### Asset endpoints

- `GET /jobs/:id/zip` - download job ZIP
- `GET /jobs/:id/images` - image metadata
- `GET /jobs/:id/images/:imageId` - JPG binary (if converted) or metadata fallback

### Logs and monitoring

- `GET /health`
- `GET /logs?limit=50`
- `GET /logs/stream` (SSE)
- `GET /events` (job update SSE)
- `GET /admin/api/overview`

Detailed endpoint examples: [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)

## Configuration

Main environment variables:

- `PORT` (default `3001`)
- `PERSIST_JOBS` (default `false`)
- `MAX_ACTIVE_SCRAPES` (default `3`)
- `JOB_MAX_RUNTIME_MS` (default `2700000`)
- `CHROME_HEADLESS` (default `true`)
- `PRODUCTS_PER_BROWSER` (default `8`)
- `IMAGE_DOWNLOAD_CONCURRENCY` (default `3`)

Use `.env.example` as a baseline for local and hosted environments.

## Railway Deployment

Railway deployment is preconfigured via `railway.toml` and Docker.

### Option 1: GitHub deploy (recommended)

1. Push repository to GitHub.
2. In Railway, choose **Deploy from GitHub repo**.
3. Select this repository.
4. Railway uses `Dockerfile` and exposes the service.
5. Verify with `/health`.

### Option 2: Railway CLI

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

Detailed guide: [`docs/DEPLOYMENT_RAILWAY.md`](docs/DEPLOYMENT_RAILWAY.md)

## CI/CD

GitHub Actions workflows are included for both validation and deployment:

- `CI` (`.github/workflows/ci.yml`) runs syntax/smoke checks, standards checks, and Docker build smoke tests.
- `CD - Railway` (`.github/workflows/cd-railway.yml`) deploys on `main` pushes or manual dispatch when Railway secrets are configured.
- `Release Drafter` (`.github/workflows/release-drafter.yml`) prepares release notes from merged PR labels.
- `Labels Sync` (`.github/workflows/labels-sync.yml`) keeps repository labels consistent from `.github/labels.json`.

Required secrets for Railway CD:

- `RAILWAY_TOKEN`
- `RAILWAY_PROJECT_ID`
- `RAILWAY_SERVICE_ID`
- `RAILWAY_ENVIRONMENT_ID` (optional)

## Docker (Any Host)

```bash
docker build -t mobilesentrix-scraper .
docker run --rm -p 3001:3001 --env-file .env.example mobilesentrix-scraper
```

## Project Structure

```text
.
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   ├── feature_request.yml
│   │   ├── support_question.yml
│   │   └── config.yml
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── cd-railway.yml
│   │   ├── release-drafter.yml
│   │   └── labels-sync.yml
│   ├── CODEOWNERS
│   ├── labels.json
│   ├── release-drafter.yml
│   ├── dependabot.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── docs/
│   ├── README.md
│   ├── API_REFERENCE.md
│   ├── DEPLOYMENT_RAILWAY.md
│   ├── QUICK_START.md
│   ├── START_SERVER.md
│   ├── OPTIMIZATION.md
│   ├── PYTHON_SETUP.md
│   └── PYTHON_CONVERSION.md
├── frontend/
├── downloads/
├── server.js
├── convert_image.py
├── create_zip.py
├── requirements.txt
├── Dockerfile
├── railway.toml
├── .env.example
├── .editorconfig
├── .gitattributes
├── package.json
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
└── LICENSE
```

## Development Checks

```bash
node -c server.js
python3 -m py_compile convert_image.py create_zip.py
```

## Documentation

- [`docs/README.md`](docs/README.md)
- [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)
- [`docs/QUICK_START.md`](docs/QUICK_START.md)
- [`docs/OPTIMIZATION.md`](docs/OPTIMIZATION.md)
- [`docs/PYTHON_SETUP.md`](docs/PYTHON_SETUP.md)
- [`docs/START_SERVER.md`](docs/START_SERVER.md)

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT. See [`LICENSE`](LICENSE).
