"""
tests/test_open_access.py — Verify private server open-access operation.

All endpoints must be accessible without login credentials, sessions, or redirects.
"""
from pathlib import Path
import pytest


def test_open_access_ui_routes():
    """Verify that all main UI views respond with 200 without login."""
    import app as app_module

    client = app_module.app.test_client()

    for path in ["/", "/automation", "/history", "/menu-map", "/extractor"]:
        response = client.get(path)
        assert response.status_code == 200, f"Expected 200 for {path}, got {response.status_code}"


def test_open_access_api_health():
    """Verify that the health check responds with healthy status without auth requirement."""
    import app as app_module

    client = app_module.app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("status") == "healthy"


def test_open_access_probes():
    """Verify kubernetes / container liveness and readiness probes respond 200."""
    import app as app_module

    client = app_module.app.test_client()
    assert client.get("/livez").status_code == 200
    assert client.get("/readyz").status_code == 200


def test_no_login_redirect_for_api():
    """Verify that API endpoints do not redirect to /login or return 401."""
    import app as app_module

    client = app_module.app.test_client()
    response = client.get("/api/history")
    assert response.status_code != 401
    assert response.status_code != 302
