"""
XCellParts Scraper Engine

Specialized scraper for xcellparts.com with proper title, price, and image extraction.
This engine is automatically used when scraping xcellparts.com URLs.

Author: Arslan
Created for: TXParts
"""

import html as html_lib
import os
import requests
import time
import re
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit
from .browser_fetcher import fetch_html as fetch_html_with_browser, should_use_browser_fetch, browser_fetch_requested
from .sku_utils import extract_jsonld_sku

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL = True
except Exception:
    HAS_CURL = False


@dataclass
class Item:
    """Product item data structure (compatible with main scraper_engine)"""
    title: str = ""
    url: str = ""
    image_url: str = ""
    original: float = 0.0
    discounted: float = 0.0
    original_formatted: str = "$0.00"
    discounted_formatted: str = "$0.00"
    site: str = ""
    sku: str = ""
    stock_status: str = "In Stock"
    description: str = ""
    extra: dict = field(default_factory=dict)

def clean_text(text: str) -> str:
    """Clean and normalize text"""
    if not text:
        return ""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


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
    """Extract numeric price from string like '$12.17' or '12.17'"""
    if not price_str:
        return 0.0
    # Remove currency symbols, commas, spaces
    clean = re.sub(r'[^\d.]', '', str(price_str))
    try:
        return float(clean) if clean else 0.0
    except (ValueError, TypeError):
        return 0.0

def fmt_price(val: float, currency: str = "USD") -> str:
    """Format price as currency string"""
    if currency == "CAD":
        return f"CA${val:.2f}"
    return f"${val:.2f}"


def apply_price_rules(price: float, rules: dict | None = None) -> float:
    value = float(price or 0.0)
    rules = rules or {}
    add_percent = float(rules.get('add_percent') or 0.0)
    percent_off = float(rules.get('percent_off') or 0.0)
    absolute_off = float(rules.get('absolute_off') or 0.0)
    if add_percent > 0:
        value *= (1 + add_percent / 100.0)
    if percent_off > 0:
        value *= (1 - percent_off / 100.0)
    if absolute_off > 0:
        value -= absolute_off
    return round(max(0.0, value), 2)

def build_session(retries: int = 2, verify_ssl: bool = True, use_curl: bool = True) -> tuple:
    """Build HTTP session with retry logic"""
    if use_curl and HAS_CURL:
        session = curl_requests.Session(impersonate="safari15_5")
        session.verify = verify_ssl
        session.xcell_last_error = ''
        return session, True

    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://xcellparts.com/',
    }

    session = requests.Session()

    retry_strategy = Retry(
        total=retries,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504]
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.verify = verify_ssl
    session.headers.update(headers)
    session.xcell_last_error = ''

    return session, False  # False = not using curl_cffi

def is_html_document(text: str) -> bool:
    """Detect whether a response body looks like HTML instead of compressed/binary data."""
    if not text:
        return False
    sample = text.lstrip()[:512].lower()
    return '<!doctype html' in sample or '<html' in sample or '<body' in sample

def parse_html_document(html: str) -> Optional[BeautifulSoup]:
    """Parse HTML with a forgiving fallback when lxml rejects malformed markup."""
    last_error = None
    for parser in ('lxml', 'html.parser'):
        try:
            return BeautifulSoup(html, parser)
        except Exception as e:
            last_error = e
    print(f"[xcell] Failed to parse HTML document: {last_error}")
    return None


def extract_canonical_url(soup: BeautifulSoup, fallback: str) -> str:
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and canonical.get('href'):
        return canonical['href']
    og_url = soup.select_one('meta[property="og:url"]')
    if og_url and og_url.get('content'):
        return og_url['content']
    return fallback


def extract_meta_description(soup: BeautifulSoup) -> str:
    meta = soup.select_one('meta[name="description"]')
    return strip_markup(meta.get('content', '')) if meta else ""


