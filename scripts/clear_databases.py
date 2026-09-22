"""Safely clear active scraper SQLite databases on a deployment host.

Default behavior is a dry run. The destructive operation requires
``--confirm-clear`` and only targets direct ``*.db`` files in the selected
database directory. Incident backups and nested directories are excluded
unless explicitly handled separately by an operator.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    default_dir = os.environ.get("DATABASES_DIR", "data/site_dbs")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-dir",
        default=default_dir,
        help=f"Active SQLite directory (default: {default_dir})",
    )
    parser.add_argument(
        "--confirm-clear",
        action="store_true",
        help="Actually clear the databases. Without this flag the command is dry-run only.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a timestamped backup before clearing. Not recommended.",
    )
    return parser


def resolve_database_files(database_dir: str | Path) -> tuple[Path, list[Path]]:
    root = Path(database_dir).expanduser().resolve()
    if not root.exists():
        raise ValueError(f"Database directory does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"Database path is not a directory: {root}")
    if root == Path(root.anchor) or root == Path.home().resolve():
        raise ValueError(f"Refusing to operate on broad directory: {root}")

    database_files = sorted(path for path in root.iterdir() if path.is_file() and path.suffix == ".db")
    return root, database_files


def backup_and_clear(root: Path, database_files: list[Path]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = root.parent / f"{root.name}.backup-{timestamp}"
    backup_dir.mkdir(parents=False, exist_ok=False)

    for database in database_files:
        shutil.copy2(database, backup_dir / database.name)
        for sidecar in (database.with_name(database.name + "-wal"), database.with_name(database.name + "-shm")):
            if sidecar.exists() and sidecar.is_file():
                shutil.copy2(sidecar, backup_dir / sidecar.name)

    for database in database_files:
        database.unlink()
        for sidecar in (database.with_name(database.name + "-wal"), database.with_name(database.name + "-shm")):
            if sidecar.exists() and sidecar.is_file():
                sidecar.unlink()

    return backup_dir


def main() -> int:
    args = build_parser().parse_args()
    try:
        root, database_files = resolve_database_files(args.database_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Database directory: {root}")
    if not database_files:
        print("No active .db files found. Nothing to clear.")
        return 0

    print("Databases found:")
    for database in database_files:
        print(f"  - {database.name}")

    if not args.confirm_clear:
        print("\nDRY RUN: no files were changed.")
        print("To clear these databases, stop the scraper and rerun with --confirm-clear.")
        return 0

    if args.no_backup:
        print("WARNING: backup disabled by --no-backup")
        backup_dir = None
        for database in database_files:
            database.unlink()
            for sidecar in (database.with_name(database.name + "-wal"), database.with_name(database.name + "-shm")):
                if sidecar.exists() and sidecar.is_file():
                    sidecar.unlink()
    else:
        backup_dir = backup_and_clear(root, database_files)

    print(f"Cleared {len(database_files)} active database(s).")
    if backup_dir:
        print(f"Backup created at: {backup_dir}")
    print("The application will recreate empty SQLite schemas on its next start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
