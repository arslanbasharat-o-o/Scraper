import csv
import json

import app as app_module
from scripts.run_menu_map_scrapers import site_result_failed
from scrapers.menu_map.common import CategoryRecord, ScrapeResult, SiteConfig, export_outputs


def test_menu_map_site_reports_invalid_categories_json(tmp_path, monkeypatch):
    site_root = tmp_path / "xcellparts"
    site_root.mkdir()
    (site_root / "categories.json").write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(app_module, "get_menu_map_output_root", lambda: tmp_path)

    with app_module.app.test_request_context():
        site = app_module.read_menu_map_site("xcellparts")

    assert site["has_output"] is True
    assert site["output_valid"] is False
    assert site["output_empty"] is False
    assert site["parse_error"]


def test_menu_map_site_reports_valid_empty_output(tmp_path, monkeypatch):
    site_root = tmp_path / "xcellparts"
    site_root.mkdir()
    (site_root / "categories.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(app_module, "get_menu_map_output_root", lambda: tmp_path)

    with app_module.app.test_request_context():
        site = app_module.read_menu_map_site("xcellparts")

    assert site["output_valid"] is True
    assert site["output_empty"] is True
    assert site["parse_error"] == ""


def test_menu_map_ignores_supplier_locked_missing_urls(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "get_menu_map_output_root", lambda: tmp_path)
    cases = {
        "mobilesentrix": {"parent_name": "Pre-Owned Devices", "sub_child_name": "", "child_name": ""},
        "mobilesentrix_canada": {"parent_name": "Pre-Owned Devices", "sub_child_name": "", "child_name": ""},
        "phonelcdparts": {"parent_name": "What's", "sub_child_name": "What's", "child_name": ""},
    }
    for slug, row in cases.items():
        site_dir = tmp_path / slug
        site_dir.mkdir()
        with (site_dir / "categories.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["parent_name", "sub_child_name", "child_name", "url_missing"])
            writer.writeheader()
            writer.writerow({**row, "url_missing": "True"})
        with app_module.app.test_request_context():
            assert app_module.read_menu_map_site(slug)["missing_urls"] == 0


def test_menu_map_rejects_overlapping_active_run():
    active_job = {
        "id": "active-job",
        "status": "running",
        "sites": ["xcellparts"],
        "site_status": {},
        "events": [],
    }
    with app_module.MENU_MAP_JOBS_LOCK:
        original_jobs = dict(app_module.MENU_MAP_JOBS)
        app_module.MENU_MAP_JOBS.clear()
        app_module.MENU_MAP_JOBS[active_job["id"]] = active_job

    try:
        response = app_module.app.test_client().post(
            "/api/menu-map/run",
            json={"sites": ["xcellparts"]},
        )
        assert response.status_code == 409
        assert response.get_json()["job"]["id"] == active_job["id"]
    finally:
        with app_module.MENU_MAP_JOBS_LOCK:
            app_module.MENU_MAP_JOBS.clear()
            app_module.MENU_MAP_JOBS.update(original_jobs)


def test_menu_map_clear_output_removes_selected_site_only(tmp_path, monkeypatch):
    xcell_root = tmp_path / "xcellparts"
    parts_root = tmp_path / "parts4cells"
    xcell_root.mkdir()
    parts_root.mkdir()
    (xcell_root / "categories.json").write_text("[]", encoding="utf-8")
    (parts_root / "categories.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(app_module, "get_menu_map_output_root", lambda: tmp_path)

    response = app_module.app.test_client().post(
        "/api/menu-map/output/clear",
        json={"sites": ["xcellparts"]},
    )

    assert response.status_code == 200
    assert response.get_json()["cleared"] == ["xcellparts"]
    assert list(path.name for path in xcell_root.iterdir()) == [".menu-map-seed-disabled"]
    assert parts_root.exists()


def test_clear_and_run_disables_bundled_seed_until_live_output_is_written(tmp_path, monkeypatch):
    output_root = tmp_path / "output"
    monkeypatch.setattr(app_module, "get_menu_map_output_root", lambda: output_root)

    response = app_module.app.test_client().post(
        "/api/menu-map/output/clear",
        json={"sites": ["phonelcdparts"]},
    )

    marker = output_root / "phonelcdparts" / ".menu-map-seed-disabled"
    assert response.status_code == 200
    assert marker.exists()
    assert app_module.ensure_menu_map_seeded("phonelcdparts", marker.parent) is False
    assert not (marker.parent / "categories.json").exists()


def test_menu_map_subprocess_errors_mark_job_failed_despite_zero_exit():
    assert app_module.menu_map_subprocess_failed(0, "Errors: 1\n") is True
    assert app_module.menu_map_subprocess_failed(0, "Errors: 0\n") is False
    assert app_module.menu_map_subprocess_failed(1, "Errors: 0\n") is True


def test_menu_map_clear_output_rejects_active_site(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "get_menu_map_output_root", lambda: tmp_path)
    active_job = {
        "id": "active-job",
        "status": "running",
        "sites": ["xcellparts"],
        "site_status": {},
        "events": [],
    }
    with app_module.MENU_MAP_JOBS_LOCK:
        original_jobs = dict(app_module.MENU_MAP_JOBS)
        app_module.MENU_MAP_JOBS.clear()
        app_module.MENU_MAP_JOBS[active_job["id"]] = active_job

    try:
        response = app_module.app.test_client().post(
            "/api/menu-map/output/clear",
            json={"sites": ["xcellparts"]},
        )
        assert response.status_code == 409
        assert response.get_json()["job"]["id"] == active_job["id"]
    finally:
        with app_module.MENU_MAP_JOBS_LOCK:
            app_module.MENU_MAP_JOBS.clear()
            app_module.MENU_MAP_JOBS.update(original_jobs)


def write_menu_tree(site_root):
    tree = [
        {
            "parent_name": "Apple",
            "parent_url": "",
            "display_order": 1,
            "sub_children": [
                {
                    "sub_child_name": "iPhone",
                    "sub_child_url": "https://example.com/shop/iphone",
                    "display_order": 1,
                    "children": [
                        {
                            "child_name": "iPhone 17",
                            "child_url": "https://example.com/shop/iphone-17",
                            "display_order": 1,
                        },
                        {
                            "child_name": "iPhone 16",
                            "child_url": "https://example.com/shop/iphone-16",
                            "display_order": 2,
                        },
                    ],
                }
            ],
        }
    ]
    site_root.mkdir()
    (site_root / "categories.json").write_text(json.dumps(tree), encoding="utf-8")
    return tree


def test_menu_map_links_export_returns_csv(tmp_path, monkeypatch):
    write_menu_tree(tmp_path / "xcellparts")
    monkeypatch.setattr(app_module, "get_menu_map_output_root", lambda: tmp_path)

    response = app_module.app.test_client().post(
        "/api/menu-map/links/export",
        json={"sites": ["xcellparts"], "scope": "full", "format": "csv"},
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "link_label,url" in body
    assert "iPhone 17,https://example.com/shop/iphone-17" in body
    assert "iPhone 16,https://example.com/shop/iphone-16" in body


def test_menu_map_links_export_respects_visible_exclusions(tmp_path, monkeypatch):
    tree = write_menu_tree(tmp_path / "xcellparts")
    child_key = app_module.menu_map_child_key(
        tree[0],
        tree[0]["sub_children"][0],
        tree[0]["sub_children"][0]["children"][1],
    )
    monkeypatch.setattr(app_module, "get_menu_map_output_root", lambda: tmp_path)

    response = app_module.app.test_client().post(
        "/api/menu-map/links/export",
        json={
            "sites": ["xcellparts"],
            "scope": "visible",
            "format": "csv",
            "excluded": {"xcellparts": [child_key]},
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "iPhone 17,https://example.com/shop/iphone-17" in body
    assert "iPhone 16,https://example.com/shop/iphone-16" not in body


def test_menu_map_links_export_returns_xlsx(tmp_path, monkeypatch):
    write_menu_tree(tmp_path / "xcellparts")
    monkeypatch.setattr(app_module, "get_menu_map_output_root", lambda: tmp_path)

    response = app_module.app.test_client().post(
        "/api/menu-map/links/export",
        json={"sites": ["xcellparts"], "scope": "full", "format": "xlsx"},
    )

    assert response.status_code == 200
    assert response.get_data()[:2] == b"PK"


def test_menu_map_ensure_seeded_populates_baseline(tmp_path, monkeypatch):
    monkeypatch.setenv("FORCE_MENU_MAP_SEED", "1")
    output_dir = tmp_path / "phonelcdparts"
    assert not output_dir.exists()

    seeded = app_module.ensure_menu_map_seeded("phonelcdparts", output_dir)
    assert seeded is True
    assert (output_dir / "categories.json").exists()
    assert (output_dir / "categories.csv").exists()

    # Re-running on already seeded non-empty directory should return False (no re-copy needed)
    assert app_module.ensure_menu_map_seeded("phonelcdparts", output_dir) is False


def test_menu_map_runner_marks_seed_restore_without_error_file_as_failed(tmp_path):
    site_dir = tmp_path / "phonelcdparts"
    site_dir.mkdir()
    (site_dir / "categories.json").write_text("[]", encoding="utf-8")

    assert site_result_failed(tmp_path, "phonelcdparts", 0) is True

    (site_dir / "scraping_errors.json").write_text("[]", encoding="utf-8")
    assert site_result_failed(tmp_path, "phonelcdparts", 0) is False


def test_menu_map_restore_from_seed_output(tmp_path):
    from scrapers.menu_map.common import is_valid_nonempty_output, restore_from_seed_output
    import logging

    test_dir = tmp_path / "phonelcdparts"
    assert not is_valid_nonempty_output(test_dir / "categories.json")

    logger = logging.getLogger("test_logger")
    restored = restore_from_seed_output("phonelcdparts", test_dir, logger)
    assert restored is True
    assert is_valid_nonempty_output(test_dir / "categories.json")

    cleared_dir = tmp_path / "cleared-phonelcdparts"
    cleared_dir.mkdir()
    (cleared_dir / ".menu-map-seed-disabled").touch()
    assert restore_from_seed_output("phonelcdparts", cleared_dir, logger) is False
    assert not (cleared_dir / "categories.json").exists()


def test_empty_output_keeps_seed_suppressed_until_new_records_exist(tmp_path):
    site_dir = tmp_path / "phonelcdparts"
    site_dir.mkdir()
    marker = site_dir / ".menu-map-seed-disabled"
    marker.touch()
    config = SiteConfig(
        website="Example",
        website_url="https://example.com",
        output_slug="example",
        base_url="https://example.com",
        parent_nav_selector="",
        parent_item_selector="",
        mega_menu_selector="",
        sub_child_panel_selector="",
        sub_child_item_selector="",
        active_sub_child_selector="",
        child_panel_selector="",
        child_link_selector="",
        scroll_container_selector="",
        menu_close_selector="",
        search_selector="",
        mobile_menu_selector="",
    )

    export_outputs(config, site_dir, ScrapeResult(), headless=True, duplicates=[])
    assert marker.exists()

    record = CategoryRecord(
        website="Example",
        website_url="https://example.com",
        parent_name="Parts",
        parent_url="https://example.com/parts",
        parent_display_order=1,
        parent_open_method="click",
    )
    export_outputs(config, site_dir, ScrapeResult(records=[record]), headless=True, duplicates=[])
    assert not marker.exists()


def test_scrapling_menu_fallback_enables_cf_solver_and_extracts_menu(monkeypatch, tmp_path):
    import logging
    import sys
    from types import SimpleNamespace
    from scrapers.menu_map.common import scrapling_menu_fallback

    calls = {}
    hierarchy = [{"name": "Parts", "url": "https://example.com/parts", "order": 1, "sub_children": []}]

    class FakePage:
        def locator(self, _selector):
            return SimpleNamespace(count=lambda: 0)

        def evaluate(self, _script, *_args):
            return hierarchy

    class FakeResponse:
        def css(self, _selector):
            return SimpleNamespace(get=lambda: "Example parts")

    class FakeStealthyFetcher:
        @staticmethod
        def fetch(url, **kwargs):
            calls.update({"url": url, **kwargs})
            kwargs["page_action"](FakePage())
            return FakeResponse()

    monkeypatch.setitem(sys.modules, "scrapling.fetchers", SimpleNamespace(StealthyFetcher=FakeStealthyFetcher))
    config = SiteConfig(
        website="Example",
        website_url="https://example.com",
        output_slug="example",
        base_url="https://example.com",
        parent_nav_selector="#nav",
        parent_item_selector="#nav > li > a",
        mega_menu_selector="",
        sub_child_panel_selector="",
        sub_child_item_selector="",
        active_sub_child_selector="",
        child_panel_selector="",
        child_link_selector="",
        scroll_container_selector="",
        menu_close_selector="",
        search_selector="",
        mobile_menu_selector="",
    )

    records = scrapling_menu_fallback(config, logging.getLogger("test-scrapling-menu"), 0)

    assert calls["solve_cloudflare"] is True
    assert calls["timeout"] >= 60000
    assert calls["real_chrome"] is True
    assert [record.parent_name for record in records] == ["Parts"]


def test_scrapling_menu_fallback_accepts_explicit_last_resort_proxy(monkeypatch):
    import logging
    import sys
    from types import SimpleNamespace
    from scrapers.menu_map.common import scrapling_menu_fallback

    calls = {}
    hierarchy = [{"name": "Parts", "url": "https://example.com/parts", "order": 1, "sub_children": []}]

    class FakePage:
        def locator(self, _selector):
            return SimpleNamespace(count=lambda: 0)

        def evaluate(self, _script, *_args):
            return hierarchy

    class FakeResponse:
        def css(self, _selector):
            return SimpleNamespace(get=lambda: "Example parts")

    class FakeStealthyFetcher:
        @staticmethod
        def fetch(_url, **kwargs):
            calls.update(kwargs)
            kwargs["page_action"](FakePage())
            return FakeResponse()

    monkeypatch.setitem(sys.modules, "scrapling.fetchers", SimpleNamespace(StealthyFetcher=FakeStealthyFetcher))
    monkeypatch.delenv("SCRAPER_PROXY_URL", raising=False)
    config = SiteConfig(
        website="Example", website_url="https://example.com", output_slug="example",
        base_url="https://example.com", parent_nav_selector="#nav", parent_item_selector="#nav > li > a",
        mega_menu_selector="", sub_child_panel_selector="", sub_child_item_selector="",
        active_sub_child_selector="", child_panel_selector="", child_link_selector="",
        scroll_container_selector="", menu_close_selector="", search_selector="", mobile_menu_selector="",
    )

    scrapling_menu_fallback(config, logging.getLogger("test-scrapling-menu-proxy"), 0,
                            "http://user:pass@proxy.example:1080")

    assert calls["proxy"] == "http://user:pass@proxy.example:1080"
