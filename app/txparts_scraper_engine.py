"""
TXParts Scraper Engine

Specialized scraper for txparts.com with proper title, price, and image extraction.
This engine is automatically used when scraping txparts.com URLs.

Author: Arslan
Created for: TXParts
"""

import requests
import time
import re
import json
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import List, Optional
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
    """Extract numeric price from string like '$14.49' or '14.49'"""
    if not price_str:
        return 0.0
    clean = re.sub(r'[^\d.]', '', str(price_str))
    try:
        return float(clean) if clean else 0.0
    except (ValueError, TypeError):
        return 0.0

def fmt_price(val: float) -> str:
    """Format price as currency string"""
    return f"${val:.2f}"


def _pick_last_srcset_url(value: str) -> str:
    if not value:
        return ""
    parts = [segment.strip() for segment in str(value).split(',') if segment.strip()]
    if not parts:
        return ""
    return parts[-1].split()[0].strip()


def _read_image_candidate_url(el) -> str:
    if not el:
        return ""
    for attr in ('data-zoom', 'data-srcset', 'srcset', 'data-src', 'data-original', 'src', 'content'):
        value = el.get(attr)
        if not value:
            continue
        if 'srcset' in attr:
            return _pick_last_srcset_url(value)
        return str(value).strip()
    return ""


def _is_decorative_image_candidate(image_url: str, el) -> bool:
    if not image_url:
        return True
    lower_url = image_url.lower()
    hints = ' '.join([
        str(el.get('alt', '') or ''),
        str(el.get('title', '') or ''),
        ' '.join(el.get('class', []) or []),
    ]).lower()
    combined = f"{lower_url} {hints}"
    return any(marker in combined for marker in (
        'logo', 'icon', 'badge', 'placeholder', 'wishlist', 'cart.svg',
        'user.svg', 'search-white', 'arrow-right', 'truck.svg', 'spinner',
        'loader',
    ))


def extract_image_url(soup: BeautifulSoup, base_url: str) -> str:
    selectors = (
        'meta[property="og:image"]',
        'img[data-zoom]',
        '.product-detail-gallery img',
        '.gallery-top img',
        '.gallery-thumbs img',
        '.woocommerce-product-gallery__image img',
        'img.wp-post-image',
        'img[data-srcset]',
        'img[srcset]',
        'img[data-src]',
        'img[src]',
    )
    best_url = ""
    best_score = -10_000
    seen = set()
    for order, selector in enumerate(selectors):
        for el in soup.select(selector):
            raw_url = _read_image_candidate_url(el)
            if not raw_url:
                continue
            image_url = urljoin(base_url, raw_url).strip()
            if not image_url or image_url in seen:
                continue
            seen.add(image_url)
            if _is_decorative_image_candidate(image_url, el):
                continue
            score = -order
            if selector.startswith('meta['):
                score += 120
            if any(token in selector for token in ('data-zoom', 'product-detail-gallery', 'gallery-top', 'gallery-thumbs', 'woocommerce-product-gallery')):
                score += 80
            if any(token in image_url.lower() for token in ('/assets/products/', '/uploads/')):
                score += 40
            if score > best_score:
                best_score = score
                best_url = image_url
    return best_url


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
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    
    return session, False

def get_html(session, url: str) -> Optional[str]:
    """Fetch HTML content from URL"""
    try:
        response = session.get(url, timeout=30)  # Consistent 30s timeout
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"[txparts] Failed to fetch {url}: {e}")
        return None


def extract_canonical_url(soup: BeautifulSoup, fallback: str) -> str:
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and canonical.get('href'):
        return canonical['href']
    og_url = soup.select_one('meta[property="og:url"]')
    if og_url and og_url.get('content'):
        return og_url['content']
    return fallback


