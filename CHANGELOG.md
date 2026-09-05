# Changelog

## [8.4.4] - 2026-09-05

- Keep canonical URL matching variant-aware so separate product variants cannot be paired accidentally.

## [8.4.3] - 2026-09-05

- Resume phase-2 SKU backfills from saved product-detail checkpoints without routing them through category crawling.
- Prevent duplicate continuation jobs and preserve clean merged-run comparisons.

## [8.4.2] - 2026-09-05

- Merged completed phase-2 SKU continuations back into their source runs so detail hydration does not create duplicate runs or false differences.
- Added cross-engine comparison regression coverage for all configured suppliers.

## [8.4.1] - 2026-09-05

- Added a resumable local phase-2 worker for backfilling SKUs in completed automation histories.

## [8.4.0] - 2026-09-05

- Enabled SKU detail recovery for every supplier engine, including TXParts and Parts4Cells browser fallback.
- Added bounded all-site live SKU smoke testing and explicit unresolved SKU reporting for resumable runs.
- Removed optimistic ETA fallbacks so the UI only estimates from measured throughput.

## [8.3.0] - 2026-09-05

- Added bounded MobileSentrix browser fallback for blocked or SKU-less detail pages while keeping Safari HTTP primary.
- Moved version information from page headers into a shared footer and added maintainer contact details.
- Tuned local and server environment examples for the detail fallback and removed the obsolete header badge styling.

## [8.2.0] - 2026-09-05

- Added memory-tuned worker profiles for 10 GB local and 40 GB server deployments.
- Fixed resume-worker shutdown lock races and expanded Phone LCD menu extraction.

All notable changes to Parts Extractor are documented here.

This project follows Semantic Versioning.

## [8.1.0] - 2026-09-01

### Added

- Flask dashboard for supplier product extraction and history review.
- Scheduled automation with resumable checkpoints.
- Supplier scrapers for MobileSentrix, XCell Parts, Parts4Cells, Phone LCD Parts, TX Parts, and GadgetFix.
- Product detail enrichment for SKU, stock, description, image, and pricing data.
- Menu-map discovery for visible supplier categories.
- Admin authentication and user role management.
- Dockerfile, deployment notes, health checks, and CI.

### Changed

- Published the repository as a single Parts Extractor application at the repo root.
- Removed unrelated application code and generated audit artifacts from the public tree.
