"""
Parts4Cells Scraper Engine — parts4cells.com (Magento 2)

Uses curl_cffi with safari15_3 impersonation because the site
blocks standard requests/Chrome fingerprints on paginated URLs.

Strategy:
  - Parse total product count from toolbar ("Items 1-12 of 64")
  - Step through ?p=N until all products are collected or pages loop
  - Detect loops via seen product-URL deduplication
"""

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin, urlparse, urlencode, parse_qs, urlunparse

try:
    from curl_cffi import requests as curl_req
    _HAS_CURL = True
except ImportError:
    import requests as curl_req      # fallback
    _HAS_CURL = False

from bs4 import BeautifulSoup


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class Item:
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text)).strip() if text else ""


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
    clean = re.sub(r'[^\d.]', '', str(price_str))
    try:
        return float(clean) if clean else 0.0
    except ValueError:
        return 0.0


def fmt_price(val: float) -> str:
    return f"${val:.2f}"


# Magento placeholder image indicators
_PLACEHOLDERS = ('placeholder', 'magento-menu-logo', 'no_selection', 'no-image', 'default/')


# ── Session / HTTP ────────────────────────────────────────────────────────────

def build_session(retries: int = 2, verify_ssl: bool = True):
    """Return (session_or_None, using_curl_cffi: bool)."""
    return None, _HAS_CURL   # we use curl_cffi per-request (stateless)


def _fetch(url: str, logger=None) -> Optional[str]:
    """
    Fetch URL content using curl_cffi with safari15_3 impersonation.
    Falls back to regular requests if curl_cffi is unavailable.

    Parts4Cells returns 403 for paginated ?p=N URLs when using
    standard requests / Chrome TLS fingerprints but allows Safari.
    """
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
    }
    try:
        if _HAS_CURL:
            r = curl_req.get(url, impersonate='safari15_3', timeout=30, headers=headers)
        else:
            import requests as req_fallback
            r = req_fallback.get(url, timeout=30, headers={
                **headers,
                'User-Agent': (
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/605.1.15 (KHTML, like Gecko) '
                    'Version/15.3 Safari/605.1.15'
                ),
            })
        if r.status_code == 200:
            return r.text
        if logger:
            logger.warning(f"[parts4cells] HTTP {r.status_code} for {url}")
        return None
    except Exception as e:
        if logger:
            logger.warning(f"[parts4cells] Fetch error for {url}: {e}")
        else:
            print(f"[parts4cells] Fetch error: {e}")
        return None


def _extract_canonical_url(soup: BeautifulSoup, fallback: str) -> str:
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and canonical.get('href'):
        return canonical['href']
    og_url = soup.select_one('meta[property="og:url"]')
    if og_url and og_url.get('content'):
        return og_url['content']
    return fallback


def _body_classes(soup: BeautifulSoup) -> str:
    body = soup.body
    if not body:
        return ""
    return ' '.join(body.get('class', []))


def _is_listing_page(soup: BeautifulSoup) -> bool:
    body_classes = _body_classes(soup)
    if 'catalog-category-view' in body_classes or 'catalogsearch-result-index' in body_classes:
        return True
    return bool(
        soup.select_one('.toolbar-amount, .products-grid, .pages')
        and soup.select('li.product-item')
    )


def _is_product_page(soup: BeautifulSoup) -> bool:
    body_classes = _body_classes(soup)
    if 'catalog-product-view' in body_classes:
        return True
    return bool(
        soup.select_one(
            '#product_addtocart_form, .product-info-main, .product.media, .product.attribute.sku'
        )
    )


