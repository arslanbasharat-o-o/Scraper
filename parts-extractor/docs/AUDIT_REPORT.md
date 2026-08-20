# Parts Extractor Audit Report

Audit date: 2026-07-24

## Scope

This audit covers only `parts-extractor`. The sibling `image-scraper` project is
out of scope.

## Architecture

- Backend: Flask with JSON APIs and a background automation scheduler.
- Persistence: one SQLite database per supplier in `data/site_dbs/`.
- Frontend: server-rendered HTML, vanilla JavaScript, and project CSS.
- Scraping: local headless Botasaurus. Selenium and Playwright are not runtime
  dependencies of Parts Extractor.
- Automation: saved jobs, durable run records, progress checkpoints, partial
  histories, and a separate resume helper process.
- Suppliers: MobileSentrix US/CA, XCell Parts, Parts4Cells, Phone LCD Parts,
  TX Parts, and GadgetFix.

## Data Baseline

- Verified backup: `data/backups/audit-baseline-20260724-142717/`
- Predeployment backup: `data/backups/predeploy-20260724-182438/`
- Eight supplier databases passed `PRAGMA quick_check`.
- Eight supplier databases reported zero foreign-key violations.
- Automation run 21 is completed with 13,385 products from 1,824 of 1,824
  targets.
- Run 21 retains its completed history and resume metadata.
- No running or resuming automation was present before or after final
  deployment. All three saved jobs are disabled.

The backup comparison found three valid manual XCell scrape histories created
after the backup. They were preserved. History `xcell:1784883844593`, containing
6,615 partial items, was explicitly deleted through the UI at 17:31. It was not
silently restored, but it remains recoverable from the baseline backup.

## Issue Inventory

| ID | Severity | Area | Confirmed problem | Resolution | Status |
| --- | --- | --- | --- | --- | --- |
| DATA-001 | Critical | Failed automation | A failed long run could lose its usable partial result. | Save a partial history from the durable checkpoint before stopping, and retain the same run for resume. | Fixed |
| DATA-002 | High | Resume | Concurrent Resume requests could launch the same run more than once. | Added an atomic SQLite `BEGIN IMMEDIATE` claim and a durable `resuming` state. | Fixed |
| DATA-003 | High | Resume launch | A helper launch failure could leave a run in an ambiguous state. | Return the same run to `failed` with its checkpoint and resume availability intact. | Fixed |
| SEC-001 | High | Scrape URLs | User-controlled URLs could request unsupported or private hosts. | Allow only configured supplier HTTP(S) hosts and reject credentials, private DNS results, and invalid URLs. | Fixed |
| SEC-002 | High | Image proxy | Redirects, private hosts, and unbounded responses created SSRF and memory risks. | Validate every redirect, allow supplier hosts only, stream responses, reject SVG/non-images, and cap size. | Fixed |
| SEC-003 | High | Destructive APIs | Delete and cleanup requests lacked a second server-side confirmation signal. | Require `X-Confirm-Destructive: permanently-delete` and keep visible UI confirmation. | Fixed |
| API-001 | Medium | Network API | Security headers, request-size limits, and health reporting were incomplete. | Added response headers, body-size limit, same-origin mutation checks, optional origin allowlist, and `/api/health`. | Fixed |
| UI-001 | Medium | Automation | Background refresh moved the desktop page to the top after about one second. | Replaced page-level `scrollIntoView()` with supplier-rail-only horizontal scrolling. | Fixed |
| UI-002 | Medium | Automation | The new resume claim state was not represented as active in the UI. | Render and poll `resuming` as a live state without exposing a second Resume action. | Fixed |
| QA-001 | Medium | Test discovery | Plain `pytest` crawled permission-locked generated output. | Added `pytest.ini` with an explicit `tests` root and generated-directory exclusions. | Fixed |
| DATA-004 | High | History differences | Category rows, duplicate target results, presentation-only title differences, missing metadata, and unscanned targets produced false change totals. | Compare unique canonical products, exclude non-products and out-of-scope rows, normalize presentation text, and compare optional metadata only when both values are known. | Fixed |

## Security Notes

No login or user authorization system exists. Same-origin checks reduce
cross-site mutation risk, but anyone who can reach the service on the trusted
LAN can use its APIs. Bind it only on a trusted network and restrict port 5000
with the host firewall. A future release should add an application token or
authenticated user model before internet exposure.

The supplier allowlist deliberately rejects arbitrary sites. Add a supplier only
through the scraper registry and its matching validation configuration.

## Residual Risks

- Supplier markup, anti-bot behavior, connectivity, and browser/runtime failures
  cannot be eliminated. Durable checkpoints make those failures recoverable.
- SQLite is appropriate for the current single-host workflow, but multiple app
  servers should not share these files over a network filesystem.
- The existing pytest cache directory has a Windows permission issue. Tests pass,
  but pytest emits a cache-write warning.
- The server is bound to the private LAN and responds through the Wi-Fi address,
  but adding a Windows Firewall allow rule requires an elevated administrator
  session. The attempted non-elevated rule creation was rejected and made no
  firewall change.
- Large histories consume disk space. Retention must remain an explicit operator
  decision; automatic destructive cleanup is intentionally disabled.
