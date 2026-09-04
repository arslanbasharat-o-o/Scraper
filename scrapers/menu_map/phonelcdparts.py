from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import SiteConfig, build_arg_parser, click_or_hover, records_from_hierarchy, run_site


@dataclass(slots=True)
class PhoneLcdPartsConfig(SiteConfig):
    BASE_URL: str = "https://www.phonelcdparts.com/"
    PARENT_NAV_SELECTOR: str = "#ninjamenus4"
    PARENT_ITEM_SELECTOR: str = "#ninjamenus4 > .magezon-builder > .nav-item > a"
    MEGA_MENU_SELECTOR: str = "#ninjamenus4 > .magezon-builder > .nav-item > .item-submenu"
    SUB_CHILD_PANEL_SELECTOR: str = "#ninjamenus4 .mgz-tabs-nav"
    SUB_CHILD_ITEM_SELECTOR: str = "#ninjamenus4 .mgz-tabs-nav .mgz-tabs-tab-title > a"
    ACTIVE_SUB_CHILD_SELECTOR: str = "#ninjamenus4 .mgz-tabs-tab-title.mgz-active"
    CHILD_PANEL_SELECTOR: str = "#ninjamenus4 .mgz-tabs-content"
    CHILD_LINK_SELECTOR: str = "#ninjamenus4 .mgz-tabs-content .nav-item a[href]"
    SCROLL_CONTAINER_SELECTOR: str = "#ninjamenus4 .mgz-tabs-nav, #ninjamenus4 .mgz-tabs-content, #ninjamenus4 .item-submenu"
    MENU_CLOSE_SELECTOR: str = "body"
    SEARCH_SELECTOR: str = "input[type='search'], .search"
    MOBILE_MENU_SELECTOR: str = ".ninjamenus-mobile, .mobile-menu-main:not(.ninjamenus-desktop)"


CONFIG = PhoneLcdPartsConfig(
    website="Phone LCD Parts",
    website_url="https://www.phonelcdparts.com/",
    output_slug="phonelcdparts",
    base_url="https://www.phonelcdparts.com/",
    parent_nav_selector="#ninjamenus4",
    parent_item_selector="#ninjamenus4 > .magezon-builder > .nav-item > a",
    mega_menu_selector="#ninjamenus4 > .magezon-builder > .nav-item > .item-submenu",
    sub_child_panel_selector="#ninjamenus4 .mgz-tabs-nav",
    sub_child_item_selector="#ninjamenus4 .mgz-tabs-nav .mgz-tabs-tab-title > a",
    active_sub_child_selector="#ninjamenus4 .mgz-tabs-tab-title.mgz-active",
    child_panel_selector="#ninjamenus4 .mgz-tabs-content",
    child_link_selector="#ninjamenus4 .mgz-tabs-content .nav-item a[href]",
    scroll_container_selector="#ninjamenus4 .mgz-tabs-nav, #ninjamenus4 .mgz-tabs-content, #ninjamenus4 .item-submenu",
    menu_close_selector="body",
    search_selector="input[type='search'], .search",
    mobile_menu_selector=".ninjamenus-mobile, .mobile-menu-main:not(.ninjamenus-desktop)",
    parent_open_method="hover",
    sub_child_activation_method="click",
)


