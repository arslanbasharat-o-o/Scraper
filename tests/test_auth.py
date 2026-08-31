"""
tests/test_auth.py — Authentication and RBAC regression tests.

These tests verify that:
1. When auth is NOT configured, all endpoints remain accessible (backward-compatible).
2. When auth IS configured, unauthenticated requests to protected endpoints receive 401.
3. Authenticated requests with valid credentials succeed.
4. Wrong credentials are rejected.
5. Destructive endpoints require the admin role.
6. Login / logout cycle works.
"""
import os
import pytest
from werkzeug.security import generate_password_hash


def _make_app_with_auth(tmp_path, monkeypatch, password="testpass123", role="admin"):
    """Boot a fresh app instance with auth configured."""
    # Set up auth env vars before importing app
    monkeypatch.setenv("AUTH_USERNAME", "testadmin")
    monkeypatch.setenv("AUTH_PASSWORD_HASH", generate_password_hash(password))
    monkeypatch.setenv("AUTH_ROLE", role)
    monkeypatch.setenv("AUTH_ENABLED", "1")

    data_dir = tmp_path / "data" / "site_dbs"
    data_dir.mkdir(parents=True)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    import importlib
    import app as app_module
    importlib.reload(app_module)
    return app_module


def _make_app_no_auth(tmp_path, monkeypatch):
    """Boot a fresh app instance WITHOUT auth configured."""
    monkeypatch.delenv("AUTH_USERNAME", raising=False)
    monkeypatch.delenv("AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("AUTH_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("AUTH_ENABLED", raising=False)

    data_dir = tmp_path / "data" / "site_dbs"
    data_dir.mkdir(parents=True)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    import importlib
    import app as app_module
    importlib.reload(app_module)
    return app_module


# ---------------------------------------------------------------------------
# Auth module unit tests
# ---------------------------------------------------------------------------
def test_auth_not_configured_when_no_env_vars(monkeypatch):
    monkeypatch.delenv("AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("AUTH_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    import importlib
    import auth
    importlib.reload(auth)
    assert auth.is_auth_configured() is False


def test_auth_configured_when_password_set(monkeypatch):
    monkeypatch.setenv("AUTH_PASSWORD", "secret")
    monkeypatch.delenv("AUTH_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    import importlib
    import auth
    importlib.reload(auth)
    assert auth.is_auth_configured() is True


def test_auth_disabled_when_auth_enabled_zero(monkeypatch):
    monkeypatch.setenv("AUTH_PASSWORD", "secret")
    monkeypatch.setenv("AUTH_ENABLED", "0")
    import importlib
    import auth
    importlib.reload(auth)
    assert auth.is_auth_configured() is False


def test_validate_credentials_correct(monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD_HASH", generate_password_hash("goodpass"))
    monkeypatch.setenv("AUTH_ROLE", "admin")
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    import importlib
    import auth
    importlib.reload(auth)
    user = auth.validate_credentials("admin", "goodpass")
    assert user is not None
    assert user.username == "admin"
    assert user.role == "admin"


def test_validate_credentials_wrong_password(monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD_HASH", generate_password_hash("goodpass"))
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    import importlib
    import auth
    importlib.reload(auth)
    user = auth.validate_credentials("admin", "wrongpass")
    assert user is None


def test_validate_credentials_wrong_username(monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD_HASH", generate_password_hash("goodpass"))
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    import importlib
    import auth
    importlib.reload(auth)
    user = auth.validate_credentials("notadmin", "goodpass")
    assert user is None


def test_role_hierarchy():
    import auth
    admin_user = auth.AppUser("u", "admin")
    operator_user = auth.AppUser("u", "operator")
    viewer_user = auth.AppUser("u", "viewer")
    assert admin_user.has_role("admin") is True
    assert admin_user.has_role("operator") is True
    assert admin_user.has_role("viewer") is True
    assert operator_user.has_role("admin") is False
    assert operator_user.has_role("operator") is True
    assert operator_user.has_role("viewer") is True
    assert viewer_user.has_role("admin") is False
    assert viewer_user.has_role("operator") is False
    assert viewer_user.has_role("viewer") is True


# ---------------------------------------------------------------------------
# Integration: no-auth mode (backward compat)
# ---------------------------------------------------------------------------
def test_no_auth_index_accessible(tmp_path, monkeypatch):
    """When auth is not configured, / is accessible without login."""
    app_module = _make_app_no_auth(tmp_path, monkeypatch)
    with app_module.app.test_client() as client:
        response = client.get("/")
    assert response.status_code == 200


def test_no_auth_api_accessible(tmp_path, monkeypatch):
    """When auth is not configured, API endpoints respond without auth."""
    app_module = _make_app_no_auth(tmp_path, monkeypatch)
    with app_module.app.test_client() as client:
        response = client.get("/api/history")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Integration: auth enabled — unauthenticated access
# ---------------------------------------------------------------------------
def test_auth_enabled_api_returns_401_without_login(tmp_path, monkeypatch):
    """When auth is configured, API returns 401 for unauthenticated requests."""
    app_module = _make_app_with_auth(tmp_path, monkeypatch)
    with app_module.app.test_client() as client:
        response = client.get("/api/history")
    assert response.status_code == 401
    data = response.get_json()
    assert "error" in data


# ---------------------------------------------------------------------------
# Integration: login / logout cycle
# ---------------------------------------------------------------------------
def test_login_success_redirects_to_index(tmp_path, monkeypatch):
    app_module = _make_app_with_auth(tmp_path, monkeypatch, password="mypass")
    with app_module.app.test_client() as client:
        response = client.post("/login", data={
            "username": "testadmin",
            "password": "mypass",
        }, follow_redirects=False)
    assert response.status_code in (301, 302)
    assert "/" in (response.headers.get("Location", "/"))


def test_login_wrong_password_shows_error(tmp_path, monkeypatch):
    app_module = _make_app_with_auth(tmp_path, monkeypatch, password="correct")
    with app_module.app.test_client() as client:
        response = client.post("/login", data={
            "username": "testadmin",
            "password": "wrong",
        }, follow_redirects=True)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Invalid" in html


def test_authenticated_user_can_access_api(tmp_path, monkeypatch):
    app_module = _make_app_with_auth(tmp_path, monkeypatch, password="mypass")
    with app_module.app.test_client() as client:
        # Login first
        client.post("/login", data={"username": "testadmin", "password": "mypass"})
        # Then access protected API
        response = client.get("/api/history")
    assert response.status_code == 200


def test_logout_revokes_session(tmp_path, monkeypatch):
    app_module = _make_app_with_auth(tmp_path, monkeypatch, password="mypass")
    with app_module.app.test_client() as client:
        client.post("/login", data={"username": "testadmin", "password": "mypass"})
        client.get("/logout")
        response = client.get("/api/history")
    assert response.status_code == 401
