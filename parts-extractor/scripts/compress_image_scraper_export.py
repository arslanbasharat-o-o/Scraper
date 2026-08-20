#!/usr/bin/env python3
"""Create a client-size ZIP from image-scraper manifests.

The source scrape stores large PNG/WebP files. This exporter converts the saved
images to JPEG on the fly and writes them directly into a ZIP, so it does not
need a second giant temporary folder.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageOps


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def safe_arc_part(value: str, fallback: str) -> str:
    cleaned = "".join(ch if ch not in '<>:"/\\|?*\x00' else "_" for ch in str(value or "").strip())
    cleaned = " ".join(cleaned.split()).strip(" .")
    return cleaned[:120] or fallback


def iter_manifest_images(download_root: Path):
    for manifest_path in sorted(download_root.rglob("manifest.json")):
        if ".bulk-cache" in manifest_path.parts:
            continue
        folder = manifest_path.parent
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            yield {"error": f"manifest read failed: {exc}", "folder": folder}
            continue

        folder_name = safe_arc_part(
            manifest.get("download_folder") or manifest.get("folder_name") or folder.name,
            folder.name,
        )
        products = manifest.get("products") if isinstance(manifest.get("products"), list) else []
        for product_index, product in enumerate(products):
            product_name = safe_arc_part(product.get("name") if isinstance(product, dict) else "", f"product_{product_index + 1:03d}")
            images = product.get("images") if isinstance(product, dict) and isinstance(product.get("images"), list) else []
            for image_index, image in enumerate(images):
                if not isinstance(image, dict):
                    continue
                raw_file = str(image.get("file_path") or "").strip()
                file_path = Path(raw_file) if raw_file else folder / str(image.get("file_name") or "")
                try:
                    file_path = file_path.resolve()
                    file_path.relative_to(folder.resolve())
                except Exception:
                    continue
                if file_path.suffix.lower() not in IMAGE_EXTS or not file_path.is_file():
                    continue
                yield {
                    "folder": folder,
                    "folder_name": folder_name,
                    "product_name": product_name,
                    "product_index": product_index,
                    "image_index": image_index,
                    "file_path": file_path,
                    "product_url": product.get("product_url", "") if isinstance(product, dict) else "",
                    "source_url": image.get("original_url") or image.get("url") or "",
                }


def convert_to_jpeg_bytes(path: Path, max_side: int, quality: int) -> tuple[bytes, tuple[int, int], tuple[int, int]]:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        original_size = image.size
        width, height = image.size
        scale = min(1.0, max_side / max(width, height))
        if scale < 1.0:
            image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.Resampling.LANCZOS)

        if image.mode != "RGB":
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            image = background

        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=quality, optimize=False, progressive=False)
        return buffer.getvalue(), original_size, image.size


def convert_worker(payload: dict) -> dict:
    try:
      data, original_size, output_size = convert_to_jpeg_bytes(
          Path(payload["source_path"]),
          max_side=int(payload["max_side"]),
          quality=int(payload["quality"]),
      )
      return {
          **payload,
          "data": data,
          "output_bytes": len(data),
          "original_size": f"{original_size[0]}x{original_size[1]}",
          "output_size": f"{output_size[0]}x{output_size[1]}",
          "error": "",
      }
    except Exception as exc:
      return {**payload, "data": b"", "output_bytes": 0, "original_size": "", "output_size": "", "error": str(exc)}


def build_export(download_root: Path, output_zip: Path, max_side: int, quality: int, limit: int = 0, workers: int = 4) -> dict:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    progress_csv = output_zip.with_suffix(".progress.csv")
    summary_json = output_zip.with_suffix(".summary.json")
    start = time.time()

    items = []
    seen_names = set()
    for item in iter_manifest_images(download_root):
        if limit and len(items) >= limit:
            break
        if item.get("error"):
            continue

        source_path = item["file_path"]
        base_name = safe_arc_part(source_path.stem, f"image_{item['image_index'] + 1:03d}")
        archive_path = (
            f"{item['folder_name']}/"
            f"{item['product_index'] + 1:03d}_{item['product_name']}/"
            f"{item['image_index'] + 1:03d}_{base_name}.jpg"
        )
        dedupe_path = archive_path
        suffix = 2
        while dedupe_path.lower() in seen_names:
            dedupe_path = archive_path[:-4] + f"_{suffix}.jpg"
            suffix += 1
        seen_names.add(dedupe_path.lower())

        try:
            source_bytes = source_path.stat().st_size
        except OSError:
            continue

        items.append(
            {
                "archive_path": dedupe_path,
                "source_path": str(source_path),
                "source_bytes": source_bytes,
                "product_url": item.get("product_url", ""),
                "source_url": item.get("source_url", ""),
                "max_side": max_side,
                "quality": quality,
            }
        )

    total_source = 0
    total_output = 0
    converted = 0
    failed = 0

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive, progress_csv.open(
        "w", newline="", encoding="utf-8"
    ) as progress_handle:
        writer = csv.DictWriter(
            progress_handle,
            fieldnames=[
                "archive_path",
                "source_path",
                "source_bytes",
                "output_bytes",
                "original_size",
                "output_size",
                "product_url",
                "source_url",
                "error",
            ],
        )
        writer.writeheader()

        print(f"queued={len(items)} workers={workers} quality={quality} max_side={max_side}", flush=True)
        with ProcessPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = [executor.submit(convert_worker, item) for item in items]
            for future in as_completed(futures):
                result = future.result()
                source_bytes = int(result.get("source_bytes") or 0)
                if result.get("error"):
                    failed += 1
                    writer.writerow(
                        {
                            "archive_path": result.get("archive_path", ""),
                            "source_path": result.get("source_path", ""),
                            "source_bytes": source_bytes,
                            "output_bytes": "",
                            "original_size": "",
                            "output_size": "",
                            "product_url": result.get("product_url", ""),
                            "source_url": result.get("source_url", ""),
                            "error": result.get("error", "conversion failed"),
                        }
                    )
                    continue

                archive.writestr(result["archive_path"], result["data"])
                total_source += source_bytes
                total_output += int(result["output_bytes"])
                converted += 1
                row = {
                    "archive_path": result["archive_path"],
                    "source_path": result["source_path"],
                    "source_bytes": source_bytes,
                    "output_bytes": result["output_bytes"],
                    "original_size": result["original_size"],
                    "output_size": result["output_size"],
                    "product_url": result.get("product_url", ""),
                    "source_url": result.get("source_url", ""),
                    "error": "",
                }
                writer.writerow(row)
                if converted % 250 == 0:
                    elapsed = max(1, time.time() - start)
                    print(
                        f"converted={converted} output_gb={total_output / (1024**3):.2f} "
                        f"speed={converted / elapsed:.1f}/s",
                        flush=True,
                    )

        metadata = {
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_root": str(download_root),
            "output_zip": str(output_zip),
            "format": "JPEG",
            "quality": quality,
            "max_side": max_side,
            "workers": workers,
            "queued": len(items),
            "converted": converted,
            "failed": failed,
            "source_gb": round(total_source / (1024**3), 3),
            "output_gb": round(total_output / (1024**3), 3),
            "elapsed_seconds": round(time.time() - start, 1),
        }
        progress_handle.flush()
        archive.writestr("_export_summary.json", json.dumps(metadata, indent=2))

    summary_json.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-root", required=True, type=Path)
    parser.add_argument("--output-zip", required=True, type=Path)
    parser.add_argument("--max-side", type=int, default=2000)
    parser.add_argument("--quality", type=int, default=82)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    args = parser.parse_args()

    result = build_export(
        download_root=args.download_root.resolve(),
        output_zip=args.output_zip.resolve(),
        max_side=args.max_side,
        quality=args.quality,
        limit=args.limit,
        workers=args.workers,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
