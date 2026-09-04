"""Single import point for the Botasaurus browser runtime.

The production server uses Snap Chromium. Snap confinement can prevent Chrome
from starting when Botasaurus places ``--user-data-dir`` under the project tree,
so browser callers should use the helpers in this module for executable,
argument, profile, and cleanup handling.
"""

from __future__ import annotations

import logging
import os
import signal
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from botasaurus.browser import Driver, browser as _botasaurus_browser


LOGGER = logging.getLogger(__name__)


def resolve_chrome_executable() -> str | None:
    """Return the Chrome/Chromium executable Botasaurus should launch."""
    configured_candidates = [
        os.getenv("CHROME_BIN"),
        os.getenv("CHROMIUM_BIN"),
        os.getenv("GOOGLE_CHROME_BIN"),
    ]
    for candidate in configured_candidates:
        path = str(candidate or "").strip()
        if not path:
            continue
        expanded = os.path.expandvars(os.path.expanduser(path))
        if Path(expanded).is_file():
            return expanded
        resolved = shutil.which(expanded)
        if resolved:
            return resolved
        LOGGER.warning("[botasaurus] Configured Chrome executable was not found: %s", path)

    discovery_candidates = [
        "google-chrome-stable",
        "google-chrome",
        "chromium",
        "chromium-browser",
        "/usr/bin/chromium",
        "/usr/bin/google-chrome",
        "/snap/bin/chromium",
    ]
    for candidate in discovery_candidates:
        path = str(candidate or "").strip()
        expanded = os.path.expandvars(os.path.expanduser(path))
        if Path(expanded).is_file():
            return expanded
        resolved = shutil.which(expanded)
        if resolved:
            return resolved
    return None


def is_snap_chromium(executable: str | None = None) -> bool:
    raw_path = (
        executable
        or os.getenv("CHROME_BIN")
        or os.getenv("CHROMIUM_BIN")
        or os.getenv("GOOGLE_CHROME_BIN")
        or resolve_chrome_executable()
        or ""
    )
    try:
        raw_path = str(Path(raw_path).resolve(strict=False))
    except (OSError, RuntimeError):
        pass
    path = raw_path.replace("\\", "/").lower()
    return "/snap/bin/chromium" in path or path.endswith("/snap/bin/chromium")


def resolve_chrome_profile_root(default_root: str | Path) -> Path:
    """Return a profile root usable by the configured Chrome executable."""
    configured = str(os.getenv("SCRAPER_CHROME_PROFILE_ROOT") or "").strip()
    if configured:
        root = Path(os.path.expandvars(os.path.expanduser(configured)))
    elif is_snap_chromium():
        root = Path.home() / "snap" / "chromium" / "common" / "scraper-browser-profiles"
    else:
        root = Path(default_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_chrome_run_profile(default_root: str | Path, label: str = "scraper") -> Path:
    """Create an isolated profile so stale Chrome locks cannot break the next run."""
    root = resolve_chrome_profile_root(default_root)
    safe_label = "".join(char if char.isalnum() or char in "-_" else "-" for char in str(label or "scraper"))
    profile = root / f"{safe_label}-{os.getpid()}-{uuid.uuid4().hex[:10]}"
    profile.mkdir(parents=True, exist_ok=False)
    return profile


def remove_chrome_run_profile(profile: str | Path, logger: logging.Logger | None = None) -> None:
    """Remove only the isolated profile created for one scraper run."""
    path = Path(profile)
    active_logger = logger or LOGGER
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        active_logger.warning("[botasaurus] Could not remove temporary Chrome profile %s: %s", path, exc)


def chrome_launch_arguments() -> list[str]:
    """Arguments required for reliable headless server Chromium startup."""
    return [
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]


def _merge_arguments(existing: list[str] | None) -> list[str]:
    merged: list[str] = []
    for arg in [*(existing or []), *chrome_launch_arguments()]:
        if arg and arg not in merged:
            merged.append(arg)
    return merged


def browser(*args: Any, **kwargs: Any) -> Callable:
    """Botasaurus browser decorator with production-safe Chrome defaults."""
    executable = resolve_chrome_executable()
    if executable and not kwargs.get("chrome_executable_path"):
        kwargs["chrome_executable_path"] = executable

    add_arguments = kwargs.get("add_arguments")
    if callable(add_arguments):
        def _add_arguments(data: Any, original: Callable = add_arguments) -> list[str]:
            return _merge_arguments(original(data))

        kwargs["add_arguments"] = _add_arguments
    else:
        kwargs["add_arguments"] = _merge_arguments(add_arguments)

    LOGGER.info(
        "[botasaurus] Chrome executable=%s arguments=%s",
        kwargs.get("chrome_executable_path") or "Botasaurus default discovery",
        " ".join(kwargs.get("add_arguments") or []),
    )
    return _botasaurus_browser(*args, **kwargs)


def _driver_browser_pid(driver: Driver) -> int | None:
    browser_obj = getattr(driver, "_browser", None)
    process = getattr(browser_obj, "_process", None)
    pid = getattr(process, "pid", None) or getattr(getattr(driver, "_browser", None), "_process_pid", None)
    try:
        return int(pid) if pid else None
    except (TypeError, ValueError):
        return None


def _direct_child_pids(pid: int | None) -> list[int]:
    if not pid or os.name != "posix":
        return []
    try:
        completed = subprocess.run(
            ["pgrep", "-P", str(pid)],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return []
    children: list[int] = []
    for line in completed.stdout.splitlines():
        try:
            children.append(int(line.strip()))
        except ValueError:
            continue
    return children


def _child_pids(pid: int | None) -> list[int]:
    pending = _direct_child_pids(pid)
    children: list[int] = []
    while pending:
        child = pending.pop(0)
        if child in children:
            continue
        children.append(child)
        pending.extend(_direct_child_pids(child))
    return children


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _terminate_tracked_pids(pids: list[int], logger: logging.Logger) -> None:
    live_pids = [pid for pid in dict.fromkeys(pids) if pid and _pid_is_alive(pid)]
    if not live_pids:
        return
    logger.warning("[botasaurus] Fallback cleanup terminating tracked Chrome PIDs: %s", live_pids)
    for pid in live_pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception as exc:
            logger.warning("[botasaurus] Could not terminate Chrome PID %s: %s", pid, exc)
    time.sleep(0.5)
    for pid in live_pids:
        if not _pid_is_alive(pid):
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception as exc:
            logger.warning("[botasaurus] Could not kill Chrome PID %s: %s", pid, exc)


def close_botasaurus_driver(driver: Driver, logger: logging.Logger | None = None) -> None:
    """Close a Botasaurus driver, logging but not masking scraper failures."""
    if driver is None or not hasattr(driver, "close"):
        return
    active_logger = logger or LOGGER
    pid = _driver_browser_pid(driver)
    tracked_pids = [pid] + _child_pids(pid)
    try:
        active_logger.info("[botasaurus] Closing browser created for scraper task%s", f" PID {pid}" if pid else "")
        driver.close()
    except Exception as exc:
        active_logger.warning("[botasaurus] Browser cleanup raised: %s", exc)
    finally:
        if os.name == "posix":
            _terminate_tracked_pids([pid for pid in tracked_pids if pid], active_logger)


__all__ = [
    "Driver",
    "browser",
    "chrome_launch_arguments",
    "close_botasaurus_driver",
    "create_chrome_run_profile",
    "is_snap_chromium",
    "resolve_chrome_executable",
    "resolve_chrome_profile_root",
    "remove_chrome_run_profile",
]
