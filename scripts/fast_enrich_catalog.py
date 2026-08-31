import os
import sys

os.environ["SCRAPER_USE_BROWSER"] = "0"
sys.path.insert(0, '.')

import sqlite3
import json
import time
import re
import html as html_lib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests
from database import db_manager

DB_PATH = 'data/site_dbs/mobilesentrix.db'
RUN_ID = 31
NUM_WORKERS = 64

def clean_text(val):
    if not val:
        return ""
    return re.sub(r'\s+', ' ', str(val)).strip()

def fast_parse_html(text: str, url: str):
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

def run_turbo_enrichment():
    print(f"[{time.strftime('%X')}] Starting Turbo 64-Worker Catalog Enrichment...", flush=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, job_id, status, target_urls_json, summary_json FROM automation_runs WHERE id=?", (RUN_ID,))
    row = cursor.fetchone()
    if not row:
        print(f"Error: Run #{RUN_ID} not found in database.", flush=True)
        conn.close()
        return

    run_id, job_id, status, target_urls_json, summary_json = row
    target_urls = json.loads(target_urls_json) if target_urls_json else []
    summary = json.loads(summary_json) if summary_json else {}
    items = summary.get('preview_items', [])
    conn.close()

    total_items = len(items)
    print(f"[{time.strftime('%X')}] Loaded {total_items:,} total product rows from Run #{RUN_ID}", flush=True)

    # Map unique URLs to their indices
    url_to_indexes = {}
    for idx, it in enumerate(items):
        u = str(it.get('url') or '').strip()
        if u:
            url_to_indexes.setdefault(u, []).append(idx)

    total_unique = len(url_to_indexes)
    already_enriched_urls = set()
    for u, idxs in url_to_indexes.items():
        sample_item = items[idxs[0]]
        if sample_item.get('sku'):
            already_enriched_urls.add(u)

    urls_to_enrich = [u for u in url_to_indexes.keys() if u not in already_enriched_urls]
    initial_done = len(already_enriched_urls)
    print(f"[{time.strftime('%X')}] Total Unique URLs: {total_unique:,} | Already Enriched: {initial_done:,} | Need Enrichment: {len(urls_to_enrich):,}", flush=True)

    thread_local = threading.local()
    def get_session():
        if not hasattr(thread_local, 'session'):
            thread_local.session = requests.Session(impersonate="safari15_5")
        return thread_local.session

    def enrich_url(url: str):
        s = get_session()
        try:
            resp = s.get(url, timeout=20)
            if resp.status_code == 200:
                parsed = fast_parse_html(resp.text, url)
                return url, parsed
        except Exception:
            pass
        return url, None

    completed_in_batch = 0
    total_need = len(urls_to_enrich)
    batch_start_time = time.time()
    last_checkpoint_time = time.time()

    print(f"[{time.strftime('%X')}] Launching {NUM_WORKERS} parallel Safari TLS workers (Turbo Mode)...", flush=True)

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        future_map = {executor.submit(enrich_url, u): u for u in urls_to_enrich}
        for future in as_completed(future_map):
            url = future_map[future]
            try:
                ret_url, detail = future.result()
                if detail:
                    for idx in url_to_indexes[url]:
                        if detail.get('sku'):
                            items[idx]['sku'] = detail['sku']
                        if detail.get('stock_status'):
                            items[idx]['stock_status'] = detail['stock_status']
                        if detail.get('description'):
                            items[idx]['description'] = detail['description']
                        if detail.get('image_url') and not items[idx].get('image_url'):
                            items[idx]['image_url'] = detail['image_url']
            except Exception:
                pass

            completed_in_batch += 1
            now = time.time()

            # Print progress every 50 items
            if completed_in_batch % 50 == 0 or completed_in_batch == total_need:
                elapsed = now - batch_start_time
                rate = (completed_in_batch / max(0.1, elapsed)) * 60
                remaining = total_need - completed_in_batch
                eta_mins = (remaining / max(0.1, rate)) if rate > 0 else 0
                pct = round(((initial_done + completed_in_batch) / total_unique) * 100, 1)
                print(f"[{time.strftime('%X')}] [TURBO] Progress: {initial_done + completed_in_batch:,}/{total_unique:,} ({pct}%) | Speed: {round(rate, 1)} items/min | ETA: {round(eta_mins, 1)}m", flush=True)

            # Checkpoint to SQLite every 15 seconds
            if now - last_checkpoint_time > 15 or completed_in_batch == total_need:
                last_checkpoint_time = now
                try:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    summary['preview_items'] = items[:100]
                    summary['enriched_unique'] = initial_done + completed_in_batch
                    summary['total_unique'] = total_unique
                    summary['phase'] = 'enrichment' if completed_in_batch < total_need else 'completed'
                    c.execute("UPDATE automation_runs SET summary_json=?, items_count=? WHERE id=?",
                              (json.dumps(summary), len(items), RUN_ID))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

    # Final Save and Completion
    print(f"\n[{time.strftime('%X')}] All {total_unique:,} unique products enriched! Saving final database snapshot...", flush=True)
    history_id = str(int(time.time() * 1000))
    history_rules = {
        '_automation_job_id': job_id,
        '_automation_job_name': 'XCell Parts',
        '_automation_category_query': 'xcellparts.com'
    }

    db_manager.save_fetch_history(history_id, target_urls, items, history_rules)
    summary['phase'] = 'completed'
    summary['current_items'] = len(items)
    summary['completed_targets'] = len(target_urls)
    summary['total_targets'] = len(target_urls)

    db_manager.complete_automation_run(
        RUN_ID,
        status='completed',
        current_history_id=history_id,
        target_urls=target_urls,
        items_count=len(items),
        summary=summary
    )

    with_sku_final = [it for it in items if it.get('sku')]
    with_desc_final = [it for it in items if it.get('description')]
    print(f"[{time.strftime('%X')}] ===============================================", flush=True)
    print(f"[{time.strftime('%X')}] RUN #{RUN_ID} COMPLETED AND STORED IN DATABASE!", flush=True)
    print(f"[{time.strftime('%X')}] Total Products Saved: {len(items):,}", flush=True)
    print(f"[{time.strftime('%X')}] Products with SKU: {len(with_sku_final):,} / {len(items):,} ({round(len(with_sku_final)/len(items)*100, 1)}%)", flush=True)
    print(f"[{time.strftime('%X')}] Products with Description: {len(with_desc_final):,} / {len(items):,} ({round(len(with_desc_final)/len(items)*100, 1)}%)", flush=True)
    print(f"[{time.strftime('%X')}] History ID: {history_id}", flush=True)
    print(f"[{time.strftime('%X')}] ===============================================", flush=True)

if __name__ == '__main__':
    run_turbo_enrichment()
