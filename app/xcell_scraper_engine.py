"""
XCellParts Scraper Engine

Specialized scraper for xcellparts.com with proper title, price, and image extraction.
This engine is automatically used when scraping xcellparts.com URLs.

Author: Arslan
Created for: TXParts
"""

import requests
import time
import re
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import List, Optional, Any
from urllib.parse import urljoin, urlparse

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

def build_session(retries: int = 2, verify_ssl: bool = True) -> tuple:
    """Build HTTP session with retry logic"""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
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
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    
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


def scrape_product_page(session, url: str, rules: dict, logger=None) -> Optional[Item]:
    """Scrape a single WooCommerce product detail page for richer metadata."""
    html = get_html(session, url)
    if not html:
        return None

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

    sku_elem = (
        soup.select_one('.product_meta .sku_wrapper .sku') or
        soup.select_one('.sku') or
        soup.select_one('[itemprop="sku"]')
    )
    if sku_elem:
        item.sku = clean_text(sku_elem.get_text() or sku_elem.get('content', ''))

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
        logger.info(f"[xcell] Enriched detail page: {item.url}")
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
    """Fetch HTML content from URL"""
    try:
        response = session.get(url, timeout=30)  # Increased from 30 to 30 (keep consistent)
        response.raise_for_status()
        html = response.text
        if is_html_document(html):
            return html

        # Some XCell responses come back Brotli-encoded if "br" is advertised upstream.
        retry_headers = dict(session.headers)
        retry_headers['Accept-Encoding'] = 'gzip, deflate'
        retry_response = session.get(url, timeout=30, headers=retry_headers)
        retry_response.raise_for_status()
        retry_html = retry_response.text
        if is_html_document(retry_html):
            return retry_html

        print(f"[xcell] Response for {url} did not look like HTML after retry")
        return None
    except Exception as e:
        print(f"[xcell] Failed to fetch {url}: {e}")
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
        sku_elem = product_elem.select_one('[data-product_sku]')
        if sku_elem:
            item.sku = clean_text(sku_elem.get('data-product_sku', ''))

        # Check stock status - xcellparts shows "out-of-stock" class or text
        if (product_elem.select_one('.out-of-stock') or 
            'outofstock' in ' '.join(product_elem.get('class', [])).lower() or
            'OUT OF STOCK' in product_elem.get_text().upper()):
            item.stock_status = "Out of Stock"
        
        return item if item.title and item.url else None
        
    except Exception as e:
        print(f"[xcell] Failed to parse product element: {e}")
        return None

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
    items = []
    
    html = get_html(session, url)
    if not html:
        if logger:
            logger.warning(f"[xcell] Failed to fetch HTML from {url}")
        return items
    
    soup = parse_html_document(html)
    if not soup:
        if logger:
            logger.warning(f"[xcell] Failed to parse HTML from {url}")
        return items
    
    # XCellParts uses WooCommerce structure
    # Products are in <ul class="products"> with <li class="product"> items
    product_containers = soup.select('ul.products li.product') or soup.select('.products .product')
    
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
    
    return items

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
    
    while current_url and page_num <= max_pages:
        if logger:
            logger.info(f"[xcell] Scraping page {page_num}/{max_pages}: {current_url}")
        
        # Scrape current page
        page_items = scrape_category_page(session, current_url, rules, logger)
        all_items.extend(page_items)
        
        if not page_items:
            if logger:
                logger.info(f"[xcell] No items found on page {page_num}, stopping pagination")
            break
        
        # Get HTML to find next page
        html = get_html(session, current_url)
        if not html:
            break
        
        soup = parse_html_document(html)
        if not soup:
            if logger:
                logger.warning(f"[xcell] Failed to parse pagination HTML from {current_url}")
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