def extract_xcell_sku(soup: Optional[BeautifulSoup] = None, html: str = "") -> str:
    """Extract authoritative SKU from an XCell product detail page."""
    # 1. Primary on XCell: [data-xcell-copy] chip attribute (sub-millisecond regex)
    if html:
        m = re.search(r'data-xcell-copy=["\']([^"\']+)["\']', html)
        if m and m.group(1).strip():
            return clean_text(m.group(1))

        # 2. Main product summary SKU badge (severed before related products carousel)
        main_html = html.split('related products')[0].split('class="related')[0].split('class="up-sells')[0]
        m = re.search(r'SKU\s*(?:[:\-])?\s*<b>([^<]+)</b>', main_html, re.I)
        if m and m.group(1).strip():
            return clean_text(m.group(1))

    # 3. DOM Fallback via BeautifulSoup
    if soup:
        copy_chip = soup.select_one('[data-xcell-copy]')
        if copy_chip and copy_chip.get('data-xcell-copy'):
            sku = clean_text(copy_chip.get('data-xcell-copy'))
            if sku:
                return sku

        for chip in soup.select('.xcell-pdp-meta__chip, .xcell-pdp-meta span, .xcell-meta span, .xcell-pdp-copy'):
            b_tag = chip.select_one('b, strong')
            if b_tag:
                sku = clean_text(b_tag.get_text())
                if sku:
                    return sku
            txt = clean_text(chip.get_text())
            if txt.upper().startswith('SKU'):
                sku = txt[3:].strip()
                if sku:
                    return sku

        summary = soup.select_one('.summary, .elementor-widget-woocommerce-product-summary, .xcell-pdp__meta-row, .entry-summary')
        if summary:
            sku_el = summary.select_one('.sku, .product_meta .sku, [itemprop="sku"]')
            if sku_el:
                sku = clean_text(sku_el.get_text())
                if sku:
                    return sku

        sku_elem = soup.select_one('.product_meta .sku_wrapper .sku, .product_meta .sku, [itemprop="sku"]')
        if sku_elem:
            sku = clean_text(sku_elem.get('content') or sku_elem.get_text() or '')
            if sku:
                return sku

    return ""


