"""Bounded live smoke test for every configured supplier engine.

This audit intentionally avoids ``execute_scrape_workflow`` so it cannot write
histories or mark automation runs complete. It crawls one category page per
domain, enriches at most ``LIVE_TEST_ITEMS`` products, and fails a site when a
returned product has neither a SKU nor an explicit unavailable/not-published
reason.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Keep the audit isolated from the developer's live database.
os.environ.setdefault("DATABASES_DIR", str(ROOT / ".tmp" / "live-audit-dbs"))
os.environ.setdefault("SCRAPER_LOCAL_BROWSER_FALLBACK", "1")
os.environ.setdefault("SCRAPER_LOCAL_BROWSER_MAX_WINDOWS", "1")
os.environ.setdefault("SCRAPER_LOCAL_BROWSER_WAIT_SECONDS", "0.3")
os.environ.setdefault("SCRAPER_LOCAL_BROWSER_CHALLENGE_WAIT_SECONDS", "5")

from app import enrich_scraped_items, summarize_sku_resolution  # noqa: E402
from scrapers import detect_scraper_key, SCRAPER_CONFIG  # noqa: E402
from scrapers import (  # noqa: E402
    gadgetfix_scraper_engine,
    parts4cells_scraper_engine,
    phonelcdparts_scraper_engine,
    txparts_scraper_engine,
    xcell_scraper_engine,
)
from scrapers import scraper_engine  # noqa: E402
from scrapers.browser_fetcher import browser_fetch_mode  # noqa: E402


TEST_CATEGORIES = [
    ("MobileSentrix US", "https://www.mobilesentrix.com/replacement-parts/apple/iphone-parts/iphone-15"),
    ("MobileSentrix Canada", "https://www.mobilesentrix.ca/replacement-parts/apple/iphone-parts/iphone-15"),
    ("XCellParts", "https://xcellparts.com/product-category/apple/iphone/iphone-15-pro/"),
    ("TXParts US", "https://txparts.com/shop/iphone"),
    ("TXParts Canada", "https://txpartscanada.ca/shop/iphone-15"),
    ("Parts4Cells", "https://parts4cells.com/apple/iphone.html"),
    ("PhoneLCDParts", "https://www.phonelcdparts.com/apple/iphone-parts/iphone-17e/lcd-assembly-for-iphone-16e-aftermarket-incell-qv6-ic-transfer-eligible-16e-qv6-inc"),
    ("GadgetFix", "https://gadgetfix.com/category/iphone-1559.html"),
]

ENGINE_MODULES = {
    "standard": scraper_engine,
    "mobilesentrix_canada": scraper_engine,
    "xcell": xcell_scraper_engine,
    "txparts": txparts_scraper_engine,
    "parts4cells": parts4cells_scraper_engine,
    "phonelcdparts": phonelcdparts_scraper_engine,
    "gadgetfix": gadgetfix_scraper_engine,
}


def _scrape_category(module, url: str, rules: dict):
    session, _ = module.build_session(retries=1, verify_ssl=True, use_curl=True)
    try:
        with browser_fetch_mode(False):
            items = module.scrape_url(session, url, rules, False, 1, 0, None)
        if items:
            return items, "HTTP/Safari"
        # A category page can be challenged even when detail pages work. This
        # explicit retry still proves HTTP was attempted first.
        with browser_fetch_mode(True):
            return module.scrape_url(session, url, rules, False, 1, 0, None), "Browser fallback"
    finally:
        if session is not None and hasattr(session, "close"):
            try:
                session.close()
            except Exception:
                pass


def main() -> int:
    limit = max(1, min(5, int(os.getenv("LIVE_TEST_ITEMS", "2") or 2)))
    rules = {"add_percent": 0, "percent_off": 0, "absolute_off": 0}
    failures = 0
    print(f"LIVE SCRAPER SKU AUDIT: {len(TEST_CATEGORIES)} sites, up to {limit} products/site")
    print("HTTP/Safari is attempted first; browser fallback is bounded to one window.")

    for index, (label, url) in enumerate(TEST_CATEGORIES, 1):
        started = time.time()
        key = detect_scraper_key(url)
        module = ENGINE_MODULES[key]
        site_label = SCRAPER_CONFIG.get(key, {}).get("label", key)
        try:
            items, crawl_transport = _scrape_category(module, url, rules)
            candidates = [item for item in items if getattr(item, "title", "") and getattr(item, "url", "")][:limit]
            if not candidates:
                raise RuntimeError("category returned no usable products")
            enriched, _ = enrich_scraped_items(
                candidates,
                rules,
                retries=1,
                verify_ssl=True,
                use_curl=True,
                enrich_details=True,
                use_browser=False,
            )
            summary = summarize_sku_resolution(enriched)
            passed = summary["sku_total"] > 0 and summary["sku_unresolved"] == 0
            if not passed:
                failures += 1
            sku_values = [
                str(getattr(item, "sku", "") or "") or str((getattr(item, "extra", {}) or {}).get("sku_status", "missing"))
                for item in enriched
            ]
            status = "PASS" if passed else "FAIL"
            print(
                f"[{index}/{len(TEST_CATEGORIES)}] {status} {label} ({site_label}) "
                f"crawl={crawl_transport}, products={summary['sku_total']}, "
                f"sku={summary['sku_found']}, not_published={summary['sku_not_published']}, "
                f"unavailable={summary['sku_unavailable']}, unresolved={summary['sku_unresolved']}, "
                f"elapsed={time.time() - started:.1f}s"
            )
            print(f"    sample SKUs: {', '.join(sku_values)}")
        except Exception as exc:
            failures += 1
            print(f"[{index}/{len(TEST_CATEGORIES)}] FAIL {label}: {exc}")

    print(f"\nAUDIT RESULT: {'PASS' if failures == 0 else 'FAIL'} ({failures} site(s) need attention)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
