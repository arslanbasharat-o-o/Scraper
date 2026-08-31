"""PhoneLCDParts scraper engine for phonelcdparts.com."""

from __future__ import annotations
import threading
_CURL_LOCK = threading.Lock()

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .browser_fetcher import fetch_html as fetch_html_with_browser, should_use_browser_fetch

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
    site: str = "phonelcdparts.com"
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


def parse_price(price_str: str) -> float:
    clean = re.sub(r'[^\d.]', '', str(price_str or ''))
    try:
        return float(clean) if clean else 0.0
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
        backoff_factor=0.4,
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
    return session, False


def _looks_like_block_page(html: str) -> bool:
    sample = (html or '').strip().lower()
    if not sample:
        return True
    if len(sample) < 500 and any(marker in sample for marker in ('forbidden', 'access denied', '403')):
        return True
    head = sample[:30_000]
    return any(marker in head for marker in (
        '<title>just a moment',
        '<title>attention required',
        'id="challenge-form"',
        "id='challenge-form'",
        'cf-browser-verification',
        'performing security verification',
        'enable javascript and cookies to continue',
    ))


def get_html(session, url: str, logger=None) -> Optional[str]:
    """Fetch HTML with Safari TLS curl_cffi session, fallback to browser if blocked."""
    if session is not None:
        try:
            r = session.get(url, timeout=25)
            if r.status_code == 200 and r.text and not _looks_like_block_page(r.text):
                return r.text
        except Exception:
            pass
    if should_use_browser_fetch():
        try:
            browser_html = fetch_html_with_browser(url, logger=logger).html
            if browser_html and not _looks_like_block_page(browser_html):
                return browser_html
        except Exception as exc:
            if logger:
                logger.warning(f"[phonelcdparts] Fetch failed for {url}: {exc}")
    return None


def extract_canonical_url(soup: BeautifulSoup, fallback: str) -> str:
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and canonical.get('href'):
        return canonical['href']
    og_url = soup.select_one('meta[property="og:url"]')
    if og_url and og_url.get('content'):
        return og_url['content']
    return fallback


def is_product_page(soup: BeautifulSoup) -> bool:
    body_classes = ' '.join(soup.body.get('class', []) if soup.body else [])
    return bool(
        'catalog-product-view' in body_classes
        or soup.select_one('#product_addtocart_form, .product-info-main, .product.media, [itemprop="sku"]')
        or soup.select_one('meta[property="og:type"][content="product"]')
    )


def is_category_page(soup: BeautifulSoup) -> bool:
    body_classes = ' '.join(soup.body.get('class', []) if soup.body else [])
    if 'catalog-product-view' in body_classes:
        return False
    return bool(
        'catalog-category-view' in body_classes
        or soup.select('li.item.product.product-item, li.product-item, form.item.product.product-item, .product_addtocart_form')
        or soup.select_one('.toolbar-amount, .pages, .products-grid')
    )


def _best_title_from_card(card, link, image) -> str:
    candidates = [
        link.get('title') if link else '',
        clean_text(link.get_text(' ', strip=True)) if link else '',
        image.get('title') if image else '',
        image.get('alt') if image else '',
    ]
    for candidate in candidates:
        text = clean_text(candidate)
        if text and not text.lower().startswith(('purchase ', 'image:')):
            return text
    return ""


def _best_image_from_card(card, base_url: str) -> str:
    for selector in (
        'img.product-image-photo',
        '.product-item-photo img',
        'img[src*="/media/catalog/product/"]',
        'img[data-src*="/media/catalog/product/"]',
        'img[src]',
    ):
        for image in card.select(selector):
            raw = image.get('data-src') or image.get('src') or ''
            if not raw:
                continue
            lowered = raw.lower()
            if any(token in lowered for token in ('header-cart.svg', 'logo', 'placeholder', 'loader', 'spinner')):
                continue
            return urljoin(base_url, raw)
    return ""