PHONE_LCD_JS = """
(parentIndex = null) => {
  const clean = s => (s || '').replace(/\\s+/g, ' ').replace(/\\bNEW\\b$/i, '').trim();
  const validHref = href => href && !/^(javascript:|#?$)/i.test(href) && !/#tab-/i.test(href);
  const css = el => {
    if (!el) return '';
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    let n = el;
    for (let i = 0; n && n.nodeType === 1 && i < 7; i++, n = n.parentElement) {
      let p = n.tagName.toLowerCase();
      if (n.id) { p += '#' + CSS.escape(n.id); parts.unshift(p); break; }
      const cls = [...n.classList].slice(0, 4);
      if (cls.length) p += '.' + cls.map(c => CSS.escape(c)).join('.');
      parts.unshift(p);
    }
    return parts.join(' > ');
  };
  const topParents = [...document.querySelectorAll('#ninjamenus4 > .magezon-builder > .nav-item')];
  const hierarchy = [];
  topParents.forEach((nav, pidx) => {
    if (parentIndex !== null && pidx !== parentIndex) return;
    const pa = nav.querySelector(':scope > a');
    const parentName = clean(pa?.querySelector('.title')?.textContent || pa?.innerText);
    if (!parentName) return;
    const parent = {order:pidx+1, name:parentName, url:validHref(pa?.href)?pa.href:'', selector:css(pa), method:'hover', sub_children:[]};
    const tabs = [...nav.querySelectorAll('.mgz-tabs-nav .mgz-tabs-tab-title')];
    tabs.forEach((tab, tidx) => {
      const ta = tab.querySelector(':scope > a[href]');
      const subName = clean(ta?.innerText || ta?.textContent);
      if (!subName) return;
      const hash = (ta?.getAttribute('href') || '').split('#').pop();
      let panel = hash ? nav.querySelector(`#${CSS.escape(hash)}, .${CSS.escape(hash)}`) : null;
      if (!panel) {
        const panels = [...nav.querySelectorAll('.mgz-tabs-content > .mgz-tabs-tab-content, .mgz-tabs-content > div')];
        panel = panels[tidx] || null;
      }
      const sub = {order:tidx+1, name:subName, url:validHref(ta?.href)?ta.href:'', selector:css(ta), method:'click', children:[]};
      const links = panel ? [...panel.querySelectorAll('.nav-item a[href], a[href]')] : [];
      links.forEach(a => {
        const childName = clean(a.querySelector('.title')?.textContent || a.innerText || a.textContent);
        if (!childName || !validHref(a.href)) return;
        const b = a.getBoundingClientRect();
        sub.children.push({order:sub.children.length+1, name:childName, url:a.href, column:Math.max(1, Math.round((b.x || 0) / 250)), row:sub.children.length+1, selector:css(a), method:'click'});
      });
      parent.sub_children.push(sub);
    });
    if (!parent.sub_children.length) {
      const links = [...nav.querySelectorAll(':scope > .item-submenu a[href]')].filter(a => validHref(a.href));
      if (links.length) {
        const sub = {order:1, name:parentName, url:'', selector:css(nav), method:'dom-inspection', children:[]};
        links.forEach(a => {
          const childName = clean(a.querySelector('.title')?.textContent || a.innerText || a.textContent);
          if (!childName) return;
          sub.children.push({order:sub.children.length+1, name:childName, url:a.href, column:1, row:sub.children.length+1, selector:css(a), method:'dom-inspection'});
        });
        parent.sub_children.push(sub);
      }
    }
    hierarchy.push(parent);
  });
  return hierarchy;
}
"""


