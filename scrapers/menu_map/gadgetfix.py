from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .common import SiteConfig, build_arg_parser, records_from_hierarchy, run_site


@dataclass(slots=True)
class GadgetFixConfig(SiteConfig):
    BASE_URL: str = "https://gadgetfix.com/"
    PARENT_NAV_SELECTOR: str = "header, nav, .menu, .mega-menu, .mega-submenu"
    PARENT_ITEM_SELECTOR: str = "a[href*='/category/']"
    MEGA_MENU_SELECTOR: str = "header, nav, .menu, .mega-menu, .mega-submenu"
    SUB_CHILD_PANEL_SELECTOR: str = ".mega-submenu, .section.links, nav, header"
    SUB_CHILD_ITEM_SELECTOR: str = "a[href*='/category/']"
    ACTIVE_SUB_CHILD_SELECTOR: str = ""
    CHILD_PANEL_SELECTOR: str = ".mega-submenu, .section.links, nav, header"
    CHILD_LINK_SELECTOR: str = "a[href*='/category/']"
    SCROLL_CONTAINER_SELECTOR: str = "body"
    MENU_CLOSE_SELECTOR: str = "body"
    SEARCH_SELECTOR: str = "input[type='search'], .search"
    MOBILE_MENU_SELECTOR: str = ".mobile-menu, .navbar-toggle, .menu-toggle"


CONFIG = GadgetFixConfig(
    website="GadgetFix",
    website_url="https://gadgetfix.com/",
    output_slug="gadgetfix",
    base_url="https://gadgetfix.com/",
    parent_nav_selector="header, nav, .menu, .mega-menu, .mega-submenu",
    parent_item_selector="a[href*='/category/']",
    mega_menu_selector="header, nav, .menu, .mega-menu, .mega-submenu",
    sub_child_panel_selector=".mega-submenu, .section.links, nav, header",
    sub_child_item_selector="a[href*='/category/']",
    active_sub_child_selector="",
    child_panel_selector=".mega-submenu, .section.links, nav, header",
    child_link_selector="a[href*='/category/']",
    scroll_container_selector="body",
    menu_close_selector="body",
    search_selector="input[type='search'], .search",
    mobile_menu_selector=".mobile-menu, .navbar-toggle, .menu-toggle",
    parent_open_method="dom-inspection",
    sub_child_activation_method="dom-inspection",
)


GADGETFIX_JS = """
() => {
  const clean = value => (value || '').replace(/\\s+/g, ' ').trim();
  const titleCase = value => value.replace(/\\b\\w/g, c => c.toUpperCase());
  const usable = anchor => {
    if (!anchor) return false;
    const raw = anchor.getAttribute('href') || '';
    if (!raw || /^(javascript:|mailto:|tel:|#?$)/i.test(raw)) return false;
    try {
      const url = new URL(raw, document.baseURI || location.href);
      if (!/gadgetfix\\.com$/i.test(url.hostname.replace(/^www\\./, ''))) return false;
      return /\\/category\\//i.test(url.pathname);
    } catch (_error) {
      return false;
    }
  };
  const labelFromUrl = href => {
    try {
      const url = new URL(href, document.baseURI || location.href);
      const tail = url.pathname.replace(/\\.html$/i, '').replace(/\\/$/, '').split('/').pop() || 'Category';
      return titleCase(tail.replace(/-\\d+$/g, '').replace(/[-_]+/g, ' '));
    } catch (_error) {
      return 'Category';
    }
  };
  const href = anchor => usable(anchor) ? new URL(anchor.getAttribute('href'), document.baseURI || location.href).href.replace(/\\/$/, '') : '';
  const uniqueAnchors = anchors => {
    const seen = new Set();
    return anchors.filter(anchor => {
      const url = href(anchor).toLowerCase();
      if (!url || seen.has(url)) return false;
      seen.add(url);
      return true;
    });
  };
  const childFrom = (anchor, order) => ({
    order,
    name: clean(anchor.innerText || anchor.textContent) || labelFromUrl(href(anchor)),
    url: href(anchor),
    column: 0,
    row: order,
    selector: '',
    method: 'dom-inspection'
  });
  const root = document.querySelector('.mega-menu > ul');
  if (!root) return [];

  return [...root.children].filter(item => item.matches('li.menu-item')).map((parentItem, parentIndex) => {
    const parentAnchor = parentItem.querySelector(':scope > a[href*="/category/"]');
    const parentName = clean(parentAnchor?.innerText || parentAnchor?.textContent);
    if (!parentName || !usable(parentAnchor)) return null;
    const subChildren = [];
    const sections = [...parentItem.querySelectorAll('.mega-submenu .section.links')];

    sections.forEach(section => {
      const headingAnchor = section.querySelector(':scope > h3 > a[href*="/category/"], :scope > h2 > a[href*="/category/"], :scope > h4 > a[href*="/category/"]');
      const childAnchors = uniqueAnchors([...section.querySelectorAll(':scope > ul a[href*="/category/"]')])
        .filter(anchor => anchor !== headingAnchor && href(anchor) !== href(headingAnchor));
      const subName = clean(headingAnchor?.innerText || headingAnchor?.textContent);
      if (subName) {
        subChildren.push({
          order: subChildren.length + 1,
          name: subName,
          url: href(headingAnchor),
          selector: '',
          method: 'dom-inspection',
          children: childAnchors.map((anchor, index) => childFrom(anchor, index + 1))
        });
      } else if (childAnchors.length) {
        subChildren.push({
          order: subChildren.length + 1,
          name: parentName,
          url: href(parentAnchor),
          selector: '',
          method: 'dom-inspection',
          children: childAnchors.map((anchor, index) => childFrom(anchor, index + 1))
        });
      }
    });

    if (!subChildren.length) {
      const anchors = uniqueAnchors([...parentItem.querySelectorAll('.mega-submenu a[href*="/category/"]')])
        .filter(anchor => href(anchor) !== href(parentAnchor));
      if (anchors.length) {
        subChildren.push({
          order: 1,
          name: parentName,
          url: href(parentAnchor),
          selector: '',
          method: 'dom-inspection',
          children: anchors.map((anchor, index) => childFrom(anchor, index + 1))
        });
      }
    }

    return {
      order: parentIndex + 1,
      name: parentName,
      url: href(parentAnchor),
      selector: '',
      method: 'dom-inspection',
      sub_children: subChildren
    };
  }).filter(Boolean);
}
"""


async def extract(page, config, args, output_dir, logger):
    hierarchy = await page.evaluate(GADGETFIX_JS)
    logger.info("Extracted hierarchy parent_count=%s", len(hierarchy))
    return records_from_hierarchy(config, hierarchy)


def main() -> None:
    parser = build_arg_parser(CONFIG.output_slug)
    args = parser.parse_args()
    asyncio.run(run_site(CONFIG, args, extract))


if __name__ == "__main__":
    main()