def extract_product_from_listing(card, base_url: str) -> Optional[Item]:
    link = (
        card.select_one('a.product-item-link[href]')
        or card.select_one('a.product-item-photo[href]')
        or card.select_one('a[href*="phonelcdparts.com/"]')
        or card.select_one('a[href]')
    )
    if not link or not link.get('href'):
        return None

    href = link.get('href', '')
    if any(token in href.lower() for token in ('/customer/', '/checkout/', '/cart/', '/media/', '/static/')):
        return None

    image = card.select_one('img.product-image-photo') or card.select_one('img')
    item = Item()
    item.url = urljoin(base_url, href)
    item.title = _best_title_from_card(card, link, image)
    item.image_url = _best_image_from_card(card, base_url)

    price_el = (
        card.select_one('[data-price-type="finalPrice"][data-price-amount]')
        or card.select_one('[data-price-amount]')
        or card.select_one('.price-box .price, .price')
    )
    if price_el:
        price_val = parse_price(price_el.get('data-price-amount') or price_el.get_text(' ', strip=True))
        if price_val > 0:
            item.original = price_val
            item.discounted = price_val
            item.original_formatted = fmt_price(price_val)
            item.discounted_formatted = fmt_price(price_val)

    sku_holder = card.select_one('[data-product-sku], [data-product_sku], [data-sku]')
    if sku_holder:
        item.sku = clean_text(
            sku_holder.get('data-product-sku')
            or sku_holder.get('data-product_sku')
            or sku_holder.get('data-sku')
            or ''
        )
    if not item.sku:
        sku_match = re.search(r"\$store\.cart\.getQty\('([^']+)'\)", str(card))
        if sku_match:
            item.sku = clean_text(sku_match.group(1).encode('utf-8').decode('unicode_escape'))

    stock_text = clean_text(card.get_text(' ', strip=True))
    if 'out of stock' in stock_text.lower() or 'out-of-stock' in ' '.join(card.get('class', [])).lower():
        item.stock_status = "Out of Stock"

    if not item.title or not item.url:
        return None
    item.extra.update({'sku': item.sku, 'stock_status': item.stock_status, 'description': item.description})
    return item


def extract_items_from_soup(soup: BeautifulSoup, url: str, rules: dict, logger=None) -> List[Item]:
    cards = soup.select(
        'li.item.product.product-item, li.product-item, '
        'div.item.product.product-item, form.item.product.product-item, .product_addtocart_form'
    )
    if logger:
        logger.info(f"[phonelcdparts] Found {len(cards)} product card(s) at {url}")

    items_by_url = {}
    for card in cards:
        item = extract_product_from_listing(card, url)
        if not item:
            continue
        adjusted = apply_price_rules(item.original, rules)
        item.discounted = adjusted
        item.discounted_formatted = fmt_price(adjusted)
        items_by_url[item.url] = item
    return list(items_by_url.values())


def extract_subcategory_urls(soup: BeautifulSoup, current_url: str) -> List[str]:
    """Return direct child category links from parent category landing pages."""
    current = urlparse(current_url)
    current_path = current.path.rstrip('/') + '/'
    discovered = []
    seen = set()
    for anchor in soup.select('main a[href], #maincontent a[href], .columns a[href]'):
        href = str(anchor.get('href') or '').strip()
        if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            continue
        child_url = urljoin(current_url, href)
        parsed = urlparse(child_url)
        if parsed.netloc.lower() != current.netloc.lower():
            continue
        child_path = parsed.path.rstrip('/') + '/'
        if child_path == current_path or not child_path.startswith(current_path):
            continue
        normalized = urlunparse(parsed._replace(fragment=''))
        if normalized not in seen:
            seen.add(normalized)
            discovered.append(normalized)
    return discovered


def find_next_page_url(soup: BeautifulSoup, current_url: str) -> Optional[str]:
    next_link = soup.select_one('li.pages-item-next a[href], a.action.next[href], a[rel="next"][href], .pages .next[href]')
    if next_link and next_link.get('href'):
        return urljoin(current_url, next_link['href'])

    toolbar = clean_text(' '.join(el.get_text(' ', strip=True) for el in soup.select('.toolbar-amount')))
    match = re.search(r'(\d+)\s*-\s*(\d+)\s+of\s+(\d+)', toolbar)
    if not match or int(match.group(2)) >= int(match.group(3)):
        return None

    parsed = urlparse(current_url)
    qs = parse_qs(parsed.query)
    current_page = int(qs.get('p', ['1'])[0] or '1')
    qs['p'] = [str(current_page + 1)]
    return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))


def scrape_category_page(session, url: str, rules: dict, logger=None) -> List[Item]:
    html = get_html(session, url, logger)
    if not html:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    return extract_items_from_soup(soup, url, rules, logger)


