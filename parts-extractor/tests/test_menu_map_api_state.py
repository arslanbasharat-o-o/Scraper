import json

import app as app_module


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
    assert not xcell_root.exists()
    assert parts_root.exists()


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
