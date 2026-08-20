# Data Quality & Database Safety Report

## Database Integrity Analysis
- **Database Engine**: SQLite 3
- **Active Connections**: Managed via `database.py` connection context managers (`get_db_connection(site_key)`).
- **WAL Mode**: Enabled for high-concurrency read/write operations during scraping.
- **Table Integrity**: Tables (`scraped_parts`, `automation_jobs`, `menu_map_items`, `schema_migrations`) hold production scraping data.

## Identified Data Quality & Backup Issues
1. **Unmanaged Backup File Storage**: Database backups created during automation or menu map runs are saved in `data/site_dbs/` alongside active databases.
2. **Duplicate Backup Artifacts**: Multiple backup files of identical size exist (e.g. `xcellparts.db.bak-restore-*` vs `xcellparts.db.bak-before-restart-*`).
3. **No File Path Records in DB**: Database tables store scraped product metadata (SKU, title, price, category, URL), not local absolute file system paths. Therefore, moving output files does NOT break DB primary keys or foreign keys.

## Data Preservation Guarantee
- NO active database file will be deleted or overwritten.
- Active DB files will remain in `data/site_dbs/`.
- Backup DB files will be archived cleanly into `storage/backups/site_dbs/`.
