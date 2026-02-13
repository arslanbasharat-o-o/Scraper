# Python Setup for Image Conversion and ZIP Creation

Python is optional but strongly recommended for better image conversion and ZIP performance.

## Install Dependencies

```bash
# Python runtime check
python3 --version

# Pillow is required for image conversion
python3 -m pip install Pillow
```

You can also run:

```bash
bash setup_python.sh
```

## Verify Scripts

```bash
python3 -m py_compile convert_image.py create_zip.py
```

## Run Server

```bash
npm run server
```

## How Runtime Detection Works

The server checks Python runtimes in this order:

1. `PYTHON_BIN` (if set)
2. `python3`
3. `python`
4. common absolute Python paths (macOS/Linux)

If Python is unavailable:

- Scraping still runs
- Original image URLs are stored
- ZIP creation falls back to Node.js archiver

## Recommended Environment Variables

```env
PYTHON_BIN=python3
IMAGE_HTTP_TIMEOUT_MS=20000
IMAGE_CONVERT_TIMEOUT_MS=25000
IMAGE_DOWNLOAD_CONCURRENCY=3
```

## API Checks

After a scrape job completes:

```bash
# Job health
curl http://localhost:3001/health

# Images metadata
curl "http://localhost:3001/jobs/<job_id>/images"

# ZIP download
curl -L "http://localhost:3001/jobs/<job_id>/zip" -o output.zip
```

## Troubleshooting

### `spawn python3 ENOENT`

- Install Python 3
- Or set `PYTHON_BIN` to your Python executable path

### `No module named PIL`

```bash
python3 -m pip install Pillow
```

### HTTP `403` during conversion

Some image hosts block direct requests. In this case conversion may fail and the server stores source URLs without stopping the job.
