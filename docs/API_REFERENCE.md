# API Reference

Base URL (local): `http://localhost:3001`

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET / POST | `/scrape` | Start a scrape job (`url` query param required) |
| GET | `/jobs` | List jobs |
| GET | `/jobs/:id` | Get job summary |
| GET | `/jobs/:id/zip` | Download ZIP result |
| GET | `/jobs/:id/images` | List image metadata for a job |
| GET | `/jobs/:id/images/:imageId` | Download image JPG (or metadata fallback) |
| POST | `/jobs/:id/stop` | Stop a running job |
| DELETE | `/jobs/:id` | Delete job and associated files |
| POST | `/jobs/reset` | Reset all jobs |
| GET | `/health` | Health and memory summary |
| GET | `/logs` | Fetch log history |
| GET | `/logs/stream` | Live logs via SSE |
| GET | `/events` | Live job updates via SSE |
| GET | `/admin/api/overview` | Aggregated job stats |
| POST | `/admin/api/pause-all` | Pause active jobs |
| POST | `/admin/api/resume-all` | Resume paused jobs |

## Start Scrape

`GET /scrape?url=<TARGET_URL>`

Example:

```bash
curl -G "http://localhost:3001/scrape" \
  --data-urlencode "url=https://www.mobilesentrix.ca/replacement-parts/motorola/g-series/moto-g06-power-xt2535-10-2025"
```

Optional idempotency key:

```bash
curl -G "http://localhost:3001/scrape" \
  --data-urlencode "url=https://example.com/category" \
  --data-urlencode "job_id=stable-job-id"
```

## Job Status

```bash
curl "http://localhost:3001/jobs/<job_id>"
```

Include products:

```bash
curl "http://localhost:3001/jobs/<job_id>?include_products=true"
```

## Download ZIP

```bash
curl -L "http://localhost:3001/jobs/<job_id>/zip" -o result.zip
```

## Image Metadata and Download

```bash
curl "http://localhost:3001/jobs/<job_id>/images"
curl "http://localhost:3001/jobs/<job_id>/images/<image_id>" -o image.jpg
```

## Health Check

```bash
curl "http://localhost:3001/health"
```

Typical response fields:

- `status`
- `uptime_seconds`
- `memory.heap_usage_percent`
- `jobs.active_scrapes`
- `jobs.queue_size`
