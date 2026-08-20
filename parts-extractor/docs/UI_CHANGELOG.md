# UI Changelog

## 2026-07-24

### UI-005: Product Table Filters Were Fragmented and Hard to Use

- Files: `templates/automation.html`, `static/js/automation.js`,
  `static/css/automation.css`, `tests/test_extractor_ui_regression_codex.py`.
- Root cause: a global search and six tiny per-column inputs competed for space,
  provided no useful price/data-quality controls, and made mobile filtering
  impractical.
- Fix: replace the column-filter row with one responsive toolbar for search,
  data completeness, source, price range, sorting, row count, pagination, live
  result totals, and full reset. Unknown zero prices now display as blank.
- Evidence: 12 focused tests pass. Live Botasaurus checks verified search,
  missing-price results, numeric price ranges, ascending sorting, 50/100/250/500
  row sizes, pagination, reset behavior, and no page overflow at 390 and 1440
  pixels.
- Compatibility: exports still include every filtered row, table headers remain
  sortable, and no product/history/database record changed.
- Rollback: restore the prior product-table renderer, filter state, and CSS.

### UI-004: Schedule and Run Cards Looked Duplicated

- Files: `templates/automation.html`, `static/js/automation.js`,
  `static/css/automation.css`, `tests/test_extractor_ui_regression_codex.py`.
- Root cause: a saved schedule and its latest execution used the same name and
  both displayed the execution's `Completed` status.
- Fix: rename the sections to `Saved Schedules` and `Run History`, label each
  card by record type, show `Active` or `Paused` on schedules, and keep the
  execution result status on run snapshots.
- Evidence: 10 focused UI tests pass; headless Botasaurus at 390 px confirms
  separate `Paused` and `Completed` states with no overflow.
- Compatibility: no API, database, schedule, run, or history record changed.
- Rollback: restore the prior labels and job status renderer.

### PERF-001: Compact Automation Polling

- Files: `app.py`, `static/js/automation.js`,
  `tests/test_api_input_validation.py`.
- Root cause: run-list responses included the full `summary.models` array even
  though run cards use aggregate counts only.
- Fix: add backward-compatible `include_models=0` support and use it from the
  Automation list request. Return `model_count` in the compact summary.
- Evidence: API compatibility regression passes; default responses still
  contain `models`. A live one-run response fell from 172,748 bytes to 922
  bytes.
- Compatibility: existing API consumers are unchanged unless they opt in.
- Rollback: remove the query parameter from the frontend.

### RT-001: Menu Map Polling Lifecycle

- Files: `static/js/menu-map.js`,
  `tests/test_extractor_ui_regression_codex.py`.
- Root cause: fixed interval polling continued in hidden tabs and retried at a
  constant rate after errors.
- Fix: recursive timeout, request-overlap guard, visibility pause/resume,
  exponential backoff capped at 30 seconds, and `pagehide` cleanup.
- Evidence: JavaScript syntax and source-contract regression pass.
- Compatibility: endpoint, payload, and rendered job state are unchanged.
- Rollback: restore the prior `beginPolling` and `pollJob` timer behavior.

### UI-003: Duplicate Theme Listener

- Files: `templates/menu_map.html`, `static/js/menu-map.js`.
- Root cause: both inline template code and the page script bound the same
  change event.
- Fix: keep startup theme application in the document head and interaction
  ownership in `bindTheme`.
- Evidence: template regression confirms no inline storage write remains.
- Compatibility: storage key and dark/light behavior are unchanged.

### Previous Audit Fixes

Earlier work in the same audit fixed Automation scroll jumps, Resume state and
atomicity, failed-run history preservation, destructive confirmation,
responsive action overlap, comparison accuracy, modal accessibility, security
headers, URL validation, and native system-font restoration. Details remain in
`AUDIT_REPORT.md` and `CHANGELOG_AUDIT.md`.
