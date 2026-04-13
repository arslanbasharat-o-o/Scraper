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
