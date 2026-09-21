import io
import json
import zipfile
from pathlib import Path
import pytest
import app as app_module


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_logs_page_renders_ok(client):
    """Test that the /logs page returns 200 with proper HTML, title, and nav links."""
    res = client.get("/logs")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Server Logs - Parts Extractor" in html
    assert "Production Server Logs" in html
    assert 'href="/automation"' in html
    assert 'href="/logs" class="nav-link active"' in html
    assert 'id="logFileSelect"' in html
    assert 'id="downloadAllLogsBtn"' in html
    assert 'id="logConsoleBody"' in html


def test_nav_links_in_all_pages(client):
    """Verify that every view contains the Server Logs link in its navigation, and Extractor is hidden from navbar."""
    for path in ["/", "/automation", "/menu-map", "/history", "/logs"]:
        res = client.get(path)
        assert res.status_code == 200
        html = res.data.decode("utf-8")
        assert 'href="/logs"' in html
        assert 'href="/extractor"' not in html


def test_extractor_accessible_via_url_only(client):
    """Verify that /extractor is live and functional via direct URL, but does not show in the navbar."""
    res = client.get("/extractor")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Parts Extractor" in html
    assert 'href="/extractor"' not in html


def test_sitemap_contains_logs_page(client):
    """Verify that sitemap.xml registers the /logs endpoint."""
    res = client.get("/sitemap.xml")
    assert res.status_code == 200
    xml_data = res.data.decode("utf-8")
    assert "/logs</loc>" in xml_data


def test_api_get_server_log_files(client):
    """Test that GET /api/logs/files returns 200 and lists available log files."""
    res = client.get("/api/logs/files")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert isinstance(data["files"], list)
    # server.log should be present
    names = [f["name"] for f in data["files"]]
    assert "server.log" in names


def test_api_tail_server_log(client):
    """Test that GET /api/logs/tail returns log lines and summary stats."""
    res = client.get("/api/logs/tail?file=server.log&lines=100")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["file"] == "server.log"
    assert isinstance(data["lines"], list)
    assert "size_formatted" in data
    assert "returned_lines" in data


def test_api_tail_filtering(client, tmp_path, monkeypatch):
    """Test level and search filtering on a simulated log file."""
    # Write a dedicated test log in APP_ROOT
    test_log = app_module.APP_ROOT / "server.log.test"
    test_content = (
        "2026-09-21 12:00:00,001 INFO [test] System initialized normally\n"
        "2026-09-21 12:00:01,002 WARNING [test] Slow connection detected on proxy\n"
        "2026-09-21 12:00:02,003 ERROR [test] Category failed HTTP 403 forbidden\n"
        "2026-09-21 12:00:03,004 INFO [test] Recovery worker started\n"
        "2026-09-21 12:00:04,005 ERROR [test] Cloudflare challenge failed\n"
    )
    test_log.write_text(test_content, encoding="utf-8")

    try:
        # Test error level filter
        res_err = client.get("/api/logs/tail?file=server.log.test&level=ERROR")
        assert res_err.status_code == 200
        data_err = res_err.get_json()
        assert data_err["returned_lines"] == 2
        assert all("ERROR" in line for line in data_err["lines"])

        # Test search filter
        res_search = client.get("/api/logs/tail?file=server.log.test&search=Cloudflare")
        assert res_search.status_code == 200
        data_search = res_search.get_json()
        assert data_search["returned_lines"] == 1
        assert "Cloudflare challenge failed" in data_search["lines"][0]

        # Test combined filter
        res_combo = client.get("/api/logs/tail?file=server.log.test&level=ERROR&search=403")
        assert res_combo.status_code == 200
        data_combo = res_combo.get_json()
        assert data_combo["returned_lines"] == 1
        assert "403 forbidden" in data_combo["lines"][0]
    finally:
        if test_log.exists():
            test_log.unlink()


def test_api_download_single_log(client):
    """Test that GET /api/logs/download returns the file as an attachment."""
    res = client.get("/api/logs/download?file=server.log")
    assert res.status_code == 200
    assert "attachment" in res.headers.get("Content-Disposition", "")
    assert "filename=server.log" in res.headers.get("Content-Disposition", "")


def test_api_download_all_logs_as_zip(client):
    """Test that GET /api/logs/download-all returns a valid zip archive with log files."""
    res = client.get("/api/logs/download-all")
    assert res.status_code == 200
    assert res.mimetype == "application/zip"
    assert "attachment" in res.headers.get("Content-Disposition", "")
    assert "server-logs-" in res.headers.get("Content-Disposition", "")

    # Validate zip integrity
    bio = io.BytesIO(res.data)
    with zipfile.ZipFile(bio, "r") as zf:
        namelist = zf.namelist()
        assert len(namelist) > 0
        assert "server.log" in namelist


def test_security_path_traversal_blocked(client):
    """Ensure path traversal attacks or attempts to download non-log files fail with 404."""
    suspicious_queries = [
        "../../etc/passwd",
        "/etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "app.py",
        ".env",
        "hostinger_server.env",
        "templates/logs.html",
        "scrapers/scraper_engine.py",
    ]

    for q in suspicious_queries:
        res_dl = client.get(f"/api/logs/download?file={q}")
        assert res_dl.status_code == 404, f"Path traversal query '{q}' was not rejected in download!"
        res_tail = client.get(f"/api/logs/tail?file={q}")
        assert res_tail.status_code == 404, f"Path traversal query '{q}' was not rejected in tail!"
