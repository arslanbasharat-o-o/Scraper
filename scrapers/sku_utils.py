"""Conservative SKU extraction helpers shared by supplier engines.

Supplier pages frequently include recommendation products and multiple JSON-LD
objects.  These helpers prefer an identifier attached to the requested product
URL and never silently substitute an MPN for a SKU.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse


_PLACEHOLDER_SKUS = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "sku",
    "not available",
    "not-applicable",
}


def clean_sku(value: object) -> str:
    """Return a stable SKU string, rejecting placeholder labels."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if text.lower() in _PLACEHOLDER_SKUS:
        return ""
    if text.lower().startswith("sku:"):
        text = text[4:].strip()
    return text


def _jsonld_values(value):
    if isinstance(value, dict):
        yield value
        for key in ("@graph", "mainEntity", "mainEntityOfPage", "itemListElement"):
            nested = value.get(key)
            if isinstance(nested, list):
                for entry in nested:
                    yield from _jsonld_values(entry)
            elif isinstance(nested, dict):
                yield from _jsonld_values(nested)
    elif isinstance(value, list):
        for entry in value:
            yield from _jsonld_values(entry)


def jsonld_products(soup):
    """Return JSON-LD Product objects from a BeautifulSoup document."""
    products = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        for candidate in _jsonld_values(payload):
            types = candidate.get("@type")
            if isinstance(types, str):
                types = [types]
            if any(str(kind).lower() == "product" for kind in (types or ())):
                products.append(candidate)
    return products


def _url_key(value: object) -> str:
    parsed = urlparse(str(value or "").strip())
    if not parsed.netloc:
        return ""
    return (parsed.netloc.lower().removeprefix("www."), parsed.path.rstrip("/").lower())


def _candidate_urls(product: dict) -> list[str]:
    values = [product.get("url"), product.get("@id")]
    for key in ("mainEntityOfPage", "offers"):
        value = product.get(key)
        if isinstance(value, dict):
            values.extend([value.get("url"), value.get("@id")])
        else:
            values.append(value)
    return [str(value) for value in values if value]


def extract_jsonld_sku(soup, canonical_url: str = "") -> str:
    """Extract a SKU from the JSON-LD Product matching ``canonical_url``.

    A URL match wins over document order so a related/recommended Product does
    not leak its SKU into the requested item.  If no Product has a URL, the
    first Product is used as the page's structured-data fallback.
    """
    requested = _url_key(canonical_url)
    best = (None, -1)
    for product in jsonld_products(soup):
        sku = clean_sku(product.get("sku"))
        if not sku:
            continue
        score = 1
        if requested:
            for value in _candidate_urls(product):
                if _url_key(value) == requested:
                    score = 100
                    break
        if score > best[1]:
            best = (sku, score)
    return best[0] or ""
