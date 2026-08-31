import argparse
import csv
import datetime as dt
import json
import re
import shutil
import sqlite3
from pathlib import Path


DEFAULT_HISTORY_ID = "1784142000000"
DEFAULT_TIMESTAMP = "2026-07-16T00:00:00+05:00"
DEFAULT_AUTOMATION_JOB_NAME = "Full Website - XCell Parts - Baseline Import"


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_price(value):
    clean = re.sub(r"[^\d.]", "", str(value or ""))
    if not clean:
        return None
    try:
        return round(float(clean), 2)
    except ValueError:
        return None


def build_urls_key(urls):
    normalized = sorted({str(url or "").strip() for url in urls if str(url or "").strip()})
    return json.dumps(normalized, separators=(",", ":"))


def load_full_site_urls(categories_csv):
    urls = []
    seen = set()
    with categories_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if clean_text(row.get("url_missing")).lower() in {"1", "true", "yes"}:
                continue
            url = clean_text(row.get("normalized_url") or row.get("child_url"))
            if not url or url in seen:
                continue
            seen.add(url)
            urls.append(url)
    return urls


def load_full_site_targets(categories_csv):
    targets = []
    seen = set()
    with categories_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if clean_text(row.get("url_missing")).lower() in {"1", "true", "yes"}:
                continue
            url = clean_text(row.get("normalized_url") or row.get("child_url"))
            if not url or url in seen:
                continue
            seen.add(url)
            parent = clean_text(row.get("parent_name"))
            sub_child = clean_text(row.get("sub_child_name"))
            child = clean_text(row.get("child_name")) or url.rstrip("/").rsplit("/", 1)[-1]
            group_parts = [part for part in (parent, sub_child) if part and part.upper() != child.upper()]
            targets.append(
                {
                    "label": child,
                    "group_label": " > ".join(group_parts),
                    "url": url,
                    "url_key": normalize_target_url(url),
                }
            )
    return targets


def load_category_lookup(categories_csv):
    lookup = {}
    with categories_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = clean_text(row.get("child_name")).upper()
            url = clean_text(row.get("normalized_url") or row.get("child_url"))
            if name and url and name not in lookup:
                lookup[name] = url
    return lookup


def load_product_items(products_csv, category_lookup):
    items = []
    seen_urls = set()
    with products_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            product_url = clean_text(row.get("Product URL"))
            title = clean_text(row.get("Name"))
            if not product_url or not title or product_url in seen_urls:
                continue
            seen_urls.add(product_url)

            category = clean_text(row.get("Category"))
            sku = clean_text(row.get("SKU"))
            price_text = clean_text(row.get("Price"))
            price_value = parse_price(price_text)
            target_url = category_lookup.get(category.upper(), "")
            extra = {
                "source_dump_id": clean_text(row.get("ID")),
                "source_category": category,
                "target_url": target_url,
                "target_label": category,
                "model_label": category,
                "sku": sku,
                "imported_from": str(products_csv),
                "imported_as": "xcell_full_site_last_week_baseline",
            }
            created_at = clean_text(row.get("Created At"))
            updated_at = clean_text(row.get("Updated At"))
            if created_at:
                extra["source_created_at"] = created_at
            if updated_at:
                extra["source_updated_at"] = updated_at

            items.append(
                {
                    "url": product_url,
                    "site": "xcellparts.com",
                    "title": title,
                    "price_value": price_value,
                    "price_currency": "USD" if "$" in price_text else "",
                    "price_text": price_text,
                    "discounted_value": price_value,
                    "discounted_formatted": price_text,
                    "original_formatted": price_text,
                    "sku": sku,
                    "stock_status": "",
                    "description": "",
                    "extra_json": json.dumps(extra, ensure_ascii=True, separators=(",", ":")),
                    "source": "xcell_csv_baseline",
                    "image_url": clean_text(row.get("Image")),
                }
            )
    return items


