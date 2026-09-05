import importlib
import sys
from datetime import datetime, timedelta


def _fresh_database_module(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASES_DIR", str(tmp_path / "site_dbs"))
    monkeypatch.delenv("DATABASE_PATH", raising=False)

    sys.modules.pop("database", None)
    return importlib.import_module("database")


def _base_job_payload():
    return {
        "name": "Schedule Test",
        "scraper_key": "xcell",
        "category_query": "iphone",
        "root_url": "https://xcellparts.com/",
        "interval_minutes": 1440,
        "enabled": True,
        "auto_discover": True,
        "crawl_pagination": True,
        "max_pages": 10,
        "delay_ms": 50,
        "retries": 1,
        "verify_ssl": True,
        "use_parallel": True,
        "enrich_details": False,
        "drop_pct": 10,
        "rules": {},
    }


def _sample_targets():
    return [{
        "label": "iPhone Screens",
        "group_label": "iPhone",
        "url": "https://xcellparts.com/collections/iphone-screens",
        "active": True,
    }]


def test_editing_interval_recalculates_next_run(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=[])
    original_next_run = datetime.fromisoformat(created["next_run_at"])

    updated_payload = {
        **_base_job_payload(),
        "id": created["id"],
        "interval_minutes": 2880,
    }
    updated = manager.save_automation_job(updated_payload, targets=[])
    updated_next_run = datetime.fromisoformat(updated["next_run_at"])

    assert updated_next_run > original_next_run + timedelta(hours=23)


def test_editing_non_schedule_fields_keeps_next_run(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=[])
    original_next_run = created["next_run_at"]

    updated = manager.save_automation_job({
        **_base_job_payload(),
        "id": created["id"],
        "name": "Renamed Job",
    }, targets=[])

    assert updated["next_run_at"] == original_next_run


def test_editing_scope_without_new_targets_clears_stale_targets(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=_sample_targets())
    assert created["target_count"] == 1
    assert created["last_discovery_at"] is not None

    updated = manager.save_automation_job({
        **_base_job_payload(),
        "id": created["id"],
        "category_query": "ipad",
    })

    assert updated["target_count"] == 0
    assert updated["targets"] == []
    assert updated["last_discovery_at"] is None


def test_editing_same_scope_without_targets_keeps_existing_targets(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=_sample_targets())
    original_last_discovery = created["last_discovery_at"]

    updated = manager.save_automation_job({
        **_base_job_payload(),
        "id": created["id"],
        "name": "Renamed Job",
    })

    assert updated["target_count"] == 1
    assert [target["url"] for target in updated["targets"]] == [target["url"] for target in _sample_targets()]
    assert updated["last_discovery_at"] == original_last_discovery


def test_manual_run_does_not_skip_the_next_scheduled_window(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=_sample_targets())
    original_next_run = created["next_run_at"]

    run = manager.create_automation_run(created["id"], trigger_type="manual", target_urls=[_sample_targets()[0]["url"]])
    assert run is not None

    completed = manager.complete_automation_run(
        run["id"],
        status="completed",
        current_history_id="xcell:history-1",
        target_urls=[_sample_targets()[0]["url"]],
        items_count=12,
        summary={"target_count": 1, "current_items": 12},
        error_text="",
    )

    assert completed is not None
    refreshed = manager.get_automation_job(created["id"], include_targets=True)
    assert refreshed is not None
    assert refreshed["next_run_at"] == original_next_run


def test_automation_run_records_previous_history_at_start(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=_sample_targets())
    run = manager.create_automation_run(
        created["id"],
        trigger_type="manual",
        target_urls=[_sample_targets()[0]["url"]],
        previous_history_id="xcell:previous-history",
    )

    assert run is not None
    assert run["previous_history_id"] == "xcell:previous-history"


def test_create_automation_run_blocks_duplicate_active_run(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=_sample_targets())
    first_run = manager.create_automation_run(
        created["id"],
        trigger_type="manual",
        target_urls=[_sample_targets()[0]["url"]],
    )
    duplicate_run = manager.create_automation_run(
        created["id"],
        trigger_type="manual",
        target_urls=[_sample_targets()[0]["url"]],
    )
    active_run = manager.get_active_automation_run_for_job(created["id"])

    assert first_run is not None
    assert duplicate_run is None
    assert active_run["id"] == first_run["id"]


def test_recover_running_run_preserves_jobs_last_history_id(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=_sample_targets())
    run = manager.create_automation_run(
        created["id"],
        trigger_type="manual",
        target_urls=[_sample_targets()[0]["url"]],
    )
    manager.complete_automation_run(
        run["id"],
        status="completed",
        current_history_id="xcell:previous-history",
        target_urls=[_sample_targets()[0]["url"]],
        items_count=12,
        summary={"target_count": 1, "current_items": 12},
    )
    interrupted = manager.create_automation_run(
        created["id"],
        trigger_type="manual",
        target_urls=[_sample_targets()[0]["url"]],
    )

    assert manager.recover_running_automation_runs() == 1

    recovered = manager.get_automation_run(interrupted["id"])
    assert recovered["status"] == "interrupted"
    assert recovered["previous_history_id"] == "xcell:previous-history"
    assert recovered["summary"]["resume_available"] is True


def test_restore_interrupted_run_for_surviving_worker(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=_sample_targets())
    run = manager.create_automation_run(
        created["id"],
        trigger_type="manual",
        target_urls=[_sample_targets()[0]["url"]],
    )
    manager.update_automation_run_progress(
        run["id"],
        items_count=42,
        summary={"current_items": 42, "completed_targets": 3},
    )
    manager.recover_running_automation_runs()

    restored = manager.restore_automation_run_for_active_worker(run["id"])
    assert restored["status"] == "running"
    assert restored["completed_at"] is None
    assert restored["error_text"] == ""
    assert restored["summary"]["current_items"] == 42
    assert restored["summary"]["worker_reconciled"] is True


def test_pause_automation_run_preserves_progress_for_resume(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=_sample_targets())
    run = manager.create_automation_run(
        created["id"],
        trigger_type="manual",
        target_urls=[_sample_targets()[0]["url"]],
        previous_history_id="xcell:previous-history",
    )
    manager.update_automation_run_progress(
        run["id"],
        items_count=42,
        summary={
            "target_count": 10,
            "total_targets": 10,
            "completed_targets": 4,
            "current_items": 42,
        },
    )

    paused = manager.pause_automation_run(run["id"], reason="Paused for test.")

    assert paused is not None
    assert paused["status"] == "paused"
    assert paused["items_count"] == 42
    assert paused["summary"]["completed_targets"] == 4
    assert paused["summary"]["resume_available"] is True


def test_automation_run_items_are_persisted_for_crash_recovery(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=_sample_targets())
    run = manager.create_automation_run(
        created["id"],
        trigger_type="manual",
        target_urls=[_sample_targets()[0]["url"]],
    )

    saved = manager.append_automation_run_items(run["id"], [
        {"title": "Screen A", "url": "https://example.test/a"},
        {"title": "Screen B", "url": "https://example.test/b"},
    ])
    manager.update_automation_run_progress(
        run["id"],
        items_count=2,
        summary={"current_items": 2, "completed_targets": 1, "total_targets": 1},
    )

    assert saved == 2
    assert [item["title"] for item in manager.get_automation_run_items(run["id"])] == ["Screen A", "Screen B"]
    assert [item["title"] for item in manager.get_automation_run_items(run["id"], limit=1)] == ["Screen A"]


def test_parallel_resume_tracks_exact_targets_and_overlays_detail_checkpoint(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))
    targets = [
        {**_sample_targets()[0], "url": "https://xcellparts.com/category/a"},
        {**_sample_targets()[0], "url": "https://xcellparts.com/category/b"},
    ]
    created = manager.save_automation_job(_base_job_payload(), targets=targets)
    run = manager.create_automation_run(created["id"], target_urls=[target["url"] for target in targets])
    manager.append_automation_run_items(run["id"], [{
        "title": "Screen B",
        "url": "https://xcellparts.com/product/b",
        "sku": "",
        "extra": {"target_url": targets[1]["url"], "target_label": "Category B"},
    }])

    manager.mark_automation_run_target_completed(run["id"], targets[1]["url"])
    manager.save_automation_run_product_detail(run["id"], {
        "title": "Screen B",
        "url": "https://xcellparts.com/product/b",
        "sku": "SKU-B",
        "extra": {"sku": "SKU-B"},
    })

    assert manager.get_automation_run_completed_target_urls(run["id"]) == [targets[1]["url"]]
    restored = manager.get_automation_run_items(run["id"])[0]
    assert restored["sku"] == "SKU-B"
    assert restored["extra"]["target_label"] == "Category B"


