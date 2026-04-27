import importlib
import sys


def _fresh_app(tmp_path, monkeypatch):
    site_dbs = tmp_path / "site_dbs"
    monkeypatch.setenv("DATABASES_DIR", str(site_dbs))
    monkeypatch.delenv("DATABASE_PATH", raising=False)

    for module_name in ("app", "database"):
        sys.modules.pop(module_name, None)

    app_module = importlib.import_module("app")
    app_module.app.config["TESTING"] = True
    app_module.ensure_automation_scheduler_started = lambda: None
    return app_module


def _sample_targets():
    return [
        {
            "label": "Main",
            "group_label": "iPhone",
            "url": "https://xcellparts.com/product-category/iphone",
            "active": True,
        },
        {
            "label": "Batteries",
            "group_label": "iPhone",
            "url": "https://xcellparts.com/product-category/iphone/batteries",
            "active": True,
        },
    ]


def _job_payload():
    return {
        "name": "Category Test",
        "scraper_key": "xcell",
        "category_query": "iphone",
        "root_url": "https://xcellparts.com/",
        "interval_minutes": 1440,
        "enabled": True,
        "auto_discover": False,
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


def test_category_manager_page_loads(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)

    with app_module.app.test_client() as client:
        response = client.get("/category-manager")

    assert response.status_code == 200
    assert b"Category Manager" in response.data


def test_category_manager_targets_api_updates_saved_targets(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)
    created = app_module.db_manager.save_automation_job(_job_payload(), targets=_sample_targets())

    with app_module.app.test_client() as client:
        response = client.post(f"/api/automation/jobs/{created['id']}/targets", json={
            "targets": [
                {
                    "label": "Main",
                    "group_label": "iPhone",
                    "url": "https://xcellparts.com/product-category/iphone",
                    "active": False,
                },
                {
                    "label": "Chargers",
                    "group_label": "Accessories",
                    "url": "https://xcellparts.com/product-category/iphone/chargers",
                    "active": True,
                },
            ]
        })

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["job"]["target_count"] == 2
    assert payload["job"]["active_target_count"] == 1
    assert payload["job"]["skipped_target_count"] == 1
    assert [target["label"] for target in payload["job"]["targets"]] == ["Main", "Chargers"]
    assert payload["job"]["targets"][0]["active"] is False
