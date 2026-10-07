"""Shared, bounded fetch pipeline used by every supplier scraper.

The order is deliberately conservative:

1. The supplier-specific HTTP session (usually curl_cffi or requests).
2. Scrapling's browser-shaped HTTP fetcher.
3. Scrapling's stealth browser, when installed and enabled.
4. The existing Botasaurus browser adapter as the final local fallback.

Each stage is attempted at most once after the configured HTTP attempts.  This
keeps a blocked page from multiplying into several expensive browser launches.
"""

from __future__ import annotations

import logging
import inspect
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlparse

from .browser_fetcher import (
    browser_fetch_explicitly_disabled,
    browser_fetch_requested,
    fetch_html as botasaurus_fetch_html,
    _local_browser_slot,
    should_use_browser_fetch,
)

logger = logging.getLogger(__name__)
_STEALTH_SESSIONS = threading.local()
_STEALTH_WORKERS = {}
_STEALTH_WORKERS_LOCK = threading.Lock()


@dataclass(slots=True)
class PipelineFetchResult:
    html: str
    final_url: str
    status_code: int
    transport: str
    http_attempts: int = 0


def is_cancellation_exception(exc: BaseException) -> bool:
    """Identify cancellation raised by a scraper callback or executor.

    asyncio's cancellation exception is a BaseException on some supported
    Python versions, while concurrent-futures cancellation is an Exception.
    A small name check also covers the application's cancellation type without
    importing its service layer here.
    """
    return isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)) or (
        "cancel" in type(exc).__name__.lower()
        or "cancel" in type(exc).__qualname__.lower()
        or bool(getattr(exc, "scraper_cancelled", False))
    )


def browser_fallback_enabled() -> bool:
    """Return whether a failed HTTP/Scrapling request may use a browser."""
    configured_value = os.getenv("SCRAPER_LOCAL_BROWSER_FALLBACK")
    if browser_fetch_explicitly_disabled() and configured_value is None:
        return False
    value = str(configured_value if configured_value is not None else "1").strip().lower()
    configured = value in {"1", "true", "yes", "on"}
    return configured or should_use_browser_fetch() or browser_fetch_requested()


