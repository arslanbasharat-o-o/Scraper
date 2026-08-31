"""
auth.py — Authentication and Role-Based Access Control for Parts Extractor.

Architecture:
- Flask-Login manages session-based authentication (no JWT, no tokens).
- Single admin user configured via environment variables (fits single-user deployment).
- Three roles: admin, operator, viewer.
- Passwords stored as werkzeug pbkdf2:sha256 hashes.

Environment variables:
  AUTH_USERNAME         — login username (default: admin)
  AUTH_PASSWORD_HASH    — werkzeug hash (generate with: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('yourpassword'))")
  AUTH_PASSWORD         — plaintext password (DEV ONLY — prefer AUTH_PASSWORD_HASH in production)
  AUTH_ROLE             — role for the single user: admin, operator, viewer (default: admin)
  AUTH_SESSION_HOURS    — session lifetime in hours (default: 8)
  AUTH_ENABLED          — set to 0/false/no to disable auth entirely
"""

from __future__ import annotations

import os
from functools import wraps

from flask import redirect, request, url_for, jsonify
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"
ROLE_HIERARCHY = {ROLE_ADMIN: 3, ROLE_OPERATOR: 2, ROLE_VIEWER: 1}


class AppUser(UserMixin):
    def __init__(self, user_id: str, username: str | None = None, role: str | None = None):
        if role is None:
            role = username
            username = user_id
        self.id = str(user_id)
        self.username = str(username or user_id)
        self.role = role if role in ROLE_HIERARCHY else ROLE_VIEWER

    def has_role(self, required_role: str) -> bool:
        return ROLE_HIERARCHY.get(self.role, 0) >= ROLE_HIERARCHY.get(required_role, 0)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def is_auth_configured() -> bool:
    if _env("AUTH_ENABLED", "").lower() in {"0", "false", "no", "off"}:
        return False
    return bool(_env("AUTH_PASSWORD_HASH") or _env("AUTH_PASSWORD"))


def get_configured_username() -> str:
    return _env("AUTH_USERNAME", "admin") or "admin"


def get_configured_role() -> str:
    role = _env("AUTH_ROLE", ROLE_ADMIN)
    return role if role in ROLE_HIERARCHY else ROLE_ADMIN


def _get_password_hash() -> str:
    stored_hash = _env("AUTH_PASSWORD_HASH")
    if stored_hash:
        return stored_hash
    plaintext = _env("AUTH_PASSWORD")
    if plaintext:
        import logging
        logging.getLogger("auth").warning(
            "AUTH_PASSWORD is set as plaintext. Use AUTH_PASSWORD_HASH in production."
        )
        return generate_password_hash(plaintext)
    return ""


def validate_credentials(username: str, password: str):
    if not is_auth_configured():
        return None
    from database import db_manager
    db = db_manager
    normalized_username = username.strip()
    user_record = db.get_user_by_username(normalized_username)
    if user_record:
        ph = user_record['password_hash']
        if ph and check_password_hash(ph, password):
            return AppUser(user_record['id'], user_record['username'], user_record['role'])

    configured_username = get_configured_username()
    configured_hash = _get_password_hash()
    if normalized_username == configured_username and configured_hash and check_password_hash(configured_hash, password):
        return AppUser(f"env:{configured_username}", configured_username, get_configured_role())
    return None


def load_user_by_id(user_id: str):
    if not is_auth_configured():
        return None
    from database import db_manager
    db = db_manager
    user_record = db.get_user_by_id(user_id)
    if not user_record:
        configured_username = get_configured_username()
        if str(user_id) == f"env:{configured_username}" and _get_password_hash():
            return AppUser(f"env:{configured_username}", configured_username, get_configured_role())
        return None
    return AppUser(user_record['id'], user_record['username'], user_record['role'])


login_manager = LoginManager()
login_manager.login_view = "auth_login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"


def init_auth(app) -> None:
    import datetime
    login_manager.init_app(app)
    login_manager.user_loader(load_user_by_id)
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    if not app.debug and not app.testing:
        app.config.setdefault("SESSION_COOKIE_SECURE", True)
    try:
        h = max(1, int(_env("AUTH_SESSION_HOURS", "8") or "8"))
    except (TypeError, ValueError):
        h = 8
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", datetime.timedelta(hours=h))


def require_login(fn):
    """Require authentication. No-op when AUTH_ENABLED=0 or no credentials configured."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_auth_configured():
            return fn(*args, **kwargs)
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required.", "login_url": url_for("auth_login")}), 401
            return redirect(url_for("auth_login", next=request.url))
        return fn(*args, **kwargs)
    return wrapper


def require_role(role: str):
    """Require a minimum role. Implicitly enforces authentication first."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_auth_configured():
                return fn(*args, **kwargs)
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"error": "Authentication required."}), 401
                return redirect(url_for("auth_login", next=request.url))
            if not current_user.has_role(role):
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"error": f"Requires '{role}' role.", "your_role": getattr(current_user, "role", "?")}), 403
                from flask import abort
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
