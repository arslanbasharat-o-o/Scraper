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


@dataclass(slots=True)
class BrowserBatchFetchResult:
    request_url: str
    final_url: str
    html: str
    status_code: int = 0
    error: str = ""


@dataclass(slots=True)
class BrowserProductDetailResult:
    request_url: str
    final_url: str
    status_code: int = 0
    detail: dict | None = None
    error: str = ""


_PREFETCHED_BROWSER_HTML = contextvars.ContextVar("prefetched_browser_html", default=None)


@contextlib.contextmanager
def prefetched_browser_html(url: str, result: BrowserBatchFetchResult | BrowserFetchResult):
    token = _PREFETCHED_BROWSER_HTML.set((str(url or "").strip(), result))
    try:
        yield
    finally:
        _PREFETCHED_BROWSER_HTML.reset(token)


def _get_prefetched_browser_html(url: str) -> BrowserFetchResult | None:
    current = _PREFETCHED_BROWSER_HTML.get()
    if not current:
        return None
    expected_url, result = current
    if str(url or "").strip() != expected_url:
        return None
    html = getattr(result, "html", "") or ""
    final_url = getattr(result, "final_url", "") or url
    if not html:
        return None
    return BrowserFetchResult(final_url=final_url, html=html)


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "browser"}


def _is_mobilesentrix_canada_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse

        hostname = (urlparse(str(url or "")).hostname or "").lower()
        return hostname.removeprefix("www.") == "mobilesentrix.ca"
    except (AttributeError, ValueError):
        return False


def _dismiss_canada_prompt(execute_script, sleep, *, url: str, logger=None, attempts: int = 8) -> bool:
    if not _is_mobilesentrix_canada_url(url):
        return False
    for _attempt in range(max(0, attempts)):
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


def _should_bypass_cloudflare() -> bool:
    return _truthy(os.getenv("SCRAPER_BOTASAURUS_BYPASS_CLOUDFLARE"))


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
    prefetched = _get_prefetched_browser_html(url)
    if prefetched:
        return prefetched

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
                    driver.get(
                        data["url"],
                        timeout=data.get("timeout", timeout),
                        bypass_cloudflare=_should_bypass_cloudflare(),
                    )
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
            finally:
                # Driver reuse keeps the process warm; Botasaurus owns the
                # pooled driver's lifecycle and closes it on process exit.
                pass
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


def _origin_url(url: str) -> str:
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(str(url or ""))
        if parsed.scheme and parsed.netloc:
            return urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))
    except ValueError:
        pass
    return str(url or "")


