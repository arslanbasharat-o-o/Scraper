import sys
import os
import time
import json

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import execute_scrape_workflow
from scrapers import detect_scraper_key, SCRAPER_CONFIG

# Define minimum 10 categories across all supported supplier engines
TEST_CATEGORIES = [
    # 1. MobileSentrix US (Standard)
    ("MobileSentrix US - iPhone 15", "https://www.mobilesentrix.com/replacement-parts/apple/iphone-parts/iphone-15"),
    ("MobileSentrix US - iPad", "https://www.mobilesentrix.com/replacement-parts/apple/ipad-parts"),

    # 2. MobileSentrix Canada
    ("MobileSentrix CA - iPhone 15", "https://www.mobilesentrix.ca/replacement-parts/apple/iphone-parts/iphone-15"),

    # 3. XCellParts
    ("XCellParts - Z Fold", "https://xcellparts.com/product-category/samsung/galaxy-z-series/"),
    ("XCellParts - iPhone 15 Pro", "https://xcellparts.com/product-category/apple/iphone/iphone-15-pro/"),

    # 4. Parts4Cells
    ("Parts4Cells - iPhone", "https://parts4cells.com/apple/iphone.html"),
    ("Parts4Cells - Samsung", "https://parts4cells.com/samsung.html"),

    # 5. TXParts (US & CA)
    ("TXParts - iPhone", "https://txparts.com/shop/iphone"),
    ("TXParts CA - iPhone 15", "https://txpartscanada.ca/shop/iphone-15"),

    # 6. PhoneLCDParts
    ("PhoneLCDParts - QMax", "https://www.phonelcdparts.com/apple/best-sellers/qmax"),

    # 7. GadgetFix
    ("GadgetFix - iPhone", "https://gadgetfix.com/category/iphone-1559.html"),
]

print("=" * 80)
print(f"LIVE TEST SUITE: {len(TEST_CATEGORIES)} CATEGORIES ACROSS ALL SUPPLIER ENGINES")
print("Settings: crawl_pagination=True, max_pages=1, enrich_details=True, delay_ms=50")
print("=" * 80)

results_summary = []

for idx, (label, url) in enumerate(TEST_CATEGORIES, 1):
    scraper_key = detect_scraper_key(url)
    cfg = SCRAPER_CONFIG.get(scraper_key, {})
    site_label = cfg.get("label", scraper_key)

    print(f"\n[{idx}/{len(TEST_CATEGORIES)}] Testing {label} ({site_label})...")
    print(f"    URL: {url}")

    t0 = time.time()
    try:
        res = execute_scrape_workflow(
            url,
            crawl_pagination=True,
            max_pages=1,
            delay_ms=50,
            retries=1,
            enrich_details=True,
            use_parallel=True
        )
        elapsed = time.time() - t0

        items_count = res.get("count", len(res.get("items", [])))
        using_browser = res.get("using_browser", False)
        using_curl = res.get("using_curl", False)
        sample_item = res.get("items", [])[0] if res.get("items") else {}

        sku = sample_item.get("sku") or (sample_item.get("extra") or {}).get("sku") or "-"
        price = sample_item.get("price_text") or sample_item.get("price") or (sample_item.get("extra") or {}).get("price_text") or "-"
        title = sample_item.get("title") or "-"

        status = "PASSED" if items_count > 0 else "EMPTY (0 items)"

        print(f"    Result: {status} in {elapsed:.2f}s | Scraped {items_count} items")
        print(f"    Engine Used: {'Browser (Botasaurus)' if using_browser else 'Fast HTTP (Safari TLS)'}")
        if items_count > 0:
            print(f"    Sample Product: {title[:55]}... | Price: {price} | SKU: {sku}")

        results_summary.append({
            "label": label,
            "site": site_label,
            "url": url,
            "count": items_count,
            "elapsed_sec": round(elapsed, 2),
            "status": status,
            "engine": "Browser" if using_browser else "HTTP",
            "sample_title": title[:50],
            "sample_sku": sku,
            "sample_price": str(price)
        })
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"    ERROR: {exc}")
        results_summary.append({
            "label": label,
            "site": site_label,
            "url": url,
            "count": 0,
            "elapsed_sec": round(elapsed, 2),
            "status": f"FAILED: {exc}",
            "engine": "N/A"
        })

print("\n" + "=" * 80)
print("FINAL LIVE SCRAPER AUDIT REPORT SUMMARY")
print("=" * 80)
print(f"{'Label':<30} | {'Site':<18} | {'Items':<6} | {'Engine':<8} | {'Time':<6} | {'Status'}")
print("-" * 80)
for r in results_summary:
    print(f"{r['label']:<30} | {r['site']:<18} | {r.get('count', 0):<6} | {r.get('engine', '-'):<8} | {r.get('elapsed_sec', 0):<5}s | {r['status']}")

print("=" * 80)
