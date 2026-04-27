# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

### Added

- Parts Extractor category manager UI, automation target management, and related tests.
- Automated Windows startup for `parts-extractor/start.bat` with dependency checks and first-run bootstrap.

### Changed

- Repository reorganized into `image-scraper/` and `parts-extractor/`.
- Root documentation and GitHub metadata updated to match the split workspace.
- CI, Dependabot, and Railway workflow paths updated for the new structure.

### Removed

- Obsolete runtime logs, dump artifacts, and the old `parts-extractor/push-to-github.sh` helper.

## [1.0.0] - 2026-02-13

### Added

- Initial public release of the MobileSentrix scraper API.
- Selenium-based scraping for category and product pages.
- Python-backed image conversion and ZIP generation pipeline.
- Job lifecycle APIs, health endpoints, and admin monitoring endpoints.
