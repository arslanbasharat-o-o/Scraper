"""Tests for system readiness, Chrome detection, proxy validation, and /readyz."""

import os
import pytest
from scrapers.system_check import check_chrome, check_proxy, check_environment, mask_proxy_url, run_preflight_check
from app import app


def test_mask_proxy_url():
    # Empty
    assert mask_proxy_url("") == ""
    assert mask_proxy_url(None) == ""

    # With credentials
    masked = mask_proxy_url("http://john:secretpass@gw.dataimpulse.com:823")
    assert "secretpass" not in masked
    assert "john:*****@gw.dataimpulse.com:823" in masked

    # Without credentials
    masked_no_auth = mask_proxy_url("http://127.0.0.1:8080")
    assert masked_no_auth == "http://127.0.0.1:8080"


def test_check_proxy_disabled(monkeypatch):
    monkeypatch.delenv("SCRAPER_PROXY_URL", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)

    status = check_proxy()
    assert status["configured"] is False
    assert status["status"] == "disabled"


def test_check_proxy_configured(monkeypatch):
    monkeypatch.setenv("SCRAPER_PROXY_URL", "http://myuser:secret123@p.webshare.io:80")

    status = check_proxy()
    assert status["configured"] is True
    assert status["status"] == "configured"
    assert status["host"] == "p.webshare.io"
    assert status["port"] == 80
    assert "secret123" not in status["masked_url"]


def test_check_chrome_missing(monkeypatch):
    monkeypatch.setattr("scrapers.system_check.resolve_chrome_executable", lambda: None)
    status = check_chrome()
    assert status["ok"] is False
    assert status["path"] is None
    assert "not found" in status["error"]


def test_check_chrome_snap_rejected(monkeypatch):
    monkeypatch.setattr("scrapers.system_check.resolve_chrome_executable", lambda: "/snap/bin/chromium")
    monkeypatch.setattr("scrapers.system_check.is_snap_chromium", lambda _p: True)

    status = check_chrome()
    assert status["ok"] is False
    assert status["is_snap"] is True
    assert "Snap package" in status["error"]


def test_is_snap_chromium_helper():
    from scrapers.botasaurus_wrapper import is_snap_chromium
    assert is_snap_chromium("/snap/bin/chromium") is True
    assert is_snap_chromium("/snap/chromium/current/usr/lib/chromium-browser/chrome") is True
    assert is_snap_chromium("/usr/bin/google-chrome") is False
    assert is_snap_chromium("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome") is False


def test_check_chrome_snap_version_fallback(monkeypatch):
    import subprocess
    monkeypatch.setattr("scrapers.system_check.resolve_chrome_executable", lambda: "/usr/bin/chromium")
    monkeypatch.setattr("scrapers.system_check.is_snap_chromium", lambda _p: False)
    
    class FakeProc:
        returncode = 0
        stdout = "Chromium 153.0.8010.36 snap"
        stderr = ""
        
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: FakeProc())

    status = check_chrome()
    assert status["ok"] is False
    assert status["is_snap"] is True
    assert "Snap package" in status["error"]


def test_check_environment_warnings(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "dev-insecure-change-me")
    monkeypatch.setenv("SCRAPER_BOTASAURUS_BYPASS_CLOUDFLARE", "1")
    monkeypatch.setenv("SCRAPER_DETAIL_BROWSER_BATCH", "1")

    status = check_environment()
    warnings = " ".join(status["warnings"])
    assert "SECRET_KEY" in warnings
    assert "SCRAPER_BOTASAURUS_BYPASS_CLOUDFLARE" in warnings
    assert "SCRAPER_DETAIL_BROWSER_BATCH" in warnings


def _get_app():
    import sys
    import importlib
    return sys.modules.get("app") or importlib.import_module("app")


def test_readyz_endpoint():
    app_module = _get_app()
    client = app_module.app.test_client()
    resp = client.get("/readyz")
    assert resp.status_code in {200, 503}
    data = resp.get_json()
    assert "status" in data
    assert "database" in data
    assert "browser" in data
    assert "proxy" in data
    assert "environment" in data


def test_readyz_rejects_snap_chromium(monkeypatch):
    app_module = _get_app()
    client = app_module.app.test_client()
    fake_chrome = {
        "ok": False,
        "is_snap": True,
        "error": "Snap blocked",
        "version": None,
        "path": "/snap/bin/chromium",
    }
    monkeypatch.setattr(app_module, "check_chrome", lambda: fake_chrome)
    resp = client.get("/readyz")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["status"] == "not_ready"
    assert data["browser"]["is_snap"] is True
