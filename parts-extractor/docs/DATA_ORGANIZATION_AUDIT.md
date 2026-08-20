# Data Organization Audit

## Active Storage vs Clutter Analysis

### 1. SQLite Databases (`data/site_dbs/`)
- **Active Databases (7 files / 57.79 MB)**:
  - `mobilesentrix.db` (20.07 MB)
  - `xcellparts.db` (34.70 MB)
  - `gadgetfix.db` (1.88 MB)
  - `mobilesentrix_ca.db` (2.13 MB)
  - `parts4cells.db` (1.11 MB)
  - `phonelcdparts.db` (0.48 MB)
  - `txparts.db` (0.23 MB)
- **Backup DB Files inside site_dbs (11 files / 62.97 MB)**:
  - `mobilesentrix.before-xcell-ui-fix.db`
  - `mobilesentrix.db.bak-automation-20260723-192941`
  - `mobilesentrix.db.bak-before-3window-resume-*`
  - `xcellparts.db.bak-20260723-192941` (16.6 MB)
  - *Recommendation*: Move all 11 `.bak` / `.before` database files out of `data/site_dbs/` into `storage/backups/site_dbs/`.

### 2. Historical & Pre-deployment Backups (`data/backups/`)
- Contains 7 backup folders (228.26 MB) from past audit/deploy runs (`predeploy-20260724-182438`, `audit-baseline-*`, `clear_20260710_*`).
- *Recommendation*: Move `data/backups` into `storage/backups/system/`.

### 3. Generated Output & Exports (`output/`)
- Contains 112 generated CSV, JSON, and ZIP export files (69.68 MB).
- *Recommendation*: Move to `storage/exports/`, ensure `.gitignore` excludes runtime export files while preserving directory structure.

### 4. Server Logs & Error Snapshots
- `server.log`, `server.log.1` (3.24 MB in project root).
- `error_logs/` (0.06 MB).
- *Recommendation*: Move server logs to `logs/` and `error_logs/` to `storage/error_logs/`.
