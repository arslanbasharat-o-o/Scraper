# Frontend Architecture

Audit date: 2026-07-24

## Scope

This document covers only `parts-extractor`. The sibling `image-scraper`
project is out of scope and its uncommitted files must not be changed.

## Current Architecture

- Rendering: Flask 3 style route handlers with Jinja templates.
- Pages: four server-rendered HTML documents.
- Frontend: semantic HTML, shared CSS tokens, page CSS, and vanilla JavaScript.
- Browser dependency: Bootstrap 5.3.3 CSS is loaded from jsDelivr. There is no
  Bootstrap JavaScript runtime.
- Fonts: native system stack with Segoe UI on Windows; no web-font request.
- Build: no bundler, package manager, compile step, or production frontend
  artifact. Flask serves `templates/` and `static/` directly.
- Scraping browser: local headless Botasaurus. It is not a frontend dependency.

## Screen and API Map

| Screen | Route | Template | CSS | JavaScript | Primary APIs |
| --- | --- | --- | --- | --- | --- |
| Extractor | `/` | `templates/index.html` | `common.css`, `main.css` | `main.js` | `/api/scrape`, `/api/export/xlsx`, `/api/comparison/upload`, `/api/watchlist` |
| History | `/history` | `templates/history.html` | `common.css`, `history.css` | `history.js` | `/api/history`, `/api/statistics`, `/api/cleanup` |
| Automation | `/automation` | `templates/automation.html` | `common.css`, `automation.css` | `automation.js` | `/api/automation/jobs`, `/api/automation/runs`, run pause/resume/delete routes |
| Menu Map | `/menu-map` | `templates/menu_map.html` | `common.css`, `menu-map.css` | `menu-map.js` | `/api/menu-map/sites`, `/api/menu-map/run`, `/api/menu-map/jobs/<id>` |

Downloads use normal browser navigation or `fetch` plus `Blob`. Destructive
requests send `X-Confirm-Destructive: permanently-delete`.

## Python Integration

`app.py` owns page routes, JSON APIs, validation, exports, security headers,
automation coordination, and menu-map background jobs. Jinja's `asset_url`
helper adds a file-modification timestamp so changed CSS and JavaScript bypass
the browser cache.

The backend contracts remain JSON over same-origin HTTP. Mutation requests are
rejected when their `Origin` is neither the active host nor an explicitly
allowed origin. API responses are marked `Cache-Control: no-store`.

There is no authentication, role model, user session, CSRF token, CORS
middleware, WebSocket server, or Server-Sent Events endpoint. Anyone with LAN
access to port 5000 can use the interface; the service must remain on a trusted
network until authentication is added.

## Persistence

`database.py` uses Python `sqlite3`, foreign keys, parameterized queries, and
one database per supplier under `data/site_dbs/`. Database connections are
closed after each Flask request. Automation runs, checkpoints, partial history,
jobs, targets, and fetch history are durable database records.

Frontend modernization must not alter schemas, migration behavior, record
identifiers, supplier database selection, or checkpoint semantics.

## Client State

- In-memory state holds current results, filters, selected jobs, selected runs,
  and loading state.
- `sessionStorage` stores only the color theme.
- `localStorage` stores extractor result cache, page size, recent models, and
  Menu Map display preferences.
- Authentication tokens and credentials are not stored in browser storage.
- URL routing is server-owned; there is no client-side router.

## Styling Architecture

`static/css/common.css` is the design-system layer. It defines color, type,
spacing, radius, shadow, focus, responsive navigation, motion, and shared
component rules. Page CSS owns only page-specific layout and components.

Dark and light themes use CSS custom properties. Reduced-motion behavior,
visible focus, responsive containers, horizontally usable data tables, and
stable control dimensions are part of the shared layer.

## Real-Time Behavior

Polling is appropriate because status updates are infrequent and several-second
latency is acceptable.

- Automation uses recursive `setTimeout`, active/idle intervals, overlap
  prevention, and visibility awareness.
- Menu Map uses recursive `setTimeout`, overlap prevention, visibility pause,
  exponential failure backoff capped at 30 seconds, and page-exit cleanup.
- No polling is required on Extractor or History.

SSE is a future option for one-way job progress only if polling becomes a
measured server burden. WebSockets are not justified.

## Target Architecture

Keep Flask/Jinja and progressively modernize vanilla JavaScript:

1. Preserve all page routes and JSON contracts.
2. Continue the token-based CSS system.
3. Split page scripts into ES modules only when a module removes real
   duplication.
4. Introduce one same-origin API client for timeout, cancellation, error
   normalization, downloads, and destructive headers.
5. Add TypeScript only for extracted API/data modules after contract tests
   exist; do not require a framework migration.
6. Keep polling lifecycle helpers small and transport-agnostic.
7. Retain direct legacy assets as the rollback path until each migrated module
   passes behavior comparison.

This architecture keeps deployment as one Python process, avoids CORS and
cookie changes, and preserves the current operational workflow.