def fetch_html_many(
    urls: list[str],
    *,
    timeout: int = 12,
    wait_seconds: float | None = None,
    logger=None,
) -> list[BrowserBatchFetchResult]:
    """Fetch many same-origin pages through one warm Botasaurus browser context."""
    clean_urls = [str(url or "").strip() for url in urls if str(url or "").strip()]
    if not clean_urls:
        return []

    try:
        from .botasaurus_wrapper import Driver, browser
    except Exception as exc:
        raise RuntimeError(f"Botasaurus is required for rendered scraping: {exc}") from exc

    wait_time = (
        float(wait_seconds)
        if wait_seconds is not None
        else float(os.getenv("SCRAPER_LOCAL_BROWSER_WAIT_SECONDS") or "0.3")
    )
    started = time.time()

    with _local_browser_slot() as slot:
        profile_dir = _local_browser_profile_dir() / f"process-{os.getpid()}" / f"batch-{slot}"
        profile_dir.mkdir(parents=True, exist_ok=True)
        chrome_executable = resolve_chrome_executable()
        if logger:
            logger.info(
                "[botasaurus] Batch slot %s fetching %s URL(s) with Chrome %s and profile %s",
                slot,
                len(clean_urls),
                chrome_executable or "Botasaurus default discovery",
                profile_dir,
            )

        fetcher_key = f"batch:{profile_dir}"
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
        def _fetch_many(driver: Driver, data):
            links = list(data["urls"])
            seed_url = data.get("seed_url") or _origin_url(links[0])
            if logger:
                logger.info("[botasaurus] Batch warming %s for %s URL(s)", seed_url, len(links))
            try:
                try:
                    driver.get(
                        seed_url,
                        timeout=max(10, int(data.get("timeout", timeout))),
                        bypass_cloudflare=_should_bypass_cloudflare(),
                    )
                except Exception as exc:
                    html = driver.page_html or ""
                    if not html:
                        raise
                    if logger:
                        logger.warning("[botasaurus] Batch warm page partially loaded: %s", exc)
                if data.get("wait_seconds", wait_time) > 0:
                    driver.sleep(data.get("wait_seconds", wait_time))
                _dismiss_canada_prompt(driver.run_js, driver.sleep, url=seed_url, logger=logger, attempts=1)
                responses = driver.requests.get_many(
                    links,
                    referer=seed_url,
                    timeout=data.get("request_timeout", timeout),
                )
                out = []
                for response in responses:
                    out.append({
                        "request_url": getattr(response, "request_url", "") or getattr(response, "url", "") or "",
                        "final_url": getattr(response, "url", "") or "",
                        "status_code": int(getattr(response, "status_code", 0) or 0),
                        "html": getattr(response, "text", "") or "",
                        "error": getattr(response, "reason", "") if int(getattr(response, "status_code", 0) or 0) >= 500 else "",
                    })
                return out
            finally:
                pass

        try:
            if cached_fetcher is None:
                with _REUSABLE_FETCHERS_LOCK:
                    cached_fetcher = _REUSABLE_FETCHERS.setdefault(fetcher_key, _fetch_many)
            raw_results = cached_fetcher({
                "urls": clean_urls,
                "slot": slot,
                "timeout": max(timeout, 10),
                "request_timeout": timeout,
                "wait_seconds": wait_time,
                "seed_url": _origin_url(clean_urls[0]),
            })
        except Exception as exc:
            if logger:
                logger.exception("[botasaurus] Batched rendered fetch failed")
            raise RuntimeError(f"Botasaurus batched browser fetch failed: {exc}") from exc

    by_request = {}
    for raw in raw_results or []:
        request_url = str(raw.get("request_url") or "").strip()
        final_url = str(raw.get("final_url") or request_url).strip()
        html = raw.get("html") or ""
        status_code = int(raw.get("status_code") or 0)
        error = str(raw.get("error") or "")
        if html and _looks_like_browser_challenge(html):
            error = error or "browser verification page"
        by_request[request_url] = BrowserBatchFetchResult(
            request_url=request_url,
            final_url=final_url or request_url,
            html=html,
            status_code=status_code,
            error=error,
        )

    results = []
    for request_url in clean_urls:
        result = by_request.get(request_url)
        if result is None:
            result = BrowserBatchFetchResult(
                request_url=request_url,
                final_url=request_url,
                html="",
                status_code=0,
                error="missing batched browser response",
            )
        results.append(result)

    if logger:
        logger.info(
            "[botasaurus] Batch returned %s/%s response(s) in %.1fs",
            sum(1 for result in results if result.html),
            len(clean_urls),
            time.time() - started,
        )
    return results