def test_completed_phase2_continuation_merges_without_false_comparison_run(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))
    target_url = "https://xcellparts.com/category/a"
    job = manager.save_automation_job(_base_job_payload(), targets=[{
        "label": "Category A",
        "url": target_url,
        "active": True,
    }])

    assert manager.save_fetch_history("1000", [target_url], [{
        "title": "Screen A",
        "url": "https://xcellparts.com/product/a",
        "site": "xcellparts.com",
        "sku": "",
        "price_value": 10.0,
        "price_text": "$10.00",
        "source": "listing",
    }], {})
    assert manager.save_fetch_history("2000", [target_url], [{
        "title": "Screen A",
        "url": "https://xcellparts.com/product/a",
        "site": "xcellparts.com",
        "sku": "SKU-A",
        "price_value": 10.0,
        "price_text": "$10.00",
        "source": "listing",
    }], {"_phase2_backfill": True})

    source = manager.create_automation_run(job["id"], target_urls=[target_url])
    manager.complete_automation_run(
        source["id"], status="completed", current_history_id="1000",
        target_urls=[target_url], items_count=1, summary={"changed": 0},
    )
    continuation = manager.create_automation_run(
        job["id"], trigger_type="phase2_sku_backfill",
        target_urls=[target_url], previous_history_id="1000",
    )
    manager.complete_automation_run(
        continuation["id"], status="completed", current_history_id="2000",
        previous_history_id="1000", target_urls=[target_url], items_count=1,
        summary={"phase": 3, "sku_found": 1, "source_run_id": source["id"]},
    )

    merged = manager.merge_automation_run(source["id"], continuation["id"])

    assert merged["id"] == source["id"]
    assert merged["current_history_id"] == "2000"
    assert merged["previous_history_id"] == ""
    assert manager.get_automation_run(continuation["id"]) is None


