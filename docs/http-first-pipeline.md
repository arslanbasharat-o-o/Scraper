# HTTP-first scraping and bounded recovery

Supplier engines and automation category discovery use this order. Menu Map
uses the same Scrapling stealth solver after its existing browser extractor
hits a verification page or fails to produce a hierarchy.

1. Existing supplier HTTP session (curl_cffi or requests).
2. Scrapling HTTP, with the configured proxy, cookies and SSL verification.
3. Scrapling stealth browser with Cloudflare solving enabled by default.
4. Botasaurus rendered recovery, once, if earlier stages fail.

HTTP 404/410 is terminal. HTTP 200 challenge pages are rejected. Explicitly
selecting **Force browser rendering** skips HTTP; the workflow otherwise
starts with HTTP and does not add an artificial delay. When HTTP is blocked,
Scrapling receives a bounded 60-second minimum to solve Cloudflare before the
existing Botasaurus fallback runs. PhoneLCDParts reuses already fetched product
HTML instead of requesting it twice.

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
| `SCRAPER_LOCAL_BROWSER_FALLBACK` | `1` | Permit Scrapling and Botasaurus browser recovery after HTTP fails; `0` disables both. |
| `SCRAPER_SCRAPLING_SOLVE_CLOUDFLARE` | `1` | Ask Scrapling's stealth browser to attempt Cloudflare challenge recovery. |
| `SCRAPER_SCRAPLING_STEALTH_TIMEOUT` | `60` | Scrapling stealth timeout in seconds, clamped to 60–120 seconds when solving is enabled. |
| `SCRAPER_PROXY_URL` | unset | Optional supplier-approved proxy used by both Scrapling fetch stages. |
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

Automation runs outside the web request and checkpoints progress. Existing
per-category pagination limits still apply.

## Regression checks

```sh
python -m pip install -r requirements-dev.txt
python -m py_compile app.py automation_service.py database.py scripts/*.py scrapers/*.py
python -m pytest tests -q
node --check static/js/automation.js
```

Offline tests mock blocked suppliers. Passing tests does not guarantee access
to a supplier that denies the deployment's IP. Scrapling attempts Cloudflare
recovery, but it cannot guarantee access when the supplier continues returning
a challenge or denies the network; use supplier-approved proxy configuration
and repeat live checks from the deployment host.
