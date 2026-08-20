# Parts Extractor Test Report

Test date: 2026-07-24

## Automated Regression

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Latest result: **74 passed** in 444.79 seconds.

After the final unknown-price presentation fix, the focused comparison suite
also passed: **6 passed** in 66.74 seconds.

Coverage includes scraper selection, Botasaurus-only rendering, API validation,
automation jobs and runs, atomic resume claims, failed resume launch recovery,
partial history behavior, menu-map parsing, supplier parsers, destructive
confirmation, security headers, same-origin mutation checks, accessibility
contracts, product-only history differences, duplicate consolidation, semantic
title normalization, target-scope protection, and frontend regressions.

Pytest emitted one non-failing warning because Windows denied writes to the
existing `.pytest_cache` directory.

The frontend modernization pilot added two regressions:

- compact Automation run summaries preserve the default API contract;
- Menu Map polling is visibility-aware, uses capped backoff, and cleans up on
  page exit.

Focused pilot result: **2 passed** in 13.63 seconds.

After the controlled restart, the live compact Automation request reduced one
run-list response from **172,748 bytes** to **922 bytes** while the default API
response stayed unchanged. Botasaurus observed the page requesting
`include_models=0` successfully with HTTP 200.

## Syntax Checks

Passed:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py database.py automation_service.py scripts\resume_automation_run.py
node --check static\js\main.js
node --check static\js\automation.js
node --check static\js\history.js
node --check static\js\menu-map.js
```

## Database Verification

The following databases passed `PRAGMA quick_check` and had zero foreign-key
violations:

- `gadgetfix.db`
- `mobilesentrix.before-xcell-ui-fix.db`
- `mobilesentrix.db`
- `mobilesentrix_ca.db`
- `parts4cells.db`
- `phonelcdparts.db`
- `txparts.db`
- `xcellparts.db`

## Headless UI Verification

UI checks used headless Botasaurus, not Playwright.

- Routes: `/`, `/automation`, `/history`
- Widths: 360, 390, 768, and 1440 pixels
- No horizontal overflow was found.
- Action buttons remained separated at mobile width.
- After the fix, the automation desktop test retained `scrollY = 265` for three
  seconds of live updates instead of jumping to zero.
- The supplier rail remains horizontally scrollable on small screens.

The 2026-07-24 extended frontend baseline checked all four routes at 320, 375,
390, 430, 768, 1024, 1280, 1440, and 1920 pixels: **36 combinations**. It found
zero horizontal overflow cases, zero captured JavaScript/unhandled-promise
errors, and zero HTTP responses at 400 or above during initialization. Visual
review confirmed the overlap heuristic's Automation/Menu Map warnings were
loading-overlay or scrolling-layer false positives.

Read-only API smoke tests returned HTTP 200 with `Cache-Control: no-store` for:

- `/api/health`
- `/api/history?limit=1`
- `/api/statistics`
- `/api/automation/overview`
- `/api/automation/jobs`
- `/api/automation/runs?limit=1`
- `/api/menu-map/sites?include_tree=0`
- `/api/watchlist`

## Operational Verification

- Run 21: completed
- Targets: 1,824 / 1,824
- Products: 13,385
- Active running/resuming jobs before deployment: 0
- Active running/resuming jobs after deployment: 0
- All three saved automation jobs after deployment: disabled
- Browser engine: Botasaurus
- Health endpoint: healthy
- Listener: `0.0.0.0:5000`
- LAN smoke test: `http://192.168.1.3:5000/` returned HTTP 200
- LAN TCP test: passed