def scrape_product_page(session, url: str, rules: dict, logger=None) -> Optional[Item]:
    """Scrape a TXParts product detail page."""
    html = get_html(session, url)
    if not html:
        return None

    soup = BeautifulSoup(html, 'lxml')
    item = Item(site="txparts.com", url=extract_canonical_url(soup, url))

    title_elem = (
        soup.select_one('h1.product_title') or
        soup.select_one('h1.entry-title') or
        soup.select_one('.product_title') or
        soup.select_one('h1')
    )
    item.title = clean_text(title_elem.get_text()) if title_elem else ""

    price_elem = (
        soup.select_one('.price-box[data-default-price]') or
        soup.select_one('[data-price-amount]') or
        soup.select_one('.getFormattedPrice') or
        soup.select_one('.summary .price .woocommerce-Price-amount') or
        soup.select_one('.summary .price .amount') or
        soup.select_one('.price .woocommerce-Price-amount') or
        soup.select_one('.price')
    )
    if price_elem:
        price_text = ''
        if price_elem.get('data-default-price'):
            try:
                raw = price_elem.get('data-default-price', '').replace('&quot;', '"')
                price_text = str(json.loads(raw).get('price') or '')
            except Exception:
                price_text = ''
        if not price_text:
            price_text = clean_text(price_elem.get('data-price-amount') or price_elem.get_text())
        price_val = parse_price_number(price_text)
        if price_val > 0:
            item.original = price_val
            item.discounted = price_val
            item.original_formatted = fmt_price(price_val)
            item.discounted_formatted = fmt_price(price_val)

    item.image_url = extract_image_url(soup, url)

    sku_elem = (
        soup.select_one('.badge-sku span:last-child') or
        soup.select_one('.product_meta .sku_wrapper .sku') or
        soup.select_one('.sku') or
        soup.select_one('[itemprop="sku"]') or
        soup.select_one('[data-product-sku]') or
        soup.select_one('[data-product_sku]')
    )
    if sku_elem:
        item.sku = clean_text(sku_elem.get_text() or sku_elem.get('content') or sku_elem.get('data-product-sku') or sku_elem.get('data-product_sku', ''))
    if not item.sku:
        text = clean_text(soup.get_text(' ', strip=True))
        match = re.search(r'\bSKU\b\s*[:#-]?\s*([A-Za-z0-9._/-]{3,})', text, re.I)
        if match:
            item.sku = clean_text(match.group(1))

    stock_elem = (
        soup.select_one('.stock') or
        soup.select_one('.availability') or
        soup.select_one('[class*="stock"]')
    )
    if stock_elem:
        item.stock_status = clean_text(stock_elem.get_text())
    elif soup.select_one('.out-stock-btn, [data-title*="Out Of Stock"], a[href*="notifyme-outstock"]'):
        item.stock_status = "Out of Stock"
    elif 'out-of-stock' in str(soup).lower() or 'outofstock' in str(soup).lower():
        item.stock_status = "Out of Stock"

    description_parts = []
    for sel in (
        '.product-detail-desc-content',
        '.woocommerce-product-details__short-description',
        '.woocommerce-Tabs-panel--description',
        '#tab-description',
        '.product-description',
        '.entry-content',
        'meta[name="description"]',
    ):
        el = soup.select_one(sel)
        if not el:
            continue
        text = strip_markup(el.get('content', '')) if el.name == 'meta' else strip_markup(el.get_text(' ', strip=True))
        if text and text not in description_parts:
            description_parts.append(text)
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
    return item if item.url else None


def enrich_item_details(session, item: Item, rules: dict | None = None, logger=None) -> Item:
    """Merge TXParts detail-page metadata into an existing listing item."""
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

