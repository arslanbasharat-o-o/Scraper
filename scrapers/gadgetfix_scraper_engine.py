"""GadgetFix scraper engine for gadgetfix.com."""

from __future__ import annotations
import threading
_CURL_LOCK = threading.Lock()

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .browser_fetcher import fetch_html as fetch_html_with_browser, should_use_browser_fetch, browser_fetch_requested
from .sku_utils import extract_jsonld_sku, clean_sku

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL = True
except Exception:
    HAS_CURL = False


@dataclass
class Item:
    title: str = ""
    url: str = ""
    image_url: str = ""
    original: float = 0.0
    discounted: float = 0.0
    original_formatted: str = "$0.00"
    discounted_formatted: str = "$0.00"
    site: str = "gadgetfix.com"
    sku: str = ""
    stock_status: str = "In Stock"
    description: str = ""
    extra: dict = field(default_factory=dict)


def clean_text(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def strip_markup(text: str) -> str:
    if not text:
        return ""
    text = str(text)
    if '<' not in text or '>' not in text:
        return clean_text(text)
    try:
        return clean_text(BeautifulSoup(text, 'html.parser').get_text(' ', strip=True))
    except Exception:
        return clean_text(text)


def parse_price_number(price_str: str) -> float:
    match = re.search(r'\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})|[0-9]+(?:\.[0-9]{1,2})?)', str(price_str or ''))
    if not match:
        return 0.0
    try:
        return float(match.group(1).replace(',', ''))
    except ValueError:
        return 0.0


def fmt_price(value: float) -> str:
    return f"${float(value or 0.0):.2f}"


def apply_price_rules(price: float, rules: dict | None = None) -> float:
    value = float(price or 0.0)
    rules = rules or {}
    add_percent = float(rules.get('add_percent') or 0.0)
    percent_off = float(rules.get('percent_off') or 0.0)
    absolute_off = float(rules.get('absolute_off') or 0.0)
    if add_percent > 0:
        value *= 1 + add_percent / 100.0
    if percent_off > 0:
        value *= 1 - percent_off / 100.0
    if absolute_off > 0:
        value -= absolute_off
    return round(max(0.0, value), 2)


def build_session(retries: int = 2, verify_ssl: bool = True, use_curl: bool = True) -> tuple:
    if use_curl and HAS_CURL:
        try:
            with _CURL_LOCK:
                session = curl_requests.Session(impersonate="safari15_5")
            session.verify = verify_ssl
            session.gadgetfix_blocked = False
            session.gadgetfix_last_error = ''
            return session, True
        except Exception:
            pass

    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retry = Retry(
        total=max(1, int(retries)),
        read=max(1, int(retries)),
        connect=max(1, int(retries)),
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(['GET', 'HEAD', 'OPTIONS']),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    session.verify = verify_ssl
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
    })
    session.gadgetfix_blocked = False
    session.gadgetfix_last_error = ''
    return session, False


def normalize_gadgetfix_url(url: str) -> str:
    raw = str(url or '').strip()
    parsed = urlparse(raw)
    if parsed.netloc.lower().replace('www.', '') == 'gadgetfix.com':
        return raw
    if parsed.netloc.lower().replace('www.', '') == 'm.gadgetfix.com':
        return raw.replace('://m.gadgetfix.com', '://gadgetfix.com', 1)
    return raw


def _looks_blocked(status_code: int, html: str) -> bool:
    sample = (html or '')[:30_000].lower()
    if int(status_code or 0) in {401, 403, 429}:
        return True
    return any(
        token in sample for token in ('<title>just a moment', '<title>attention required', 'id="challenge-form"', 'cf-browser-verification', 'performing security verification')
    )


