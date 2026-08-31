from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .common import SiteConfig, build_arg_parser, click_or_hover, records_from_hierarchy, run_site


@dataclass(slots=True)
class Parts4CellsConfig(SiteConfig):
    BASE_URL: str = "https://parts4cells.com/"
    PARENT_NAV_SELECTOR: str = "#mainMenu"
    PARENT_ITEM_SELECTOR: str = "#mainMenu > li.category-menu > a.level0.dropdown-toggle"
    MEGA_MENU_SELECTOR: str = "#mainMenu > li.category-menu > ul.dropdown-menu"
    SUB_CHILD_PANEL_SELECTOR: str = "#mainMenu .dropdown-menu .mega-menu-content"
    SUB_CHILD_ITEM_SELECTOR: str = "#mainMenu .dropdown-menu a.sub-menu-toggle"
    ACTIVE_SUB_CHILD_SELECTOR: str = "#mainMenu > li.li-main-hover"
    CHILD_PANEL_SELECTOR: str = "#mainMenu .dropdown-menu .level2"
    CHILD_LINK_SELECTOR: str = "#mainMenu .dropdown-menu a.sub-category-link"
    SCROLL_CONTAINER_SELECTOR: str = "#mainMenu .dropdown-menu"
    MENU_CLOSE_SELECTOR: str = "body"
    SEARCH_SELECTOR: str = "input[type='search'], .search"
    MOBILE_MENU_SELECTOR: str = ".nav-mobile, .mobile-menu"


CONFIG = Parts4CellsConfig(
    website="Parts4Cells",
    website_url="https://parts4cells.com/",
    output_slug="parts4cells",
    base_url="https://parts4cells.com/",
    parent_nav_selector="#mainMenu",
    parent_item_selector="#mainMenu > li.category-menu > a.level0.dropdown-toggle",
    mega_menu_selector="#mainMenu > li.category-menu > ul.dropdown-menu",
    sub_child_panel_selector="#mainMenu .dropdown-menu .mega-menu-content",
    sub_child_item_selector="#mainMenu .dropdown-menu a.sub-menu-toggle",
    active_sub_child_selector="#mainMenu > li.li-main-hover",
    child_panel_selector="#mainMenu .dropdown-menu .level2",
    child_link_selector="#mainMenu .dropdown-menu a.sub-category-link",
    scroll_container_selector="#mainMenu .dropdown-menu",
    menu_close_selector="body",
    search_selector="input[type='search'], .search",
    mobile_menu_selector=".nav-mobile, .mobile-menu",
    parent_open_method="click",
    sub_child_activation_method="dom-inspection",
)


PARTS4CELLS_JS = """
() => {
  const text = el => (el?.innerText || el?.textContent || '').replace(/\\s+/g, ' ').trim();
  const clean = s => (s || '')
    .replace(/\\s*(New|Sale)\\s*$/gi, ' ')
    .replace(/^\\s*(New|Sale)\\s*/gi, ' ')
    .replace(/\\b(New|Sale)\\b/g, ' ')
    .replace(/\\s+/g, ' ')
    .trim();
  const validHref = href => {
    const h = (href || '').trim();
    return h && !/^(javascript[:;]?|javascript:void\\(0\\)|#?$)/i.test(h);
  };
  const validAnchor = a => a && validHref(a.getAttribute('href')) && validHref(a.href);
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
  const parents = [...document.querySelectorAll('#mainMenu > li.category-menu')];
  parents.forEach((li, pidx) => {
    const pa = li.querySelector(':scope > a.level0');
    const parentName = clean(text(pa?.querySelector('span[data-hover]')) || text(pa));
    if (!parentName) return;
    const parent = {order:pidx+1, name:parentName, url:validAnchor(pa)?pa.href:'', selector:css(pa), method:'click', sub_children:[]};
    const groups = [...li.querySelectorAll('ul.dropdown-menu .megamenu, ul.dropdown-menu .col-md-12.megamenu')];
    const orderedAnchors = [...li.querySelectorAll('ul.dropdown-menu a[href]')];
    let subOrder = 0;
    groups.forEach((group, groupIndex) => {
      const toggle = group.querySelector('.sub-menu-toggle-main > a.sub-menu-toggle, a.sub-menu-toggle');
      const heading = group.querySelector('.category-heading-title a[href]');
      const name = clean(text(toggle) || text(heading));
      if (!name) return;
      subOrder += 1;
      const headingName = clean(text(heading));
      const subUrl = validAnchor(toggle) ? toggle.href : ((headingName === name && validAnchor(heading)) ? heading.href : '');
      const sub = {order:subOrder, name, url:subUrl, selector:css(toggle || heading), method:'dom-inspection', children:[]};
      const startAnchor = toggle || heading || group.querySelector('a[href]');
      const nextGroup = groups[groupIndex + 1];
      const nextAnchor = nextGroup?.querySelector('.sub-menu-toggle-main > a.sub-menu-toggle, a.sub-menu-toggle, .category-heading-title a[href], a[href]');
      const startIndex = startAnchor ? orderedAnchors.indexOf(startAnchor) : -1;
      const nextIndex = nextAnchor ? orderedAnchors.indexOf(nextAnchor) : -1;
      let links = [...group.querySelectorAll('a[href]')];
      if (startIndex >= 0) {
        const sectionEnd = nextIndex > startIndex ? nextIndex : orderedAnchors.length;
        const sectionLinks = orderedAnchors.slice(startIndex + 1, sectionEnd);
        if (sectionLinks.length > links.length) links = sectionLinks;
      }
      links = links.filter(a => {
        if (a === toggle || a === heading) return false;
        if (a.closest('.sub-menu-toggle-main')) return false;
        return validAnchor(a);
      });
      const seen = new Set();
      links.forEach((a, cidx) => {
        const childName = clean(text(a));
        if (!childName || !validAnchor(a)) return;
        const key = childName.toLowerCase() + '|' + a.href;
        if (seen.has(key)) return;
        seen.add(key);
        const box = a.getBoundingClientRect();
        sub.children.push({order:sub.children.length+1, name:childName, url:a.href, column:Math.max(1, Math.round((box.x || 0) / 260)), row:sub.children.length+1, selector:css(a), method:'dom-inspection'});
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

                await save_screenshot(page, output_dir, f"parts4cells-parent-{i + 1}")
        except Exception as exc:
            logger.warning("Parent click failed index=%s error=%s", i, exc)
    hierarchy = await page.evaluate(PARTS4CELLS_JS)
    logger.info("Extracted hierarchy parent_count=%s", len(hierarchy))
    return records_from_hierarchy(config, hierarchy)


def main() -> None:
    parser = build_arg_parser(CONFIG.output_slug)
    args = parser.parse_args()
    asyncio.run(run_site(CONFIG, args, extract))


if __name__ == "__main__":
    main()
