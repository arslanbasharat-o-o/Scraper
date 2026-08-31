import os
import sys
import time
import json
import sqlite3
import re
import html as html_lib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ["SCRAPER_USE_BROWSER"] = "0"
sys.path.insert(0, '.')

from curl_cffi import requests
from scrapers.xcell_scraper_engine import scrape_category_page, Item
from database import db_manager

DB_PATH = 'data/site_dbs/mobilesentrix.db'
RUN_ID = 31
NUM_CAT_WORKERS = 20
NUM_DETAIL_WORKERS = 24

def clean_text(val):
    if not val:
        return ""
    return re.sub(r'\s+', ' ', str(val)).strip()

def fast_parse_detail_html(text: str):
    if not text:
        return None

    # Title
    t_match = re.search(r'<h1[^>]*class="[^"]*product_title[^"]*"[^>]*>(.*?)</h1>', text, re.DOTALL | re.IGNORECASE)
    title = html_lib.unescape(re.sub(r'<[^>]+>', '', t_match.group(1))).strip() if t_match else ""

    # SKU
    sku_match = re.search(r'data-product_sku="([^"]+)"', text, re.IGNORECASE)
    if not sku_match:
        sku_match = re.search(r'class="[^"]*sku[^"]*"[^>]*>(.*?)<', text, re.IGNORECASE)
    if not sku_match:
        sku_match = re.search(r'\bSKU[:\s]+([A-Za-z0-9][A-Za-z0-9 _\-]{1,38}?)(?=\s+(?:IPHONE|SAMSUNG|APPLE|HUAWEI|\$|In stock|Out of))', text, re.IGNORECASE)
    sku = clean_text(html_lib.unescape(sku_match.group(1))) if sku_match else ""

    # Stock
    stock_match = re.search(r'class="[^"]*stock[^"]*"[^>]*>(.*?)<', text, re.IGNORECASE)
    stock = clean_text(html_lib.unescape(stock_match.group(1))) if stock_match else ("Out of Stock" if "outofstock" in text.lower() else "In Stock")

    # Description
    desc_match = re.search(r'class="[^"]*woocommerce-product-details__short-description[^"]*"[^>]*>(.*?)</div>', text, re.DOTALL | re.IGNORECASE)
    desc = clean_text(html_lib.unescape(re.sub(r'<[^>]+>', ' ', desc_match.group(1)))) if desc_match else ""

    # Image
    img_match = re.search(r'class="[^"]*woocommerce-product-gallery__image[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"', text, re.IGNORECASE)
    if not img_match:
        img_match = re.search(r'class="[^"]*wp-post-image[^"]*"[^>]*src="([^"]+)"', text, re.IGNORECASE)
    image_url = img_match.group(1).strip() if img_match else ""

    return {
        'title': title,
        'sku': sku,
        'stock_status': stock,
        'description': desc,
        'image_url': image_url
    }