_PRODUCT_DETAIL_BATCH_JS = r"""
const clean = value => (value || '').replace(/\s+/g, ' ').trim();
const absoluteUrl = (value, baseUrl) => {
  try { return value ? new URL(value, baseUrl).href : ''; } catch (_) { return value || ''; }
};
const firstText = (doc, selectors) => {
  for (const selector of selectors) {
    const element = doc.querySelector(selector);
    const text = clean(element?.textContent || element?.getAttribute('content') || element?.getAttribute('value') || '');
    if (text) return text;
  }
  return '';
};
const firstAttr = (doc, selectors, attr, baseUrl) => {
  for (const selector of selectors) {
    const element = doc.querySelector(selector);
    const value = clean(element?.getAttribute(attr) || '');
    if (value) return absoluteUrl(value, baseUrl);
  }
  return '';
};
const parseJsonLdProducts = doc => {
  const products = [];
  const visit = value => {
    if (!value) return;
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    if (typeof value !== 'object') return;
    const type = value['@type'];
    const types = Array.isArray(type) ? type : [type];
    if (types.some(item => String(item || '').toLowerCase() === 'product')) {
      products.push(value);
    }
    if (Array.isArray(value['@graph'])) value['@graph'].forEach(visit);
  };
  doc.querySelectorAll('script[type="application/ld+json"]').forEach(script => {
    try { visit(JSON.parse(script.textContent || '')); } catch (_) {}
  });
  return products;
};
const offerValue = (offers, key) => {
  if (!offers) return '';
  if (Array.isArray(offers)) {
    for (const offer of offers) {
      const value = offerValue(offer, key);
      if (value) return value;
    }
    return '';
  }
  if (typeof offers === 'object') return clean(String(offers[key] || ''));
  return '';
};
const pickImage = (product, doc, baseUrl) => {
  const image = product?.image;
  if (Array.isArray(image) && image.length) return absoluteUrl(String(image[0] || ''), baseUrl);
  if (typeof image === 'string' && image) return absoluteUrl(image, baseUrl);
  return firstAttr(doc, [
    'meta[property="og:image"]',
    'meta[name="twitter:image"]',
    '.product.media img',
    '.gallery-placeholder img',
    'img[itemprop="image"]',
    'img'
  ], 'content', baseUrl) || firstAttr(doc, [
    '.product.media img',
    '.gallery-placeholder img',
    'img[itemprop="image"]',
    'img'
  ], 'src', baseUrl);
};
const pickSku = (product, doc) => {
  const jsonSku = clean(String(product?.sku || product?.mpn || ''));
  if (jsonSku) return jsonSku;
  for (const selector of [
    '[itemprop="sku"]',
    '.product.attribute.sku .value',
    '.product-info-stock-sku .sku .value',
    '.sku_wrapper .sku',
    '.sku',
    '[data-product-sku]',
    '[data-sku]',
    '[data-product_sku]'
  ]) {
    const element = doc.querySelector(selector);
    const value = clean(
      element?.getAttribute('content') ||
      element?.getAttribute('value') ||
      element?.getAttribute('data-product-sku') ||
      element?.getAttribute('data-sku') ||
      element?.getAttribute('data-product_sku') ||
      element?.textContent ||
      ''
    ).replace(/^sku\s*[:#-]?\s*/i, '');
    if (value && !/^sku$|^n\/a$/i.test(value)) return value;
  }
  const pageText = clean(doc.body?.textContent || '');
  const match = pageText.match(/\bsku\b\s*[:#-]?\s*([A-Za-z0-9._/-]{3,})/i);
  return match ? clean(match[1]) : '';
};
const extractDetail = (text, finalUrl) => {
  const doc = new DOMParser().parseFromString(text || '', 'text/html');
  const products = parseJsonLdProducts(doc);
  const product = products[0] || {};
  const offers = product.offers;
  const title = clean(String(product.name || '')) || firstText(doc, [
    'h1.page-title',
    '.page-title .base',
    'h1',
    'meta[property="og:title"]',
    'title'
  ]);
  const canonical = firstAttr(doc, ['link[rel="canonical"]', 'meta[property="og:url"]'], 'href', finalUrl)
    || firstAttr(doc, ['meta[property="og:url"]'], 'content', finalUrl)
    || finalUrl;
  const priceText = offerValue(offers, 'price') || firstText(doc, [
    'meta[property="product:price:amount"]',
    'meta[itemprop="price"]',
    '[itemprop="price"]',
    '.price-final_price .price',
    '.product-info-price .price',
    '.price'
  ]);
  const description = clean(String(product.description || '')) || firstText(doc, [
    '.product.attribute.description .value',
    '#description',
    '.product.attribute.overview .value',
    '[itemprop="description"]',
    '.description',
    'meta[name="description"]'
  ]);
  const availability = offerValue(offers, 'availability') || firstText(doc, [
    '.product-info-stock-sku .stock',
    '.stock',
    '.availability',
    '.inventory-status',
    '[class*="stock"]'
  ]);
  return {
    url: canonical,
    title,
    sku: pickSku(product, doc),
    price_text: priceText,
    price_currency: offerValue(offers, 'priceCurrency'),
    stock_status: availability,
    description,
    image_url: pickImage(product, doc, finalUrl),
  };
};

const links = args.links || [];
const results = new Array(links.length);
const concurrency = Math.max(1, Math.min(args.concurrency || 6, links.length || 1));
const staggerMs = args.stagger_ms !== undefined ? args.stagger_ms : 25;

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function fetchOne(url) {
  return window.fetch(url, {
    headers: {
      'priority': 'u=0, i',
      'sec-fetch-dest': 'document',
      'sec-fetch-mode': 'navigate',
      'sec-fetch-site': 'same-origin',
      'sec-fetch-user': '?1',
      'upgrade-insecure-requests': '1',
      ...(args.headers || {}),
    },
    referrer: args.referrer,
    referrerPolicy: 'strict-origin-when-cross-origin',
    method: 'GET',
    mode: 'cors',
    credentials: 'include',
    signal: AbortSignal.timeout((args.timeout || 12) * 1000),
  })
  .then(response => {
    return response.text().then(text => {
      return {
        request_url: url,
        final_url: response.url || url,
        status_code: response.status,
        detail: extractDetail(text, response.url || url),
        error: '',
      };
    });
  })
  .catch(error => {
    return {
      request_url: url,
      final_url: url,
      status_code: 0,
      detail: null,
      error: String(error),
    };
  });
}

let index = 0;
function nextWorker(workerId) {
  const startDelay = workerId > 0 && staggerMs > 0 ? delay(workerId * staggerMs) : Promise.resolve();
  return startDelay.then(() => {
    function runNext() {
      if (index >= links.length) return Promise.resolve();
      const cur = index++;
      return fetchOne(links[cur]).then(res => {
        results[cur] = res;
        return staggerMs > 0 ? delay(staggerMs).then(runNext) : runNext();
      });
    }
    return runNext();
  });
}

const workers = [];
for (let w = 0; w < concurrency; w++) {
  workers.push(nextWorker(w));
}
return Promise.all(workers).then(() => results);
"""


