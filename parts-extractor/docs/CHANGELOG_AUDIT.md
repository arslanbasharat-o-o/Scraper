# Audit Changelog

## 2026-07-24

### Data Safety

- Added durable partial-history preservation for failed automation.
- Kept failed, paused, and interrupted work resumable on the same run.
- Added an atomic `resuming` claim to prevent duplicate helper launches.
- Returned failed helper launches to a resumable failed state.
- Recovered abandoned `running` and `resuming` runs safely at startup.

### API and Security

- Restricted scrape, automation, discovery, and image URLs to configured public
  supplier hosts.
- Validated DNS results and every image-proxy redirect.
- Added request and proxied-image size limits.
- Added security headers, API no-cache behavior, same-origin mutation checks,
  and an optional `CORS_ALLOWED_ORIGINS` allowlist.
- Added `/api/health`.
- Added server-side confirmation for destructive endpoints.

### Frontend

- Fixed the one-second Automation page scroll jump.
- Added live `resuming` status handling.
- Preserved responsive job and run action layouts.
- Kept destructive-action error handling and confirmations visible.

### Quality

- Added resume-race, helper-launch, URL-validation, image-proxy, health-header,
  origin-validation, and destructive-action regression tests.
- Added deterministic pytest discovery configuration.
- Verified responsive behavior with headless Botasaurus.
- Verified all supplier SQLite databases without modifying business data.
- Created a SQLite-consistent predeployment backup containing the latest manual
  histories.
- Restarted the app hidden on `0.0.0.0:5000` and disabled all saved jobs.

### Difference Accuracy

- Excluded category and navigation rows from product differences.
- Consolidated overlapping category results by canonical product URL while
  retaining the most complete row.
- Normalized HTML entities, Unicode punctuation, casing, invisible characters,
  URL queries, and trailing slashes for comparison only.
- Stopped reporting missing SKU, stock, or description metadata as a business
  change.
- Excluded previous products whose originating target was not scraped in the
  current run.
- Preserved raw row counts and saved histories while presenting clean unique
  product totals.
- Displayed missing historical prices as unknown instead of fabricating `$0.00`.