def scrape_product_page(url: str, rules: dict, logger=None,
                        html: Optional[str] = None,
                        soup: Optional[BeautifulSoup] = None) -> Optional[Item]:
    """Scrape a Magento product detail page for richer metadata."""
    if soup is None:
        if html is None:
            html = _fetch(url, logger)
        if not html:
            return None
        soup = BeautifulSoup(html, 'html.parser')
    item = Item(site="parts4cells.com", url=_extract_canonical_url(soup, url))

    title_elem = (
        soup.select_one('h1.page-title .base') or
        soup.select_one('span[data-ui-id="page-title-wrapper"]') or
        soup.select_one('h1.page-title') or
        soup.select_one('h1')
    )
    item.title = clean_text(title_elem.get_text()) if title_elem else ""
    if not item.title:
        return None

    price_elem = (
        soup.select_one('span.price-final_price [data-price-amount]') or
        soup.select_one('[data-price-amount]') or
        soup.select_one('.price-box .price') or
        soup.select_one('.price')
    )
    if price_elem:
        raw = price_elem.get('data-price-amount') or price_elem.get_text()
        price_val = parse_price(raw)
        if price_val > 0:
            item.original = price_val
            item.discounted = price_val
            item.original_formatted = fmt_price(price_val)
            item.discounted_formatted = fmt_price(price_val)

    img_elem = (
        soup.select_one('.gallery-placeholder img') or
        soup.select_one('.fotorama__stage img') or
        soup.select_one('img.fotorama__img') or
        soup.select_one('meta[property="og:image"]')
    )
    if img_elem:
        item.image_url = img_elem.get('src') or img_elem.get('content') or img_elem.get('data-src') or ''
        if item.image_url and not item.image_url.startswith('http'):
            item.image_url = urljoin(url, item.image_url)

    sku_elem = (
        soup.select_one('.product.attribute.sku .value') or
        soup.select_one('.product-info-stock-sku .sku .value') or
        soup.select_one('[itemprop="sku"]')
    )
    if sku_elem:
        item.sku = clean_text(sku_elem.get('content') or sku_elem.get_text())

    stock_elem = (
        soup.select_one('.product-info-stock-sku .stock') or
        soup.select_one('.stock.available') or
        soup.select_one('.stock.unavailable') or
        soup.select_one('.stock')
    )
    if stock_elem:
        item.stock_status = clean_text(stock_elem.get_text())
    elif 'out-of-stock' in str(soup).lower() or 'outofstock' in str(soup).lower():
        item.stock_status = "Out of Stock"

    description_parts = []
    for sel in (
        '#description',
        '.product.attribute.description .value',
        '.product.attribute.overview .value',
        '[itemprop="description"]',
        'meta[name="description"]',
    ):
        el = soup.select_one(sel)
        if not el:
            continue
        text = strip_markup(el.get('content', '')) if el.name == 'meta' else strip_markup(el.get_text(' ', strip=True))
        if text and text not in description_parts:
            description_parts.append(text)
    item.description = ' '.join(description_parts).strip()

    _apply_rules(item, rules)
    item.extra.update({
        'sku': item.sku,
        'stock_status': item.stock_status,
        'description': item.description,
    })
    return item


def enrich_item_details(session, item: Item, rules: dict | None = None, logger=None) -> Item:
    """Merge a product detail page into a listing item."""
    detail = scrape_product_page(item.url, rules or {}, logger)
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


# ── Product Extraction ────────────────────────────────────────────────────────

