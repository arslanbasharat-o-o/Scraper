# Changelog

## [8.4.22] - 2026-09-08
- Fix desktop dashboard header broken layout: remove conflicting inline `<style>` block in `automation.html` that overrode `common.css` 3-column desktop grid with a 2-row layout, causing the nav bar to appear beneath the brand row even on wide screens.

## [8.4.21] - 2026-09-08
- Fix mobile responsiveness across all pages: eliminate 2x2 broken navigation grid on narrow screens and replace with a sleek segmented control with smooth touch scrolling.
- Refactor mobile header into a balanced 2-row layout keeping the brand on top left and theme switch on top right with zero empty vertical space.
- Standardize Category Menu Map action buttons into a symmetrical 2x2 grid on mobile screens with uniform 40px touch targets.
- Refine Automation supplier tab bar on mobile with compact padding and smooth momentum scroll.

## [8.4.20] - 2026-09-08
- Make Automation (`/automation`) the default landing page for root `/` and authentication redirects, establishing `/extractor` for the Extractor view.

## [8.4.19] - 2026-09-08
- Reorder primary navigation tabs across all templates to `Automation`, `Menu Map`, `History`, `Extractor`.

## [8.4.18] - 2026-09-08
- Add comprehensive production fallback benchmark suite (`scripts/production_fallback_benchmark.py`) covering 4 scenarios: HTTP Happy Path, 100% Botasaurus Fallback, Mixed Ratio Matrix (90/10, 80/20, 70/30, 50/50), and Android/Mobile stress testing.
- Quantify Botasaurus cold start vs warm reuse latency and project 40 GB server concurrency at 12 browser windows (~1,220 products/minute).
- Verify graceful automatic fallback recovery and 100% SKU resolution on throttled mobile and Android endpoints.

## [8.4.17] - 2026-09-08
- Fix persistent "Failed to fetch" error notifications on background polling in Automation and History views with exponential retry backoff and silent error handling.
- Fix UI toast/notification positioning across all pages by hoisting `#toastContainer` to viewport level and removing CSS animation transform containment.
- Fix PhoneLCDParts scraper stability by migrating TLS impersonation to Chrome 124 JA3/JA4 fingerprinting with full Client Hints and proxy support.
- Optimize high-core 40 GB server scraper performance by raising local browser window limit from 4 to 16, adding proxy routing, and establishing unified production `.env.example`.
- Update PhoneLCDParts production benchmark target to valid category endpoint.

## [8.4.16] - 2026-09-07
- Auto-seed menu maps from bundled baseline data in `data/menu_map_seeds/` whenever site output is missing, empty, or corrupted by server-level Cloudflare access blocks.
- Preserve healthy previous menu map outputs and fall back to baseline seeds on Cloudflare HTTP 403 or verification challenge blocks, preventing empty output replacement (`[]`).
- Add baseline seed fallback in Phone LCD Parts direct HTTP extractor.
- Clear stale scrape error indicators when baseline seed is restored.

## [8.4.15] - 2026-09-07
- Add automatic Cloudflare access challenge waiting in Menu Map runner.
- Add direct HTTP NinjaMenus extraction fallback for Phone LCD Parts (`/swpninjamenu/index/menu`) to bypass datacenter IP verification hurdles.
- Remove redundant manual timestamp subtitle from automation run cards to avoid UI duplication with the run detail panel.

## [8.4.14] - 2026-09-07
- Consolidate repeated product URLs across scrape responses, saved histories, live automation previews, and product tables.
- Keep valid same-name products and multi-category occurrences from being treated as duplicate products.
- Add regression coverage for project-wide product deduplication.

## [8.4.13] - 2026-09-06
- Add a compact batched Botasaurus retry lane for blocked MobileSentrix detail pages so phase-2 SKU recovery can extract many SKUs per warmed browser session without returning full page HTML to Python.
- Keep MobileSentrix HTTP/Safari enrichment primary, but defer retryable blocked detail misses into browser batches instead of one-by-one browser navigation.
- Add a separate browser-batch timeout so high-concurrency detail retries can keep SKU completeness without slowing the fast HTTP path.
- Enable resuming phase-2 SKU continuations directly via the SKU backfill worker from the Web UI and automation API.
- Prevent active phase-2 SKU backfill workers from being falsely marked interrupted on server restarts via process lock tracking and graceful pause support.

## [8.4.12] - 2026-09-06
- Detect Cloudflare challenge responses via the documented `cf-mitigated` header, including HTTP 200 challenge pages.

## [8.4.11] - 2026-09-06
- Verified reusable browser fallback syntax and pooled-driver lifecycle handling.

## [8.4.10] - 2026-09-06
- Corrected the reusable browser fallback cleanup block and verified module compilation.

## [8.4.9] - 2026-09-06
- Keep Botasaurus browser fallback drivers warm with blocked-image, early-load settings to remove per-URL Chrome startup overhead.

## [8.4.8] - 2026-09-06
- Skip terminal SKU outcomes during detail enrichment and make HTTP detail timeout configurable for faster, safer phase-2 resumes.

## [8.4.7] - 2026-09-06

- Avoid launching rendered browser fallback for successful detail pages that explicitly omit a SKU; retain fallback for blocked and transient responses.

## [8.4.6] - 2026-09-05

- Speed up detail enrichment by preventing duplicate HTTP requests during rendered fallback and isolating Chrome profiles per worker process.
- Keep failed browser fetches unresolved instead of misclassifying them as products without published SKUs.

## [8.4.5] - 2026-09-05

- Replace stale ETA/speed fields with measured rolling progress observations and explicit waiting-for-progress states.

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
