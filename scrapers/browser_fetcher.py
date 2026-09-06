"""Botasaurus-only rendered HTML fetching for scraper engines."""

from __future__ import annotations

import contextlib
import contextvars
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .botasaurus_wrapper import close_botasaurus_driver, resolve_chrome_executable, resolve_chrome_profile_root


_BROWSER_FETCH_ENABLED = contextvars.ContextVar("browser_fetch_enabled", default=None)
_BROWSER_FETCH_DIRECT = contextvars.ContextVar("browser_fetch_direct", default=False)
_LOCAL_BROWSER_SLOT_LOCK = threading.Lock()
_LOCAL_BROWSER_SEMAPHORE = None
_LOCAL_BROWSER_SEMAPHORE_SIZE = 0
_LOCAL_BROWSER_AVAILABLE_SLOTS: list[int] = []
_REUSABLE_FETCHERS: dict[str, object] = {}
_REUSABLE_FETCHERS_LOCK = threading.Lock()


MOBILESENTRIX_CANADA_POPUP_DISMISS_JS = r"""
(() => {
  const clean = value => (value || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const stayPattern = /^(?:or\s+)?stay on (?:www\.)?mobilesentrix\.ca[.!]?$/i;
  const candidates = [...document.querySelectorAll('button, a, [role="button"], div, span, p')];
  const stay = candidates.find(element => stayPattern.test(clean(element.textContent)));
  if (stay) {
    stay.click();
    return true;
  }
  const popup = candidates.find(element => /we noticed you.*re in/.test(clean(element.textContent)));
  if (!popup) return false;
  const root = popup.closest('[role="dialog"], .modal, [class*="location"], [class*="country"]') || popup.parentElement;
  const close = root?.querySelector('[aria-label*="close" i], button.close, .modal-close, [class*="close"]');
  if (!close) return false;
  close.click();
  return true;
})()
"""


@dataclass(slots=True)
class BrowserFetchResult:
    final_url: str
    html: str


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "browser"}


def _is_mobilesentrix_canada_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse

        hostname = (urlparse(str(url or "")).hostname or "").lower()
        return hostname.removeprefix("www.") == "mobilesentrix.ca"
    except (AttributeError, ValueError):
        return False


def _dismiss_canada_prompt(execute_script, sleep, *, url: str, logger=None) -> bool:
    if not _is_mobilesentrix_canada_url(url):
        return False
    for _attempt in range(8):
        try:
            if execute_script(MOBILESENTRIX_CANADA_POPUP_DISMISS_JS):
                if logger:
                    logger.info("[botasaurus] Dismissed MobileSentrix Canada location prompt")
                sleep(0.75)
                return True
        except Exception as exc:
            if logger:
                logger.warning("[botasaurus] Could not dismiss Canada location prompt: %s", exc)
            return False
        sleep(0.5)
    return False


def _local_browser_max_windows() -> int:
    value = os.getenv("SCRAPER_LOCAL_BROWSER_MAX_WINDOWS") or "1"
    try:
        return max(1, min(4, int(value)))
    except (TypeError, ValueError):
        return 1


def _get_local_browser_semaphore():
    global _LOCAL_BROWSER_SEMAPHORE, _LOCAL_BROWSER_SEMAPHORE_SIZE
    max_windows = _local_browser_max_windows()
    with _LOCAL_BROWSER_SLOT_LOCK:
        if _LOCAL_BROWSER_SEMAPHORE is None or _LOCAL_BROWSER_SEMAPHORE_SIZE != max_windows:
            _LOCAL_BROWSER_SEMAPHORE = threading.BoundedSemaphore(max_windows)
            _LOCAL_BROWSER_SEMAPHORE_SIZE = max_windows
            _LOCAL_BROWSER_AVAILABLE_SLOTS[:] = list(range(max_windows))
        return _LOCAL_BROWSER_SEMAPHORE


@contextlib.contextmanager
def _local_browser_slot():
    semaphore = _get_local_browser_semaphore()
    semaphore.acquire()
    slot = 0
    try:
        with _LOCAL_BROWSER_SLOT_LOCK:
            if not _LOCAL_BROWSER_AVAILABLE_SLOTS:
                _LOCAL_BROWSER_AVAILABLE_SLOTS.append(0)
            slot = _LOCAL_BROWSER_AVAILABLE_SLOTS.pop(0)
        yield slot
    finally:
        with _LOCAL_BROWSER_SLOT_LOCK:
            if slot not in _LOCAL_BROWSER_AVAILABLE_SLOTS:
                _LOCAL_BROWSER_AVAILABLE_SLOTS.append(slot)
                _LOCAL_BROWSER_AVAILABLE_SLOTS.sort()
        semaphore.release()


@contextlib.contextmanager
def browser_fetch_mode(enabled: bool | None):
    token = _BROWSER_FETCH_ENABLED.set(None if enabled is None else bool(enabled))
    direct_token = _BROWSER_FETCH_DIRECT.set(bool(enabled))
    try:
        yield
    finally:
        _BROWSER_FETCH_DIRECT.reset(direct_token)
        _BROWSER_FETCH_ENABLED.reset(token)


def browser_fetch_requested() -> bool:
    """Whether the current enrichment explicitly requested rendered-only fetch."""
    return bool(_BROWSER_FETCH_DIRECT.get())


def should_use_browser_fetch() -> bool:
    explicit = _BROWSER_FETCH_ENABLED.get()
    if explicit is not None:
        return bool(explicit)
    configured = os.getenv("SCRAPER_USE_BROWSER")
    return False if configured is None else _truthy(configured)


def _local_browser_headless() -> bool:
    value = os.getenv("SCRAPER_LOCAL_BROWSER_HEADLESS")
    return True if value is None else _truthy(value)


