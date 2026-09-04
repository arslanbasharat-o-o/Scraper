# Changelog

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
