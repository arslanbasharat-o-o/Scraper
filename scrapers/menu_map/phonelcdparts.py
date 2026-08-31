from __future__ import annotations

import asyncio
from dataclasses import dataclass

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
    parent_open_method="hover-and-click",
    sub_child_activation_method="click",
)


PHONE_LCD_JS = """
() => {
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
    const pa = nav.querySelector(':scope > a');
    const parentName = clean(pa?.querySelector('.title')?.textContent || pa?.innerText);
    if (!parentName) return;
    const parent = {order:pidx+1, name:parentName, url:validHref(pa?.href)?pa.href:'', selector:css(pa), method:'hover-and-click', sub_children:[]};
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


async def extract(page, config, args, output_dir, logger):
    count = await page.locator(config.parent_item_selector).count()
    logger.info("Detected %s top-level nav anchors", count)
    for i in range(count):
        try:
            await click_or_hover(page, config.parent_item_selector, i, "hover-and-click", args.interaction_delay)
            if args.save_parent_screenshots:
                from .common import save_screenshot

                await save_screenshot(page, output_dir, f"phonelcdparts-parent-{i + 1}")
        except Exception as exc:
            logger.warning("Parent activation failed index=%s error=%s", i, exc)
    hierarchy = await page.evaluate(PHONE_LCD_JS)
    logger.info("Extracted hierarchy parent_count=%s", len(hierarchy))
    return records_from_hierarchy(config, hierarchy)


def main() -> None:
    parser = build_arg_parser(CONFIG.output_slug)
    args = parser.parse_args()
    asyncio.run(run_site(CONFIG, args, extract))


if __name__ == "__main__":
    main()