def normalize_target_url(url):
    normalized = clean_text(url)
    if normalized.endswith("/") and len(normalized) > len("https://a/"):
        normalized = normalized.rstrip("/")
    return normalized


def register_automation_run(control_db_path, categories_csv, history_id, timestamp, item_count):
    targets = load_full_site_targets(categories_csv)
    if not targets:
        raise RuntimeError(f"No automation targets found in {categories_csv}")

    public_history_id = f"xcell:{history_id}"
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=5))).replace(microsecond=0).isoformat()
    run_uuid = f"import-xcell-full-baseline-{history_id}"
    target_urls = [target["url"] for target in targets]
    summary = {
        "target_count": len(targets),
        "total_targets": len(targets),
        "completed_targets": len(targets),
        "current_items": int(item_count),
        "previous_items": 0,
        "changed": 0,
        "added": 0,
        "removed": 0,
        "price_changes": 0,
        "stock_changes": 0,
        "title_changes": 0,
        "sku_changes": 0,
        "description_changes": 0,
        "url_changes": 0,
        "price_drop_alerts": 0,
        "models": [],
        "imported_baseline": True,
    }

    backup_path = control_db_path.with_suffix(
        control_db_path.suffix + f".bak-automation-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    shutil.copy2(control_db_path, backup_path)

    conn = sqlite3.connect(control_db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        row = cursor.execute(
            "SELECT id FROM automation_jobs WHERE name = ? AND scraper_key = ? LIMIT 1",
            (DEFAULT_AUTOMATION_JOB_NAME, "xcell"),
        ).fetchone()
        if row:
            job_id = int(row[0])
            cursor.execute(
                """
                UPDATE automation_jobs
                SET
                    category_query = ?, root_url = ?, interval_minutes = ?,
                    enabled = ?, auto_discover = ?, crawl_pagination = ?,
                    max_pages = ?, delay_ms = ?, retries = ?, verify_ssl = ?,
                    use_parallel = ?, enrich_details = ?, drop_pct = ?,
                    rules_json = ?, last_discovery_at = ?, last_run_at = ?,
                    next_run_at = ?, last_status = ?, last_error = ?,
                    last_history_ids = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    "Full Website Baseline Import",
                    "https://xcellparts.com",
                    10080,
                    0,
                    0,
                    1,
                    10,
                    50,
                    1,
                    1,
                    1,
                    0,
                    10.0,
                    json.dumps({"_baseline_import": True}, separators=(",", ":")),
                    timestamp,
                    timestamp,
                    None,
                    "completed",
                    "",
                    json.dumps([public_history_id], separators=(",", ":")),
                    now,
                    job_id,
                ),
            )
            cursor.execute("DELETE FROM automation_job_targets WHERE job_id = ?", (job_id,))
        else:
            cursor.execute(
                """
                INSERT INTO automation_jobs (
                    name, scraper_key, category_query, root_url,
                    interval_minutes, enabled, auto_discover, crawl_pagination,
                    max_pages, delay_ms, retries, verify_ssl, use_parallel,
                    enrich_details, drop_pct, rules_json,
                    last_discovery_at, last_run_at, next_run_at, last_status,
                    last_error, last_history_ids, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    DEFAULT_AUTOMATION_JOB_NAME,
                    "xcell",
                    "Full Website Baseline Import",
                    "https://xcellparts.com",
                    10080,
                    0,
                    0,
                    1,
                    10,
                    50,
                    1,
                    1,
                    1,
                    0,
                    10.0,
                    json.dumps({"_baseline_import": True}, separators=(",", ":")),
                    timestamp,
                    timestamp,
                    None,
                    "completed",
                    "",
                    json.dumps([public_history_id], separators=(",", ":")),
                    now,
                    now,
                ),
            )
            job_id = int(cursor.lastrowid)

        cursor.executemany(
            """
            INSERT INTO automation_job_targets (
                job_id, label, group_label, url, url_key, active, position, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            [
                (
                    job_id,
                    target["label"],
                    target["group_label"],
                    target["url"],
                    target["url_key"],
                    index,
                    now,
                    now,
                )
                for index, target in enumerate(targets)
            ],
        )

        cursor.execute("DELETE FROM automation_runs WHERE run_uuid = ?", (run_uuid,))
        cursor.execute(
            """
            INSERT INTO automation_runs (
                job_id, run_uuid, trigger_type, status, started_at, completed_at,
                current_history_id, previous_history_id, target_urls_json,
                items_count, summary_json, error_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                run_uuid,
                "import",
                "completed",
                timestamp,
                timestamp,
                public_history_id,
                "",
                json.dumps(target_urls, ensure_ascii=True, separators=(",", ":")),
                int(item_count),
                json.dumps(summary, ensure_ascii=True, separators=(",", ":")),
                "",
                now,
            ),
        )
        run_id = int(cursor.lastrowid)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "control_backup_path": str(backup_path),
        "automation_job_id": job_id,
        "automation_run_id": run_id,
        "automation_target_count": len(targets),
    }


def import_baseline(db_path, products_csv, categories_csv, history_id, timestamp):
    urls = load_full_site_urls(categories_csv)
    if not urls:
        raise RuntimeError(f"No category URLs found in {categories_csv}")

    category_lookup = load_category_lookup(categories_csv)
    items = load_product_items(products_csv, category_lookup)
    if not items:
        raise RuntimeError(f"No product rows found in {products_csv}")

    backup_path = db_path.with_suffix(db_path.suffix + f".bak-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(db_path, backup_path)

    rules = {
        "_baseline_import": True,
        "_baseline_scope": "xcell_full_site",
        "_baseline_label": "Last week XCell Parts full-site CSV dump",
        "_source_csv": str(products_csv),
        "_category_url_source": str(categories_csv),
    }

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("DELETE FROM items WHERE history_id = ?", (history_id,))
        cursor.execute("DELETE FROM fetch_history WHERE id = ?", (history_id,))
        cursor.execute(
            """
            INSERT INTO fetch_history (id, timestamp, urls, urls_key, items_count, rules)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                history_id,
                timestamp,
                json.dumps(urls),
                build_urls_key(urls),
                len(items),
                json.dumps(rules, ensure_ascii=True, separators=(",", ":")),
            ),
        )
        cursor.executemany(
            """
            INSERT INTO items (
                history_id, url, site, title, price_value, price_currency,
                price_text, discounted_value, discounted_formatted,
                original_formatted, sku, stock_status, description,
                extra_json, source, image_url
            ) VALUES (
                :history_id, :url, :site, :title, :price_value, :price_currency,
                :price_text, :discounted_value, :discounted_formatted,
                :original_formatted, :sku, :stock_status, :description,
                :extra_json, :source, :image_url
            )
            """,
            [{**item, "history_id": history_id} for item in items],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "backup_path": str(backup_path),
        "history_id": history_id,
        "timestamp": timestamp,
        "category_url_count": len(urls),
        "item_count": len(items),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--db", default=Path("data/site_dbs/xcellparts.db"), type=Path)
    parser.add_argument("--categories", default=Path("output/xcellparts/categories.csv"), type=Path)
    parser.add_argument("--control-db", default=Path("data/site_dbs/mobilesentrix.db"), type=Path)
    parser.add_argument("--history-id", default=DEFAULT_HISTORY_ID)
    parser.add_argument("--timestamp", default=DEFAULT_TIMESTAMP)
    parser.add_argument("--skip-automation-registration", action="store_true")
    args = parser.parse_args()

    result = import_baseline(
        args.db.resolve(),
        args.csv.resolve(),
        args.categories.resolve(),
        str(args.history_id),
        str(args.timestamp),
    )
    if not args.skip_automation_registration:
        result.update(
            register_automation_run(
                args.control_db.resolve(),
                args.categories.resolve(),
                str(args.history_id),
                str(args.timestamp),
                result["item_count"],
            )
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
