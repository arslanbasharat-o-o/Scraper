# Safely Reorganized Structure & Execution Plan

## Safe Phase-by-Phase Restructuring Sequence

### Phase 1: Low-Risk Documentation & Log Reorganization (Non-code breaking)
1. Create `docs/` directory.
2. Move 12 root markdown documentation files (`AUDIT_REPORT.md`, `UI_AUDIT_REPORT.md`, `FRONTEND_ARCHITECTURE.md`, `FRONTEND_MIGRATION_PLAN.md`, `DATA_SAFETY_PLAN.md`, `DEPLOYMENT_ROLLBACK.md`, `REAL_TIME_UI_PLAN.md`, `STACK_RECOMMENDATION.md`, `TEST_REPORT.md`, `UI_CHANGELOG.md`, `UI_UX_REVIEW.md`, `CHANGELOG_AUDIT.md`) into `docs/`. Preserve `README.md` in root.
3. Create `logs/` directory.
4. Move `server.log`, `server.log.1`, `server.stderr.log`, `server.stdout.log` into `logs/`.

### Phase 2: Runtime Storage & Backup Reorganization
1. Create `storage/exports/`, `storage/backups/site_dbs/`, `storage/backups/system/`, `storage/error_logs/`, `storage/temp/`.
2. Move 11 `.bak` / `.before` database files from `data/site_dbs/` into `storage/backups/site_dbs/`.
3. Move `data/backups/` subdirectories into `storage/backups/system/`.
4. Move `error_logs/` subdirectories into `storage/error_logs/`.
5. Update `output/` directory handling: alias `output/` to `storage/exports/` or retain `output/` as a backward-compatible symlink/directory pointing to storage.

### Phase 3: Configuration & Git Safety Updates
1. Update `.gitignore` to exclude log files, backup files, and runtime exports.
2. Add `.gitkeep` files in empty storage directories to preserve directory tree in Git.
3. Update `.env.example` with configurable storage path defaults.

### Phase 4: Verification & Test Suite Validation
1. Run pytest suite (`python -m pytest`).
2. Verify application startup (`app.py`).
3. Verify menu map scrapers and database accessibility.