def scrape_category_all_pages(session, url: str, rules: dict, max_pages: int = 20, delay_ms: int = 200, logger=None, initial_html: str | None = None, expand_subcategories: bool = True) -> List[Item]:
    items_by_url = {}
    current_url = url
    seen_pages = set()
    page_num = 1

    while current_url and page_num <= max_pages and current_url not in seen_pages:
        seen_pages.add(current_url)
        html = initial_html if page_num == 1 and initial_html is not None else get_html(session, current_url, logger)
        initial_html = None
        if not html:
            break
        soup = BeautifulSoup(html, 'html.parser')
        page_items = extract_items_from_soup(soup, current_url, rules, logger)
        for item in page_items:
            items_by_url[item.url] = item
        if not page_items:
            child_urls = extract_subcategory_urls(soup, current_url) if expand_subcategories else []
            if child_urls and logger:
                logger.info(f"[phonelcdparts] Expanding {len(child_urls)} child category link(s) from {current_url}")
            for child_url in child_urls:
                child_items = scrape_category_all_pages(
                    session,
                    child_url,
                    rules,
                    max_pages=max_pages,
                    delay_ms=delay_ms,
                    logger=logger,
                    expand_subcategories=False,
                )
                for item in child_items:
                    items_by_url[item.url] = item
            break

        next_url = find_next_page_url(soup, current_url)
        if not next_url:
            break
        current_url = next_url
        page_num += 1
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    if logger:
        logger.info(f"[phonelcdparts] Total unique items scraped: {len(items_by_url)}")
    return list(items_by_url.values())


def scrape_product_page(session, url: str, rules: dict, logger=None) -> Optional[Item]:
    html = get_html(session, url, logger)
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    item = Item(url=extract_canonical_url(soup, url))

    title_el = (
        soup.select_one('h1.page-title .base')
        or soup.select_one('span[data-ui-id="page-title-wrapper"]')
        or soup.select_one('h1.page-title')
        or soup.select_one('h1')
        or soup.select_one('meta[property="og:title"]')
    )
    item.title = clean_text(title_el.get('content') if title_el and title_el.name == 'meta' else title_el.get_text(' ', strip=True) if title_el else '')
    if not item.title:
        return None

    price_el = (
        soup.select_one('meta[property="product:price:amount"]')
        or soup.select_one('[data-price-type="finalPrice"][data-price-amount]')
        or soup.select_one('[data-price-amount]')
        or soup.select_one('.price-box .price, .price')
    )
    if price_el:
        price_val = parse_price(
            price_el.get('content')
            or price_el.get('data-price-amount')
            or price_el.get_text(' ', strip=True)
        )
        if price_val > 0:
            item.original = price_val
            item.discounted = apply_price_rules(price_val, rules)
            item.original_formatted = fmt_price(price_val)
            item.discounted_formatted = fmt_price(item.discounted)

    image = (
        soup.select_one('.gallery-placeholder img')
        or soup.select_one('.product.media img')
        or soup.select_one('img.fotorama__img')
        or soup.select_one('meta[property="og:image"]')
    )
    if image:
        raw = image.get('src') or image.get('data-src') or image.get('content') or ''
        item.image_url = urljoin(url, raw) if raw else ''

    sku_el = soup.select_one(
        '#product_addtocart_form[data-sku], '
        'form[data-sku]:not(.product-item), '
        '.product.attribute.sku .value, '
        '.product-info-stock-sku .sku .value, '
        '[itemprop="sku"]'
    )
    if sku_el:
        item.sku = clean_text(
            sku_el.get('data-sku')
            or sku_el.get('content')
            or sku_el.get_text(' ', strip=True)
        )

    stock_el = soup.select_one('.product-info-stock-sku .stock, .stock.available, .stock.unavailable, .stock')
    if stock_el:
        item.stock_status = clean_text(stock_el.get_text(' ', strip=True))
    elif 'out-of-stock' in str(soup).lower() or 'outofstock' in str(soup).lower():
        item.stock_status = "Out of Stock"

    description_parts = []
    for selector in ('#description', '.product.attribute.description .value', '.product.attribute.overview .value', 'meta[name="description"]'):
        el = soup.select_one(selector)
        if not el:
            continue
        text = strip_markup(el.get('content', '')) if el.name == 'meta' else strip_markup(el.get_text(' ', strip=True))
        if text and text not in description_parts:
            description_parts.append(text)
    item.description = ' '.join(description_parts)
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
    if logger:
        logger.info(f"[phonelcdparts] Starting scrape of: {url}")

    html = get_html(session, url, logger)
    if not html:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    if is_product_page(soup) and not is_category_page(soup):
        item = scrape_product_page(session, url, rules, logger)
        return [item] if item else []

    if crawl_pagination:
        return scrape_category_all_pages(
            session,
            url,
            rules,
            max_pages=max_pages,
            delay_ms=delay_ms,
            logger=logger,
            initial_html=html,
        )
    return extract_items_from_soup(soup, url, rules, logger)