def _extract_product(li, base_url: str) -> Optional[Item]:
    """
    Parse one <li class="item product product-item"> element.

    Price is in the onclick JSON:  "price":"20.00"
    Image may be a Magento placeholder — skip those.
    """
    try:
        item = Item(site="parts4cells.com")

        # Title + URL
        a = li.select_one('a.product-item-link')
        if not a:
            return None
        item.title = clean_text(a.get_text())
        href = a.get('href', '')
        item.url = href if href.startswith('http') else urljoin(base_url, href)

        if not item.title or not item.url:
            return None

        # Price from onclick data-layer JSON
        for sel in ('a.product-item-photo[onclick]', 'a.product-item-link[onclick]'):
            anchor = li.select_one(sel)
            if anchor:
                m = re.search(r'"price"\s*:\s*"?([\d.]+)"?', anchor.get('onclick', ''))
                if m:
                    try:
                        v = float(m.group(1))
                        item.original = v
                        item.discounted = v
                        item.original_formatted = fmt_price(v)
                        item.discounted_formatted = fmt_price(v)
                        break
                    except ValueError:
                        pass

        # Fallback: .price-box
        if item.original == 0.0:
            pe = li.select_one('.price-box .price, .price')
            if pe:
                v = parse_price(pe.get_text())
                item.original = v
                item.discounted = v
                item.original_formatted = fmt_price(v)
                item.discounted_formatted = fmt_price(v)

        # Image (skip placeholders)
        img = li.select_one('img.product-image-photo') or li.find('img')
        if img:
            src = img.get('src', '')
            if src and not any(p in src for p in _PLACEHOLDERS):
                item.image_url = src if src.startswith('http') else urljoin(base_url, src)

        # SKU is available on add-to-cart forms in the listing HTML.
        sku_holder = li.select_one('[data-product-sku]')
        if sku_holder:
            item.sku = clean_text(sku_holder.get('data-product-sku', ''))

        # Stock
        cls = ' '.join(li.get('class', []))
        if 'out-of-stock' in cls or 'outofstock' in cls:
            item.stock_status = "Out of Stock"
        elif 'instock' in cls:
            item.stock_status = "In Stock"

        stock_el = li.select_one('.stock span, .stock, .product-item-info span')
        if stock_el:
            stock_text = clean_text(stock_el.get_text())
            if 'out of stock' in stock_text.lower():
                item.stock_status = "Out of Stock"
            elif 'in stock' in stock_text.lower():
                item.stock_status = "In Stock"

        return item

    except Exception as e:
        print(f"[parts4cells] Parse error: {e}")
        return None


def _parse_total_and_limit(soup) -> tuple:
    """
    Parse the Magento toolbar to get (total_products, products_per_page).
    Toolbar text example: "Items 1-12 of 64"
    """
    toolbar = soup.select_one('.toolbar-amount')
    if toolbar:
        t = toolbar.get_text(strip=True)
        m = re.search(r'(\d+)\s*-\s*(\d+)\s+of\s+(\d+)', t)
        if m:
            start = int(m.group(1))
            end = int(m.group(2))
            total = int(m.group(3))
            per_page = end - start + 1
            return total, per_page
    return None, 12   # default Magento page size


# ── Apply Rules ───────────────────────────────────────────────────────────────

def _apply_rules(item: Item, rules: dict) -> Item:
    pct = float(rules.get('percent_off') or 0)
    fixed = float(rules.get('absolute_off') or 0)
    add_percent = float(rules.get('add_percent') or 0)
    disc = item.original
    if add_percent > 0:
        disc = disc * (1 + add_percent / 100.0)
    if pct > 0:
        disc = max(0.0, disc - disc * (pct / 100.0))
    if fixed > 0:
        disc = max(0.0, disc - fixed)
    item.discounted = round(disc, 2)
    item.discounted_formatted = fmt_price(item.discounted)
    return item


# ── Page URL Builder ──────────────────────────────────────────────────────────

def _page_url(base_url: str, page_num: int) -> str:
    """
    Build Magento page URL.
    Page 1: clean base URL (no ?p=) — parts4cells returns 403 for ?p=1
    Page 2+: base_url + ?p=N
    """
    # Strip any existing ?p= first
    parsed = urlparse(base_url)
    path = parsed.path or ''
    if path not in ('', '/') and not path.lower().endswith('.html'):
        path = f"{path.rstrip('/')}.html"
        parsed = parsed._replace(path=path)
    qs = parse_qs(parsed.query)
    qs.pop('p', None)
    clean_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

    if page_num <= 1:
        return clean_url

    qs['p'] = [str(page_num)]
    return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))


# ── Single-page Scraper ───────────────────────────────────────────────────────

def _scrape_one_page(url: str, rules: dict, logger=None,
                     html: Optional[str] = None,
                     soup: Optional[BeautifulSoup] = None) -> tuple:
    """
    Scrape one page. Returns (items, soup | None).
    soup is returned so the caller can parse pagination without a second request.
    """
    if soup is None:
        if html is None:
            html = _fetch(url, logger)
        if not html:
            return [], None
        soup = BeautifulSoup(html, 'html.parser')
    lis = soup.select('li.product-item') or soup.select('li.item.product') or soup.select('.product-item')

    if logger:
        logger.info(f"[parts4cells] {len(lis)} products at {url}")

    items = []
    for li in lis:
        item = _extract_product(li, url)
        if item:
            _apply_rules(item, rules)
            items.append(item)

    return items, soup