def _local_browser_profile_dir() -> Path:
    configured = (os.getenv("SCRAPER_LOCAL_BROWSER_PROFILE_DIR") or "").strip()
    default = Path(configured) if configured else Path.cwd() / "data" / "browser_profiles"
    return resolve_chrome_profile_root(default)


def _should_use_botasaurus_request_html() -> bool:
    return _truthy(os.getenv("SCRAPER_BOTASAURUS_REQUEST_HTML"))


def _looks_like_html_document(text: str) -> bool:
    sample = (text or "").lstrip()[:512].lower()
    return "<!doctype html" in sample or "<html" in sample or "<body" in sample


def _looks_like_browser_challenge(html: str) -> bool:
    sample = (html or "").lower()
    return any(marker in sample for marker in (
        "just a moment",
        "performing security verification",
        "verify you are human",
        "enable javascript and cookies to continue",
        "cf-browser-verification",
        "cloudflare ray id",
    ))


def fetch_html(
    url: str,
    *,
    timeout: int = 60,
    wait_seconds: float | None = None,
    logger=None,
) -> BrowserFetchResult:
    """Fetch a rendered page with a headless local Botasaurus browser."""
    try:
        from .botasaurus_wrapper import Driver, browser
    except Exception as exc:
        raise RuntimeError(f"Botasaurus is required for rendered scraping: {exc}") from exc

    wait_time = (
        float(wait_seconds)
        if wait_seconds is not None
        else float(os.getenv("SCRAPER_LOCAL_BROWSER_WAIT_SECONDS") or "1")
    )
    challenge_wait_seconds = float(os.getenv("SCRAPER_LOCAL_BROWSER_CHALLENGE_WAIT_SECONDS") or "30")
    started = time.time()

    with _local_browser_slot() as slot:
        # Browser slots are process-local; include the PID so concurrent scraper
        # workers never attach to the same Chrome profile/DevTools port.
        profile_dir = _local_browser_profile_dir() / f"process-{os.getpid()}" / f"worker-{slot}"
        profile_dir.mkdir(parents=True, exist_ok=True)
        chrome_executable = resolve_chrome_executable()
        if logger:
            logger.info(
                "[botasaurus] Starting browser slot %s with Chrome executable %s and profile %s",
                slot,
                chrome_executable or "Botasaurus default discovery",
                profile_dir,
            )

        fetcher_key = str(profile_dir)
        with _REUSABLE_FETCHERS_LOCK:
            cached_fetcher = _REUSABLE_FETCHERS.get(fetcher_key)

        @browser(
            headless=_local_browser_headless(),
            profile=str(profile_dir),
            window_size=(1440, 1200),
            lang="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            output=None,
            raise_exception=True,
            create_error_logs=False,
            close_on_crash=True,
            reuse_driver=True,
            block_images=True,
            wait_for_complete_page_load=False,
        )
        def _fetch(driver: Driver, data):
            if logger:
                logger.info("[botasaurus] Fetching %s in browser slot %s", data["url"], data["slot"])
            try:
                try:
                    driver.get(data["url"], timeout=data.get("timeout", timeout))
                except Exception as exc:
                    partial_html = driver.page_html or ""
                    if partial_html and _looks_like_html_document(partial_html):
                        if logger:
                            logger.warning(
                                "[botasaurus] Page load did not fully complete for %s; using rendered HTML already present: %s",
                                data["url"],
                                exc,
                            )
                    else:
                        raise
                if data.get("wait_seconds", wait_time) > 0:
                    driver.sleep(data.get("wait_seconds", wait_time))
                _dismiss_canada_prompt(driver.run_js, driver.sleep, url=data["url"], logger=logger)

                html = driver.page_html or ""
                challenge_deadline = time.time() + max(0.0, challenge_wait_seconds)
                while time.time() < challenge_deadline and _looks_like_browser_challenge(html):
                    driver.sleep(2)
                    html = driver.page_html or ""

                final_url = driver.current_url or data["url"]
                if _should_use_botasaurus_request_html() and not _looks_like_browser_challenge(html):
                    try:
                        response = driver.requests.get(data["url"])
                        response_text = getattr(response, "text", "") or ""
                        response_status = int(getattr(response, "status_code", 0) or 0)
                        if (
                            response_text
                            and (response_status == 0 or response_status < 400)
                            and _looks_like_html_document(response_text)
                            and not _looks_like_browser_challenge(response_text)
                        ):
                            html = response_text
                            final_url = getattr(response, "url", "") or final_url
                    except Exception as exc:
                        if logger:
                            logger.warning("[botasaurus] Browser-backed request failed: %s", exc)

                return {"final_url": final_url, "html": html}
        try:
            if cached_fetcher is None:
                with _REUSABLE_FETCHERS_LOCK:
                    cached_fetcher = _REUSABLE_FETCHERS.setdefault(fetcher_key, _fetch)
            result = cached_fetcher({"url": url, "slot": slot, "timeout": timeout, "wait_seconds": wait_time})
        except Exception as exc:
            if logger:
                logger.exception("[botasaurus] DevTools connection or rendered fetch failed for %s", url)
            raise RuntimeError(f"Botasaurus browser fetch failed for {url}: {exc}") from exc

    html = (result or {}).get("html") or ""
    final_url = (result or {}).get("final_url") or url
    if _looks_like_browser_challenge(html):
        raise RuntimeError("Botasaurus remained on a browser verification page")
    if not _looks_like_html_document(html):
        raise RuntimeError("Botasaurus returned an empty or invalid HTML document")
    if logger:
        logger.info(
            "[botasaurus] Rendered %s bytes from %s in %.1fs",
            len(html),
            final_url,
            time.time() - started,
        )
    return BrowserFetchResult(final_url=final_url, html=html)
