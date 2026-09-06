"""Backfill missing product SKUs for completed local automation runs.

The worker creates a separate phase-2 continuation run for each completed run,
so the original category crawl remains intact. Product-detail checkpoints are
written as each URL finishes and the continuation can be inspected/resumed if
the process is interrupted.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import time
from pathlib import Path
import pytz

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The local machine profile is the safe base for this worker. HTTP/Safari is
# still primary; browser fallback is bounded to one Chrome window.
os.environ.setdefault("SCRAPER_WORKER_PROFILE", "local_10gb")
os.environ.setdefault("SCRAPER_LOCAL_BROWSER_FALLBACK", "1")
os.environ.setdefault("SCRAPER_LOCAL_BROWSER_MAX_WINDOWS", "1")

from app import (  # noqa: E402
    AutomationRunPaused,
    app,
    db_manager,
    deserialize_scraped_item,
    enrich_scraped_items,
    make_automation_run_stop_checker,
    normalize_compare_url,
    summarize_sku_resolution,
)


def _missing_sku_items(history: dict) -> list:
    result = []
    for raw_item in history.get("items") or []:
        item = deserialize_scraped_item(raw_item)
        if item is None or not str(getattr(item, "url", "") or "").strip():
            continue
        if str(getattr(item, "sku", "") or "").strip():
            continue
        status = str((getattr(item, "extra", {}) or {}).get("sku_status") or "").strip().lower()
        if status in {"not_published", "unavailable"}:
            continue
        result.append(item)
    return result


def _public_history_id(scraper_key: str, raw_history_id: str) -> str:
    return f"{scraper_key}:{raw_history_id}"


def _run_one(source_run: dict, continuation: dict | None = None) -> None:
    source_id = int(source_run["id"])
    continuation_summary = (continuation or {}).get("summary") if continuation else {}
    source_history_id = str(
        (continuation_summary or {}).get("source_history_id")
        or source_run.get("current_history_id")
        or ""
    ).strip()
    history = db_manager.get_history_detail(source_history_id) or {}
    items = [deserialize_scraped_item(raw) for raw in history.get("items") or []]
    items = [item for item in items if item is not None]
    if continuation:
        checkpoints = db_manager.get_automation_run_product_details(continuation["id"])
        for item in items:
            detail = checkpoints.get(normalize_compare_url(getattr(item, "url", "")))
            if detail:
                for key, value in detail.items():
                    if key == "extra" and isinstance(value, dict):
                        item.extra = {**(item.extra or {}), **value}
                    elif hasattr(item, key):
                        setattr(item, key, value)
    missing = [item for item in items if not str(getattr(item, "sku", "") or "").strip()
               and str((getattr(item, "extra", {}) or {}).get("sku_status") or "").strip().lower()
               not in {"not_published", "unavailable"}]
    if not missing:
        print(f"[run {source_id}] already has no retryable missing SKUs; skipping", flush=True)
        return

    job = db_manager.get_automation_job(source_run.get("job_id"), include_targets=True) or {}
    target_urls = list(source_run.get("target_urls") or history.get("urls") or [])
    if continuation:
        continuation_id = int(continuation["id"])
        existing_total = int((continuation_summary or {}).get("phase2_total") or 0)
        total = max(existing_total, len({str(getattr(item, "url", "") or "").strip() for item in missing}))
        initial_done = max(0, total - len({str(getattr(item, "url", "") or "").strip() for item in missing}))
        db_manager.mark_automation_run_resuming(
            continuation_id,
            target_urls=target_urls,
            previous_history_id=source_history_id,
            summary={**(continuation_summary or {}), "phase": 2, "phase2_total": total, "phase2_completed": initial_done},
        )
    else:
        active = db_manager.get_active_automation_run_for_job(source_run.get("job_id"))
        if active:
            print(f"[run {source_id}] active continuation {active.get('id')} already exists; skipping", flush=True)
            return
        continuation = db_manager.create_automation_run(
            int(source_run["job_id"]),
            trigger_type="phase2_sku_backfill",
            target_urls=target_urls,
            previous_history_id=source_history_id,
        )
        if not continuation:
            raise RuntimeError(f"could not create continuation run for source run {source_id}")
        continuation_id = int(continuation["id"])
        total = len({str(getattr(item, "url", "") or "").strip() for item in missing})
        initial_done = 0
    db_manager.update_automation_run_progress(
        continuation_id,
        items_count=len(items),
        summary={
            "phase": 2,
            "phase_name": "Phase 2: Product SKU & Detail Scan",
            "phase2_completed": initial_done,
            "phase2_total": total,
            "target_count": len(target_urls),
            "total_targets": len(target_urls),
            "completed_targets": len(target_urls),
            "current_items": len(items),
            "source_run_id": source_id,
            "source_history_id": source_history_id,
            "status_message": f"Recovering SKUs for {total:,} product URLs.",
        },
    )
    print(
        f"[run {source_id}] continuation {continuation_id}: "
        f"{len(items):,} products, {total:,} unique detail URLs",
        flush=True,
    )

    lock_file = ROOT / ".tmp" / f"resume-run-{continuation_id}.lock"
    created_lock = False
    if not lock_file.exists():
        try:
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            lock_file.write_text(
                json.dumps(
                    {
                        "run_id": continuation_id,
                        "pid": os.getpid(),
                        "started_at": datetime.datetime.now(pytz.timezone("Asia/Karachi")).isoformat(),
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            created_lock = True
        except Exception:
            pass

    automation_stop_check = make_automation_run_stop_checker(continuation_id)

    def progress_callback(progress: dict) -> None:
        if automation_stop_check:
            automation_stop_check()
        enriched = progress.get("enriched_item")
        if isinstance(enriched, dict):
            # Persist under the original queued URL as well as any canonical
            # URL returned by the supplier.  Resume overlays by the queued
            # URL, so redirects must not cause a completed item to be fetched
            # again after a restart.
            checkpoint_url = str(progress.get("last_item_url") or "").strip()
            db_manager.save_automation_run_product_detail(continuation_id, enriched, checkpoint_url=checkpoint_url)
        completed = initial_done + int(progress.get("phase2_completed") or 0)
        phase_total = max(total, int(progress.get("phase2_total") or 0))
        db_manager.update_automation_run_progress(
            continuation_id,
            items_count=len(items),
            summary={
                "phase": 2,
                "phase_name": "Phase 2: Product SKU & Detail Scan",
                "phase2_completed": completed,
                "phase2_total": phase_total,
                "target_count": len(target_urls),
                "total_targets": len(target_urls),
                "completed_targets": len(target_urls),
                "current_items": len(items),
                "source_run_id": source_id,
                "source_history_id": source_history_id,
                "status_message": f"Recovered {completed:,} of {phase_total:,} product detail URLs.",
            },
        )

    try:
        with app.app_context():
            enriched_items, enriched_count = enrich_scraped_items(
                items,
                job.get("rules") or history.get("rules") or {},
                retries=int(job.get("retries") or 1),
                verify_ssl=bool(job.get("verify_ssl", True)),
                use_curl=True,
                enrich_details=True,
                logger=app.logger,
                use_browser=False,
                progress_callback=progress_callback,
                stop_check=automation_stop_check,
            )
            summary = summarize_sku_resolution(enriched_items)
            raw_history_id = str(int(time.time() * 1000))
            scraper_key = str(source_run.get("scraper_key") or history.get("scraper_key") or "standard")
            rules = dict(history.get("rules") or job.get("rules") or {})
            rules.update({"_phase2_backfill": True, "_source_run_id": source_id})
            saved = db_manager.save_fetch_history(raw_history_id, target_urls, enriched_items, rules)
            if not saved:
                raise RuntimeError("failed to save enriched history")
            public_history_id = _public_history_id(scraper_key, raw_history_id)
            final_summary = {
                "phase": 3 if summary["sku_unresolved"] == 0 else 2,
                "phase_name": "Complete" if summary["sku_unresolved"] == 0 else "Phase 2: SKU retry required",
                "phase2_completed": initial_done + enriched_count,
                "phase2_total": total,
                "target_count": len(target_urls),
                "total_targets": len(target_urls),
                "completed_targets": len(target_urls),
                "current_items": len(enriched_items),
                "source_run_id": source_id,
                "source_history_id": source_history_id,
                **summary,
            }
            error_text = ""
            status = "completed"
            if summary["sku_unresolved"]:
                status = "failed"
                error_text = (
                    f"SKU recovery incomplete: {summary['sku_unresolved']:,} detail URL(s) remain unresolved; "
                    "resume this continuation run to retry them."
                )
            db_manager.complete_automation_run(
                continuation_id,
                status=status,
                current_history_id=public_history_id,
                previous_history_id=source_history_id,
                target_urls=target_urls,
                items_count=len(enriched_items),
                summary=final_summary,
                error_text=error_text,
            )
            if status == "completed":
                merged = db_manager.merge_automation_run(source_id, continuation_id)
                if not merged:
                    raise RuntimeError(
                        f"continuation {continuation_id} completed but could not merge into source run {source_id}"
                    )
                print(f"[run {source_id}] merged continuation {continuation_id} into the original run", flush=True)
            print(
                f"[run {source_id}] continuation {continuation_id} finished: "
                f"SKU found={summary['sku_found']:,}/{summary['sku_total']:,}, "
                f"unresolved={summary['sku_unresolved']:,}",
                flush=True,
            )
    except AutomationRunPaused:
        print(f"[run {source_id}] continuation {continuation_id} paused by user.", flush=True)
        return
    except Exception as exc:
        db_manager.complete_automation_run(
            continuation_id,
            status="failed",
            current_history_id="",
            previous_history_id=source_history_id,
            target_urls=target_urls,
            items_count=len(items),
            summary={
                "phase": 2,
                "phase_name": "Phase 2 failed",
                "source_run_id": source_id,
                "source_history_id": source_history_id,
                "current_items": len(items),
            },
            error_text=str(exc),
        )
        raise
    finally:
        if created_lock:
            try:
                if lock_file.exists():
                    data = json.loads(lock_file.read_text(encoding="utf-8") or "{}")
                    if int(data.get("pid") or 0) == os.getpid():
                        lock_file.unlink(missing_ok=True)
            except Exception:
                pass


def main() -> int:
    requested = {int(value) for value in sys.argv[1:] if str(value).isdigit()}
    continuation_runs = [
        run for run in db_manager.list_automation_runs(limit=100)
        if run.get("trigger_type") == "phase2_sku_backfill"
        and run.get("status") in {"paused", "interrupted", "running", "resuming"}
        and isinstance(run.get("summary"), dict)
        and run["summary"].get("source_run_id")
        and (not requested or int(run["summary"].get("source_run_id") or 0) in requested or int(run.get("id") or 0) in requested)
    ]
    for continuation in continuation_runs:
        source = db_manager.get_automation_run(int(continuation["summary"]["source_run_id"]))
        if source:
            _run_one(source, continuation=continuation)

    if requested and continuation_runs:
        return 0

    runs = [
        run for run in db_manager.list_automation_runs(limit=100)
        if run.get("status") == "completed"
        and run.get("current_history_id")
        and (not requested or int(run.get("id") or 0) in requested)
    ]
    if not runs:
        if not continuation_runs:
            print("No completed runs with histories matched.", flush=True)
        return 0
    print(f"Starting local phase-2 SKU backfill for {len(runs)} completed run(s).", flush=True)
    for source_run in sorted(runs, key=lambda row: int(row.get("id") or 0)):
        _run_one(source_run)
    print("Phase-2 SKU backfill queue finished.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
