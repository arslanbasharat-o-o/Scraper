#!/usr/bin/env python3
"""
Create a bulk ZIP from selected job folders.
Keeps files under a single root folder, e.g. Bulk Jobs/iPhone 15/...
"""

import json
import os
import sys
import zipfile
from pathlib import Path


def create_bulk_zip(source_root, output_path, root_folder, folder_names):
    try:
        source_root = Path(source_root).resolve()
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        file_count = 0
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED) as zipf:
            for folder_name in folder_names:
                folder_path = (source_root / folder_name).resolve()
                if not folder_path.is_dir():
                    continue
                try:
                    folder_path.relative_to(source_root)
                except ValueError:
                    continue

                for current_root, _dirs, files in os.walk(folder_path):
                    current_root_path = Path(current_root)
                    for file_name in files:
                        if file_name.lower() == "manifest.json":
                            continue
                        file_path = current_root_path / file_name
                        relative = file_path.relative_to(folder_path)
                        arcname = Path(root_folder) / folder_name / relative
                        zipf.write(file_path, arcname.as_posix())
                        file_count += 1

        size = output_path.stat().st_size
        return {
            "success": True,
            "path": str(output_path),
            "size": size,
            "size_mb": round(size / (1024 * 1024), 2),
            "file_count": file_count,
            "compression": "STORE"
        }
    except Exception as exc:
        return {"success": False, "error": f"Bulk ZIP creation failed: {exc}"}


def main():
    if len(sys.argv) < 5:
        print(json.dumps({
            "success": False,
            "error": "Usage: create_bulk_zip.py <source_root> <output_path> <root_folder> <folder> [folder...]"
        }))
        sys.exit(1)

    if sys.argv[4] == "--folders-json":
        if len(sys.argv) < 6:
            result = {"success": False, "error": "Missing folder JSON path"}
        else:
            try:
                with open(sys.argv[5], "r", encoding="utf-8-sig") as handle:
                    folder_names = json.load(handle)
                if not isinstance(folder_names, list) or not all(isinstance(name, str) for name in folder_names):
                    raise ValueError("folder JSON must be a list of strings")
                result = create_bulk_zip(sys.argv[1], sys.argv[2], sys.argv[3], folder_names)
            except Exception as exc:
                result = {"success": False, "error": f"Could not read folder JSON: {exc}"}
    else:
        result = create_bulk_zip(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
    print(json.dumps(result))


if __name__ == "__main__":
    main()