def get_html(session, url: str, logger=None) -> Optional[str]:
    url = normalize_gadgetfix_url(url)
    session.gadgetfix_blocked = False
    session.gadgetfix_last_error = ''
    session.gadgetfix_last_status = 0

    if browser_fetch_requested():
        return fetch_html_with_browser(url, logger=logger).html
    if session is not None:
        try:
            r = session.get(url, timeout=25)
            session.gadgetfix_last_status = int(getattr(r, 'status_code', 0) or 0)
            if r.status_code == 200 and r.text and not _looks_blocked(200, r.text):
                return r.text
        except Exception:
            pass

    if should_use_browser_fetch():
        try:
            browser_html = fetch_html_with_browser(url, logger=logger, wait_seconds=3).html
            if not browser_html or _looks_blocked(200, browser_html):
                session.gadgetfix_blocked = True
                session.gadgetfix_last_error = "Fetch returned a blocked or empty page"
                if logger:
                    logger.warning(f"[gadgetfix] {session.gadgetfix_last_error}: {url}")
                return None
            return browser_html
        except Exception as exc:
            session.gadgetfix_blocked = True
            session.gadgetfix_last_error = str(exc)
            if logger:
                logger.warning(f"[gadgetfix] Fetch failed for {url}: {exc}")
            return None
    session.gadgetfix_blocked = True
    session.gadgetfix_last_error = "HTTP fetch returned a blocked or empty page"
    return None


def extract_canonical_url(soup: BeautifulSoup, fallback: str) -> str:
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and canonical.get('href'):
        return normalize_gadgetfix_url(canonical['href'])
    og_url = soup.select_one('meta[property="og:url"]')
    if og_url and og_url.get('content'):
        return normalize_gadgetfix_url(og_url['content'])
    return normalize_gadgetfix_url(fallback)


def is_product_url(url: str) -> bool:
    path = urlparse(str(url or '')).path.lower()
    return bool(path.endswith('.html') and '/category/' not in path and re.search(r'-\d+\.html$', path))


def is_product_page(soup: BeautifulSoup) -> bool:
    text = clean_text(soup.get_text(' ', strip=True)).lower()
    return bool(
        soup.select_one('[itemprop="sku"], .product-view, .product-essential, .product-shop')
        or ('availability:' in text and 'price:' in text and 'condition:' in text)
    )


def is_category_page(soup: BeautifulSoup) -> bool:
    return bool(soup.select('a[href*="/category/"], a[href$=".html"]') and not is_product_page(soup))


def _closest_product_container(anchor):
    for parent in anchor.parents:
        if not getattr(parent, 'name', None):
            continue
        if parent.name in {'li', 'article'}:
            return parent
        classes = ' '.join(parent.get('class', [])).lower()
        if any(token in classes for token in ('product', 'item', 'grid', 'cell')):
            return parent
    return anchor.parent or anchor


def _find_image(container, base_url: str) -> str:
    for image in container.select('img[src], img[data-src], img[data-original]'):
        raw = image.get('data-src') or image.get('data-original') or image.get('src') or ''
        if not raw:
            continue
        lowered = raw.lower()
        if any(token in lowered for token in ('logo', 'placeholder', 'loader', 'spinner', 'processing')):
            continue
        return urljoin(base_url, raw)
    return ""


def _find_price(container) -> float:
    for selector in ('.price', '[class*="price"]', '.regular-price', '.special-price'):
        for el in container.select(selector):
            value = parse_price_number(el.get_text(' ', strip=True))
            if value > 0:
                return value
    text = clean_text(container.get_text(' ', strip=True))
    prices = [parse_price_number(match.group(0)) for match in re.finditer(r'\$\s*\d+(?:,\d{3})*(?:\.\d{1,2})?', text)]
    prices = [price for price in prices if price > 0]
    return prices[0] if prices else 0.0


