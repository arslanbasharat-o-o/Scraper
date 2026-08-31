from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .common import SiteConfig, build_arg_parser, click_or_hover, records_from_hierarchy, run_site


@dataclass(slots=True)
class MobileSentrixConfig(SiteConfig):
    BASE_URL: str = "https://www.mobilesentrix.com/"
    PARENT_NAV_SELECTOR: str = "#nav"
    PARENT_ITEM_SELECTOR: str = "#nav > li > a"
    MEGA_MENU_SELECTOR: str = "#nav > li > ul.level0.slayouts-menu"
    SUB_CHILD_PANEL_SELECTOR: str = "#nav .sview-allmenu, #nav .sview-inul"
    SUB_CHILD_ITEM_SELECTOR: str = "#nav .sview-title > a, #nav .sview-row > a:first-child"
    ACTIVE_SUB_CHILD_SELECTOR: str = "#nav > li.li-hover"
    CHILD_PANEL_SELECTOR: str = "#nav .sview-inul, #nav .sview-row"
    CHILD_LINK_SELECTOR: str = "#nav .sview-inul a[href], #nav .sview-row a[href]"
    SCROLL_CONTAINER_SELECTOR: str = "#nav > li > ul.level0.slayouts-menu, header.ms-header"
    MENU_CLOSE_SELECTOR: str = "body"
    SEARCH_SELECTOR: str = "input[type='search'], .search, .ms-searchbx"
    MOBILE_MENU_SELECTOR: str = ".hamburgermenu-icon, .mob-menu, .mobile-menu"


CONFIG = MobileSentrixConfig(
    website="MobileSentrix",
    website_url="https://www.mobilesentrix.com/",
    output_slug="mobilesentrix",
    base_url="https://www.mobilesentrix.com/",
    parent_nav_selector="#nav",
    parent_item_selector="#nav > li > a",
    mega_menu_selector="#nav > li > ul.level0.slayouts-menu",
    sub_child_panel_selector="#nav .sview-allmenu, #nav .sview-inul",
    sub_child_item_selector="#nav .sview-title > a, #nav .sview-row > a:first-child",
    active_sub_child_selector="#nav > li.li-hover",
    child_panel_selector="#nav .sview-inul, #nav .sview-row",
    child_link_selector="#nav .sview-inul a[href], #nav .sview-row a[href]",
    scroll_container_selector="#nav > li > ul.level0.slayouts-menu, header.ms-header",
    menu_close_selector="body",
    search_selector="input[type='search'], .search, .ms-searchbx",
    mobile_menu_selector=".hamburgermenu-icon, .mob-menu, .mobile-menu",
    parent_open_method="click",
    sub_child_activation_method="dom-inspection",
)


MOBILESENTRIX_JS = """
() => {
  const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
  const validHref = href => href && !/^(javascript:|#?$)/i.test(href);
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
  const hierarchy = [];
  const buildSub = (parent, title, group) => {
    const subName = clean(title?.innerText || title?.textContent);
    if (!subName || /view all models/i.test(subName)) return null;
    const sub = {order:parent.sub_children.length+1, name:subName, url:validHref(title?.href)?title.href:'', selector:css(title), method:'dom-inspection', children:[]};
    const childLinks = [...group.querySelectorAll(':scope > ul.sview-inul a[href], :scope ul.submenu a[href]')];
    childLinks.forEach(a => {
      const childName = clean(a.innerText || a.textContent);
      if (!childName || childName === subName || /view all models/i.test(childName) || !validHref(a.href)) return;
      const b = a.getBoundingClientRect();
      sub.children.push({order:sub.children.length+1, name:childName, url:a.href, column:Math.max(1, Math.round((b.x || 0) / 240)), row:sub.children.length+1, selector:css(a), method:'dom-inspection'});
    });
    return sub;
  };
  [...document.querySelectorAll('#nav > li')].forEach((li, pidx) => {
    const pa = li.querySelector(':scope > a');
    const parentName = clean(pa?.innerText || pa?.textContent);
    if (!parentName) return;
    const dataUrl = li.getAttribute('data-url') || pa?.getAttribute('data-url') || '';
    const parent = {order:pidx+1, name:parentName, url:validHref(pa?.href)?pa.href:(dataUrl ? new URL(dataUrl, location.origin).href : ''), selector:css(pa), method:'click', sub_children:[]};
    const menu = li.querySelector(':scope > ul.level0.slayouts-menu');
    if (!menu) { hierarchy.push(parent); return; }

    const panelGroups = [...menu.children].filter(group =>
      group.matches?.('li') &&
      !group.matches('.sview-allmenu') &&
      group.querySelector(':scope > ul.sview-inul')
    );
    panelGroups.forEach(group => {
      const title = group.querySelector(':scope > a:first-child, :scope .sview-title > a');
      const sub = buildSub(parent, title, group);
      if (sub) parent.sub_children.push(sub);
    });
    if (parent.sub_children.length) {
      hierarchy.push(parent);
      return;
    }

    const groupNodes = [...menu.querySelectorAll(':scope > li.sview-allmenu > ul > li.sview-li, :scope > li.sview-row')];
    groupNodes.forEach(group => {
      let title = group.querySelector(':scope .sview-title > a, :scope > a:first-child');
      if (!title) title = group.querySelector(':scope a[href]');
      const subName = clean(title?.innerText || title?.textContent);
      if (!subName || /view all models/i.test(subName)) return;
      const sub = {order:parent.sub_children.length+1, name:subName, url:validHref(title?.href)?title.href:'', selector:css(title), method:'dom-inspection', children:[]};
      const childLinks = [...group.querySelectorAll('a[href]')];
      childLinks.forEach(a => {
        const childName = clean(a.innerText || a.textContent);
        if (!childName || childName === subName || /view all models/i.test(childName) || !validHref(a.href)) return;
        const b = a.getBoundingClientRect();
        sub.children.push({order:sub.children.length+1, name:childName, url:a.href, column:Math.max(1, Math.round((b.x || 0) / 240)), row:sub.children.length+1, selector:css(a), method:'dom-inspection'});
      });
      parent.sub_children.push(sub);
    });
    hierarchy.push(parent);
  });
  return hierarchy;
}
"""


async def extract(page, config, args, output_dir, logger):
    count = await page.locator(config.parent_item_selector).count()
    logger.info("Detected %s parent menu items", count)
    for i in range(count):
        try:
            await click_or_hover(page, config.parent_item_selector, i, "click", args.interaction_delay)
            if args.save_parent_screenshots:
                from .common import save_screenshot

                await save_screenshot(page, output_dir, f"mobilesentrix-parent-{i + 1}")
        except Exception as exc:
            logger.warning("Parent click failed index=%s error=%s", i, exc)
    hierarchy = await page.evaluate(MOBILESENTRIX_JS)
    logger.info("Extracted hierarchy parent_count=%s", len(hierarchy))
    return records_from_hierarchy(config, hierarchy)


def main() -> None:
    parser = build_arg_parser(CONFIG.output_slug)
    args = parser.parse_args()
    asyncio.run(run_site(CONFIG, args, extract))


if __name__ == "__main__":
    main()
