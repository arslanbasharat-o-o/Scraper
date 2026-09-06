import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import sqlite3
import app

# 1. Load backup
backup_path = Path("data/backup_mobilesentrix_jobs.json")
with open(backup_path, "r", encoding="utf-8") as f:
    backup = json.load(f)

job_3_data = backup["job_3"]
job_4_data = backup["job_4"]
runs_3_data = backup.get("runs_3", [])
runs_4_data = backup.get("runs_4", [])

print(f"Loaded backup: Job 3 targets={len(job_3_data['targets'])}, Job 4 targets={len(job_4_data['targets'])}")

# 2. Connect to main database (mobilesentrix.db)
main_conn = sqlite3.connect(app.db_manager.db_path)
main_cursor = main_conn.cursor()

# Restore Jobs
for job_data in [job_3_data, job_4_data]:
    jid = job_data["id"]
    print(f"Restoring Job {jid}: {job_data['name']}")
    rules = job_data.get("rules") or {}
    rules_json = json.dumps(rules, ensure_ascii=True, separators=(',', ':')) if isinstance(rules, dict) else str(rules)
    last_hids = job_data.get("last_history_ids") or []
    last_hids_json = json.dumps(last_hids, ensure_ascii=True, separators=(',', ':')) if isinstance(last_hids, list) else str(last_hids)

    main_cursor.execute("""
        INSERT OR REPLACE INTO automation_jobs (
            id, name, scraper_key, category_query, root_url,
            interval_minutes, enabled, auto_discover, crawl_pagination,
            max_pages, delay_ms, retries, verify_ssl, use_parallel,
            enrich_details, drop_pct, rules_json, last_discovery_at,
            last_run_at, next_run_at, last_status, last_error,
            last_history_ids, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        jid,
        job_data["name"],
        job_data["scraper_key"],
        job_data["category_query"],
        job_data["root_url"],
        job_data.get("interval_minutes", 1440),
        1 if job_data.get("enabled") else 0,
        1 if job_data.get("auto_discover") else 0,
        1 if job_data.get("crawl_pagination") else 0,
        job_data.get("max_pages", 10),
        job_data.get("delay_ms", 50),
        job_data.get("retries", 1),
        1 if job_data.get("verify_ssl") else 0,
        1 if job_data.get("use_parallel") else 0,
        1 if job_data.get("enrich_details") else 0,
        job_data.get("drop_pct", 10.0),
        rules_json,
        job_data.get("last_discovery_at"),
        job_data.get("last_run_at"),
        job_data.get("next_run_at"),
        "interrupted",
        "",
        last_hids_json,
        job_data.get("created_at"),
        job_data.get("updated_at"),
    ))

    # Restore Targets
    targets = job_data.get("targets", [])
    print(f"  Restoring {len(targets)} targets for Job {jid}...")
    main_cursor.execute("DELETE FROM automation_job_targets WHERE job_id = ?", (jid,))
    main_cursor.executemany("""
        INSERT INTO automation_job_targets (
            id, job_id, label, group_label, url, url_key, active, position, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (
            t["id"],
            jid,
            t.get("label", ""),
            t.get("group_label", ""),
            t["url"],
            t.get("url_key", ""),
            1 if t.get("active", True) else 0,
            t.get("position", 0),
            t.get("created_at", ""),
            t.get("updated_at", "")
        )
        for t in targets
    ])

# Restore Runs
for run in runs_3_data + runs_4_data:
    rid = run["id"]
    jid = run["job_id"]
    st = run.get("status", "interrupted")
    # For in-progress or interrupted runs, make sure they are ready to resume
    if st in {"running", "resuming"}:
        st = "interrupted"
    summary = run.get("summary") or {}
    # If run 4 had completed with fake not_published items, mark it interrupted with unresolved items
    if rid == 4:
        st = "interrupted"
        summary["phase"] = 2
        summary["phase_name"] = "Phase 2: Product Detail Fetching"
        summary["sku_not_published"] = 0
        summary["sku_unresolved"] = 19563
        summary["interrupted"] = True

    summary_json = json.dumps(summary, ensure_ascii=True, separators=(',', ':'))
    target_urls_json = json.dumps(run.get("target_urls") or [], ensure_ascii=True, separators=(',', ':'))

    print(f"Restoring Run {rid} (Job {jid}, status: {st})")
    main_cursor.execute("""
        INSERT OR REPLACE INTO automation_runs (
            id, job_id, run_uuid, trigger_type, status, started_at,
            completed_at, current_history_id, previous_history_id,
            target_urls_json, items_count, summary_json, error_text, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        rid,
        jid,
        run["run_uuid"],
        run.get("trigger_type", "manual"),
        st,
        run.get("started_at"),
        run.get("completed_at"),
        run.get("current_history_id", ""),
        run.get("previous_history_id", ""),
        target_urls_json,
        run.get("items_count", 0),
        summary_json,
        run.get("error_text", ""),
        run.get("created_at"),
    ))

main_conn.commit()
print("Main database jobs and runs restored successfully.")

# 3. Repair items in mobilesentrix_ca.db for run 4
ca_db_path = Path("data/site_dbs/mobilesentrix_ca.db")
if ca_db_path.exists():
    ca_conn = sqlite3.connect(ca_db_path)
    ca_cursor = ca_conn.cursor()

    # Build title lookup from original uncorrupted crawl 1788583003960
    ca_cursor.execute("SELECT url, title FROM items WHERE history_id = '1788583003960'")
    original_titles = {row[0]: row[1] for row in ca_cursor.fetchall() if row[1] and "Error 1015" not in row[1]}
    print(f"Found {len(original_titles)} legitimate titles from crawl 1788583003960")

    # Repair history 1788667575002 items
    ca_cursor.execute("SELECT id, url, title, extra_json FROM items WHERE history_id = '1788667575002'")
    items_to_fix = ca_cursor.fetchall()
    repaired_count = 0

    for item_id, url, title, extra_json in items_to_fix:
        extra = json.loads(extra_json or '{}')
        needs_fix = False
        new_title = title

        if "Error 1015" in (title or ""):
            new_title = original_titles.get(url, title)
            needs_fix = True

        if extra.get("sku_status") == "not_published":
            extra["sku_status"] = "unresolved"
            extra["sku_error"] = "Cloudflare Error 1015 rate limit - ready to resume"
            needs_fix = True

        if needs_fix:
            ca_cursor.execute(
                "UPDATE items SET title = ?, extra_json = ? WHERE id = ?",
                (new_title, json.dumps(extra, ensure_ascii=True, separators=(',', ':')), item_id)
            )
            repaired_count += 1

    ca_conn.commit()
    print(f"Repaired {repaired_count} items in mobilesentrix_ca.db history 1788667575002.")