def extract_product_from_listing_anchor(anchor, base_url: str) -> Optional[Item]:
    href = anchor.get('href') or ''
    product_url = normalize_gadgetfix_url(urljoin(base_url, href))
    if not is_product_url(product_url):
        return None

    container = _closest_product_container(anchor)
    image = container.select_one('img[alt]') or anchor.select_one('img[alt]')
    title = clean_text(anchor.get('title') or anchor.get_text(' ', strip=True))
    if title.lower().startswith('image:') or not title:
        title = clean_text((image.get('alt') if image else '') or title).removeprefix('Image:').strip()
    if not title:
        return None

    item = Item(title=title, url=product_url)
    item.image_url = _find_image(container, base_url)
    price_val = _find_price(container)
    if price_val > 0:
        item.original = price_val
        item.discounted = price_val
        item.original_formatted = fmt_price(price_val)
        item.discounted_formatted = fmt_price(price_val)

    text = clean_text(container.get_text(' ', strip=True)).lower()
    if 'out of stock' in text or 'sold out' in text:
        item.stock_status = "Out of Stock"
    item.extra.update({'sku': item.sku, 'stock_status': item.stock_status, 'description': item.description})
    return item


def extract_items_from_soup(soup: BeautifulSoup, url: str, rules: dict, logger=None) -> List[Item]:
    items_by_url = {}
    anchors = soup.select('a[href$=".html"], a[href*=".html?"]')
    if logger:
        logger.info(f"[gadgetfix] Scanning {len(anchors)} catalog link(s) at {url}")

    for anchor in anchors:
        item = extract_product_from_listing_anchor(anchor, url)
        if not item:
            continue
        adjusted = apply_price_rules(item.original, rules)
        item.discounted = adjusted
        item.discounted_formatted = fmt_price(adjusted)
        items_by_url[item.url] = item

    return list(items_by_url.values())


def find_next_page_url(soup: BeautifulSoup, current_url: str) -> Optional[str]:
    next_link = (
        soup.find('a', string=re.compile(r'^\s*>>\s*$'))
        or soup.select_one('a.next[href], .pagination a.next[href], a[rel="next"][href]')
    )
    if next_link and next_link.get('href'):
        return normalize_gadgetfix_url(urljoin(current_url, next_link['href']))

    current_marker = clean_text(soup.get_text(' ', strip=True))
    match = re.search(r'\bPage:\s*(\d+)\s+(\d+)\b', current_marker)
    if match:
        current_page = int(match.group(1))
        next_page = current_page + 1
        page_anchor = soup.find('a', string=re.compile(rf'^\s*{next_page}\s*$'))
        if page_anchor and page_anchor.get('href'):
            return normalize_gadgetfix_url(urljoin(current_url, page_anchor['href']))
    return None


def scrape_category_page(session, url: str, rules: dict, logger=None) -> List[Item]:
    html = get_html(session, url, logger)
    if not html:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    return extract_items_from_soup(soup, url, rules, logger)


def scrape_category_all_pages(session, url: str, rules: dict, max_pages: int = 20, delay_ms: int = 200, logger=None) -> List[Item]:
    current_url = normalize_gadgetfix_url(url)
    seen_pages = set()
    items_by_url = {}
    page_num = 1

    while current_url and page_num <= max_pages and current_url not in seen_pages:
        seen_pages.add(current_url)
        html = get_html(session, current_url, logger)
        if not html:
            break
        soup = BeautifulSoup(html, 'html.parser')
        page_items = extract_items_from_soup(soup, current_url, rules, logger)
        for item in page_items:
            items_by_url[item.url] = item
        if not page_items:
            break

        next_url = find_next_page_url(soup, current_url)
        if not next_url:
            break
        current_url = next_url
        page_num += 1
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    if logger:
        logger.info(f"[gadgetfix] Total unique items scraped: {len(items_by_url)}")
    return list(items_by_url.values())


