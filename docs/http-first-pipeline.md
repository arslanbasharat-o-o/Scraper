# HTTP-first scraping and bounded recovery

All supplier engines and automation category discovery use this order:

1. Existing supplier HTTP session (curl_cffi or requests).
2. Scrapling HTTP, with the configured proxy, cookies and SSL verification.
3. Scrapling stealth browser when local browser fallback is enabled.
4. Botasaurus rendered recovery, once, if earlier stages fail.

HTTP 404/410 is terminal. HTTP 200 challenge pages are rejected. Explicitly
selecting **Force browser rendering** skips HTTP; the extractor otherwise
starts with HTTP and does not add an artificial delay. PhoneLCDParts reuses
already fetched product HTML instead of requesting it twice.

## Updating a deployment

From the deployed checkout, pull changes and run the deployment script:

```sh
git pull origin main && bash deploy.sh
```

Scrapling uses a detected local Chrome executable where available. If no Chrome
is installed, its stealth stage needs the browser binaries supplied by
`scrapling install`; otherwise that optional stage is skipped on
failure and Botasaurus is tried. Scrapling HTTP still works without its browser.
Restart the existing single-worker web service after updating.

## Environment controls

| Variable | Default | Purpose |
| --- | --- | --- |
| `SCRAPER_SCRAPLING_ENABLED` | `1` | Enable Scrapling stages; `0` skips them. |
| `SCRAPER_LOCAL_BROWSER_FALLBACK` | `0` | `1` permits browser recovery after HTTP fails. The example environment enables it. |
| `SCRAPER_LOCAL_BROWSER_MAX_WINDOWS` | `2` | Shared limit on active rendered fetches, including Scrapling. |
| `SCRAPER_LOCAL_BROWSER_SLOT_TIMEOUT` | `60` | Maximum slot wait, also capped by the request timeout. |
| `SCRAPER_MAX_TARGET_URLS` | `5000` | Reject oversized URL batches before fetching. |
| `SCRAPER_MAX_DURATION_SECONDS` | `18000` | Workflow budget; hard ceiling is five hours. |

Scrapling keeps one reusable session per fixed browser-slot worker, not one per
HTTP thread. Both browser adapters reuse warm contexts; retained contexts for
different transports can coexist, while active work shares the semaphore.

## Large runs and limits

Use the existing Automation workflow for large catalogs: it runs outside the
web request and persists category and detail checkpoints. Runtime expiry marks
an automation run failed/resumable and keeps checkpoints. A parent-process
watchdog terminates stuck detached workers after the five-hour budget plus a
two-minute checkpoint-flush allowance. It requires the
web process to remain alive; workers also check their own deadline between
requests and waits. Native HTTP/DevTools calls cannot be forcibly cancelled by
Python threads and finish at their configured timeout or next boundary.

The extractor waits up to five hours, but a reverse proxy may have a shorter
request timeout. Configure that proxy separately or use Automation. Cancelling
the extractor only stops the browser's wait; it is not server cancellation.
Existing per-category pagination limits still apply.

A manual timeout returns already-collected products in its HTTP 504 response
for display/export. It does not save incomplete data as a trusted baseline.

## Regression checks

```sh
python -m pip install -r requirements-dev.txt
python -m py_compile app.py automation_service.py database.py scripts/*.py scrapers/*.py
python -m pytest tests -q
node --check static/js/main.js
```

Offline tests mock blocked suppliers. Passing tests does not guarantee access
to a supplier that denies the deployment's IP; proxy configuration and live
supplier checks remain deployment-specific.