def scrapling_enabled() -> bool:
    value = str(os.getenv("SCRAPER_SCRAPLING_ENABLED", "1")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def scrapling_cloudflare_solver_enabled() -> bool:
    value = str(os.getenv("SCRAPER_SCRAPLING_SOLVE_CLOUDFLARE", "1")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def _response_html(response) -> str:
    body = getattr(response, "body", None)
    if isinstance(body, bytes):
        encoding = getattr(response, "encoding", None) or "utf-8"
        try:
            return body.decode(encoding, errors="replace")
        except (LookupError, TypeError):
            return body.decode("utf-8", errors="replace")
    text = getattr(response, "text", None)
    if text is not None:
        return str(text)
    return ""


def _session_cookies(session) -> dict[str, str]:
    cookies = getattr(session, "cookies", None)
    if cookies is None:
        return {}
    try:
        return {str(k): str(v) for k, v in cookies.items()}
    except (AttributeError, TypeError, ValueError):
        return {}


def _session_proxy(session, fallback: Optional[str]) -> Optional[str]:
    proxies = getattr(session, "proxies", None)
    if isinstance(proxies, dict):
        proxy = proxies.get("https") or proxies.get("http")
        if proxy:
            return str(proxy)
    return fallback


def _last_resort_proxy_for_url(url: str) -> Optional[str]:
    """Enable the residential proxy only for the requested final-fallback hosts."""
    proxy = str(os.getenv("SCRAPER_LAST_RESORT_PROXY_URL") or "").strip()
    if not proxy:
        return None
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    allowed = ("mobilesentrix.com", "mobilesentrix.ca", "phonelcdparts.com")
    if any(host == domain or host.endswith(f".{domain}") for domain in allowed):
        return proxy
    return None


def _supported_kwargs(callable_, kwargs: dict) -> dict:
    """Avoid passing transport options to older Scrapling releases."""
    try:
        signature = inspect.signature(callable_)
    except (TypeError, ValueError):
        return kwargs
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return kwargs
    return {key: value for key, value in kwargs.items() if key in signature.parameters}


def _scrapling_http(url: str, timeout: int, proxy: Optional[str], session=None):
    """Use Scrapling's fast curl_cffi-backed fetcher, if available."""
    from scrapling.fetchers import Fetcher  # imported lazily and is optional

    kwargs = {
        "impersonate": "chrome",
        "stealthy_headers": True,
        "timeout": timeout,
        "retries": 1,
    }
    if proxy:
        kwargs["proxy"] = proxy
    cookies = _session_cookies(session)
    if cookies:
        kwargs["cookies"] = cookies
    verify = getattr(session, "verify", None)
    if verify is not None:
        kwargs["verify"] = verify
    response = Fetcher.get(url, **_supported_kwargs(Fetcher.get, kwargs))
    html = _response_html(response)
    status = int(getattr(response, "status", 0) or 0)
    final_url = str(getattr(response, "url", "") or url)
    return status, final_url, html, getattr(response, "headers", {}) or {}


def _stealth_fetch_on_worker(url, timeout, proxy, stop_check):
    """Keep each Playwright session on one fixed browser-slot thread."""
    from scrapling.fetchers import StealthySession  # optional reusable API
    from .botasaurus_wrapper import resolve_chrome_executable

    solve_cloudflare = scrapling_cloudflare_solver_enabled()
    kwargs = {
        "headless": True,
        "timeout": max(100, float(timeout) * 1000 - 300),
        "wait": 300,
        "load_dom": True,
        "network_idle": False,
        "solve_cloudflare": solve_cloudflare,
    }
    if proxy:
        kwargs["proxy"] = proxy
    deadline = time.monotonic() + float(timeout)
    if stop_check:
        stop_check()
    last_failure = getattr(_STEALTH_SESSIONS, 'start_failure', None)
    if last_failure and last_failure[0] == proxy and time.monotonic() < last_failure[1]:
        raise RuntimeError('Scrapling browser startup is temporarily unavailable')
    cached = getattr(_STEALTH_SESSIONS, "current", None)
    if cached is not None and cached[0] != proxy:
        cached[1].close()
        cached = _STEALTH_SESSIONS.current = None
    if cached is None:
        config = {
            "headless": True, "timeout": kwargs["timeout"],
            "retries": 1, "max_pages": 1,
            "additional_args": {"timeout": max(100, float(timeout) * 1000)},
        }
        chrome = resolve_chrome_executable()
        if chrome:
            config["executable_path"] = chrome
        if proxy:
            config["proxy"] = proxy
        warmed = StealthySession(**_supported_kwargs(StealthySession, config))
        try:
            warmed.__enter__()
        except Exception:
            _STEALTH_SESSIONS.start_failure = (proxy, time.monotonic() + 60)
            raise
        _STEALTH_SESSIONS.start_failure = None
        _STEALTH_SESSIONS.current = (proxy, warmed)
    else:
        warmed = cached[1]
    if stop_check:
        stop_check()
    fetch_kwargs = {k: v for k, v in kwargs.items() if k not in {"headless", "proxy"}}
    remaining = deadline - time.monotonic()
    if remaining <= 0.3:
        raise TimeoutError("Scrapling browser startup exhausted the fetch budget")
    fetch_kwargs["timeout"] = max(100, remaining * 1000 - 300)
    try:
        response = warmed.fetch(url, **_supported_kwargs(warmed.fetch, fetch_kwargs))
    except Exception as exc:
        if not is_cancellation_exception(exc):
            _STEALTH_SESSIONS.current = None
            try:
                warmed.close()
            except Exception:
                pass
        raise
    html = _response_html(response)
    status = int(getattr(response, "status", 0) or 0)
    final_url = str(getattr(response, "url", "") or url)
    return status, final_url, html, getattr(response, "headers", {}) or {}


def _scrapling_stealth(url: str, timeout: int, proxy: Optional[str], stop_check=None):
    # Fixed slot workers prevent a retained browser per HTTP thread (which can
    # otherwise grow to hundreds despite limiting simultaneous navigations).
    with _local_browser_slot(timeout=timeout) as slot:
        with _STEALTH_WORKERS_LOCK:
            worker = _STEALTH_WORKERS.get(slot)
            if worker is None:
                worker = _STEALTH_WORKERS[slot] = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix=f"scrapling-slot-{slot}"
                )
        return worker.submit(_stealth_fetch_on_worker, url, timeout, proxy, stop_check).result()


def _transport_response(raw):
    # Preserve compatibility with adapters returning the historical triple.
    status, final_url, html = raw[:3]
    headers = raw[3] if len(raw) > 3 else {}
    return status, final_url, html, headers


def _is_cf_challenge(status: int, headers, html: str) -> bool:
    mitigated = next((v for k, v in (headers or {}).items() if str(k).lower() == "cf-mitigated"), "")
    return str(mitigated or "").strip().lower() == "challenge" or any(
        marker in (html or "")[:30_000].lower()
        for marker in (
            "just a moment",
            "performing security verification",
            "verify you are human",
            "enable javascript and cookies to continue",
            "cf-browser-verification",
        )
    )


def _usable_response(status: int, html: str, blocked: bool) -> bool:
    return 200 <= int(status or 0) < 400 and bool(html) and not blocked


def copy_fetch_metadata(session, supplier: str) -> None:
    if session is None:
        return
    for suffix, shared in (
        ("last_status", "fetch_last_status"),
        ("last_url", "fetch_last_url"),
        ("last_transport", "fetch_last_transport"),
        ("browser_attempted", "fetch_browser_attempted"),
    ):
        setattr(session, f"{supplier}_{suffix}", getattr(session, shared, None))


def fetch_with_pipeline(
    session,
    url: str,
    *,
    timeout: int = 25,
    http_attempts: int = 2,
    logger_: Optional[logging.Logger] = None,
    blocked_detector: Optional[Callable[[int, str], bool]] = None,
    browser_timeout: Optional[int] = None,
    allow_browsers: Optional[bool] = None,
    browser_fetch_fn: Optional[Callable] = None,
) -> Optional[PipelineFetchResult]:
    """Fetch one URL through a bounded HTTP -> Scrapling -> browser pipeline."""
    log = logger_ or logger
    detector = blocked_detector or (lambda status, html: status in {401, 403, 429} or not html)
    attempts = max(1, min(5, int(http_attempts or 1)))
    timeout = max(1, int(timeout or 25))
    proxy = (
        os.getenv("SCRAPER_PROXY_URL")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("HTTP_PROXY")
        or os.getenv("https_proxy")
        or os.getenv("http_proxy")
        or ""
    ).strip() or None
    last_status = 0
    direct_browser = browser_fetch_requested()

    def check_stop():
        callback = getattr(session, 'scraper_stop_check', None)
        if callable(callback):
            try:
                callback()
            except Exception as exc:
                exc.scraper_cancelled = True
                raise

    def record(status, final_url, transport, blocked=False):
        if session is not None:
            if status:
                session.fetch_last_status = status
            session.fetch_last_url = final_url
            session.fetch_last_transport = transport
            session.fetch_blocked = blocked

    def is_blocked(status, html, headers=None):
        return _is_cf_challenge(status, headers or {}, html) or bool(detector(status, html))

    def abort_if_cancelled(exc):
        if is_cancellation_exception(exc):
            raise exc

    if session is not None:
        # These fields describe this URL, rather than leaking the previous
        # URL's result into an engine wrapper when every transport fails.
        session.fetch_last_status = None
        session.fetch_last_url = url
        session.fetch_last_transport = ""
        session.fetch_blocked = False
        session.fetch_browser_attempted = False
    check_stop()

    # A direct browser request is retained for callers that explicitly opt in
    # through browser_fetch_mode(True). Normal operation never enters here.
    if direct_browser:
        allow_browsers = True
        attempts = 0

    for attempt in range(attempts):
        check_stop()
        if session is not None:
            session.fetch_last_transport = "http"
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
            status = int(getattr(response, "status_code", 0) or 0)
            final_url = str(getattr(response, "url", "") or url)
            html = getattr(response, "text", "") or ""
            last_status = status
            headers = getattr(response, 'headers', {}) or {}
            blocked = is_blocked(status, html, headers)
            record(status, final_url, "http", blocked)
            if _usable_response(status, html, blocked):
                return PipelineFetchResult(html, final_url, status, "http", attempt + 1)
            if status in {404, 410}:
                return None
            if blocked:
                # Retrying the same blocked fingerprint is slow and rarely helps.
                attempts = attempt + 1
                break
        except Exception as exc:
            abort_if_cancelled(exc)
            if attempt == attempts - 1:
                log.debug("[fetch] HTTP failed for %s: %s", url, exc)
        if attempt + 1 < attempts:
            check_stop()
            time.sleep(min(0.75, 0.2 * (attempt + 1)))

    check_stop()
    if scrapling_enabled() and not direct_browser:
        if session is not None:
            session.fetch_last_transport = "scrapling-http"
        try:
            status, final_url, html, headers = _transport_response(
                _scrapling_http(url, timeout, _session_proxy(session, proxy), session)
            )
            last_status = status or last_status
            blocked = is_blocked(status, html, headers)
            record(status, final_url, "scrapling-http", blocked)
            if _usable_response(status, html, blocked):
                return PipelineFetchResult(html, final_url, status, "scrapling-http", attempts)
            if status in {404, 410}:
                return None
        except Exception as exc:
            abort_if_cancelled(exc)
            log.debug("[fetch] Scrapling HTTP failed for %s: %s", url, exc)

    if allow_browsers is None:
        allow_browsers = browser_fallback_enabled()
    browser_timeout = max(5, min(120, int(browser_timeout or timeout)))
    # Scrapling stealth is optional. If it is not installed or cannot solve a
    # challenge, continue to the already-supported Botasaurus adapter exactly
    # once.
    check_stop()
    if allow_browsers and scrapling_enabled() and not direct_browser:
        if session is not None:
            session.fetch_browser_attempted = True
            session.fetch_last_transport = "scrapling-stealth"
        try:
            scrapling_timeout = browser_timeout
            if scrapling_cloudflare_solver_enabled():
                try:
                    configured_timeout = int(os.getenv("SCRAPER_SCRAPLING_STEALTH_TIMEOUT", "60") or 60)
                except (TypeError, ValueError):
                    configured_timeout = 60
                scrapling_timeout = max(60, min(120, configured_timeout))
            status, final_url, html, headers = _transport_response(
                _scrapling_stealth(url, scrapling_timeout, _session_proxy(session, proxy), stop_check=check_stop)
            )
            last_status = status or last_status
            blocked = is_blocked(status, html, headers)
            record(status, final_url, "scrapling-stealth", blocked)
            if status in {404, 410}:
                return None
            if _usable_response(status, html, blocked):
                return PipelineFetchResult(html, final_url, status or 200, "scrapling-stealth", attempts)
        except Exception as exc:
            abort_if_cancelled(exc)
            log.debug("[fetch] Scrapling stealth failed for %s: %s", url, exc)

    if allow_browsers:
        check_stop()
        if session is not None:
            session.fetch_browser_attempted = True
            session.fetch_last_transport = "botasaurus"
        browser_fetcher = browser_fetch_fn or botasaurus_fetch_html
        try:
            result = browser_fetcher(url, **_supported_kwargs(browser_fetcher, {
                "timeout": browser_timeout, "logger": log, "stop_check": check_stop,
            }))
            status = int(getattr(result, "status_code", 200) or 200)
            final_url = getattr(result, "final_url", None) or url
            blocked = is_blocked(status, result.html, getattr(result, "headers", {}) or {})
            record(status, final_url, "botasaurus", blocked)
            if _usable_response(status, result.html, blocked):
                return PipelineFetchResult(result.html, final_url, status, "botasaurus", attempts)
        except Exception as exc:
            abort_if_cancelled(exc)
            log.warning("[fetch] Direct transports failed for %s (last HTTP status %s): %s", url, last_status, exc)

    # The residential proxy is deliberately isolated from normal traffic. It is
    # tried only after all direct transports, and only for MobileSentrix and
    # PhoneLCDParts, where residential egress is an explicit recovery tactic.
    fallback_proxy = _last_resort_proxy_for_url(url)
    if fallback_proxy:
        log.warning("[fetch] Direct tactics failed; trying the configured last-resort proxy for %s", url)
        if scrapling_enabled():
            check_stop()
            if session is not None:
                session.fetch_last_transport = "last-resort-proxy-scrapling-http"
            try:
                status, final_url, html, headers = _transport_response(
                    _scrapling_http(url, timeout, fallback_proxy, session)
                )
                last_status = status or last_status
                blocked = is_blocked(status, html, headers)
                record(status, final_url, "last-resort-proxy-scrapling-http", blocked)
                if _usable_response(status, html, blocked):
                    return PipelineFetchResult(html, final_url, status, "last-resort-proxy-scrapling-http", attempts)
            except Exception as exc:
                abort_if_cancelled(exc)
                log.debug("[fetch] Last-resort proxy HTTP failed for %s: %s", url, exc)

            if allow_browsers:
                check_stop()
                if session is not None:
                    session.fetch_browser_attempted = True
                    session.fetch_last_transport = "last-resort-proxy-scrapling-stealth"
                try:
                    status, final_url, html, headers = _transport_response(
                        _scrapling_stealth(url, browser_timeout, fallback_proxy, stop_check=check_stop)
                    )
                    last_status = status or last_status
                    blocked = is_blocked(status, html, headers)
                    record(status, final_url, "last-resort-proxy-scrapling-stealth", blocked)
                    if _usable_response(status, html, blocked):
                        return PipelineFetchResult(html, final_url, status, "last-resort-proxy-scrapling-stealth", attempts)
                except Exception as exc:
                    abort_if_cancelled(exc)
                    log.warning("[fetch] Last-resort proxy browser failed for %s: %s", url, exc)
    return None
