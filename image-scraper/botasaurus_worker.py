#!/usr/bin/env python3
"""Headless Botasaurus extraction worker for the image scraper."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from botasaurus.browser import Driver, browser


IMAGE_EXTENSIONS = re.compile(r"\.(?:jpe?g|png|webp|bmp|tiff?|heic)(?:[?#]|$)", re.I)
CATALOG_IMAGE = re.compile(r"https?://[^\s\"'<>]+/catalog/product/image/[^\s\"'<>]+", re.I)
NON_PRODUCT_ASSET_RE = re.compile(
    r"(?:logo|brandmark|flag|country|canada|united[-_ ]?states|usa|all[-_ ]?colors|"
    r"placeholder|favicon|apple-touch-icon|banner|sprite|icon)",
    re.I,
)


def _absolute(value: str, base_url: str) -> str:
    value = str(value or "").strip()
    if not value or value.startswith(("data:", "javascript:")):
        return ""
    try:
        result = urljoin(base_url, value)
        parsed = urlparse(result)
        return result if parsed.scheme in ("http", "https") and parsed.hostname else ""
    except ValueError:
        return ""


def _first_src(value: str) -> str:
    return str(value or "").split(",", 1)[0].strip().split(" ", 1)[0].strip()


def _node_context(node) -> str:
    values = []
    for current in (node, node.parent):
        if not current:
            continue
        for attribute in ("class", "id", "alt", "title", "aria-label", "src", "href", "content"):
            value = current.get(attribute) if hasattr(current, "get") else ""
            if isinstance(value, (list, tuple)):
                value = " ".join(map(str, value))
            if value:
                values.append(str(value))
    return " ".join(values)


def _looks_like_non_product_asset(value: str, context: str = "") -> bool:
    sample = f"{value or ''} {context or ''}".lower()
    if not sample:
        return True
    if sample.endswith((".gif", ".svg")):
        return True
    return bool(NON_PRODUCT_ASSET_RE.search(sample))


def extract_category_products(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "lxml")
    selectors = (
        "article.xcell-podev",
        "li.item",
        "[data-product-id]",
        "div.product-item",
        "article.product",
        ".wd-product",
        ".product-grid-item",
    )
    items = []
    for selector in selectors:
        items = soup.select(selector)
        if items:
            break

    products = []
    seen = set()
    for item in items:
        link = (
            item.select_one("a.xcell-podev__nm[href]")
            or item.select_one("a.xcell-podev__img[href]")
            or item.select_one("a.product-image.figure[href]")
            or item.select_one('a[href*="/product"]')
            or item.select_one("a[data-url]")
        )
        raw_url = link.get("href") if link and link.get("href") else link.get("data-url") if link else ""
        product_url = _absolute(raw_url, base_url)
        if not product_url or product_url in seen:
            continue
        seen.add(product_url)

        name_node = item.select_one(".xcell-podev__nm, h2.product-name, h2, h3, [data-name]")
        price_node = item.select_one(".xcell-podev__price, span.regular-price, .price, [data-price]")
        image_node = None
        for candidate in item.select("a.xcell-podev__img img, img"):
            raw_candidate = " ".join(
                _first_src(candidate.get(attribute))
                for attribute in ("src", "data-src", "srcset", "data-lazy", "data-original")
                if candidate.get(attribute)
            )
            if "/catalog/product/" in raw_candidate.lower() or "/wp-content/uploads/" in raw_candidate.lower():
                image_node = candidate
                break
        if image_node is None:
            image_node = item.select_one("img.small-img, img[data-src], img")
        raw_image = ""
        if image_node:
            for attribute in ("src", "data-src", "srcset", "data-lazy", "data-original"):
                raw_image = _first_src(image_node.get(attribute))
                if raw_image:
                    break

        products.append(
            {
                "name": name_node.get_text(" ", strip=True) if name_node else "",
                "price": price_node.get_text(" ", strip=True) if price_node else "",
                "product_url": product_url,
                "img": _absolute(raw_image, base_url),
                "images": [],
                "source_images": [],
            }
        )
    return products


def extract_image_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html or "", "lxml")
    candidates = []
    selectors = (
        "a.MagicZoom[href]",
        'a[id^="MagicZoomPlusImage"][href]',
        ".MagicToolboxContainer a[href], .MagicToolboxContainer img",
        ".product-img-box a[href], .product-img-box img",
        ".product-gallery a[href], .product-gallery img",
        ".product-images a[href], .product-images img",
        ".product-image-container a[href], .product-image-container img",
        ".more-views a[href], .more-views img",
        ".gallery a[href], .gallery img",
        ".fotorama a[href], .fotorama img, .fotorama__img",
        ".slick-slide a[href], .slick-slide img",
        ".swiper-slide a[href], .swiper-slide img",
        'meta[property="og:image"]',
        'link[rel="image_src"]',
    )
    for node in soup.select(",".join(selectors)):
        context = _node_context(node)
        for attribute in (
            "href",
            "content",
            "data-zoom-image",
            "data-original",
            "data-src",
            "src",
            "srcset",
        ):
            value = _first_src(node.get(attribute))
            if value and not _looks_like_non_product_asset(value, context):
                candidates.append(value)

    for match in CATALOG_IMAGE.findall(html or ""):
        index = (html or "").find(match)
        context = (html or "")[max(0, index - 500) : index + len(match) + 500] if index >= 0 else ""
        if re.search(r"(MagicZoom|MagicToolbox|product-img-box|product\.media|more-views|gallery|fotorama)", context, re.I):
            candidates.append(match)

    for match in re.findall(r'https?:\\?/\\?/[^\s"\'<>]+', html or ""):
        normalized = match.replace("\\/", "/")
        if not (IMAGE_EXTENSIONS.search(normalized) or "/catalog/product/image/" in normalized):
            continue
        index = (html or "").find(match)
        context = (html or "")[max(0, index - 500) : index + len(match) + 500] if index >= 0 else ""
        if re.search(r"(MagicZoom|MagicToolbox|product-img-box|product\.media|more-views|gallery|fotorama|og:image|image_src)", context, re.I):
            candidates.append(normalized)

    output = []
    seen = set()
    for candidate in candidates:
        absolute = _absolute(candidate, base_url)
        lower = absolute.lower()
        if (
            not absolute
            or absolute in seen
            or _looks_like_non_product_asset(absolute)
        ):
            continue
        if "/catalog/product/image/" not in lower and not IMAGE_EXTENSIONS.search(absolute):
            continue
        seen.add(absolute)
        output.append(absolute)
    return output


def _looks_like_challenge(html: str) -> bool:
    sample = (html or "").lower()
    return any(
        marker in sample
        for marker in (
            "<title>just a moment",
            "checking your browser",
            "checking if the site connection is secure",
            "just a moment",
            "cf-browser-verification",
        )
    )


def _write_result(path_value: str, payload: dict) -> None:
    target = Path(path_value).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    temporary.replace(target)


def run_task(action: str, url: str, output_path: str, profile_path: str, timeout_seconds: int) -> None:
    @browser(
        headless=True,
        profile=profile_path,
        window_size=(1440, 1000),
        lang="en-US",
        block_images=True,
        output=None,
        raise_exception=True,
        close_on_crash=True,
    )
    def _run(driver: Driver, data):
        driver.get(data["url"], timeout=data["timeout"])
        driver.sleep(0.5)

        deadline = time.time() + min(30, data["timeout"])
        html = driver.page_html or ""
        while _looks_like_challenge(html) and time.time() < deadline:
            driver.sleep(2)
            html = driver.page_html or ""
        if _looks_like_challenge(html):
            raise RuntimeError("Botasaurus remained on a browser verification page")

        if data["action"] == "category":
            previous_count = -1
            stable_rounds = 0
            for _ in range(25):
                count = int(
                    driver.run_js(
                        """
                        window.scrollTo(0, document.body.scrollHeight);
                        return document.querySelectorAll(
                          'article.xcell-podev,li.item,[data-product-id],div.product-item,article.product,.wd-product,.product-grid-item'
                        ).length;
                        """
                    )
                    or 0
                )
                driver.sleep(0.6)
                stable_rounds = stable_rounds + 1 if count == previous_count else 0
                previous_count = count
                if stable_rounds >= 4:
                    break
            html = driver.page_html or html

        final_url = driver.current_url or data["url"]
        if data["action"] == "category":
            return {"products": extract_category_products(html, final_url), "final_url": final_url}
        if data["action"] == "images":
            return {"images": extract_image_urls(html, final_url), "final_url": final_url}
        if data["action"] == "title":
            soup = BeautifulSoup(html, "lxml")
            heading = soup.select_one("h1, .product-name, [itemprop='name']")
            title = heading.get_text(" ", strip=True) if heading else (soup.title.string.strip() if soup.title and soup.title.string else "")
            return {"title": title, "final_url": final_url}
        raise ValueError(f"Unknown action: {data['action']}")

    result = _run({"action": action, "url": url, "timeout": timeout_seconds})
    _write_result(output_path, {"success": True, **(result or {})})


def self_test() -> None:
    fixture = """
    <ul><li class="item"><h2 class="product-name">Test Screen</h2>
    <span class="regular-price">$12</span><a class="product-image figure" href="/product/test">
    <img data-src="/media/test.jpg"></a></li></ul>
    <a class="MagicZoom" href="/catalog/product/image/test.png">Zoom</a>
    """
    products = extract_category_products(fixture, "https://www.mobilesentrix.com/category")
    images = extract_image_urls(fixture, "https://www.mobilesentrix.com/product/test")
    assert products[0]["product_url"] == "https://www.mobilesentrix.com/product/test"
    assert images == ["https://www.mobilesentrix.com/catalog/product/image/test.png"]


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        self_test()
        print("Botasaurus worker parser tests passed")
        return 0
    if len(sys.argv) < 6:
        print("Usage: botasaurus_worker.py <category|images|title> <url> <output> <profile> <timeout>", file=sys.stderr)
        return 2

    action, url, output_path, profile_path = sys.argv[1:5]
    timeout_seconds = max(5, min(180, int(sys.argv[5])))
    try:
        run_task(action, url, output_path, profile_path, timeout_seconds)
        return 0
    except Exception as exc:
        _write_result(output_path, {"success": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
