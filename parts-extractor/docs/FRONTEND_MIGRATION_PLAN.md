# Frontend Migration Plan

Plan date: 2026-07-24

## Principles

- Keep Flask, Jinja, API routes, request bodies, response defaults, exports,
  supplier databases, and durable run semantics compatible.
- Change one screen or shared primitive at a time.
- Do not combine UI migration with authentication, schema, scraper, or
  deployment replacement.
- Add a regression test for each confirmed defect.
- Keep the existing asset available until its replacement is verified.

## Phase 0: Baseline - Complete

- Inventory four screens and API dependencies.
- Preserve the dirty worktree and unrelated sibling-project changes.
- Verify page routes, read-only APIs, security headers, syntax, and databases.
- Capture Botasaurus responsive and runtime baseline.

Rollback: none; discovery is read-only.

## Phase 1: Design System - Complete

- Centralize color, spacing, type, focus, radius, shadow, and responsive tokens
  in `common.css`.
- Use native Segoe UI/system fonts.
- Retain page CSS for page-specific layout.

Rollback: restore the prior CSS asset version. No backend or data impact.

## Phase 2: Pilot - Menu Map and Automation Lists

Status: implemented.

- Pause Menu Map polling while hidden.
- Prevent overlap, back off on failures, and clean up on page exit.
- Remove duplicate theme binding.
- Let Automation list polling opt into model-free summaries.
- Preserve default API payloads for compatibility.

Exit criteria:

- focused API and source-contract tests pass;
- no console/network errors;
- no overflow at required widths;
- active menu job polling resumes after visibility restoration;
- compact run payload contains `model_count` but not `models`.

Rollback:

- remove `include_models=0` from `automation.js`;
- restore the prior Menu Map polling function;
- leave the optional backend parameter in place or revert it safely because it
  does not write data.

## Phase 3: Shared API Client

- Create one ES module for same-origin JSON, timeouts, cancellation, error
  normalization, downloads, and destructive confirmation.
- Do not automatically retry POST, PATCH, PUT, or DELETE.
- Migrate Menu Map first, then Automation, History, and Extractor.
- Keep request payload snapshots in integration tests.

Feature boundary: one script tag per migrated page. Legacy scripts remain the
rollback path during verification.

## Phase 4: History

- Move fetch/error/download behavior to the shared client.
- Preserve filter values after failed requests.
- Verify search, site/date filters, detail view, export, delete, cleanup, focus
  trap, and Escape behavior.

## Phase 5: Automation

- Separate list/status rendering from selected-run detail rendering.
- Consider row virtualization only after measuring the largest real detail.
- Preserve pause/resume idempotency and the same run identifier.
- Never hide or replace unfinished runs.

## Phase 6: Extractor

- Migrate last because it has the broadest business surface.
- Preserve URL validation, filters, result cache, pagination, watchlist,
  comparison upload, and CSV/XLSX behavior.
- Compare submitted JSON and exported columns before switching.

## Phase 7: Optional Tooling

Adopt TypeScript and Vite only if at least two extracted modules benefit from
shared typed contracts. Output must remain static assets served by Flask.
React/Vue remains out of scope unless screen count and client state grow
substantially.

## Verification Per Phase

- Python and JavaScript syntax.
- Focused unit and API integration tests.
- Full pytest suite before deployment.
- Botasaurus console, network, responsive, keyboard, and screenshot checks.
- Read-only SQLite integrity checks.
- Health endpoint, localhost, and LAN URL.
- Zero active jobs before any controlled server restart.
