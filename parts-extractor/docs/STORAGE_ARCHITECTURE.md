# Storage Architecture Specification

## Centralized Storage Layout (`storage/` & `logs/`)
```text
parts-extractor/
├── data/
│   └── site_dbs/          <- Active Production SQLite Databases
├── storage/
│   ├── exports/           <- Output generated exports (CSV, JSON, ZIP)
│   ├── backups/           <- Archived DB backups & system backups
│   ├── error_logs/        <- Failed run HTML snapshots & debug logs
│   ├── uploads/           <- Future user upload storage
│   └── temp/              <- Temporary processing files
└── logs/                  <- Server runtime stdout/stderr logs
```

## Environment Configuration Variables
```env
# Path Configuration Options (with safe defaults)
SITE_DBS_DIR=data/site_dbs
STORAGE_EXPORTS_DIR=storage/exports
STORAGE_BACKUPS_DIR=storage/backups
STORAGE_ERROR_LOGS_DIR=storage/error_logs
LOGS_DIR=logs
```

## Git Ignore Rules Update
```gitignore
# Exclude runtime storage contents while preserving folder structure
storage/exports/*
!storage/exports/.gitkeep
storage/backups/*
!storage/backups/.gitkeep
storage/error_logs/*
!storage/error_logs/.gitkeep
storage/temp/*
!storage/temp/.gitkeep
logs/*
!logs/.gitkeep
server.log*
```
