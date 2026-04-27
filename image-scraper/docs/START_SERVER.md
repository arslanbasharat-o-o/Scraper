# Server Startup Guide

## Start Options

### Option 1: Standard start (recommended)

```bash
npm start
```

### Option 2: Startup checks + server boot

```bash
npm run start:check
```

### Option 3: Platform scripts

```bash
# macOS/Linux
npm run start:linux

# Windows
npm run start:windows
```

## What `npm run start:check` Does

The startup script verifies and then starts the server:

- Node.js and npm availability
- Installed dependencies (`express`, `selenium-webdriver`, `chromedriver`, `archiver`)
- Chrome/Chromium availability (recommended)
- Required directories (`downloads/`, `frontend/`)

## Defaults

- Server URL: `http://localhost:3001`
- Frontend: `http://localhost:3001/`
- API base: `http://localhost:3001`

## Key Endpoints

- `GET /health`
- `GET /jobs`
- `GET /jobs/:id`
- `GET /jobs/:id/zip`
- `GET /jobs/:id/images`
- `GET /logs`
- `GET /logs/stream` (SSE)
- `GET /events` (SSE)
- `GET|POST /scrape?url=<TARGET_URL>`

## Common Issues

### Missing dependencies

```bash
npm install
```

### Selenium cannot launch browser

- Install Chrome/Chromium
- Keep `CHROME_HEADLESS=true` in hosted environments
- If needed, set `CHROME_BIN` and `CHROMEDRIVER_PATH`

### Port already in use

```bash
# macOS/Linux
lsof -ti:3001 | xargs kill -9

# Windows
netstat -ano | findstr :3001
taskkill /PID <PID> /F
```

### Python runtime not found

Install Python 3 and ensure `python3` is in `PATH`, or set `PYTHON_BIN` explicitly.

## Useful Environment Variables

```env
PORT=3001
PERSIST_JOBS=false
MAX_ACTIVE_SCRAPES=3
CHROME_HEADLESS=true
PRODUCTS_PER_BROWSER=8
IMAGE_DOWNLOAD_CONCURRENCY=3
```

See `.env.example` for a fuller template.
