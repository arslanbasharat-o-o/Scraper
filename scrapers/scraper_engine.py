import threading
_CURL_LOCK = threading.Lock()
"""
MobileSentrix Scraper Engine
============================
Core scraping logic separated from Flask routes for better maintainability.
This module handles:
- HTTP session management
- HTML parsing and data extraction
- Product and category page scraping
- Pagination support
- Parallel URL processing
"""

from bs4 import BeautifulSoup
import importlib.util
import requests
import re
import json
import time
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, urlunparse
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from .browser_fetcher import fetch_html as fetch_html_with_browser, should_use_browser_fetch, browser_fetch_mode, browser_fetch_requested

# Optional curl_cffi for better Cloudflare bypass
try:
    from curl_cffi import requests as curl_requests
    HAS_CURL = True
except Exception:
    HAS_CURL = False

# Check for lxml parser (faster than html.parser)
if importlib.util.find_spec('lxml') is not None:
    PARSER = 'lxml'
else:
    PARSER = 'html.parser'

# -------- Data Classes --------

@dataclass
class Item:
    """Represents a scraped product item"""
    url: str
    site: str
    title: str
    price_value: Optional[float]
    price_currency: Optional[str]
    price_text: str
    discounted_value: Optional[float]
    discounted_formatted: str
    original_formatted: str
    source: str
    image_url: str
    sku: str = ""
    stock_status: str = ""
    description: str = ""
    extra: dict = field(default_factory=dict)


# -------- Text & Price Utilities --------

MONEY_RE = re.compile(r'([\$£€]|CA\$)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+(?:\.[0-9]{2})?)')
CURRENCY_SYMBOLS = {'USD': '$', 'CAD': 'CA$', 'usd': '$', 'cad': 'CA$'}


def clean_text(s: Optional[str]) -> str:
    """Clean and normalize text by removing extra whitespace"""
    if not s:
        return ""
    return re.sub(r'\s+', ' ', s).strip()


def strip_markup(value: Optional[str]) -> str:
    """Convert small HTML snippets or rich-text fragments into plain text."""
    if not value:
        return ""
    text = clean_text(value)
    if '<' not in text or '>' not in text:
        return text
    try:
        return clean_text(BeautifulSoup(text, 'html.parser').get_text(' ', strip=True))
    except Exception:
        return text


def host_currency(host: str) -> str:
    """Detect currency based on hostname (CA domains = CAD, others = USD)"""
    host = (host or '').lower()
    if host.endswith('.ca') or host.startswith('ca.') or '.ca.' in host:
        return 'CAD'
    return 'USD'


def parse_price_number(text: str) -> Optional[float]:
    """Extract numeric price value from text"""
    if not text:
        return None
    m = MONEY_RE.search(text)
    if not m:
        return None
    num = m.group(2).replace(',', '')
    try:
        return float(num)
    except Exception:
        return None


def fmt_price(val: Optional[float], currency: Optional[str], host: str) -> str:
    """Format price with appropriate currency symbol"""
    if val is None:
        return ""
    sym = CURRENCY_SYMBOLS.get((currency or '').upper()) or CURRENCY_SYMBOLS.get(host_currency(host)) or '$'
    return f"{sym}{val:,.2f}"


def apply_rules(price: Optional[float], percent_off: float, absolute_off: float, add_percent: float = 0.0):
    """Apply pricing rules to a price."""
    if price is None:
        return None
    p = float(price)
    if add_percent and add_percent > 0:
        p *= (1 + add_percent/100.0)
    if percent_off and percent_off > 0:
        p *= (1 - percent_off/100.0)
    if absolute_off and absolute_off > 0:
        p -= absolute_off
    return round(p + 1e-9, 2)


# -------- HTTP Session Management --------

