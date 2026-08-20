# UI Audit Report

Audit date: 2026-07-24

## Method

The audit reviewed all four templates, five CSS files, four page scripts,
Flask routes, SQLite access, tests, and the live application. Headless
Botasaurus checked 36 route/viewport combinations at 320, 375, 390, 430, 768,
1024, 1280, 1440, and 1920 pixels.

The live baseline found:

- zero horizontal page-overflow cases;
- zero captured JavaScript or unhandled-promise errors;
- zero HTTP responses at 400 or above during page initialization;
- no confirmed control collisions after screenshot review;
- the native Segoe UI/system font stack on every screen;
- HTTP 200 for all page routes and read-only API smoke tests.

## Screen Inventory

| Screen | Purpose and actions | Main UI | Business risk | Migration phase |
| --- | --- | --- | --- | --- |
| Extractor | Scrape URLs, filter, compare, watch, export | URL form, filters, result table, comparison upload | Critical | Last |
| History | Search, filter, inspect, export, delete, cleanup | Session cards, filters, detail and confirmation dialogs | High | Third |
| Automation | Manage jobs, monitor runs, pause/resume, compare snapshots | Supplier rail, job/run lists, inspector and product table | Critical | Second |
| Menu Map | Inspect category hierarchy and launch jobs | Site list, hierarchy tree, run status | Medium | Pilot |

No login, logout, account, role, order, customer, payment, or inventory screens
exist in this repository.

## Issue Inventory

| ID | Severity | Screen | Root cause | Resolution | Status |
| --- | --- | --- | --- | --- | --- |
| DATA-001 | Critical | Automation | Failed long runs did not always expose their partial data safely. | Persist partial history and resume the same run. | Fixed |
| DATA-002 | High | Automation | Concurrent Resume requests could claim one run twice. | Atomic SQLite resume claim and `resuming` state. | Fixed |
| DATA-004 | High | Automation | Category rows, duplicates, and presentation-only differences polluted comparisons. | Product filtering, canonical deduplication, semantic normalization, and scope checks. | Fixed |
| UI-001 | High | Automation | Background refresh called page-level `scrollIntoView`. | Supplier-rail-only horizontal scroll preservation. | Fixed |
| UI-002 | Medium | Automation | `resuming` was not represented as active. | Active rendering and polling without a second Resume action. | Fixed |
| PERF-001 | High | Automation | List polling returned full `summary.models`; one run measured about 172 KB. | UI opts into `include_models=0`; default API remains compatible. | Fixed |
| RT-001 | Medium | Menu Map | Fixed interval continued in hidden tabs and had no error backoff or cleanup. | Visibility-aware recursive timeout with capped backoff and `pagehide` cleanup. | Fixed |
| UI-003 | Low | Menu Map | Theme change was bound inline and in the page script. | Keep only the page-script listener. | Fixed |
| SEC-001 | High | Shared | User URLs could reach unsupported/private hosts. | Supplier host and resolved-address validation. | Fixed |
| SEC-003 | High | Shared | Destructive APIs lacked server-verifiable confirmation. | Explicit destructive confirmation header. | Fixed |
| ARCH-001 | Medium | Shared | Four scripts have separate fetch/error patterns. | Migrate behind one tested API module incrementally. | Planned |
| PERF-002 | Medium | Shared | Bootstrap CSS is a runtime CDN dependency. | Vendor or replace only after utility-class inventory and visual regression. | Planned |
| SEC-004 | High | Shared | No application authentication exists. | Keep trusted-LAN-only; design authentication separately. | Open |

## Layout and Responsive Review

Navigation wraps or becomes horizontally usable without hiding routes. Forms
stack at mobile widths. Automation actions remain separate, including Resume
and Delete. Tables retain horizontal access instead of hiding important
columns. Modal content is constrained to the viewport. Screenshot review found
that geometric overlap warnings were loading-overlay or scrolling-layer false
positives, not button collisions.

## Accessibility Review

The current UI includes semantic buttons, labeled primary navigation, visible
focus, reduced-motion support, form labels, named icon controls, live status
regions, dialog roles, focus return, and keyboard-friendly confirmation flows.
Existing contract tests cover key labels and dialog focus behavior.

Remaining manual work is a full screen-reader pass and measured color-contrast
sampling in both themes. There are no content images that require alt text.

## JavaScript and Security Review

Dynamic business data is escaped before HTML insertion in the inspected paths.
Supplier URLs are validated server-side. Destructive actions require visible
confirmation and a server-checked header. XLSX cell text is cleaned of illegal
control characters.

The main architectural weakness is duplicated request handling. Automatic
retries must remain disabled for state-changing requests. Client-side controls
must never be treated as authorization.

## Performance Review

The application has no JavaScript bundle, web font, charting library, or SPA
runtime. The measured high-impact issue was Automation's model-heavy polling
payload, now compacted by an opt-in query parameter. Large run details remain
loaded only when a run is selected.

The next performance measurements should record response transfer size and
render time for the largest real history and automation detail, then decide
whether row virtualization is justified.

## Remaining Risks

- Supplier markup and anti-bot behavior can still fail; durable history and
  checkpoints limit loss but cannot prevent external failures.
- Authentication is required before any internet exposure.
- Bootstrap CDN availability is an offline-startup risk.
- Large tables need ongoing real-data performance checks.
- Existing unrelated and user-authored Git changes must remain untouched.
