import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import (  # noqa: E402
    AUTOMATION_CHECKPOINT_ITEM_LIMIT,
    AutomationRunPaused,
    automation_progress_write_due,
    app,
    build_automation_run_summary,
    db_manager,
    execute_scrape_workflow,
    make_automation_run_stop_checker,
    save_automation_partial_history,
    validate_supplier_remote_urls,
)


def _target_labels(targets):
    return {
        str(target.get("url") or "").strip(): str(target.get("label") or "").strip()
        for target in targets or []
        if str(target.get("url") or "").strip()
    }


def resume_run(run_id: int) -> int:
    run = db_manager.get_automation_run(run_id)
    if not run:
        print(f"Run {run_id} was not found.")
        return 1

    job = db_manager.get_automation_job(run.get("job_id"), include_targets=True)
    if not job:
        print(f"Job {run.get('job_id')} for run {run_id} was not found.")
        return 1

    targets = [target for target in job.get("targets", []) if target.get("active", True)]
    target_urls = [
        str(target.get("url") or "").strip()
        for target in targets
        if str(target.get("url") or "").strip()
    ]
    if not target_urls:
        print(f"Job {job.get('id')} has no active targets.")
        db_manager.fail_automation_run_resume_launch(run_id, "Automation job has no active targets.")
        return 1
    try:
        target_urls = validate_supplier_remote_urls(target_urls, job.get("scraper_key"))
    except ValueError as exc:
        db_manager.fail_automation_run_resume_launch(run_id, str(exc))
        print(str(exc))
        return 1

    previous_history_id = str(run.get("previous_history_id") or "").strip()
    if not previous_history_id:
        last_history_ids = job.get("last_history_ids") or []
        previous_history_id = str(last_history_ids[0] or "").strip() if last_history_ids else ""

    previous_history = db_manager.get_history_detail(previous_history_id) if previous_history_id else None
    total_target_count = len(target_urls)
    original_summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
    resume_from_checkpoint = _truthy_env("RESUME_FROM_CHECKPOINT")
    base_completed_targets = 0
    completed_target_urls = []
    base_items_count = 0
    base_preview_items = []
    if resume_from_checkpoint:
        completed_target_urls = db_manager.get_automation_run_completed_target_urls(run_id)
        completed_target_keys = {
            str(url or "").strip().rstrip("/").lower()
            for url in completed_target_urls
            if str(url or "").strip()
        }
        completed_target_urls = [
            url for url in target_urls
            if str(url or "").strip().rstrip("/").lower() in completed_target_keys
        ]
        base_completed_targets = len(completed_target_urls)
        base_items_count = max(
            0,
            int(
                original_summary.get("current_items")
                or original_summary.get("items_count")
                or run.get("items_count")
                or 0
            ),
        )
        base_preview_items = original_summary.get("preview_items") if isinstance(original_summary.get("preview_items"), list) else []
        if len(base_preview_items) < base_items_count and run.get("current_history_id"):
            checkpoint_history = db_manager.get_history_detail(str(run.get("current_history_id") or ""))
            history_items = checkpoint_history.get("items") if isinstance((checkpoint_history or {}).get("items"), list) else []
            if len(history_items) >= base_items_count:
                base_preview_items = history_items[:base_items_count]
        checkpoint_items = db_manager.get_automation_run_items(run_id)
        if checkpoint_items:
            base_preview_items = checkpoint_items
            base_items_count = len(checkpoint_items)
    completed_target_keys = {
        str(url or "").strip().rstrip("/").lower()
        for url in completed_target_urls
    }
    remaining_target_urls = [
        url for url in target_urls
        if str(url or "").strip().rstrip("/").lower() not in completed_target_keys
    ]
    checkpoint_only_phase1 = base_items_count > 0 and base_completed_targets <= 0
    phase_name = "Restoring Product Checkpoint" if checkpoint_only_phase1 else "Phase 1: Category Crawling"
    db_manager.mark_automation_run_resuming(
        run_id,
        target_urls=target_urls,
        previous_history_id=previous_history_id,
        summary={
            "phase": 1,
            "phase_name": phase_name,
            "target_count": total_target_count,
            "completed_targets": base_completed_targets,
            "total_targets": total_target_count,
            "current_items": base_items_count,
            "progress_percent": 1.0 if checkpoint_only_phase1 else round((base_completed_targets / max(1, total_target_count)) * 100, 1),
            "last_target_url": str(original_summary.get("last_target_url") or ""),
            "last_target_items": int(original_summary.get("last_target_items") or 0),
            "resumed_run": True,
            "resumed_from_status": run.get("status") or "",
            "resumed_from_checkpoint": resume_from_checkpoint,
            "preview_items": base_preview_items[:AUTOMATION_CHECKPOINT_ITEM_LIMIT],
            "phase1_completed": base_completed_targets,
            "phase1_total": total_target_count,
            "status_message": "Restoring saved products while category completion catches up." if checkpoint_only_phase1 else "Resuming category crawling.",
            "activity_label": phase_name,
        },
    )

    recent_progress = []
    recent_enrich_progress = []
    automation_stop_check = make_automation_run_stop_checker(run_id)
    progress_write_state: Dict[str, object] = {}
    progress_summary_cache: Dict[str, object] = dict(original_summary)

    def progress_callback(progress: Dict[str, object]):
        automation_stop_check()
        enriched_checkpoint = progress.get("enriched_item")
        if isinstance(enriched_checkpoint, dict):
            db_manager.save_automation_run_product_detail(run_id, enriched_checkpoint)
        now = time.time()
        current_phase = int(progress.get("phase") or (2 if progress.get("phase2_total") else 1))
        total_targets_local = max(1, total_target_count)
        completed_targets = total_target_count if current_phase == 2 else int(
            progress.get("completed_targets") if progress.get("completed_targets") is not None else base_completed_targets
        )
        current_items = int(progress.get("current_items") if progress.get("current_items") is not None else base_items_count)
        checkpoint_only_phase1 = current_phase == 1 and current_items > 0 and completed_targets <= 0
        phase_name = str(
            progress.get("phase_name")
            or ("Phase 2: Product SKU & Detail Scan" if current_phase == 2 else "Phase 1: Category Crawling")
        )
        if checkpoint_only_phase1:
            phase_name = "Restoring Product Checkpoint"
        last_target_items = int(progress.get("last_target_items") or 0)
        preview_items = progress.get("preview_items") if isinstance(progress.get("preview_items"), list) else []
        checkpoint_preview_items = preview_items or base_preview_items[:AUTOMATION_CHECKPOINT_ITEM_LIMIT]
        cutoff = now - 10 * 60
        phase2_completed = int(
            progress.get("phase2_completed")
            if progress.get("phase2_completed") is not None
            else progress_summary_cache.get("phase2_completed") or 0
        )
        phase2_total = int(
            progress.get("phase2_total")
            if progress.get("phase2_total") is not None
            else progress_summary_cache.get("phase2_total") or 0
        )
        if current_phase == 2 and phase2_completed > 0:
            phase2_total = max(phase2_total, phase2_completed)

        if current_phase == 2:
            recent_enrich_progress.append((now, phase2_completed))
            while len(recent_enrich_progress) > 1 and recent_enrich_progress[0][0] < cutoff:
                recent_enrich_progress.pop(0)
        else:
            recent_progress.append((now, completed_targets, current_items))
            while len(recent_progress) > 1 and recent_progress[0][0] < cutoff:
                recent_progress.pop(0)

        recent_targets_per_min = float(progress_summary_cache.get("recent_targets_per_min") or 0.0)
        recent_items_per_min = float(progress_summary_cache.get("recent_items_per_min") or 0.0)
        if len(recent_progress) >= 2:
            first_time, first_targets, first_items = recent_progress[0]
            elapsed_minutes = max((now - first_time) / 60.0, 0.001)
            recent_targets_per_min = max(0.0, (completed_targets - first_targets) / elapsed_minutes)
            recent_items_per_min = max(0.0, (current_items - first_items) / elapsed_minutes)
        if len(recent_enrich_progress) >= 2:
            first_time, first_enriched = recent_enrich_progress[0]
            elapsed_minutes = max((now - first_time) / 60.0, 0.001)
            recent_items_per_min = max(0.0, (phase2_completed - first_enriched) / elapsed_minutes)

        if progress.get("progress_percent") is not None:
            try:
                progress_percent = max(0.0, min(100.0, round(float(progress.get("progress_percent")), 1)))
            except (TypeError, ValueError):
                progress_percent = 0.0
        elif current_phase == 2:
            progress_percent = round((phase2_completed / max(1, phase2_total)) * 100, 1) if phase2_total else 0.0
        else:
            progress_percent = 1.0 if checkpoint_only_phase1 else round((completed_targets / total_targets_local) * 100, 1)

        progress_summary = {
            "phase": current_phase,
            "phase_name": phase_name,
            "target_count": total_target_count,
            "completed_targets": completed_targets,
            "total_targets": total_targets_local,
            "current_items": current_items,
            "progress_percent": progress_percent,
            "last_target_url": str(progress.get("last_target_url") or ""),
            "last_target_items": last_target_items,
            "preview_items": checkpoint_preview_items[:AUTOMATION_CHECKPOINT_ITEM_LIMIT],
            "resumed_run": True,
            "resumed_from_checkpoint": resume_from_checkpoint,
            "recent_targets_per_min": round(recent_targets_per_min, 2),
            "recent_items_per_min": round(recent_items_per_min, 2),
            "recent_rate_window_seconds": 600,
            "phase1_completed": completed_targets,
            "phase1_total": total_targets_local,
            "phase2_completed": phase2_completed,
            "phase2_total": phase2_total,
            "phase2_speed": f"{recent_items_per_min:.0f} items/min" if current_phase == 2 and recent_items_per_min > 0 else "Starting...",
            "status_message": str(
                progress.get("status_message")
                or ("Restoring saved products while category completion catches up." if checkpoint_only_phase1 else ("Enriching product details." if current_phase == 2 else "Resuming category crawling."))
            ),
            "activity_label": str(progress.get("activity_label") or phase_name),
        }
        progress_summary_cache.update(progress_summary)
        progress_completed = phase2_completed if current_phase == 2 else completed_targets
        progress_total = phase2_total if current_phase == 2 else total_targets_local
        if not automation_progress_write_due(
            progress_write_state,
            now=now,
            phase=current_phase,
            completed=progress_completed,
            total=progress_total,
        ):
            return

        db_manager.update_automation_run_progress(
            run_id,
            items_count=current_items,
            summary=progress_summary,
        )

    try:
        workflow_job = dict(job)
        workflow_job["_active_run_id"] = run_id
        result = execute_scrape_workflow(
            target_urls,
            crawl_pagination=job.get("crawl_pagination", True),
            max_pages=job.get("max_pages", 10),
            delay_ms=job.get("delay_ms", 50),
            retries=job.get("retries", 1),
            verify_ssl=job.get("verify_ssl", True),
            use_curl=True,
            use_browser=_truthy_value(job.get("use_browser", False)),
            use_parallel=job.get("use_parallel", True),
            enrich_details=job.get("enrich_details", True),
            rules=job.get("rules", {}),
            drop_pct=job.get("drop_pct", 10.0),
            target_labels=_target_labels(targets),
            automation_job=workflow_job,
            previous_history_override=previous_history,
            progress_callback=progress_callback,
            stop_check=automation_stop_check,
            initial_items=base_preview_items if resume_from_checkpoint else None,
            skip_target_urls=completed_target_urls if resume_from_checkpoint else None,
        )
    except AutomationRunPaused as exc:
        db_manager.pause_automation_run(run_id, reason=str(exc) or "Automation run paused.")
        db_manager.close_connection()
        return 0
    except Exception as exc:
        error_text = str(exc) or "Automation run failed before completion."
        partial_history_id, partial_count, partial_summary = save_automation_partial_history(
            run_id,
            job,
            target_urls,
            previous_history=previous_history,
            error_text=error_text,
        )
        db_manager.complete_automation_run(
            run_id,
            status="failed",
            current_history_id=partial_history_id,
            previous_history_id=previous_history_id,
            target_urls=target_urls,
            items_count=partial_count,
            summary=partial_summary,
            error_text=error_text,
        )
        db_manager.close_connection()
        return 2

    summary = build_automation_run_summary(
        target_urls,
        result.get("comparison") or {},
        result.get("price_drops") or [],
    )
    summary["resumed_run"] = True
    summary["resumed_from_checkpoint"] = resume_from_checkpoint
    summary["completed_targets"] = total_target_count
    summary["total_targets"] = total_target_count
    result_count = int(result.get("count") or 0)
    summary["current_items"] = result_count
    summary["progress_percent"] = round((summary["completed_targets"] / max(1, total_target_count)) * 100, 1)
    workflow_error = str(result.get("error") or "").strip()
    no_items_error = ""
    if remaining_target_urls and int(result.get("count") or 0) == 0:
        no_items_error = "No products were scraped from the selected category targets."

    final_error_text = workflow_error or no_items_error
    if final_error_text and not result.get("history_public_id") and result_count > 0:
        partial_history_id, partial_count, partial_summary = save_automation_partial_history(
            run_id,
            job,
            target_urls,
            previous_history=previous_history,
            error_text=final_error_text,
        )
        if partial_history_id:
            result["history_public_id"] = partial_history_id
            result_count = partial_count
            summary = partial_summary

    db_manager.complete_automation_run(
        run_id,
        status="failed" if final_error_text else "completed",
        current_history_id=result.get("history_public_id") or "",
        previous_history_id=(result.get("comparison") or {}).get("previous_history_id") or previous_history_id,
        target_urls=target_urls,
        items_count=result_count,
        summary=summary,
        error_text=final_error_text,
    )
    db_manager.close_connection()
    return 0 if not final_error_text else 2


def _truthy_env(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _truthy_value(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume an existing automation run without creating a new run row.")
    parser.add_argument("run_id", type=int)
    args = parser.parse_args()
    with app.app_context():
        return resume_run(args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