def _fill_lazy_menu_children(hierarchy, logger):
    """Fill menu panels omitted from headless Chrome using the desktop menu API."""
    missing = [
        (parent, subgroup)
        for parent in hierarchy
        for subgroup in parent.get("sub_children", [])
        if not subgroup.get("children")
    ]
    if not missing:
        return hierarchy

    try:
        from curl_cffi import requests as curl_requests

        response = curl_requests.post(
            "https://www.phonelcdparts.com/swpninjamenu/index/menu",
            impersonate="safari15_5",
            data={"screenSize": "1920"},
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": "https://www.phonelcdparts.com/"},
            timeout=30,
        )
        response.raise_for_status()
        menu_soup = BeautifulSoup(response.content, "html.parser")
        filled = 0
        for parent in hierarchy:
            nav = next(
                (
                    item
                    for item in menu_soup.select("#ninjamenus4 > .magezon-builder > .nav-item")
                    if str(item.select_one(":scope > a") and item.select_one(":scope > a").get_text(" ", strip=True)).casefold()
                    == str(parent.get("name") or "").casefold()
                ),
                None,
            )
            if nav is None:
                continue
            for subgroup in parent.get("sub_children", []):
                if subgroup.get("children"):
                    continue
                tab = next(
                    (
                        item
                        for item in nav.select(".mgz-tabs-nav .mgz-tabs-tab-title")
                        if item.get_text(" ", strip=True).casefold()
                        == str(subgroup.get("name") or "").casefold()
                    ),
                    None,
                )
                if tab is None:
                    continue
                anchor = tab.select_one(":scope > a[href]")
                panel_id = str(anchor.get("href") or "").split("#")[-1] if anchor else ""
                panel = nav.select_one(f"#{panel_id}") if panel_id else None
                if panel is None:
                    continue
                seen = {str(child.get("url") or "") for child in subgroup.get("children", [])}
                for link in panel.select("a[href]"):
                    child_url = urljoin("https://www.phonelcdparts.com/", link.get("href") or "")
                    child_name = link.get_text(" ", strip=True) or ""
                    if not child_name:
                        image = link.select_one("img[alt], img[title]")
                        child_name = (image.get("alt") or image.get("title") or "") if image else ""
                    child_name = re.sub(r"\s+", " ", child_name).strip()
                    if not child_name or child_url in seen or child_url.endswith("#"):
                        continue
                    seen.add(child_url)
                    subgroup.setdefault("children", []).append(
                        {
                            "order": len(subgroup["children"]) + 1,
                            "name": child_name,
                            "url": child_url,
                            "column": 1,
                            "row": len(subgroup["children"]) + 1,
                            "selector": "",
                            "method": "safari-http-menu-api",
                        }
                    )
                if subgroup.get("children"):
                    filled += 1
        logger.info("Filled %s lazy Phone LCD menu panels via Safari HTTP menu API", filled)

        # GraphQL is a secondary fallback for category panels the menu API
        # intentionally leaves as a single landing link.
        missing = [
            (parent, subgroup)
            for parent in hierarchy
            for subgroup in parent.get("sub_children", [])
            if not subgroup.get("children")
        ]
        if not missing:
            return hierarchy

        fields = "name url_path children { name url_path }"
        data = {}
        # Magento rejects one very large aliased query with HTTP 500. Small
        # batches stay below its GraphQL complexity limit and remain much
        # faster than opening every missing category in a browser.
        for batch_start in range(0, len(missing), 8):
            batch = missing[batch_start : batch_start + 8]
            aliases = " ".join(
                f"q{index}: categoryList(filters: {{name: {{match: {json.dumps(subgroup.get('name') or '')}}}}}) {{ {fields} }}"
                for index, (_, subgroup) in enumerate(batch, start=batch_start)
            )
            response = curl_requests.post(
                "https://www.phonelcdparts.com/graphql",
                impersonate="safari15_5",
                json={"query": f"query MenuMapFallback {{ {aliases} }}"},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            batch_data = payload.get("data") if isinstance(payload, dict) else {}
            if isinstance(batch_data, dict):
                data.update(batch_data)

        def slug(value):
            return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")

        filled = 0
        for index, (parent, subgroup) in enumerate(missing):
            candidates = data.get(f"q{index}") or []
            exact = [
                category
                for category in candidates
                if str(category.get("name") or "").strip().casefold()
                == str(subgroup.get("name") or "").strip().casefold()
            ]
            if exact:
                candidates = exact
            parent_slug = slug(parent.get("name"))
            category = max(
                candidates,
                key=lambda item: (
                    str(item.get("url_path") or "").lower().startswith(f"{parent_slug}/"),
                    len(item.get("children") or []),
                ),
                default=None,
            )
            if not category:
                continue
            category_path = str(category.get("url_path") or "").strip("/")
            if category_path:
                subgroup["url"] = f"https://www.phonelcdparts.com/{category_path}"
            for child in category.get("children") or []:
                child_name = str(child.get("name") or "").strip()
                child_path = str(child.get("url_path") or "").strip("/")
                if not child_name or not child_path:
                    continue
                subgroup["children"].append(
                    {
                        "order": len(subgroup["children"]) + 1,
                        "name": child_name,
                        "url": f"https://www.phonelcdparts.com/{child_path}",
                        "column": 1,
                        "row": len(subgroup["children"]) + 1,
                        "selector": "",
                        "method": "safari-http-graphql",
                    }
                )
            if subgroup["children"]:
                filled += 1
        logger.info("Filled %s/%s lazy Phone LCD menu panels via Safari HTTP GraphQL", filled, len(missing))
    except Exception as exc:
        logger.warning("Phone LCD GraphQL menu fallback failed: %s", exc)
    return hierarchy


async def extract(page, config, args, output_dir, logger):
    count = await page.locator(config.parent_item_selector).count()
    logger.info("Detected %s top-level nav anchors", count)
    hierarchy = []
    for i in range(count):
        try:
            await click_or_hover(page, config.parent_item_selector, i, "hover", max(args.interaction_delay, 250))
            if args.save_parent_screenshots:
                from .common import save_screenshot

                await save_screenshot(page, output_dir, f"phonelcdparts-parent-{i + 1}")
            # Phone LCD lazy-renders the later mega-menu panels. Capture each
            # parent while it is open; a single final DOM pass loses those
            # panels and leaves real subgroups with zero children.
            hierarchy.extend(await page.evaluate(PHONE_LCD_JS, i))
        except Exception as exc:
            logger.warning("Parent activation failed index=%s error=%s", i, exc)
    hierarchy = await asyncio.to_thread(_fill_lazy_menu_children, hierarchy, logger)
    logger.info("Extracted hierarchy parent_count=%s", len(hierarchy))
    return records_from_hierarchy(config, hierarchy)


def main() -> None:
    parser = build_arg_parser(CONFIG.output_slug)
    args = parser.parse_args()
    asyncio.run(run_site(CONFIG, args, extract))


if __name__ == "__main__":
    main()