def main():
    print(f"[{time.strftime('%X')}] ===============================================", flush=True)
    print(f"[{time.strftime('%X')}] STARTING FULL TURBO PIPELINE FOR RUN #{RUN_ID}", flush=True)
    print(f"[{time.strftime('%X')}] ===============================================", flush=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, job_id, target_urls_json FROM automation_runs WHERE id=?", (RUN_ID,))
    row = cursor.fetchone()
    if not row:
        print(f"Error: Run #{RUN_ID} not found.", flush=True)
        conn.close()
        return

    run_id, job_id, target_urls_json = row
    target_urls = json.loads(target_urls_json) if target_urls_json else []
    conn.close()

    total_targets = len(target_urls)
    print(f"[{time.strftime('%X')}] Loaded {total_targets:,} category targets to crawl...", flush=True)

    # 1. Thread-local session pool
    thread_local = threading.local()
    def get_session():
        if not hasattr(thread_local, 'session'):
            thread_local.session = requests.Session(impersonate="safari15_5")
        return thread_local.session

    # -------------------------------------------------------------
    # PHASE 1: Fast Parallel Category Crawling
    # -------------------------------------------------------------
    print(f"\n[{time.strftime('%X')}] >>> PHASE 1: Harvesting all category targets with {NUM_CAT_WORKERS} workers...", flush=True)

    def crawl_category(url):
        s = get_session()
        items = scrape_category_page(s, url, rules={'percent_off': 0, 'absolute_off': 0})
        return url, items

    harvested_items = []
    seen_key = set()
    cat_done = 0
    p1_start = time.time()
    last_db_save = time.time()

    with ThreadPoolExecutor(max_workers=NUM_CAT_WORKERS) as executor:
        future_map = {executor.submit(crawl_category, u): u for u in target_urls}
        for fut in as_completed(future_map):
            try:
                url, cat_items = fut.result()
                for it in cat_items:
                    item_dict = {
                        'title': it.title,
                        'url': it.url,
                        'image_url': it.image_url,
                        'original': it.original,
                        'discounted': it.discounted,
                        'original_formatted': it.original_formatted,
                        'discounted_formatted': it.discounted_formatted,
                        'site': it.site or 'xcellparts.com',
                        'sku': it.sku or '',
                        'stock_status': it.stock_status or 'In Stock',
                        'description': it.description or '',
                    }
                    dedup_k = (it.url, it.title)
                    if dedup_k not in seen_key:
                        seen_key.add(dedup_k)
                        harvested_items.append(item_dict)
            except Exception:
                pass

            cat_done += 1
            now = time.time()

            if cat_done % 50 == 0 or cat_done == total_targets:
                elapsed = now - p1_start
                rate = (cat_done / max(0.1, elapsed)) * 60
                eta_m = ((total_targets - cat_done) / max(0.1, rate)) if rate > 0 else 0
                pct = round((cat_done / total_targets) * 100, 1)
                print(f"[{time.strftime('%X')}] [P1 Categories] {cat_done:,}/{total_targets:,} ({pct}%) | Harvested: {len(harvested_items):,} products | Speed: {round(rate, 1)} cat/min | ETA: {round(eta_m, 1)}m", flush=True)

            if now - last_db_save > 15 or cat_done == total_targets:
                last_db_save = now
                try:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    summary = {
                        'phase': 'crawling',
                        'completed_targets': cat_done,
                        'total_targets': total_targets,
                        'recent_targets_per_min': round(rate, 1),
                        'current_items': len(harvested_items),
                        'preview_items': harvested_items[:100]
                    }
                    c.execute("UPDATE automation_runs SET summary_json=?, items_count=?, status='running' WHERE id=?",
                              (json.dumps(summary), len(harvested_items), RUN_ID))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

    p1_duration = time.time() - p1_start
    total_products = len(harvested_items)
    print(f"\n[{time.strftime('%X')}] >>> PHASE 1 COMPLETE! Harvested {total_products:,} products across {total_targets:,} categories in {round(p1_duration/60, 1)} minutes!", flush=True)

    # -------------------------------------------------------------
    # PHASE 2: Fast Product Detail & SKU Enrichment
    # -------------------------------------------------------------
    print(f"\n[{time.strftime('%X')}] >>> PHASE 2: Enriching SKUs & Descriptions with {NUM_DETAIL_WORKERS} workers...", flush=True)

    url_to_indexes = {}
    for idx, it in enumerate(harvested_items):
        u = str(it.get('url') or '').strip()
        if u:
            url_to_indexes.setdefault(u, []).append(idx)

    unique_urls = list(url_to_indexes.keys())
    total_unique = len(unique_urls)
    print(f"[{time.strftime('%X')}] Unique Product URLs to enrich: {total_unique:,}", flush=True)

    def enrich_detail(url):
        s = get_session()
        try:
            r = s.get(url, timeout=15)
            if r.status_code == 200:
                parsed = fast_parse_detail_html(r.text)
                return url, parsed
        except Exception:
            pass
        return url, None

    detail_done = 0
    p2_start = time.time()
    last_db_save = time.time()

    with ThreadPoolExecutor(max_workers=NUM_DETAIL_WORKERS) as executor:
        future_map = {executor.submit(enrich_detail, u): u for u in unique_urls}
        for fut in as_completed(future_map):
            try:
                url, detail = fut.result()
                if detail:
                    for idx in url_to_indexes[url]:
                        if detail.get('sku'):
                            harvested_items[idx]['sku'] = detail['sku']
                        if detail.get('stock_status'):
                            harvested_items[idx]['stock_status'] = detail['stock_status']
                        if detail.get('description'):
                            harvested_items[idx]['description'] = detail['description']
                        if detail.get('image_url') and not harvested_items[idx].get('image_url'):
                            harvested_items[idx]['image_url'] = detail['image_url']
            except Exception:
                pass

            detail_done += 1
            now = time.time()

            if detail_done % 100 == 0 or detail_done == total_unique:
                elapsed = now - p2_start
                rate = (detail_done / max(0.1, elapsed)) * 60
                eta_m = ((total_unique - detail_done) / max(0.1, rate)) if rate > 0 else 0
                pct = round((detail_done / total_unique) * 100, 1)
                print(f"[{time.strftime('%X')}] [P2 Details] {detail_done:,}/{total_unique:,} ({pct}%) | Speed: {round(rate, 1)} prod/min | ETA: {round(eta_m, 1)}m", flush=True)

            if now - last_db_save > 15 or detail_done == total_unique:
                last_db_save = now
                try:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    summary = {
                        'phase': 'enrichment',
                        'completed_targets': total_targets,
                        'total_targets': total_targets,
                        'current_items': total_products,
                        'enriched_unique': detail_done,
                        'total_unique': total_unique,
                        'preview_items': harvested_items[:100]
                    }
                    c.execute("UPDATE automation_runs SET summary_json=?, items_count=? WHERE id=?",
                              (json.dumps(summary), total_products, RUN_ID))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

    # -------------------------------------------------------------
    # FINAL COMMIT
    # -------------------------------------------------------------
    print(f"\n[{time.strftime('%X')}] Saving entire master catalog ({total_products:,} items) to database...", flush=True)
    history_id = str(int(time.time() * 1000))
    history_rules = {
        '_automation_job_id': job_id,
        '_automation_job_name': 'XCell Parts',
        '_automation_category_query': 'xcellparts.com'
    }

    db_manager.save_fetch_history(history_id, target_urls, harvested_items, history_rules)
    final_summary = {
        'phase': 'completed',
        'current_items': total_products,
        'completed_targets': total_targets,
        'total_targets': total_targets,
        'preview_items': harvested_items[:100]
    }

    db_manager.complete_automation_run(
        RUN_ID,
        status='completed',
        current_history_id=history_id,
        target_urls=target_urls,
        items_count=total_products,
        summary=final_summary
    )

    with_sku_final = [it for it in harvested_items if it.get('sku')]
    with_desc_final = [it for it in harvested_items if it.get('description')]
    print(f"[{time.strftime('%X')}] ===============================================", flush=True)
    print(f"[{time.strftime('%X')}] RUN #{RUN_ID} COMPLETED & COMMITTED!", flush=True)
    print(f"[{time.strftime('%X')}] Total Products: {total_products:,}", flush=True)
    print(f"[{time.strftime('%X')}] Products with SKU: {len(with_sku_final):,} ({round(len(with_sku_final)/max(1, total_products)*100, 1)}%)", flush=True)
    print(f"[{time.strftime('%X')}] Products with Description: {len(with_desc_final):,} ({round(len(with_desc_final)/max(1, total_products)*100, 1)}%)", flush=True)
    print(f"[{time.strftime('%X')}] History ID: {history_id}", flush=True)
    print(f"[{time.strftime('%X')}] ===============================================", flush=True)

if __name__ == '__main__':
    main()