def parse_xcell_product_detail_fast(html: str, url: str, rules: dict | None = None) -> Optional[Item]:
    """Extract XCell detail fields without building a full DOM for multi-megabyte pages."""
    if not html:
        return None

    def text_from_fragment(fragment: str) -> str:
        return clean_text(html_lib.unescape(re.sub(r'<[^>]+>', ' ', fragment or '')))

    def first_match(patterns, *, flags=re.I | re.S) -> str:
        for pattern in patterns:
            match = re.search(pattern, html, flags)
            if match and match.group(1):
                return clean_text(html_lib.unescape(match.group(1)))
        return ''

    title_fragment = first_match([
        r'<h1[^>]*class=["\'][^"\']*(?:product_title|entry-title)[^"\']*["\'][^>]*>(.*?)</h1>',
        r'<h1[^>]*>(.*?)</h1>',
    ])
    title = text_from_fragment(title_fragment)
    if not title:
        title = first_match([r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']'])

    sku = extract_xcell_sku(None, html)
    if not title or not sku:
        return None

    canonical = first_match([
        r'<link[^>]+rel=["\'][^"\']*canonical[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\'][^"\']*canonical[^"\']*["\']',
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
    ]) or url

    item = Item(site='xcellparts.com', url=canonical, title=title, sku=sku)
    price_fragment = first_match([
        r'<bdi[^>]*>(.*?)</bdi>',
        r'class=["\'][^"\']*woocommerce-Price-amount[^"\']*["\'][^>]*>(.*?)</span>',
    ])
    price_value = parse_price_number(text_from_fragment(price_fragment)) if price_fragment else 0.0
    if price_value > 0:
        item.original = price_value
        item.discounted = price_value
        item.original_formatted = fmt_price(price_value)
        item.discounted_formatted = fmt_price(price_value)

    item.image_url = first_match([
        r'class=["\'][^"\']*woocommerce-product-gallery__image[^"\']*["\'][^>]*>\s*<a[^>]+href=["\']([^"\']+)["\']',
        r'<img[^>]+class=["\'][^"\']*wp-post-image[^"\']*["\'][^>]+(?:src|data-src)=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    ])
    if item.image_url:
        item.image_url = urljoin(url, item.image_url)

    stock_fragment = first_match([
        r'class=["\'][^"\']*stock[^"\']*["\'][^>]*>(.*?)</(?:p|div|span)>',
    ])
    stock_text = text_from_fragment(stock_fragment)
    if stock_text:
        item.stock_status = stock_text
    elif 'outofstock' in html.lower() or 'out of stock' in html.lower():
        item.stock_status = 'Out of Stock'

    description_fragment = first_match([
        r'class=["\'][^"\']*woocommerce-product-details__short-description[^"\']*["\'][^>]*>(.*?)</div>',
        r'id=["\']tab-description["\'][^>]*>(.*?)</(?:div|section)>',
    ])
    item.description = text_from_fragment(description_fragment)
    if not item.description:
        item.description = first_match([
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        ])

    adjusted_price = apply_price_rules(item.original, rules or {})
    if adjusted_price != round(float(item.original or 0.0), 2):
        item.discounted = adjusted_price
        item.discounted_formatted = fmt_price(adjusted_price)
    item.extra.update({
        'sku': item.sku,
        'stock_status': item.stock_status,
        'description': item.description,
    })
    return item


def scrape_product_page(session, url: str, rules: dict, logger=None) -> Optional[Item]:
    """Scrape a single WooCommerce product detail page for richer metadata."""
    html = get_html(session, url)
    if not html:
        return None

    fast_item = parse_xcell_product_detail_fast(html, url, rules)
    if fast_item:
        if logger:
            logger.debug(f"[xcell] Enriched detail page: {fast_item.url}")
        return fast_item

    soup = parse_html_document(html)
    if not soup:
        return None

    item = Item(site="xcellparts.com", url=extract_canonical_url(soup, url))

    title_elem = (
        soup.select_one('h1.product_title') or
        soup.select_one('h1.entry-title') or
        soup.select_one('h1')
    )
    item.title = clean_text(title_elem.get_text()) if title_elem else ""

    price_elem = (
        soup.select_one('.summary .price .woocommerce-Price-amount') or
        soup.select_one('.summary .price .amount') or
        soup.select_one('.woocommerce-Price-amount')
    )
    if price_elem:
        price_text = clean_text(price_elem.get_text())
        price_val = parse_price_number(price_text)
        if price_val > 0:
            item.original = price_val
            item.discounted = price_val
            item.original_formatted = fmt_price(price_val)
            item.discounted_formatted = fmt_price(price_val)

    img_elem = (
        soup.select_one('.woocommerce-product-gallery__image img') or
        soup.select_one('img.wp-post-image') or
        soup.select_one('meta[property="og:image"]')
    )
    if img_elem:
        item.image_url = urljoin(url, img_elem.get('src') or img_elem.get('content') or img_elem.get('data-src') or '')

    # Authoritative SKU extraction for XCell WooCommerce Elementor pages
    item.sku = extract_xcell_sku(soup, html)
    if not item.sku:
        item.sku = extract_jsonld_sku(soup, item.url)

    stock_elem = soup.select_one('.stock')
    if stock_elem:
        item.stock_status = clean_text(stock_elem.get_text())
    elif soup.select_one('.out-of-stock') or 'outofstock' in str(soup).lower():
        item.stock_status = "Out of Stock"

    description_parts = []
    for sel in (
        '.woocommerce-product-details__short-description',
        '.woocommerce-Tabs-panel--description',
        '#tab-description',
        '.entry-summary .woocommerce-product-details__short-description',
        '#tab-panel-description',
        '.product-description',
    ):
        el = soup.select_one(sel)
        if not el:
            continue
        text = strip_markup(el.get_text(' ', strip=True))
        if text and text not in description_parts:
            description_parts.append(text)
    if not description_parts:
        meta_description = extract_meta_description(soup)
        if meta_description:
            description_parts.append(meta_description)
    # Last resort: og:description
    if not description_parts:
        og_desc = soup.select_one('meta[property="og:description"]')
        if og_desc and og_desc.get('content'):
            description_parts.append(strip_markup(og_desc['content']))
    item.description = ' '.join(description_parts).strip()

    adjusted_price = apply_price_rules(item.original, rules)
    if adjusted_price != round(float(item.original or 0.0), 2):
        item.discounted = adjusted_price
        item.discounted_formatted = fmt_price(item.discounted)

    item.extra.update({
        'sku': item.sku,
        'stock_status': item.stock_status,
        'description': item.description,
    })

    if logger and item.title:
        logger.debug(f"[xcell] Enriched detail page: {item.url}")
    return item if item.url else None


def enrich_item_details(session, item: Item, rules: dict | None = None, logger=None) -> Item:
    """Merge product detail metadata into an already-scraped listing item."""
    detail = scrape_product_page(session, item.url, rules or {'percent_off': 0, 'absolute_off': 0}, logger)
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
    if detail.sku:
        item.sku = detail.sku
    if detail.stock_status:
        item.stock_status = detail.stock_status
    if detail.description:
        item.description = detail.description
    if isinstance(item.extra, dict):
        item.extra.update(detail.extra)
    return item

def get_html(session, url: str) -> Optional[str]:
    """Fetch HTML content from URL.

    Uses fast impersonated curl HTTP session first. If direct HTTP is blocked
    or unavailable and browser mode is active, it falls back to Botasaurus.
    """
    session.xcell_last_error = ''
    session.xcell_blocked = False
    session.xcell_last_status = 0
    if browser_fetch_requested():
        result = fetch_html_with_browser(url)
        session.xcell_last_status = 200
        return result.html

    is_curl_sess = HAS_CURL and isinstance(session, curl_requests.Session)
    if is_curl_sess:
        try:
            response = session.get(url, timeout=20, allow_redirects=True)
            status_code = int(getattr(response, 'status_code', 0) or 0)
            session.xcell_last_status = status_code
            response_text = getattr(response, 'text', '') or ''
            if status_code == 200 and is_html_document(response_text):
                session.xcell_last_error = ''
                return response_text
            if status_code in {401, 403, 429}:
                try:
                    session.get("https://xcellparts.com/", timeout=10)
                    retry_resp = session.get(url, timeout=20, allow_redirects=True)
                    session.xcell_last_status = int(getattr(retry_resp, 'status_code', 0) or 0)
                    if retry_resp.status_code == 200 and is_html_document(retry_resp.text):
                        session.xcell_last_error = ''
                        return retry_resp.text
                except Exception:
                    pass
        except Exception as curl_exc:
            session.xcell_last_error = f"curl fetch error: {curl_exc}"

    if should_use_browser_fetch():
        try:
            result = fetch_html_with_browser(url)
            if result and result.html:
                return result.html
        except Exception as e:
            browser_error_prefix = f"Botasaurus failed: {e}; "
            session.xcell_last_error = browser_error_prefix.rstrip('; ')
    try:
        response = session.get(url, timeout=30, allow_redirects=True)
        status_code = int(getattr(response, 'status_code', 0) or 0)
        session.xcell_last_status = status_code
        response_text = getattr(response, 'text', '') or ''
        if status_code in {401, 403, 429}:
            lowered = response_text[:1000].lower()
            if 'just a moment' in lowered or 'cloudflare' in lowered:
                browser_error = session.xcell_last_error
                session.xcell_blocked = True
                block_error = f'blocked by Cloudflare challenge ({status_code})'
                session.xcell_last_error = f"{browser_error}; {block_error}" if browser_error else block_error
                return None
        response.raise_for_status()
        html = response_text
        if is_html_document(html):
            session.xcell_last_error = ''
            return html

        # Some XCell responses come back Brotli-encoded if "br" is advertised upstream.
        retry_headers = dict(session.headers)
        retry_headers['Accept-Encoding'] = 'gzip, deflate'
        retry_response = session.get(url, timeout=30, headers=retry_headers, allow_redirects=True)
        retry_status_code = int(getattr(retry_response, 'status_code', 0) or 0)
        session.xcell_last_status = retry_status_code
        retry_text = getattr(retry_response, 'text', '') or ''
        if retry_status_code in {401, 403, 429}:
            lowered = retry_text[:1000].lower()
            if 'just a moment' in lowered or 'cloudflare' in lowered:
                browser_error = session.xcell_last_error
                session.xcell_blocked = True
                block_error = f'blocked by Cloudflare challenge ({retry_status_code})'
                session.xcell_last_error = f"{browser_error}; {block_error}" if browser_error else block_error
                return None
        retry_response.raise_for_status()
        retry_html = retry_text
        if is_html_document(retry_html):
            session.xcell_last_error = ''
            return retry_html

        browser_error = session.xcell_last_error
        session.xcell_last_error = (
            f"{browser_error}; response did not look like HTML after retry"
            if browser_error
            else 'response did not look like HTML after retry'
        )
        return None
    except Exception as e:
        browser_error = session.xcell_last_error
        fetch_error = str(e)
        session.xcell_last_error = f"{browser_error}; direct fetch failed: {fetch_error}" if browser_error else fetch_error
        return None

def extract_product_from_listing(product_elem, base_url: str) -> Optional[Item]:
    """
    Extract product data from a product listing element on xcellparts.com

    HTML Structure (Actual from xcellparts.com):
    <li class="product">
        <a class="woocommerce-LoopProduct-link" href="PRODUCT_URL">
            <img src="IMAGE_URL">
            <h2 class="woocommerce-loop-product__title">TITLE</h2>
        </a>
        <span class="price">
            <span class="woocommerce-Price-amount amount">$12.17</span>
        </span>
    </li>
    """
    try:
        item = Item()
        item.site = "xcellparts.com"

        # Extract title - xcellparts has title directly in h2 (not inside a link)
        title_elem = (
            product_elem.select_one('h2.woocommerce-loop-product__title') or
            product_elem.select_one('.woocommerce-loop-product__title') or
            product_elem.select_one('h2')
        )

        if title_elem:
            item.title = clean_text(title_elem.get_text())

        # Extract URL - separate from title
        link_elem = (
            product_elem.select_one('a.woocommerce-LoopProduct-link') or
            product_elem.select_one('a[href*="/product/"]') or
            product_elem.find('a', href=True)
        )

        if link_elem:
            item.url = urljoin(base_url, link_elem.get('href', ''))
            item.extra["canonical_url"] = normalize_product_url(item.url, base_url)

        # If still no title, try getting from link or img alt
        if not item.title and link_elem:
            img = link_elem.find('img', alt=True)
            if img:
                item.title = clean_text(img.get('alt', ''))

        if not item.title or not item.url:
            return None

        # Extract image URL
        img_elem = product_elem.select_one('img')
        if img_elem:
            # XCellParts uses data-src for lazy loading, but falls back to src
            img_url = img_elem.get('data-src') or img_elem.get('src') or ''
            if img_url:
                item.image_url = urljoin(base_url, img_url)

        # Extract price
        price_elem = (
            product_elem.select_one('.price .woocommerce-Price-amount') or
            product_elem.select_one('.woocommerce-Price-amount') or
            product_elem.select_one('.price .amount') or
            product_elem.select_one('.price')
        )

        if price_elem:
            price_text = clean_text(price_elem.get_text())
            price_val = parse_price_number(price_text)
            item.original = price_val
            item.discounted = price_val
            item.original_formatted = fmt_price(price_val)
            item.discounted_formatted = fmt_price(price_val)

        # SKU is exposed in the add-to-cart button on listing pages.
        # In extract_product_from_listing the product_elem IS the <li class="product">
        # so [data-product_sku] search is safely scoped to this one product.
        sku_elem = product_elem.select_one('[data-product_sku]')
        if sku_elem:
            item.sku = clean_text(sku_elem.get('data-product_sku', ''))
        product_id_elem = product_elem.select_one('[data-product_id], [data-product-id], [name="add-to-cart"]')
        if product_id_elem:
            item.extra["product_id"] = clean_text(
                product_id_elem.get('data-product_id')
                or product_id_elem.get('data-product-id')
                or product_id_elem.get('value')
                or ''
            )

        # Try to extract description from JSON-LD embedded inside the product element
        # WooCommerce injects <script type="application/ld+json"> per product on some themes
        import json as _json
        for script_tag in product_elem.select('script[type="application/ld+json"]'):
            try:
                ld = _json.loads(script_tag.string or '')
                entries = ld if isinstance(ld, list) else [ld]
                for entry in entries:
                    desc = str(entry.get('description') or '').strip()
                    if desc and desc.lower() != 'n/a':
                        item.description = strip_markup(desc)
                        break
            except Exception:
                pass
            if item.description:
                break

        # Check stock status - xcellparts shows "out-of-stock" class or text
        if (product_elem.select_one('.out-of-stock') or
            'outofstock' in ' '.join(product_elem.get('class', [])).lower() or
            'OUT OF STOCK' in product_elem.get_text().upper()):
            item.stock_status = "Out of Stock"

        return item if item.title and item.url else None

    except Exception as e:
        print(f"[xcell] Failed to parse product element: {e}")
        return None


def normalize_product_url(url: str, base_url: str) -> str:
    absolute = urljoin(base_url, url or "")
    parsed = urlsplit(absolute)
    return urlunsplit(parsed._replace(query="", fragment="")).rstrip("/") + "/"


def is_product_href(href: str) -> bool:
    if not href:
        return False
    path = urlsplit(href).path.lower()
    return "/product/" in path and "/product-category/" not in path


def choose_product_title(anchors) -> str:
    rejected = {
        "add to cart",
        "read more",
        "select options",
        "quick view",
        "view cart",
    }
    candidates = []
    for anchor in anchors:
        for value in (
            anchor.get_text(" ", strip=True),
            anchor.get("title", ""),
            (anchor.find("img") or {}).get("alt", "") if anchor.find("img") else "",
            anchor.get("aria-label", ""),
        ):
            text = clean_text(value)
            if not text:
                continue
            lowered = text.lower()
            if lowered in rejected or any(lowered.startswith(f"{word}:") for word in rejected):
                continue
            candidates.append(text)
    if not candidates:
        return ""
    return max(candidates, key=len)


def find_product_card(anchor, normalized_url: str, base_url: str):
    current = anchor
    best = anchor.parent
    for _depth in range(8):
        current = current.parent
        if current is None or getattr(current, "name", None) in {"body", "html"}:
            break
        product_urls = {
            normalize_product_url(a.get("href", ""), base_url)
            for a in current.select('a[href*="/product/"]')
            if is_product_href(a.get("href", ""))
        }
        if product_urls == {normalized_url}:
            best = current
        elif normalized_url in product_urls and len(product_urls) > 1:
            break
    return best or anchor


def extract_product_from_link_group(anchors, url: str, base_url: str, rules: dict) -> Optional[Item]:
    normalized_url = normalize_product_url(url, base_url)
    title = choose_product_title(anchors)
    card = find_product_card(anchors[0], normalized_url, base_url)

    item = Item(site="xcellparts.com", url=normalized_url, title=title)
    item.extra["canonical_url"] = normalized_url

    if not item.title:
        item.title = choose_product_title(card.select('a[href*="/product/"]'))
    if not item.title:
        return None

    img_elem = None
    for anchor in anchors:
        img_elem = anchor.find("img")
        if img_elem:
            break
    if not img_elem and card:
        img_elem = card.select_one("img")
    if img_elem:
        img_url = (
            img_elem.get("data-src")
            or img_elem.get("data-lazy-src")
            or img_elem.get("src")
            or img_elem.get("srcset", "").split(" ")[0]
            or ""
        )
        if img_url:
            item.image_url = urljoin(base_url, img_url)

    price_elem = (
        card.select_one(".price .woocommerce-Price-amount")
        or card.select_one(".woocommerce-Price-amount")
        or card.select_one("[data-price-amount]")
        or card.select_one(".price .amount")
        or card.select_one(".price")
    )
    price_text = ""
    if price_elem:
        price_text = price_elem.get("data-price-amount") or clean_text(price_elem.get_text(" ", strip=True))
    else:
        price_match = re.search(r"(?:US)?\$\s*[\d,]+(?:\.\d{2})?", card.get_text(" ", strip=True) if card else "")
        if price_match:
            price_text = price_match.group(0)
    price_val = parse_price_number(price_text)
    if price_val > 0:
        item.original = price_val
        item.discounted = price_val
        item.original_formatted = fmt_price(price_val)
        item.discounted_formatted = fmt_price(price_val)

    # SKU on listing page (must be strictly scoped to this product's anchor/card)
    item.sku = ""
    for anchor in anchors:
        sku_val = anchor.get("data-xcell-copy", "") or anchor.get("data-product_sku", "")
        if sku_val and clean_text(sku_val):
            item.sku = clean_text(sku_val)
            break

    # Fallback: trust the card ONLY if it uniquely wraps this one product
    if not item.sku and card:
        card_product_urls = {
            normalize_product_url(a.get("href", ""), base_url)
            for a in card.select('a[href*="/product/"]')
            if is_product_href(a.get("href", ""))
        }
        if card_product_urls == {normalized_url}:
            sku_elem = card.select_one("[data-xcell-copy], [data-product_sku]")
            if sku_elem:
                item.sku = clean_text(sku_elem.get("data-xcell-copy") or sku_elem.get("data-product_sku") or "")

    product_id_elem = card.select_one('[data-product_id], [data-product-id], [name="add-to-cart"]') if card else None
    if product_id_elem:
        item.extra["product_id"] = clean_text(
            product_id_elem.get("data-product_id")
            or product_id_elem.get("data-product-id")
            or product_id_elem.get("value")
            or ""
        )

    card_text = card.get_text(" ", strip=True) if card else ""
    card_classes = " ".join(card.get("class", [])) if card else ""
    if "out of stock" in card_text.lower() or "outofstock" in card_classes.lower():
        item.stock_status = "Out of Stock"

    adjusted_price = apply_price_rules(item.original, rules)
    if adjusted_price != round(float(item.original or 0.0), 2):
        item.discounted = adjusted_price
        item.discounted_formatted = fmt_price(item.discounted)

    return item


def extract_items_from_product_links(soup: BeautifulSoup, url: str, rules: dict) -> List[Item]:
    grouped = {}
    order = []
    for anchor in soup.select('a[href*="/product/"]'):
        href = anchor.get("href", "")
        if not is_product_href(href):
            continue
        normalized_url = normalize_product_url(href, url)
        if normalized_url not in grouped:
            grouped[normalized_url] = []
            order.append(normalized_url)
        grouped[normalized_url].append(anchor)

    items = []
    for product_url in order:
        item = extract_product_from_link_group(grouped[product_url], product_url, url, rules)
        if item:
            items.append(item)
    return items

def extract_items_from_category_soup(soup: BeautifulSoup, url: str, rules: dict, logger=None) -> List[Item]:
    """Extract product listing items from an already-fetched category page."""
    items = []

    # XCellParts uses WooCommerce structure
    # Products are in <ul class="products"> with <li class="product"> items
    product_containers = soup.select('ul.products li.product') or soup.select('.products .product')
    if not product_containers:
        seen_containers = set()
        for link in soup.select('a[href*="/product/"]'):
            container = (
                link.find_parent(['li', 'article'], class_=re.compile(r'product|type-product|item', re.I)) or
                link.find_parent(['div', 'section'], class_=re.compile(r'product|type-product|item|card|grid', re.I)) or
                link.find_parent(['li', 'article', 'div'])
            )
            if not container:
                continue
            key = id(container)
            if key in seen_containers:
                continue
            seen_containers.add(key)
            product_containers.append(container)

    link_items = extract_items_from_product_links(soup, url, rules)
    if len(link_items) > len(product_containers):
        if logger:
            logger.info(
                f"[xcell] Found {len(link_items)} products from rendered product links on page: {url}"
            )
        _enrich_items_from_jsonld(soup, url, link_items)
        return link_items

    if logger:
        logger.info(f"[xcell] Found {len(product_containers)} products on page: {url}")

    for product_elem in product_containers:
        item = extract_product_from_listing(product_elem, url)
        if item:
            # Apply discount rules
            adjusted_price = apply_price_rules(item.original, rules)
            if adjusted_price != round(float(item.original or 0.0), 2):
                item.discounted = adjusted_price
                item.discounted_formatted = fmt_price(item.discounted)

            items.append(item)

    # Enrich items from page-level JSON-LD (WooCommerce injects this for all products)
    _enrich_items_from_jsonld(soup, url, items)

    return items


def _enrich_items_from_jsonld(soup: BeautifulSoup, base_url: str, items: List[Item]) -> None:
    """Parse JSON-LD blocks from the page and apply description/SKU to matching items."""
    import json as _json
    # Build lookup: normalised_url -> {description, sku}
    ld_map: dict = {}
    for script_tag in soup.select('script[type="application/ld+json"]'):
        try:
            ld = _json.loads(script_tag.string or '')
        except Exception:
            continue
        entries = ld if isinstance(ld, list) else [ld]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            # Individual product entry
            product_url = str(entry.get('url') or '').strip()
            if product_url and entry.get('@type') in ('Product', 'product'):
                norm = normalize_product_url(product_url, base_url)
                desc = strip_markup(str(entry.get('description') or '').strip())
                sku = clean_text(str(entry.get('sku') or entry.get('mpn') or ''))
                if desc or sku:
                    ld_map[norm] = {'description': desc, 'sku': sku}
            # ItemList wrapping multiple products
            elif entry.get('@type') == 'ItemList':
                for element in (entry.get('itemListElement') or []):
                    if not isinstance(element, dict):
                        continue
                    item_data = element.get('item') or element
                    product_url = str(item_data.get('url') or '').strip()
                    if product_url:
                        norm = normalize_product_url(product_url, base_url)
                        desc = strip_markup(str(item_data.get('description') or '').strip())
                        sku = clean_text(str(item_data.get('sku') or item_data.get('mpn') or ''))
                        if desc or sku:
                            ld_map[norm] = {'description': desc, 'sku': sku}

    if not ld_map:
        return

    for item in items:
        norm = normalize_product_url(item.url, base_url)
        match = ld_map.get(norm)
        if not match:
            continue
        if not item.description and match.get('description'):
            item.description = match['description']
        # Only fill SKU from LD if SKU is still empty (scraper result takes precedence)
        if not item.sku and match.get('sku'):
            item.sku = match['sku']

def scrape_category_page(session, url: str, rules: dict, logger=None) -> List[Item]:
    """
    Scrape a single category page from xcellparts.com

    Args:
        session: HTTP session
        url: Category page URL
        rules: Discount rules (percent_off, absolute_off)
        logger: Optional logger instance

    Returns:
        List of Item objects
    """
    html = get_html(session, url)
    if not html:
        if logger:
            suffix = f": {session.xcell_last_error}" if getattr(session, 'xcell_last_error', '') else ''
            logger.warning(f"[xcell] Failed to fetch HTML from {url}{suffix}")
        return []

    soup = parse_html_document(html)
    if not soup:
        if logger:
            logger.warning(f"[xcell] Failed to parse HTML from {url}")
        return []

    return extract_items_from_category_soup(soup, url, rules, logger)

def find_next_page_url(soup, current_url: str) -> Optional[str]:
    """
    Find the next pagination page URL

    XCellParts uses WooCommerce pagination:
    <nav class="woocommerce-pagination">
        <a class="next page-numbers" href="NEXT_PAGE_URL">Next</a>
    </nav>
    """
    # Try to find "Next" link
    next_link = (
        soup.select_one('a.next.page-numbers') or
        soup.select_one('.woocommerce-pagination a.next') or
        soup.select_one('.pagination .next') or
        soup.find('a', string=re.compile(r'Next|→', re.I))
    )

    if next_link and next_link.get('href'):
        return urljoin(current_url, next_link['href'])

    return None

def scrape_category_all_pages(session, url: str, rules: dict, max_pages: int = 20, delay_ms: int = 200, logger=None) -> List[Item]:
    """
    Scrape all pagination pages from a category

    Args:
        session: HTTP session
        url: Initial category URL
        rules: Discount rules
        max_pages: Maximum pages to scrape
        delay_ms: Delay between page requests (milliseconds)
        logger: Optional logger

    Returns:
        Combined list of items from all pages
    """
    all_items = []
    current_url = url
    page_num = 1
    session.xcell_page_stats = []
    session.xcell_incomplete = False

    while current_url and page_num <= max_pages:
        if logger:
            logger.info(f"[xcell] Scraping page {page_num}/{max_pages}: {current_url}")

        html = get_html(session, current_url)
        if not html:
            session.xcell_incomplete = True
            session.xcell_page_stats.append({
                "page": page_num,
                "url": current_url,
                "status": "fetch_failed",
                "item_count": 0,
                "error": getattr(session, "xcell_last_error", "") or "No HTML returned",
            })
            if logger:
                suffix = f": {session.xcell_last_error}" if getattr(session, 'xcell_last_error', '') else ''
                logger.warning(f"[xcell] Failed to fetch HTML from {current_url}{suffix}")
            break

        soup = parse_html_document(html)
        if not soup:
            session.xcell_incomplete = True
            session.xcell_last_error = f"Failed to parse HTML from {current_url}"
            session.xcell_page_stats.append({
                "page": page_num,
                "url": current_url,
                "status": "parse_failed",
                "item_count": 0,
                "error": session.xcell_last_error,
            })
            if logger:
                logger.warning(f"[xcell] Failed to parse HTML from {current_url}")
            break

        page_items = extract_items_from_category_soup(soup, current_url, rules, logger)
        for item in page_items:
            if not isinstance(getattr(item, "extra", None), dict):
                item.extra = {}
            item.extra["xcell_page"] = page_num
            item.extra["xcell_page_url"] = current_url
        all_items.extend(page_items)
        session.xcell_page_stats.append({
            "page": page_num,
            "url": current_url,
            "status": "ok" if page_items else "empty",
            "item_count": len(page_items),
            "error": "",
        })

        if not page_items:
            session.xcell_incomplete = True
            session.xcell_last_error = f"No products parsed on page {page_num}: {current_url}"
            if logger:
                logger.info(f"[xcell] No items found on page {page_num}, stopping pagination")
            break

        next_url = find_next_page_url(soup, current_url)

        if not next_url:
            if logger:
                logger.info(f"[xcell] No more pages found after page {page_num}")
            break

        current_url = next_url
        page_num += 1

        # Delay before next request
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    if current_url and page_num > max_pages:
        session.xcell_incomplete = True
        session.xcell_last_error = f"Pagination reached max_pages={max_pages} before natural completion"
        session.xcell_page_stats.append({
            "page": page_num,
            "url": current_url,
            "status": "max_pages_reached",
            "item_count": 0,
            "error": session.xcell_last_error,
        })

    if logger:
        logger.info(f"[xcell] Total items scraped: {len(all_items)} from {page_num} pages")

    return all_items

def scrape_url(session, url: str, rules: dict, crawl_pagination: bool = True,
               max_pages: int = 20, delay_ms: int = 200, logger=None) -> List[Item]:
    """
    Main entry point for scraping XCellParts URLs

    Args:
        session: HTTP session
        url: Product or category URL
        rules: Discount rules (percent_off, absolute_off)
        crawl_pagination: Whether to follow pagination
        max_pages: Max pages to crawl
        delay_ms: Delay between requests
        logger: Optional logger

    Returns:
        List of Item objects
    """
    if logger:
        logger.info(f"[xcell] Starting scrape of: {url}")

    # Determine if it's a category or product page
    if '/product-category/' in url:
        # Category page
        if crawl_pagination:
            return scrape_category_all_pages(session, url, rules, max_pages, delay_ms, logger)
        else:
            return scrape_category_page(session, url, rules, logger)
    elif '/product/' in url:
        # Single product page
        item = scrape_product_page(session, url, rules, logger)
        return [item] if item else []
    else:
        # Try as category by default
        if logger:
            logger.warning(f"[xcell] URL type unclear, trying as category: {url}")
        return scrape_category_page(session, url, rules, logger)