def scrape_product_page(session, url: str, rules: dict, logger=None) -> Optional[Item]:
    html = get_html(session, url, logger)
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')

    title = ''
    for title_el in soup.select('h1'):
        title = clean_text(title_el.get_text(' ', strip=True))
        if title:
            break
    if not title:
        title_meta = soup.select_one('meta[property="og:title"]')
        title = clean_text(title_meta.get('content') if title_meta else '')
    if not title:
        for title_el in soup.select('h2'):
            title = clean_text(title_el.get_text(' ', strip=True))
            if title:
                break
    if not title:
        return None

    item = Item(title=title, url=extract_canonical_url(soup, url))
    image = soup.select_one('meta[property="og:image"]') or soup.select_one('.product img[src], img[itemprop="image"], img[src]')
    if image:
        raw = image.get('content') or image.get('src') or image.get('data-src') or ''
        item.image_url = urljoin(url, raw) if raw else ''

    price_text = ''
    price_el = soup.select_one('[itemprop="price"], .price, [class*="price"]')
    if price_el:
        price_text = price_el.get('content') or price_el.get_text(' ', strip=True)
    if not price_text:
        match = re.search(r'Price:\s*(\$\s*\d+(?:,\d{3})*(?:\.\d{1,2})?)', soup.get_text(' ', strip=True), re.I)
        price_text = match.group(1) if match else ''
    price_val = parse_price_number(price_text)
    if price_val > 0:
        item.original = price_val
        item.discounted = apply_price_rules(price_val, rules)
        item.original_formatted = fmt_price(price_val)
        item.discounted_formatted = fmt_price(item.discounted)

    page_text = clean_text(soup.get_text(' ', strip=True))
    sku_match = re.search(r'\bItem:\s*([A-Za-z0-9._/-]+)', page_text, re.I)
    if sku_match:
        item.sku = clean_sku(sku_match.group(1))
    if not item.sku:
        item.sku = extract_jsonld_sku(soup, item.url)
    stock_match = re.search(r'\bAvailability:\s*([^:]+?)(?:\s+Brand:|\s+Compatible with:|\s+What you get:|$)', page_text, re.I)
    if stock_match:
        item.stock_status = clean_text(stock_match.group(1))
    elif 'out of stock' in page_text.lower():
        item.stock_status = "Out of Stock"

    description_parts = []
    for label in ('Compatible with:', 'What you get:'):
        idx = page_text.lower().find(label.lower())
        if idx >= 0:
            description_parts.append(page_text[idx:idx + 300])
    meta = soup.select_one('meta[name="description"]')
    if meta and meta.get('content'):
        description_parts.append(strip_markup(meta.get('content', '')))
    item.description = clean_text(' '.join(dict.fromkeys(description_parts)))
    item.extra.update({'sku': item.sku, 'stock_status': item.stock_status, 'description': item.description})
    return item


def enrich_item_details(session, item: Item, rules: dict | None = None, logger=None) -> Item:
    detail = scrape_product_page(session, item.url, rules or {}, logger)
    if not detail:
        return item
    item.url = detail.url or item.url
    item.title = detail.title or item.title
    item.image_url = detail.image_url or item.image_url
    if detail.original > 0:
        item.original = detail.original
        item.discounted = detail.discounted
        item.original_formatted = detail.original_formatted
        item.discounted_formatted = detail.discounted_formatted
    item.sku = detail.sku or item.sku
    item.stock_status = detail.stock_status or item.stock_status
    item.description = detail.description or item.description
    if isinstance(item.extra, dict):
        item.extra.update(detail.extra)
    return item


def scrape_url(session, url: str, rules: dict, crawl_pagination: bool = True,
               max_pages: int = 20, delay_ms: int = 200, logger=None) -> List[Item]:
    url = normalize_gadgetfix_url(url)
    if logger:
        logger.info(f"[gadgetfix] Starting scrape of: {url}")

    if is_product_url(url):
        item = scrape_product_page(session, url, rules, logger)
        return [item] if item else []

    if crawl_pagination:
        return scrape_category_all_pages(session, url, rules, max_pages=max_pages, delay_ms=delay_ms, logger=logger)
    return scrape_category_page(session, url, rules, logger)
