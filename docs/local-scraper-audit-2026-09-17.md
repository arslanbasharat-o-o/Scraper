# Local scraper audit — 2026-09-17

## Findings and fixes

- The workstation has approximately 10 GB RAM, but its local configuration used server overrides (up to 128 workers and eight browsers). Selected the existing `local_10gb` profile, removed overriding worker settings, and limited browser concurrency to one. Added the missing local environment template referenced by README.
- Failed/partial category targets were marked completed before validation. Completion checkpoints now require success; recoverable products are still checkpointed.
- Category failures now get one automatic HTTP-first recovery attempt in the same run. Exhausted failures remain errors.
- Fetch errors now reject an incomplete first run even when no baseline exists or baseline count protection is disabled.
- Partial pagination error rows and supplier fetch metadata now reach the workflow validation guard.
- Per-target HTTP sessions now close on success, exception, or pause.
- Resume now ignores legacy completion markers when there are no usable saved products. Live paused run 12 has 28 such markers and zero product checkpoints; it remains paused and was not restarted by the audit.

## Live validation

Initial HTTP-first smoke: all eight domains passed; 15 sampled product details resolved SKUs. HTTP-first allows configured browser fallback, so this does not assert that every request used HTTP exclusively.

Browser-mode audit: pagination enabled up to two pages per category, two detail samples per site. Parts4Cells retains its engine's HTTP-first behavior even when browser mode is requested. MobileSentrix US required a retry after an intermittent browser failure.

| Supplier | Listing rows | Detail samples with SKU | Seconds |
|---|---:|---:|---:|
| MobileSentrix US | 93 | 2 | 70.3 |
| MobileSentrix Canada | 93 | 2 | 53.0 |
| XCellParts | 44 | 2 | 19.3 |
| TXParts US | 40 | 2 | 25.5 |
| TXParts Canada | 40 | 2 | 17.4 |
| Parts4Cells | 24 | 2 | 6.1 |
| PhoneLCDParts | 296 | 2 | 35.8 |
| GadgetFix | 78 | 2 | 61.1 |

These are bounded live samples, not a full catalog or sustained concurrency certification. Anti-bot failures can still occur; the changes recover once and prevent exhausted failures from being presented as complete.

## Regression validation

- Baseline suite: 167 passed.
- Failure/checkpoint regressions: 7 passed.
- Supplier parser/fetch tests: 22 passed.
- Browser recovery and legacy-empty-checkpoint tests: 2 passed.
- Final full suite: 175 passed in 410.49 seconds.
- Latest recovery regressions: 9 passed in 59.23 seconds. Two tests added after full-suite collection (supplier fetch metadata and legacy resume) also passed in the focused runs above.
- Python compilation and `git diff --check`: passed.

Raw logs: `.tmp/live-audit-current.log`, `.tmp/live-browser-pagination.log`, `.tmp/final-test-suite.log`, `.tmp/resume-recovery-regression.log`.

## Local application

Automatic approval review rejected the restart command as blocked by policy. The old server remains reachable (dashboard HTTP 200), and run 12 remains paused. Restart with `start.bat` to load the saved code and local profile; the restart itself and large-scale resumed job are not verified. Audit requests used isolated databases and did not resume or modify the paused production job.