# ── Multi-page Scraper ────────────────────────────────────────────────────────

def _scrape_all_pages(base_url: str, rules: dict,
                      max_pages: int = 20, delay_ms: int = 300,
                      logger=None,
                      first_page_html: Optional[str] = None,
                      first_page_soup: Optional[BeautifulSoup] = None) -> List[Item]:
    all_items_by_url: dict = {}   # product_url -> Item (dedup)
    page_num = 1

    # Page 1 — fetch from clean base URL (no ?p= param)
    page_url = _page_url(base_url, 1)
    items, soup = _scrape_one_page(
        page_url,
        rules,
        logger,
        html=first_page_html,
        soup=first_page_soup,
    )

    if not items:
        return []

    for it in items:
        all_items_by_url[it.url] = it

    # Determine total pages from toolbar
    total, per_page = _parse_total_and_limit(soup) if soup else (None, 12)
    if total:
        num_pages = min(max_pages, -(-total // per_page))   # ceiling division
        if logger:
            logger.info(f"[parts4cells] {total} total products → {num_pages} pages of {per_page}")
    else:
        num_pages = max_pages
        if logger:
            logger.info(f"[parts4cells] Could not determine total — will scrape up to {max_pages} pages")

    canonical_listing_url = _extract_canonical_url(soup, page_url) if soup else page_url

    # Pages 2..N
    for p in range(2, num_pages + 1):
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        purl = _page_url(canonical_listing_url, p)
        page_items, _ = _scrape_one_page(purl, rules, logger)

        if not page_items:
            if logger:
                logger.info(f"[parts4cells] Empty page {p}, stopping")
            break

        # Detect loops: if all URLs already seen, we've wrapped
        new_items = [it for it in page_items if it.url not in all_items_by_url]
        if not new_items:
            if logger:
                logger.info(f"[parts4cells] Page {p} all duplicates (loop detected), stopping")
            break

        for it in new_items:
            all_items_by_url[it.url] = it

        if logger:
            logger.info(f"[parts4cells] Page {p}: {len(new_items)} new items (total so far: {len(all_items_by_url)})")

    result = list(all_items_by_url.values())
    if logger:
        logger.info(f"[parts4cells] Done: {len(result)} unique products")
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def scrape_url(session, url: str, rules: dict,
               crawl_pagination: bool = True,
               max_pages: int = 20,
               delay_ms: int = 300,
               logger=None) -> List[Item]:
    """Entry point called by app.py."""
    if logger:
        logger.info(f"[parts4cells] Starting: {url} (curl_cffi={'yes' if _HAS_CURL else 'no-fallback'})")

    parsed_path = urlparse(url).path.lower()
    initial_html = None
    initial_soup = None
    page_is_listing = False
    page_is_product = False

    if parsed_path.endswith('.html'):
        initial_html = _fetch(url, logger)
        if initial_html:
            initial_soup = BeautifulSoup(initial_html, 'html.parser')
            page_is_listing = _is_listing_page(initial_soup)
            page_is_product = _is_product_page(initial_soup)
            if page_is_product and not page_is_listing:
                product = scrape_product_page(url, rules, logger, html=initial_html, soup=initial_soup)
                return [product] if product else []

    if crawl_pagination:
        items = _scrape_all_pages(
            url,
            rules,
            max_pages,
            delay_ms,
            logger,
            first_page_html=initial_html if page_is_listing else None,
            first_page_soup=initial_soup if page_is_listing else None,
        )
        if items:
            return items
    else:
        items, _ = _scrape_one_page(
            url,
            rules,
            logger,
            html=initial_html if page_is_listing else None,
            soup=initial_soup if page_is_listing else None,
        )
        if items:
            return items

    product = scrape_product_page(url, rules, logger, html=initial_html, soup=initial_soup)
    return [product] if product else []
