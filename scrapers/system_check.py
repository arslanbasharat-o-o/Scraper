"""Pre-flight system, browser, proxy, and environment readiness checks.

Ensures that before scraping or server launch, Google Chrome, proxy configurations,
and environment parameters are verified and operational.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from .botasaurus_wrapper import is_snap_chromium, resolve_chrome_executable

LOGGER = logging.getLogger(__name__)


def mask_proxy_url(proxy_url: str | None) -> str:
    """Return a sanitized proxy URL masking user/pass credentials."""
    if not proxy_url:
        return ""
    try:
        parsed = urlparse(proxy_url.strip())
        if not parsed.scheme or not parsed.netloc:
            return proxy_url[:10] + "..."
        auth = ""
        if parsed.username:
            auth = f"{parsed.username}:*****@"
        host_port = parsed.hostname or ""
        if parsed.port:
            host_port += f":{parsed.port}"
        return f"{parsed.scheme}://{auth}{host_port}"
    except Exception:
        return "configured (credentials hidden)"


def check_chrome() -> Dict[str, Any]:
    """Inspect Google Chrome installation, version, and snap status."""
    path = resolve_chrome_executable()
    if not path:
        return {
            "ok": False,
            "path": None,
            "version": None,
            "is_snap": False,
            "error": "Google Chrome / Chromium executable not found on system.",
            "recommendation": (
                "Install official Google Chrome: run 'bash scripts/setup_server.sh' "
                "or download from https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
            ),
        }

    is_snap = is_snap_chromium(path)
    version = None
    exec_error = None

    try:
        proc = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0:
            version = proc.stdout.strip() or proc.stderr.strip()
        else:
            exec_error = proc.stderr.strip() or f"Process exited with {proc.returncode}"
    except Exception as exc:
        exec_error = str(exc)

    if not is_snap and version and "snap" in version.lower():
        is_snap = True

    if is_snap:
        return {
            "ok": False,
            "path": path,
            "version": version or "Unknown",
            "is_snap": True,
            "error": (
                f"Chrome at {path} is an Ubuntu Snap package. "
                "Ubuntu Snap sandboxing (AppArmor) blocks DevTools remote-debugging sockets."
            ),
            "recommendation": (
                "Install the official Google Chrome .deb package (which supports DevTools sockets): "
                "run 'bash scripts/setup_server.sh'"
            ),
        }

    if exec_error and not version:
        return {
            "ok": False,
            "path": path,
            "version": None,
            "is_snap": False,
            "error": f"Failed to execute Chrome at {path}: {exec_error}",
            "recommendation": "Verify executable permissions and required OS shared libraries.",
        }

    return {
        "ok": True,
        "path": path,
        "version": version,
        "is_snap": False,
        "error": None,
        "recommendation": None,
    }


def check_proxy() -> Dict[str, Any]:
    """Inspect proxy environment configuration."""
    raw_proxy = (
        os.getenv("SCRAPER_PROXY_URL")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("HTTP_PROXY")
        or os.getenv("https_proxy")
        or os.getenv("http_proxy")
        or ""
    ).strip()

    if not raw_proxy:
        return {
            "configured": False,
            "status": "disabled",
            "masked_url": None,
            "scheme": None,
            "host": None,
            "port": None,
            "note": "Direct connection (no proxy). To bypass Cloudflare on datacenter VPS, set SCRAPER_PROXY_URL.",
        }

    try:
        parsed = urlparse(raw_proxy)
        if not parsed.scheme or not parsed.hostname:
            return {
                "configured": False,
                "status": "malformed",
                "masked_url": raw_proxy[:15],
                "error": "Proxy URL must include scheme and host, e.g. http://user:pass@host:port",
            }
        return {
            "configured": True,
            "status": "configured",
            "masked_url": mask_proxy_url(raw_proxy),
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
            "error": None,
        }
    except Exception as exc:
        return {
            "configured": False,
            "status": "malformed",
            "masked_url": None,
            "error": f"Invalid proxy format: {exc}",
        }


def check_environment() -> Dict[str, Any]:
    """Inspect critical environment variables for production readiness."""
    warnings = []
    errors = []

    secret_key = os.getenv("SECRET_KEY", "").strip()
    if not secret_key or secret_key in {"dev-insecure-change-me", "dev-insecure-secret-key-change-me"}:
        warnings.append("SECRET_KEY is empty or using a default insecure development value.")

    profile = str(os.getenv("SCRAPER_WORKER_PROFILE") or "").strip().lower()
    botasaurus_turnstile = str(os.getenv("SCRAPER_BOTASAURUS_BYPASS_CLOUDFLARE") or "0").strip()
    if botasaurus_turnstile in {"1", "true", "yes"}:
        warnings.append(
            "SCRAPER_BOTASAURUS_BYPASS_CLOUDFLARE=1 can loop indefinitely on headless Linux. "
            "Set to 0 to prevent Turnstile hangs."
        )

    detail_batch = str(os.getenv("SCRAPER_DETAIL_BROWSER_BATCH") or "0").strip()
    if detail_batch in {"1", "true", "yes"}:
        warnings.append(
            "SCRAPER_DETAIL_BROWSER_BATCH=1 forces product detail scans into headless Chrome. "
            "Set to 0 to prioritize fast curl_cffi Safari HTTP."
        )

    return {
        "profile": profile or "default",
        "warnings": warnings,
        "errors": errors,
    }


def run_preflight_check(fail_fast: bool = False) -> Dict[str, Any]:
    """Execute complete readiness check and print colorized diagnostics."""
    chrome_status = check_chrome()
    proxy_status = check_proxy()
    env_status = check_environment()

    overall_ok = chrome_status["ok"] and not env_status["errors"]

    print("=" * 65)
    print("  SCRAPER PRODUCTION READINESS & PRE-FLIGHT CHECK")
    print("=" * 65)

    # 1. Chrome
    if chrome_status["ok"]:
        print(f"  [PASS] Google Chrome: {chrome_status['version']}")
        print(f"         Binary Path:   {chrome_status['path']}")
    elif chrome_status["is_snap"]:
        print(f"  [FAIL] Chrome Error:   {chrome_status['error']}")
        print(f"         Recommendation: {chrome_status['recommendation']}")
    else:
        print(f"  [WARN] Chrome:         {chrome_status['error']}")
        if chrome_status["recommendation"]:
            print(f"         Recommendation: {chrome_status['recommendation']}")

    # 2. Proxy
    if proxy_status["configured"]:
        print(f"  [PASS] Proxy Status:   Active ({proxy_status['masked_url']})")
    else:
        note = proxy_status.get("note") or proxy_status.get("error")
        print(f"  [INFO] Proxy Status:   {proxy_status['status']} - {note}")

    # 3. Environment
    print(f"  [INFO] Worker Profile: {env_status['profile']}")
    for warning in env_status["warnings"]:
        print(f"  [WARN] Config Warning: {warning}")
    for error in env_status["errors"]:
        print(f"  [FAIL] Config Error:   {error}")

    print("=" * 65)
    if overall_ok:
        print("  ✓ SYSTEM IS READY FOR SCRAPING JOBS")
    else:
        print("  ⚠ SYSTEM HAS ISSUES REQUIRING ATTENTION")
    print("=" * 65)

    if fail_fast and not overall_ok:
        raise SystemExit(1)

    return {
        "overall_ok": overall_ok,
        "chrome": chrome_status,
        "proxy": proxy_status,
        "env": env_status,
    }


if __name__ == "__main__":
    run_preflight_check(fail_fast=False)
