import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import execute_scrape_workflow
res = execute_scrape_workflow("https://www.mobilesentrix.com/replacement-parts/apple/iphone-parts/iphone-15", max_pages=1, enrich_details=True)
items = res.get("items", [])
if items:
    print(json.dumps(items[0].get("extra", {}), indent=2))