def extract_products_from_page(soup, base_url: str) -> List[Item]:
    """
    Extract all products from a TXParts category page
    
    TXParts Structure:
    - Product images in <div class="flipper">
    - Product titles and prices after the flipper
    - Links with /product/ in href
    """
    items = []
    
    # Find all product links (excluding stretched-link which is for the image)
    product_links = soup.find_all('a', href=lambda x: x and '/product/' in x)
    
    # Group links - TXParts has 2 links per product (image link + title link)
    seen_urls = {}
    
    for link in product_links:
        url = urljoin(base_url, link.get('href', ''))
        
        if url in seen_urls:
            continue
        
        # Create item
        item = Item()
        item.site = "txparts.com"
        item.url = url
        
        # Get title from link text
        title_text = clean_text(link.get_text())
        if title_text and len(title_text) > 5:  # Valid title
            item.title = title_text
        
        # If no title yet, try to find it nearby
        if not item.title:
            # Look for title in parent or sibling elements
            parent = link.parent
            if parent:
                # Try finding a text node with product name
                for elem in parent.find_all(['h6', 'h5', 'h4', 'a']):
                    text = clean_text(elem.get_text())
                    if text and len(text) > 10 and '/product/' in elem.get('href', ''):
                        item.title = text
                        break
        
        # Find price - look in parent container
        price_found = False
        search_parent = link.parent
        attempts = 0
        while search_parent and attempts < 5:
            # Look for price pattern
            price_match = re.search(r'\$(\d+\.?\d*)', search_parent.get_text())
            if price_match:
                price_val = parse_price_number(price_match.group())
                if price_val > 0:
                    item.original = price_val
                    item.discounted = price_val
                    item.original_formatted = fmt_price(price_val)
                    item.discounted_formatted = fmt_price(price_val)
                    price_found = True
                    break
            search_parent = search_parent.parent
            attempts += 1
        
        # Find image - look backwards for flipper div with image OR any img in parent
        img_found = False
        if link.parent:
            # Look for previous sibling or parent with flipper class
            container = link.parent.parent if link.parent.parent else link.parent
            flipper = container.find('div', class_='flipper') if container else None
            
            if not flipper:
                # Try finding in previous siblings
                for prev_sibling in link.parent.find_previous_siblings():
                    flipper = prev_sibling.find('div', class_='flipper')
                    if flipper:
                        break
            
            if flipper:
                img = flipper.find('img')
                if img:
                    img_url = img.get('src') or img.get('data-src') or ''
                    if img_url:
                        item.image_url = urljoin(base_url, img_url)
                        img_found = True
            
            # If no flipper found, search for any product image in parent/grandparent
            if not img_found and link.parent:
                # Search in parent
                search_container = link.parent
                for _ in range(3):  # Check up to 3 levels up
                    if search_container:
                        img = search_container.find('img', src=lambda x: x and 'admin.txparts.com' in x)
                        if img:
                            img_url = img.get('src') or img.get('data-src') or ''
                            if img_url:
                                item.image_url = urljoin(base_url, img_url)
                                img_found = True
                                break
                        search_container = search_container.parent
        
        # Only add item if we have at least title or URL
        if item.title or (item.url and price_found):
            # If no title, use a default from URL
            if not item.title:
                # Extract title from URL
                url_parts = item.url.split('/')
                if url_parts:
                    slug = url_parts[-1]
                    item.title = slug.replace('-', ' ').title()
            
            seen_urls[url] = True
            items.append(item)
    
    return items

def scrape_category_page(session, url: str, rules: dict, logger=None) -> List[Item]:
    """
    Scrape a single category page from txparts.com
    """
    items = []
    
    html = get_html(session, url)
    if not html:
        if logger:
            logger.warning(f"[txparts] Failed to fetch HTML from {url}")
        return items
    
    soup = BeautifulSoup(html, 'lxml')
    
    # Extract products
    items = extract_products_from_page(soup, url)
    
    if logger:
        logger.info(f"[txparts] Found {len(items)} products on page: {url}")
    
    # Apply discount rules
    for item in items:
        adjusted_price = apply_price_rules(item.original, rules)
        if adjusted_price != round(float(item.original or 0.0), 2):
            item.discounted = adjusted_price
            item.discounted_formatted = fmt_price(item.discounted)
    
    return items

def scrape_url(session, url: str, rules: dict, crawl_pagination: bool = True,
               max_pages: int = 20, delay_ms: int = 200, logger=None) -> List[Item]:
    """
    Main entry point for scraping TXParts URLs
    """
    if logger:
        logger.info(f"[txparts] Starting scrape of: {url}")
    
    if '/product/' in url:
        item = scrape_product_page(session, url, rules, logger)
        return [item] if item else []

    # TXParts doesn't have traditional pagination on category pages.
    return scrape_category_page(session, url, rules, logger)