def test_resume_claim_is_atomic_and_preserves_checkpoint(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=_sample_targets())
    run = manager.create_automation_run(
        created["id"],
        trigger_type="manual",
        target_urls=[_sample_targets()[0]["url"]],
    )
    manager.update_automation_run_progress(
        run["id"],
        items_count=42,
        summary={
            "completed_targets": 4,
            "current_items": 42,
            "preview_items": [{"title": "Saved Product", "url": "https://example.test/product"}],
        },
    )
    manager.pause_automation_run(run["id"], reason="Paused for test.")

    claimed = manager.claim_automation_run_resume(run["id"])
    duplicate_claim = manager.claim_automation_run_resume(run["id"])

    assert claimed is not None
    assert claimed["status"] == "resuming"
    assert claimed["items_count"] == 42
    assert claimed["summary"]["completed_targets"] == 4
    assert claimed["summary"]["preview_items"][0]["title"] == "Saved Product"
    assert duplicate_claim is None


def test_failed_resume_launch_returns_run_to_resumable_state(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    created = manager.save_automation_job(_base_job_payload(), targets=_sample_targets())
    run = manager.create_automation_run(
        created["id"],
        trigger_type="manual",
        target_urls=[_sample_targets()[0]["url"]],
    )
    manager.pause_automation_run(run["id"], reason="Paused for test.")
    assert manager.claim_automation_run_resume(run["id"])["status"] == "resuming"

    failed = manager.fail_automation_run_resume_launch(run["id"], "Process launch failed.")

    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["error_text"] == "Process launch failed."
    assert failed["summary"]["resume_available"] is True


def test_list_automation_runs_can_filter_by_scraper_key(tmp_path, monkeypatch):
    database = _fresh_database_module(tmp_path, monkeypatch)
    manager = database.DatabaseManager(db_path=str(tmp_path / "automation.db"))

    xcell_job = manager.save_automation_job(_base_job_payload(), targets=_sample_targets())
    txparts_payload = {
        **_base_job_payload(),
        "name": "TXParts Job",
        "scraper_key": "txparts",
        "root_url": "https://txparts.com/",
    }
    txparts_job = manager.save_automation_job(txparts_payload, targets=[{
        "label": "iPhone 15",
        "url": "https://txparts.com/shop/iphone-15",
        "active": True,
    }])

    manager.create_automation_run(xcell_job["id"], trigger_type="manual", target_urls=[_sample_targets()[0]["url"]])
    txparts_run = manager.create_automation_run(txparts_job["id"], trigger_type="manual", target_urls=["https://txparts.com/shop/iphone-15"])

    runs = manager.list_automation_runs(scraper_key="txparts", limit=10)

    assert [run["id"] for run in runs] == [txparts_run["id"]]
    assert runs[0]["scraper_key"] == "txparts"