def fetch_product_details_many(
    urls: list[str],
    *,
    timeout: int = 12,
    wait_seconds: float | None = None,
    logger=None,
) -> list[BrowserProductDetailResult]:
    """Fetch and extract compact product detail snapshots inside Botasaurus."""
    clean_urls = [str(url or "").strip() for url in urls if str(url or "").strip()]
    if not clean_urls:
        return []

    try:
        from .botasaurus_wrapper import Driver, browser
    except Exception as exc:
        raise RuntimeError(f"Botasaurus is required for rendered scraping: {exc}") from exc

    wait_time = (
        float(wait_seconds)
        if wait_seconds is not None
        else float(os.getenv("SCRAPER_LOCAL_BROWSER_WAIT_SECONDS") or "0.3")
    )
    started = time.time()

    with _local_browser_slot() as slot:
        profile_dir = _local_browser_profile_dir() / f"process-{os.getpid()}" / f"detail-batch-{slot}"
        profile_dir.mkdir(parents=True, exist_ok=True)
        fetcher_key = f"detail-batch:{profile_dir}"
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
        def _fetch_details(driver: Driver, data):
            links = list(data["urls"])
            seed_url = data.get("seed_url") or _origin_url(links[0])
            if logger:
                logger.info("[botasaurus] Detail batch warming %s for %s URL(s)", seed_url, len(links))
            try:
                try:
                    driver.get(
                        seed_url,
                        timeout=max(10, int(data.get("timeout", timeout))),
                        bypass_cloudflare=_should_bypass_cloudflare(),
                    )
                except Exception as exc:
                    if not (driver.page_html or ""):
                        raise
                    if logger:
                        logger.warning("[botasaurus] Detail batch warm page partially loaded: %s", exc)
                if data.get("wait_seconds", wait_time) > 0:
                    driver.sleep(data.get("wait_seconds", wait_time))
                _dismiss_canada_prompt(driver.run_js, driver.sleep, url=seed_url, logger=logger, attempts=1)
                concurrency = int(data.get("concurrency") or os.getenv("SCRAPER_MOBILESENTRIX_BATCH_CONCURRENCY") or 6)
                stagger_ms = int(data.get("stagger_ms") or os.getenv("SCRAPER_MOBILESENTRIX_BATCH_STAGGER_MS") or 25)
                return driver.run_js(
                    _PRODUCT_DETAIL_BATCH_JS,
                    args={
                        "links": links,
                        "timeout": data.get("request_timeout", timeout),
                        "referrer": seed_url,
                        "concurrency": concurrency,
                        "stagger_ms": stagger_ms,
                    },
                )
            finally:
                pass

        try:
            if cached_fetcher is None:
                with _REUSABLE_FETCHERS_LOCK:
                    cached_fetcher = _REUSABLE_FETCHERS.setdefault(fetcher_key, _fetch_details)
            raw_results = cached_fetcher({
                "urls": clean_urls,
                "slot": slot,
                "timeout": max(timeout, 10),
                "request_timeout": timeout,
                "wait_seconds": wait_time,
                "seed_url": _origin_url(clean_urls[0]),
            })
        except Exception as exc:
            if logger:
                logger.exception("[botasaurus] Batched detail extraction failed")
            raise RuntimeError(f"Botasaurus batched detail extraction failed: {exc}") from exc

    by_request = {}
    for raw in raw_results or []:
        request_url = str(raw.get("request_url") or "").strip()
        final_url = str(raw.get("final_url") or request_url).strip()
        status_code = int(raw.get("status_code") or 0)
        detail = raw.get("detail") if isinstance(raw.get("detail"), dict) else None
        error = str(raw.get("error") or "")
        by_request[request_url] = BrowserProductDetailResult(
            request_url=request_url,
            final_url=final_url or request_url,
            status_code=status_code,
            detail=detail,
            error=error,
        )

    results = []
    for request_url in clean_urls:
        result = by_request.get(request_url)
        if result is None:
            result = BrowserProductDetailResult(
                request_url=request_url,
                final_url=request_url,
                status_code=0,
                detail=None,
                error="missing batched browser detail response",
            )
        results.append(result)

    if logger:
        logger.info(
            "[botasaurus] Detail batch returned %s/%s SKU candidate(s) in %.1fs",
            sum(1 for result in results if (result.detail or {}).get("sku")),
            len(clean_urls),
            time.time() - started,
        )
    return results