def build_session(retries: int = 1, verify_ssl: bool = True, use_curl: bool = True):
    """
    Build HTTP session with retries and proper headers.
    Returns (session, is_curl_session)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    if use_curl and HAS_CURL:
        try:
            with _CURL_LOCK:
                s = curl_requests.Session(impersonate="safari15_5")
            s.headers.update(headers)
            s.verify = verify_ssl
            s.timeout = 30
            return s, True
        except Exception:
            pass

    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    s = requests.Session()
    s.headers.update(headers)

    # Increased retries and backoff for better reliability
    retry = Retry(
        total=max(1, int(retries) * 2),  # Double the retries
        read=max(1, int(retries) * 2),
        connect=max(1, int(retries) * 2),
        backoff_factor=0.5,  # Increased from 0.1 to 0.5 for longer waits between retries
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(['GET', 'HEAD', 'OPTIONS'])
    )

    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    s.mount('https://', adapter)
    s.mount('http://', adapter)
    s.verify = verify_ssl

    return s, False


def _set_fetch_metadata(sess, *, status_code=None, final_url: str = "", error: str = "", blocked: bool = False):
    """Attach the latest MobileSentrix fetch metadata to the session for logging."""
    try:
        sess.mobilesentrix_last_status = status_code
        sess.mobilesentrix_last_url = final_url or ""
        sess.mobilesentrix_last_error = error or ""
        sess.mobilesentrix_blocked = bool(blocked)
    except Exception:
        pass


def _looks_like_antibot_challenge(status_code: int, html: str) -> bool:
    sample = (html or "")[:3000].lower()
    challenge_markers = (
        "just a moment",
        "cloudflare",
        "captcha",
        "verify you are human",
        "access denied",
    )
    if any(marker in sample for marker in challenge_markers):
        return True
    return int(status_code or 0) in {401, 403, 429} and bool(sample)


import logging

logger = logging.getLogger(__name__)

def get_html(sess, url: str, timeout: int = 30) -> Tuple[str, str]:
    """Fetch HTML from URL. Returns (final_url, html_content)"""
    _set_fetch_metadata(sess, status_code=None, final_url=url)
    if browser_fetch_requested():
        result = fetch_html_with_browser(url, timeout=max(timeout, 60))
        _set_fetch_metadata(sess, status_code=200, final_url=result.final_url, blocked=False)
        return result.final_url, result.html
    try:
        # Fast Safari TLS HTTP request first
        r = sess.get(url, timeout=timeout, allow_redirects=True)
        status_code = int(getattr(r, 'status_code', 0) or 0)
        final_url = str(getattr(r, 'url', '') or url)
        html = getattr(r, 'text', '') or ''
        blocked = _looks_like_antibot_challenge(status_code, html)
        _set_fetch_metadata(sess, status_code=status_code, final_url=final_url, blocked=blocked)
        if blocked:
            if should_use_browser_fetch():
                logger.info(f"[fetch] HTTP {status_code} blocked on {url} - falling back to browser")
                result = fetch_html_with_browser(url, timeout=max(timeout, 60))
                _set_fetch_metadata(sess, status_code=200, final_url=result.final_url, blocked=False)
                return result.final_url, result.html
            logger.warning(f"[fetch] HTTP {status_code} blocked on {url} - browser fallback disabled")
            raise requests.HTTPError(f"blocked by anti-bot challenge ({status_code})", response=r)
        r.raise_for_status()
        return (final_url, html)
    except Exception as exc:
        if should_use_browser_fetch() and not isinstance(exc, (KeyboardInterrupt, SystemExit)):
            logger.info(f"[fetch] HTTP error ({type(exc).__name__}) on {url} - falling back to browser")
            try:
                result = fetch_html_with_browser(url, timeout=max(timeout, 60))
                _set_fetch_metadata(sess, status_code=200, final_url=result.final_url, blocked=False)
                return result.final_url, result.html
            except Exception as browser_exc:
                logger.error(f"[fetch] Browser fallback failed for {url}: {browser_exc}")
        error = f'{type(exc).__name__}: {exc}'
        status_code = getattr(sess, 'mobilesentrix_last_status', None)
        final_url = getattr(sess, 'mobilesentrix_last_url', url)
        blocked = bool(getattr(sess, 'mobilesentrix_blocked', False))
        _set_fetch_metadata(sess, status_code=status_code, final_url=final_url, error=error, blocked=blocked)
        raise


def get_html_safe(sess, url: str, delay_ms: int):
    """Fetch HTML with delay and error handling. Returns (url, html) or (None, error)"""
    if delay_ms:
        time.sleep(delay_ms / 1000.0)
    try:
        return get_html(sess, url)
    except Exception as e:
        error = f'{type(e).__name__}: {e}'
        _set_fetch_metadata(
            sess,
            status_code=getattr(sess, 'mobilesentrix_last_status', None),
            final_url=getattr(sess, 'mobilesentrix_last_url', url),
            error=error,
            blocked=bool(getattr(sess, 'mobilesentrix_blocked', False)),
        )
        return None, error


# -------- HTML Parsing Utilities --------

def find_jsonld_products(soup: BeautifulSoup) -> List[dict]:
    """Extract Product schema from JSON-LD structured data"""
    out = []
    for tag in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(tag.string or tag.get_text() or '')
        except Exception:
            continue

        if isinstance(data, dict):
            candidates = [data]
        elif isinstance(data, list):
            candidates = data
        else:
            continue

        for obj in candidates:
            if isinstance(obj, dict) and (obj.get('@type') == 'Product'):
                out.append(obj)
            if isinstance(obj, dict) and isinstance(obj.get('@graph'), list):
                for g in obj['@graph']:
                    if isinstance(g, dict) and g.get('@type') == 'Product':
                        out.append(g)

    return out


def price_from_offers(offers) -> Tuple[Optional[float], Optional[str]]:
    """Extract price and currency from offers object in JSON-LD"""
    if isinstance(offers, dict):
        price = offers.get('price')
        currency = offers.get('priceCurrency')
        try:
            return float(price), currency
        except Exception:
            return parse_price_number(str(price)), currency

    if isinstance(offers, list):
        for off in offers:
            v, c = price_from_offers(off)
            if v is not None:
                return v, c

    return None, None


def availability_from_offers(offers) -> str:
    """Extract stock availability text from Product schema offers."""
    if isinstance(offers, dict):
        availability = clean_text(offers.get('availability') or '')
        if availability:
            return availability
    if isinstance(offers, list):
        for off in offers:
            availability = availability_from_offers(off)
            if availability:
                return availability
    return ""


def normalize_availability_text(value: Optional[str]) -> str:
    """Normalize common stock values while preserving meaningful quantity text."""
    text = clean_text(value)
    if not text:
        return ""
    lower = text.lower()
    if 'instock' in lower or lower.endswith('/instock'):
        return "In Stock"
    if 'outofstock' in lower or lower.endswith('/outofstock'):
        return "Out of Stock"
    if 'preorder' in lower or lower.endswith('/preorder'):
        return "Preorder"
    if 'backorder' in lower or lower.endswith('/backorder'):
        return "Backorder"
    return text


def extract_title(soup: BeautifulSoup) -> str:
    """Extract product title from page"""
    for sel in ['h1.page-title .base', 'span[data-ui-id="page-title-wrapper"]', 'h1.product', 'h1']:
        el = soup.select_one(sel)
        if el:
            t = clean_text(el.get_text())
            if t:
                return t

    og = soup.select_one('meta[property="og:title"]')
    if og and og.get('content'):
        return clean_text(og['content'])

    return ""


def extract_canonical_or_og_url(soup: BeautifulSoup, fallback: str) -> str:
    """Extract canonical URL or og:url meta tag"""
    can = soup.select_one('link[rel="canonical"]')
    if can and can.get('href'):
        return can['href']

    og = soup.select_one('meta[property="og:url"]')
    if og and og.get('content'):
        return og['content']

    return fallback


def extract_price(soup: BeautifulSoup) -> Tuple[Optional[float], str, str]:
    """
    Extract price from page using various selectors.
    Returns (price_value, currency, source_selector)
    """
    el = soup.select_one('[data-price-amount]')
    if el and el.get('data-price-amount'):
        try:
            v = float(el['data-price-amount'])
            return v, '', 'data-price-amount'
        except Exception:
            pass

    for sel in (
        'meta[itemprop="price"]',
        '[itemprop="price"][content]',
        'span[itemprop="price"][content]',
    ):
        el = soup.select_one(sel)
        if not el:
            continue
        v = parse_price_number(el.get('content', ''))
        if v is not None:
            return v, '', sel

    for sel in [
        'span.price-final_price [data-price-amount]',
        'span.price-final_price span.price',
        'div.price-box [data-price-amount]',
        'div.price-box span.price',
        'span[id^="product-price-"] [data-price-amount]',
        'span[id^="product-price-"] span.price',
        'span.price',
        '[class*="price"]', '[id*="price"]'
    ]:
        for e in soup.select(sel):
            txt = clean_text(e.get_text())
            v = parse_price_number(txt)
            if v is not None:
                return v, '', sel

    return None, '', ''


def extract_image_url(container: BeautifulSoup) -> str:
    """Extract the best product image URL from a page fragment."""
    return extract_best_image_url(container)


def _pick_last_srcset_url(value: str) -> str:
    """Prefer the largest candidate from a srcset-like attribute."""
    if not value:
        return ""
    parts = [segment.strip() for segment in str(value).split(',') if segment.strip()]
    if not parts:
        return ""
    return parts[-1].split()[0].strip()


def _read_image_candidate_url(el) -> str:
    """Read the most useful image-like URL from an element."""
    if not el:
        return ""
    for attr in ('data-zoom', 'data-srcset', 'srcset', 'data-src', 'data-lazy-src', 'data-original', 'src', 'content'):
        value = el.get(attr)
        if not value:
            continue
        if 'srcset' in attr:
            return _pick_last_srcset_url(value)
        return str(value).strip()
    return ""


def _is_decorative_image_candidate(image_url: str, el) -> bool:
    """Reject logos, badges, swatches, and other non-product artwork."""
    if not image_url:
        return True

    lower_url = image_url.lower()
    if lower_url.startswith('data:'):
        return True

    attrs = [
        el.get('alt', ''),
        el.get('title', ''),
        ' '.join(el.get('class', []) if hasattr(el, 'get') else []),
    ]
    hint_text = ' '.join(str(value or '') for value in attrs).lower()
    combined = f"{lower_url} {hint_text}"

    decorative_markers = (
        'badge', 'badges', 'opt-badges', 'color_badges', 'color-badges',
        'logo', 'icon', 'sprite', 'placeholder', 'no-image', 'no_image',
        'swatch', 'wishlist', 'cart.svg', 'user.svg', 'search-white',
        'arrow-right', 'truck.svg', 'loader', 'spinner', 'recently-img',
        'calogo', 'top-cmn-img', 'casper-',
    )
    return any(marker in combined for marker in decorative_markers)


def _score_image_candidate(selector: str, image_url: str, el) -> int:
    """Prefer product gallery images over generic page artwork."""
    score = 0
    lower_url = image_url.lower()
    lower_selector = selector.lower()
    classes = ' '.join(el.get('class', []) if hasattr(el, 'get') else []).lower()

    if lower_selector.startswith('meta['):
        score += 120
    if any(token in lower_selector for token in (
        'data-zoom', 'product-detail-gallery', 'gallery', 'woocommerce-product-gallery',
        'fotorama', 'wp-post-image', 'product-image-photo', 'product-item-photo'
    )):
        score += 80
    if any(token in classes for token in ('tf-image-zoom-inner', 'wp-post-image', 'product-image-photo', 'product-item-photo')):
        score += 60
    if any(token in lower_url for token in ('/catalog/product/', '/uploads/', '/assets/products/', '/pub/media/catalog/product/')):
        score += 40
    if lower_url.endswith('.svg'):
        score -= 60
    return score


def extract_best_image_url(container: BeautifulSoup, base_url: str = "") -> str:
    """Scan known image locations and return the strongest non-decorative candidate."""
    if not container:
        return ""

    selectors = (
        'meta[property="og:image"]',
        'meta[name="twitter:image"]',
        'img[data-zoom]',
        '.product-detail-gallery img',
        '.woocommerce-product-gallery__image img',
        '.gallery-placeholder img',
        '.product.media img',
        '.fotorama img',
        'img.wp-post-image',
        'img.product-image-photo',
        '.product-image img',
        'a.product-image img',
        'img[data-srcset]',
        'img[srcset]',
        'img[data-src]',
        'img[src]',
    )

    best_url = ""
    best_score = -10_000
    seen_urls = set()

    for order, selector in enumerate(selectors):
        for el in container.select(selector):
            raw_url = _read_image_candidate_url(el)
            if not raw_url:
                continue
            image_url = urljoin(base_url, raw_url).strip() if base_url else raw_url.strip()
            if not image_url or image_url in seen_urls:
                continue
            seen_urls.add(image_url)
            if _is_decorative_image_candidate(image_url, el):
                continue

            score = _score_image_candidate(selector, image_url, el) - order
            if score > best_score:
                best_score = score
                best_url = image_url

    return best_url


def _extract_text_from_element(el) -> str:
    if not el:
        return ""
    for attr in ('content', 'value', 'data-product-sku', 'data-sku', 'data-product_sku'):
        if el.get(attr):
            return clean_text(el.get(attr))
    return clean_text(el.get_text(' ', strip=True))


def extract_sku(soup: BeautifulSoup, jsonld_products: Optional[List[dict]] = None) -> str:
    """Extract SKU from structured data or common product page selectors."""
    jsonld_products = jsonld_products or find_jsonld_products(soup)
    for obj in jsonld_products:
        sku = clean_text(obj.get('sku') or obj.get('mpn') or '')
        if sku:
            return sku

    for sel in (
        '[itemprop="sku"]',
        '.product.attribute.sku .value',
        '.product-info-stock-sku .sku .value',
        '.sku_wrapper .sku',
        '.sku',
        '[data-product-sku]',
        '[data-product_sku]',
    ):
        el = soup.select_one(sel)
        text = _extract_text_from_element(el)
        if text and text.lower() not in {'sku', 'n/a'}:
            if text.lower().startswith('sku '):
                text = clean_text(text[4:])
            return text

    page_text = clean_text(soup.get_text(' ', strip=True))
    sku_match = re.search(r'\bsku\b\s*[:#-]?\s*([A-Za-z0-9._/-]{3,})', page_text, re.I)
    return clean_text(sku_match.group(1)) if sku_match else ""


def extract_description(soup: BeautifulSoup, jsonld_products: Optional[List[dict]] = None) -> str:
    """Extract product description from detail page containers."""
    jsonld_products = jsonld_products or find_jsonld_products(soup)
    for obj in jsonld_products:
        description = strip_markup(obj.get('description') or '')
        if description:
            return description

    for sel in (
        '.product.attribute.description .value',
        '.product.attribute.overview .value',
        '.woocommerce-product-details__short-description',
        '.woocommerce-Tabs-panel--description',
        '#tab-description',
        '[itemprop="description"]',
        'meta[name="description"]',
    ):
        el = soup.select_one(sel)
        if not el:
            continue
        if el.name == 'meta':
            text = strip_markup(el.get('content', ''))
        else:
            text = strip_markup(el.get_text(' ', strip=True))
        if text:
            return text
    return ""


def extract_stock_status(soup: BeautifulSoup, jsonld_products: Optional[List[dict]] = None) -> str:
    """Extract stock or availability text from the detail page."""
    for sel in (
        '.product-info-stock-sku .stock',
        '.stock',
        '.availability',
        '.inventory-status',
        '[class*="stock"]',
    ):
        for el in soup.select(sel):
            text = clean_text(el.get_text(' ', strip=True))
            lower = text.lower()
            if text and any(term in lower for term in ('stock', 'available', 'pre-order', 'preorder', 'backorder')):
                return normalize_availability_text(text)

    page_html = str(soup)
    if 'out-of-stock' in page_html or 'outofstock' in page_html:
        return "Out of Stock"
    if 'in-stock' in page_html or 'instock' in page_html:
        return "In Stock"

    jsonld_products = jsonld_products or find_jsonld_products(soup)
    for obj in jsonld_products:
        availability = normalize_availability_text(availability_from_offers(obj.get('offers')))
        if availability:
            return availability
    return ""


def extract_product_detail_snapshot(soup: BeautifulSoup, final_url: str) -> Dict[str, object]:
    """Build a normalized product snapshot from a detail page."""
    host = urlparse(final_url).hostname or ''
    jsonld_products = find_jsonld_products(soup)

    title = ""
    price_val = None
    currency = None
    source = "product"

    if jsonld_products:
        obj = jsonld_products[0]
        title = clean_text(obj.get('name') or '')
        pv, cur = price_from_offers(obj.get('offers'))
        if pv is not None:
            price_val, currency, source = pv, cur, "jsonld"

    if not title:
        title = extract_title(soup)
    if price_val is None:
        pv, cur, src = extract_price(soup)
        price_val, currency = pv, cur or currency
        if pv is not None:
            source = src

    image_url = extract_best_image_url(soup, final_url)
    sku = extract_sku(soup, jsonld_products)
    description = extract_description(soup, jsonld_products)
    stock_status = extract_stock_status(soup, jsonld_products)

    return {
        'url': extract_canonical_or_og_url(soup, final_url),
        'site': host,
        'title': title or '',
        'price_value': price_val,
        'price_currency': currency or host_currency(host),
        'price_text': '' if price_val is not None else 'price_not_found_or_hidden',
        'source': source,
        'image_url': image_url,
        'sku': sku,
        'stock_status': stock_status,
        'description': description,
    }


def enrich_item_details(sess, item: Item, rules: Optional[Dict] = None, logger=None) -> Item:
    """Fetch a product detail page and merge richer metadata into an existing item."""
    if not getattr(item, 'url', ''):
        return item

    try:
        # The caller controls the fetch mode. Automation starts with the fast
        # Safari HTTP path and may explicitly retry this method in a browser
        # context when the supplier blocks or omits dynamic SKU markup.
        final_url, html = get_html(sess, item.url, timeout=5)
        soup = BeautifulSoup(html, PARSER)
        detail = extract_product_detail_snapshot(soup, final_url)

        if detail.get('url'):
            item.url = detail['url']
        if detail.get('site'):
            item.site = detail['site']
        if detail.get('title'):
            item.title = detail['title']
        if detail.get('image_url'):
            item.image_url = detail['image_url']
        if detail.get('sku'):
            item.sku = detail['sku']
        if detail.get('stock_status'):
            item.stock_status = detail['stock_status']
        if detail.get('description'):
            item.description = detail['description']

        price_val = detail.get('price_value')
        if price_val is not None:
            percent_off = float((rules or {}).get('percent_off') or 0.0)
            absolute_off = float((rules or {}).get('absolute_off') or 0.0)
            add_percent = float((rules or {}).get('add_percent') or 0.0)
            final_price = apply_rules(price_val, percent_off, absolute_off, add_percent)
            item.price_value = price_val
            item.price_currency = detail.get('price_currency') or item.price_currency or host_currency(item.site)
            item.price_text = detail.get('price_text', '') or ''
            item.discounted_value = final_price
            item.discounted_formatted = fmt_price(final_price, item.price_currency, item.site) if final_price is not None else ''
            item.original_formatted = fmt_price(price_val, item.price_currency, item.site)

        if isinstance(item.extra, dict):
            item.extra.update({
                'sku': item.sku,
                'stock_status': item.stock_status,
                'description': item.description,
            })
        return item
    except Exception as exc:
        if logger:
            logger.warning(f"[detail] Failed to enrich {getattr(item, 'url', '')}: {exc}")
        return item


def is_product_page(soup: BeautifulSoup) -> bool:
    """Detect if page is a product detail page without matching category headings."""
    if soup.select_one(
        'form#product_addtocart_form, .product-info-main, .product-detail-right, '
        '.product-info-stock-sku, .product.media, '
        '[itemprop="sku"], meta[itemprop="price"], [itemprop="price"][content]'
    ):
        return True

    og_type = soup.select_one('meta[property="og:type"]')
    if og_type and clean_text(og_type.get('content', '')).lower() == 'product':
        return True

    jsonld_products = find_jsonld_products(soup)
    if jsonld_products and not is_category_page(soup):
        return True

    return False


def is_category_page(soup: BeautifulSoup) -> bool:
    """Detect if page is a category/listing page"""
    return bool(soup.select_one('ul.product-listing li.item')) or \
           bool(soup.select_one('ol.products li.product-item')) or \
           bool(soup.select_one('div.product-item-info, div.product-card, li.product'))


def find_next_page_url(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """
    Find next page URL for pagination.
    Handles both traditional pagination links and query parameter pagination.
    """
    # Check for traditional pagination links first
    cand = soup.select_one('li.pages-item-next a, a.action.next, a[rel="next"], .pages .next')
    if cand and cand.get('href'):
        return urljoin(base_url, cand['href'])

    # For MobileSentrix specifically, try to detect pagination patterns
    parsed = urlparse(base_url)
    query_params = parse_qs(parsed.query)

    # Get current page number (default to 1)
    current_page = int(query_params.get('p', ['1'])[0])

    # Look for pagination indicators in the page
    products = soup.select('ul.product-listing li.item')

    if products:
        # Look for pagination info or toolbar
        toolbar = soup.select('.toolbar-amount, .limiter, .pages-items, .pagination')
        if toolbar:
            toolbar_text = ' '.join([t.get_text() for t in toolbar])
            # Check for patterns like "1-48 of 150"
            if 'of' in toolbar_text.lower():
                match = re.search(r'(\d+)-(\d+)\s+of\s+(\d+)', toolbar_text)
                if match:
                    end_item = int(match.group(2))
                    total_items = int(match.group(3))
                    if end_item < total_items:
                        # There are more items, construct next page URL
                        query_params['p'] = [str(current_page + 1)]
                        new_query = urlencode(query_params, doseq=True)
                        return urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                                         parsed.params, new_query, parsed.fragment))

        # If no clear pagination indicator but we have products, try next page anyway
        if len(products) >= 20:
            query_params['p'] = [str(current_page + 1)]
            new_query = urlencode(query_params, doseq=True)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path,
                             parsed.params, new_query, parsed.fragment))

    return None


# -------- Main Scraping Functions --------

def scrape_product(sess, final_url: str, html: str, rules: Dict) -> List[Item]:
    """
    Scrape a single product page.
    Returns list with one Item.
    """
    host = urlparse(final_url).hostname or ''
    soup = BeautifulSoup(html, PARSER)
    final_url = extract_canonical_or_og_url(soup, final_url)

    detail = extract_product_detail_snapshot(soup, final_url)
    price_val = detail['price_value']
    currency = detail['price_currency']
    source = detail['source']

    # Apply discount rules
    percent_off = float(rules.get('percent_off') or 0.0)
    absolute_off = float(rules.get('absolute_off') or 0.0)
    add_percent = float(rules.get('add_percent') or 0.0)
    final_price = apply_rules(price_val, percent_off, absolute_off, add_percent)

    return [Item(
        url=detail['url'],
        site=detail['site'] or host,
        title=detail['title'] or '',
        price_value=price_val,
        price_currency=currency or host_currency(host),
        price_text=detail['price_text'],
        discounted_value=final_price,
        discounted_formatted=fmt_price(final_price, currency, host) if final_price is not None else '',
        original_formatted=fmt_price(price_val, currency, host),
        source=source,
        image_url=detail['image_url'],
        sku=detail['sku'],
        stock_status=detail['stock_status'],
        description=detail['description'],
        extra={
            'sku': detail['sku'],
            'stock_status': detail['stock_status'],
            'description': detail['description'],
        }
    )]


def scrape_category_page(sess, final_url: str, html: str, rules: Dict, logger=None) -> List[Item]:
    """
    Scrape a category/listing page (single page, no pagination).
    Returns list of Items found on the page.
    """
    host = urlparse(final_url).hostname or ''
    soup = BeautifulSoup(html, PARSER)
    out: List[Item] = []

    # Find product cards
    cards = soup.select('ul.product-listing li.item')
    if not cards:
        cards = soup.select('ol.products li.product-item, div.product-item-info, div.product-card, li.product')
    if logger:
        logger.info(f"[mobilesentrix] Product card selector count={len(cards)} url={final_url}")

    percent_off = float(rules.get('percent_off') or 0.0)
    absolute_off = float(rules.get('absolute_off') or 0.0)

    for card in cards:
        a = card.select_one('a[href]')
        if not a:
            continue

        title = clean_text(a.get_text())
        href = a.get('href') or ''
        prod_url = urljoin(final_url, href)
        image = extract_best_image_url(card, final_url)

        # Extract price
        price_val = None
        price_text = ''
        pel = card.select_one('[data-price-amount]')
        if pel and pel.get('data-price-amount'):
            try:
                price_val = float(pel['data-price-amount'])
            except Exception:
                price_val = None

        if price_val is None:
            pt_el = card.select_one('.price, .price-final_price .price, [class*="price"]')
            price_text = clean_text(pt_el.get_text()) if pt_el else ''
            price_val = parse_price_number(price_text)

        add_percent = float(rules.get('add_percent') or 0.0)
        final_price = apply_rules(price_val, percent_off, absolute_off, add_percent)

        out.append(Item(
            url=prod_url,
            site=host,
            title=title or '',
            price_value=price_val,
            price_currency=host_currency(host),
            price_text=price_text if price_val is None else '',
            discounted_value=final_price,
            discounted_formatted=fmt_price(final_price, None, host) if final_price is not None else '',
            original_formatted=fmt_price(price_val, None, host),
            source='category-card',
            image_url=image
        ))

    if logger:
        logger.info(f"[mobilesentrix] Product count found={len(out)} url={final_url}")
    return out


def scrape_category_all_pages(sess, start_url: str, rules: Dict, max_pages: int = 10,  # Reduced default from 20 to 10
                              delay_ms: int = 50, logger=None, initial_pair: Optional[Tuple[str, str]] = None):
    """
    Scrape a category with pagination support.
    Automatically follows 'Next' links up to max_pages.
    Tracks seen products to avoid duplicates.
    """
    items: List[Item] = []
    seen_urls: Set[str] = set()
    seen_products: Set[str] = set()
    url = start_url
    pages = 0
    consecutive_empty_pages = 0

    # Stop if: reached max_pages OR found 2 consecutive pages with NO new items
    while url and pages < max_pages and consecutive_empty_pages < 2:
        pages += 1
        if logger:
            logger.info(f"[mobilesentrix] Scraping category page {pages}: {url}")

        pair = initial_pair if pages == 1 and initial_pair is not None else get_html_safe(sess, url, delay_ms)
        initial_pair = None
        if pair[0] is None:
            if logger:
                logger.error(
                    f"[mobilesentrix] Request failed url={url} "
                    f"status={getattr(sess, 'mobilesentrix_last_status', None)} "
                    f"error={pair[1]}"
                )
            # Fetch failed - add error item
            items.append(Item(
                url=url,
                site=urlparse(url).hostname or '',
                title='',
                price_value=None,
                price_currency=None,
                price_text=f'fetch_failed: {pair[1]}',
                discounted_value=None,
                discounted_formatted='',
                original_formatted='',
                source='error',
                image_url=''
            ))
            break

        final_url, html = pair
        if logger:
            logger.info(
                f"[mobilesentrix] Response status={getattr(sess, 'mobilesentrix_last_status', None)} "
                f"url={url} final_url={final_url} bytes={len(html)}"
            )
        soup = BeautifulSoup(html, PARSER)

        # Get products from this page
        page_items = scrape_category_page(sess, final_url, html, rules, logger=logger)

        # Check for new products
        new_products_found = 0
        for item in page_items:
            if item.url not in seen_products:
                seen_products.add(item.url)
                items.append(item)
                new_products_found += 1

        if logger:
            logger.info(f"[mobilesentrix] Page {pages}: found={len(page_items)} new={new_products_found}")

        # If no new products found, increment counter
        if new_products_found == 0:
            consecutive_empty_pages += 1
            if logger:
                logger.info(f"[mobilesentrix] No new products on page {pages}; empty_pages={consecutive_empty_pages}")
        else:
            consecutive_empty_pages = 0

        # Mark this URL as seen
        seen_urls.add(final_url)

        # Find next page
        nxt = find_next_page_url(soup, final_url)

        # Free memory
        del html
        del soup

        if not nxt or nxt in seen_urls:
            if logger:
                logger.info("[mobilesentrix] No more pages found or URL already visited")
            break

        url = nxt

    if logger:
        logger.info(f"[mobilesentrix] Finished scraping after {pages} page(s); total_unique_items={len(items)}")

    return items


def scrape_url(sess, url: str, rules: Dict, crawl_pagination: bool,
              max_pages: int, delay_ms: int, logger=None) -> List[Item]:
    """
    Main entry point for scraping a URL.
    Automatically detects if it's a product or category page.
    """
    started_at = time.strftime('%Y-%m-%d %H:%M:%S')
    if logger:
        logger.info(f"[mobilesentrix] Scraper started_at={started_at} url={url}")

    pair = get_html_safe(sess, url, delay_ms=0)
    if pair[0] is None:
        if logger:
            logger.error(
                f"[mobilesentrix] Request failed url={url} "
                f"status={getattr(sess, 'mobilesentrix_last_status', None)} "
                f"error={pair[1]}"
            )
        return [Item(
            url=url,
            site=urlparse(url).hostname or '',
            title='',
            price_value=None,
            price_currency=None,
            price_text=f'fetch_failed: {pair[1]}',
            discounted_value=None,
            discounted_formatted='',
            original_formatted='',
            source='error',
            image_url=''
        )]

    final_url, html = pair
    if logger:
        logger.info(
            f"[mobilesentrix] Response status={getattr(sess, 'mobilesentrix_last_status', None)} "
            f"url={url} final_url={final_url} bytes={len(html)}"
        )
    soup = BeautifulSoup(html, PARSER)
    page_is_product = is_product_page(soup)
    page_is_category = is_category_page(soup)
    if logger:
        logger.info(
            f"[mobilesentrix] Page classification url={final_url} "
            f"is_product={page_is_product} is_category={page_is_category}"
        )

    if page_is_product:
        items = scrape_product(sess, final_url, html, rules)
        if logger:
            logger.info(f"[mobilesentrix] Product count found={len(items)} url={final_url}")
        return items

    if page_is_category:
        if crawl_pagination:
            items = scrape_category_all_pages(sess, final_url, rules,
                                             max_pages=max_pages, delay_ms=delay_ms, logger=logger,
                                             initial_pair=(final_url, html))
        else:
            items = scrape_category_page(sess, final_url, html, rules, logger=logger)
        if logger:
            logger.info(f"[mobilesentrix] Scraper finished url={final_url} product_count={len(items)}")
        return items

    # Default: treat as product page
    if logger:
        logger.warning(f"[mobilesentrix] Page type unclear; treating as product url={final_url}")
    items = scrape_product(sess, final_url, html, rules)
    if logger:
        logger.info(f"[mobilesentrix] Product count found={len(items)} url={final_url}")
    return items


def scrape_urls_parallel(urls: List[str], rules: Dict, crawl_pagination: bool,
                        max_pages: int, delay_ms: int, retries: int,
                        verify_ssl: bool, use_curl: bool, max_workers: int = 3, logger=None) -> List[Item]:
    """
    Scrape multiple URLs in parallel for faster processing.
    Each URL gets its own session to avoid threading conflicts.
    """
    all_items: List[Item] = []

    def scrape_single_url(url: str) -> List[Item]:
        # Each thread gets its own session
        sess, _ = build_session(retries=retries, verify_ssl=verify_ssl, use_curl=use_curl)
        return scrape_url(sess, url, rules, crawl_pagination, max_pages, delay_ms, logger)

    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all URL scraping tasks
        future_to_url = {executor.submit(scrape_single_url, url): url for url in urls}

        # Collect results as they complete
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                items = future.result()
                all_items.extend(items)
                if logger:
                    logger.info(f"Completed scraping {url}: {len(items)} items")
            except Exception as e:
                if logger:
                    logger.error(f"Error scraping {url}: {e}")
                # Add error item
                all_items.append(Item(
                    url=url,
                    site=urlparse(url).hostname or '',
                    title='',
                    price_value=None,
                    price_currency=None,
                    price_text=f'parallel_scrape_failed: {e}',
                    discounted_value=None,
                    discounted_formatted='',
                    original_formatted='',
                    source='error',
                    image_url=''
                ))

    return all_items
