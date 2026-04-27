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


def test_scrape_requires_at_least_one_url(tmp_path, monkeypatch):
    app_module = _fresh_app(tmp_path, monkeypatch)

    with app_module.app.test_client() as client:
        response = client.post("/api/scrape", json={})

    payload = response.get_json()

    assert response.status_code == 400
    assert payload["error"] == "At least one URL is required."
    assert payload["history_saved"] is False
    assert payload["count"] == 0
    assert app_module.db_manager.get_history_list(limit=10) == []
