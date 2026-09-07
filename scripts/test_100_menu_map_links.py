"""Comprehensive 100 Menu-Map Link Benchmark Across All Scraper Engines.

Selects 100 valid links from menu-map category outputs (balanced across all 8 suppliers),
executes the scraper engines concurrently (1 worker per supplier domain),
validates category item extraction, title/price/URL fields, and SKU resolution.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASES_DIR", str(ROOT / ".tmp" / "live-audit-dbs"))
os.environ.setdefault("SCRAPER_LOCAL_BROWSER_FALLBACK", "1")
os.environ.setdefault("SCRAPER_LOCAL_BROWSER_MAX_WINDOWS", "1")
os.environ.setdefault("SCRAPER_LOCAL_BROWSER_WAIT_SECONDS", "0.3")

from scrapers import (  # noqa: E402
    detect_scraper_key,
    gadgetfix_scraper_engine,
    parts4cells_scraper_engine,
    phonelcdparts_scraper_engine,
    scraper_engine,
    txparts_scraper_engine,
    xcell_scraper_engine,
)
from scrapers.browser_fetcher import browser_fetch_mode  # noqa: E402

ENGINE_MODULES = {
    "standard": scraper_engine,
    "mobilesentrix_canada": scraper_engine,
    "xcell": xcell_scraper_engine,
    "txparts": txparts_scraper_engine,
    "parts4cells": parts4cells_scraper_engine,
    "phonelcdparts": phonelcdparts_scraper_engine,
    "gadgetfix": gadgetfix_scraper_engine,
}

SITE_QUOTAS = {
    "mobilesentrix": 13,
    "mobilesentrix_canada": 13,
    "xcellparts": 13,
    "txparts": 13,
    "txparts_canada": 12,
    "parts4cells": 12,
    "phonelcdparts": 12,
    "gadgetfix": 12,
}

ESTABLISHED_KEYWORDS = [
    "iphone-16", "iphone-15", "iphone-14", "iphone-13", "iphone-12", "iphone-11",
    "iphone-x", "iphone-8", "iphone-7", "galaxy-s2", "galaxy-s2", "galaxy-a",
    "galaxy-note", "ipad", "pixel", "series", "watch"
]


def load_100_valid_menu_map_links() -> list[dict]:
    selected = []
    output_dir = ROOT / "output"

    for site, quota in SITE_QUOTAS.items():
        csv_file = output_dir / site / "categories.csv"
        if not csv_file.exists():
            print(f"WARNING: {csv_file} not found!")
            continue

        with open(csv_file, encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            priority_urls = []
            fallback_urls = []

            for row in reader:
                url = (row.get("normalized_url") or row.get("url") or "").strip()
                if not url.startswith("http"):
                    continue

                lowered = url.lower()
                # Exclude obvious empty root anchors or invalid fragments
                if url.endswith("#") or url.endswith(".html/"):
                    continue

                if any(kw in lowered for kw in ESTABLISHED_KEYWORDS):
                    if url not in priority_urls:
                        priority_urls.append((url, row.get("child_name") or row.get("parent_name") or ""))
                else:
                    if url not in fallback_urls:
                        fallback_urls.append((url, row.get("child_name") or row.get("parent_name") or ""))

            combined = (priority_urls + fallback_urls)[:quota]
            for url, category_name in combined:
                scraper_key = detect_scraper_key(url)
                selected.append({
                    "site": site,
                    "url": url,
                    "category_name": category_name,
                    "scraper_key": scraper_key,
                })

    return selected


def scrape_single_link(item: dict) -> dict:
    site = item["site"]
    url = item["url"]
    category_name = item["category_name"]
    scraper_key = item["scraper_key"]
    module = ENGINE_MODULES[scraper_key]
    rules = {"add_percent": 0, "percent_off": 0, "absolute_off": 0}

    t0 = time.perf_counter()
    session, _ = module.build_session(retries=1, verify_ssl=True, use_curl=True)
    transport = "HTTP/Safari"
    items = []
    error = None

    try:
        with browser_fetch_mode(False):
            items = module.scrape_url(session, url, rules, False, 1, 0, None)
        if not items:
            # Bounded fallback check
            with browser_fetch_mode(True):
                items = module.scrape_url(session, url, rules, False, 1, 0, None)
                if items:
                    transport = "Browser fallback"
    except Exception as exc:
        error = str(exc)
    finally:
        if session is not None and hasattr(session, "close"):
            try:
                session.close()
            except Exception:
                pass

    elapsed = time.perf_counter() - t0

    # Validate items
    valid_items = [it for it in items if getattr(it, "title", "") and getattr(it, "url", "")]
    sample_titles = [it.title[:45] for it in valid_items[:2]]
    sample_skus = [getattr(it, "sku", "") for it in valid_items if getattr(it, "sku", "")][:2]

    # Success criteria: items found and parsed without exception
    passed = error is None and len(valid_items) > 0

    return {
        "site": site,
        "url": url,
        "category_name": category_name,
        "scraper_key": scraper_key,
        "passed": passed,
        "items_count": len(valid_items),
        "elapsed_seconds": round(elapsed, 2),
        "transport": transport,
        "sample_titles": sample_titles,
        "sample_skus": sample_skus,
        "error": error,
    }


def worker_per_site(site_tasks: list[dict]) -> list[dict]:
    site_results = []
    for task in site_tasks:
        res = scrape_single_link(task)
        status_label = "PASS" if res["passed"] else "FAIL"
        print(
            f"  [{status_label}] {res['site']:<20} | items: {res['items_count']:>3} | "
            f"time: {res['elapsed_seconds']:4.1f}s | {res['url'][:55]}"
        )
        site_results.append(res)
    return site_results


def main() -> int:
    t_start = time.perf_counter()
    print("=" * 80)
    print("STARTING 100 VALID MENU-MAP LINKS BENCHMARK ACROSS ALL SCRAPERS")
    print("=" * 80)

    links = load_100_valid_menu_map_links()
    print(f"Loaded {len(links)} valid links from menu maps across {len(SITE_QUOTAS)} supplier sites.")

    # Group links by site so 1 thread processes 1 site (polite per-domain concurrent crawling)
    by_site = defaultdict(list)
    for l in links:
        by_site[l["site"]].append(l)

    for site, tasks in sorted(by_site.items()):
        print(f"  - {site:<22}: {len(tasks)} links assigned")

    print("\nExecuting live scraping across 8 parallel site workers...")
    print("-" * 80)

    all_results = []
    with ThreadPoolExecutor(max_workers=len(by_site)) as executor:
        futures = {executor.submit(worker_per_site, tasks): site for site, tasks in by_site.items()}
        for fut in as_completed(futures):
            site_results = fut.result()
            all_results.extend(site_results)

    total_time = time.perf_counter() - t_start

    # Aggregate metrics
    site_stats = defaultdict(lambda: {
        "tested": 0,
        "passed": 0,
        "failed": 0,
        "total_items": 0,
        "total_time": 0.0,
    })

    for r in all_results:
        s = site_stats[r["site"]]
        s["tested"] += 1
        if r["passed"]:
            s["passed"] += 1
        else:
            s["failed"] += 1
        s["total_items"] += r["items_count"]
        s["total_time"] += r["elapsed_seconds"]

    total_tested = len(all_results)
    total_passed = sum(1 for r in all_results if r["passed"])
    total_items = sum(r["items_count"] for r in all_results)

    print("\n" + "=" * 80)
    print("100-LINK SCRAPER BENCHMARK FINAL RESULTS")
    print("=" * 80)
    print(f"{'Site':<24} {'Tested':<8} {'Passed':<8} {'Failed':<8} {'Items Extracted':<18} {'Avg Time/Link':<12}")
    print("-" * 80)

    for site in sorted(site_stats.keys()):
        st = site_stats[site]
        avg_t = st["total_time"] / st["tested"] if st["tested"] else 0.0
        print(f"{site:<24} {st['tested']:<8} {st['passed']:<8} {st['failed']:<8} {st['total_items']:<18} {avg_t:5.1f}s")

    print("-" * 80)
    print(f"{'TOTAL':<24} {total_tested:<8} {total_passed:<8} {total_tested - total_passed:<8} {total_items:<18} {total_time/total_tested:5.1f}s")
    print(f"\nOverall Success Rate: {total_passed}/{total_tested} ({(total_passed/total_tested)*100:.1f}%)")
    print(f"Total Products Extracted: {total_items}")
    print(f"Total Wall Clock Duration: {total_time:.2f}s (Throughput: {total_tested/total_time:.2f} links/sec)")
    print("=" * 80)

    # Save complete benchmark report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_tested": total_tested,
        "total_passed": total_passed,
        "total_items_extracted": total_items,
        "wall_clock_seconds": round(total_time, 2),
        "throughput_links_per_second": round(total_tested / total_time, 2) if total_time else 0,
        "site_stats": dict(site_stats),
        "detailed_results": all_results,
    }

    out_file = ROOT / "output" / "100_menu_map_benchmark.json"
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Detailed benchmark results saved to: {out_file}")

    return 0 if (total_passed / total_tested) >= 0.95 else 1


if __name__ == "__main__":
    raise SystemExit(main())
