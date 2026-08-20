from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .common import SiteConfig, build_arg_parser, records_from_hierarchy, run_site


@dataclass(slots=True)
class TXPartsConfig(SiteConfig):
    BASE_URL: str = "https://txparts.com/"
    PARENT_NAV_SELECTOR: str = "ul.desktop-view-menu, ul.mobil-view-menu"
    PARENT_ITEM_SELECTOR: str = "ul.desktop-view-menu > li > a.menu-l, ul.mobil-view-menu > li > a.menu-l"
    MEGA_MENU_SELECTOR: str = ".normal-sub, .normal-sub-menu"
    SUB_CHILD_PANEL_SELECTOR: str = "ul.other-brand-menu > li.category-list, ul.tabs.vertical > li.tab-title"
    SUB_CHILD_ITEM_SELECTOR: str = ".nav-title > a.product-main-menu, ul.tabs.vertical > li.tab-title > a"
    ACTIVE_SUB_CHILD_SELECTOR: str = ""
    CHILD_PANEL_SELECTOR: str = "ul.other-brand-menu > li.category-list, .tabs-content"
    CHILD_LINK_SELECTOR: str = "ul.mobil-view-menu a[href*='/shop/'], ul.desktop-view-menu a[href*='/shop/']"
    SCROLL_CONTAINER_SELECTOR: str = "body"
    MENU_CLOSE_SELECTOR: str = "body"
    SEARCH_SELECTOR: str = "input[type='search'], .search"
    MOBILE_MENU_SELECTOR: str = ".mobile-menu, .navbar-toggle, .menu-toggle"


CONFIG = TXPartsConfig(
    website="TXParts",
    website_url="https://txparts.com/",
    output_slug="txparts",
    base_url="https://txparts.com/",
    parent_nav_selector="ul.desktop-view-menu, ul.mobil-view-menu",
    parent_item_selector="ul.desktop-view-menu > li > a.menu-l, ul.mobil-view-menu > li > a.menu-l",
    mega_menu_selector=".normal-sub, .normal-sub-menu",
    sub_child_panel_selector="ul.other-brand-menu > li.category-list, ul.tabs.vertical > li.tab-title",
    sub_child_item_selector=".nav-title > a.product-main-menu, ul.tabs.vertical > li.tab-title > a",
    active_sub_child_selector="",
    child_panel_selector="ul.other-brand-menu > li.category-list, .tabs-content",
    child_link_selector="ul.mobil-view-menu a[href*='/shop/'], ul.desktop-view-menu a[href*='/shop/']",
    scroll_container_selector="body",
    menu_close_selector="body",
    search_selector="input[type='search'], .search",
    mobile_menu_selector=".mobile-menu, .navbar-toggle, .menu-toggle",
    parent_open_method="dom-inspection",
    sub_child_activation_method="dom-inspection",
)


TXPARTS_JS = """
() => {
  const clean = value => (value || '').replace(/\\s+/g, ' ').trim();
  const pageHost = location.hostname.replace(/^www\\./, '').toLowerCase();
  const usableUrl = anchor => {
    if (!anchor) return false;
    const raw = anchor.getAttribute('href') || '';
    if (!raw || /^(javascript:|mailto:|tel:|#?$)/i.test(raw)) return false;
    try {
      const url = new URL(raw, document.baseURI || location.href);
      const host = url.hostname.replace(/^www\\./, '').toLowerCase();
      if (host !== pageHost && !['txparts.com', 'txpartscanada.ca'].includes(host)) return false;
      return /\\/(shop|product-category)\\//i.test(url.pathname);
    } catch (_error) {
      return false;
    }
  };
  const href = anchor => usableUrl(anchor) ? new URL(anchor.getAttribute('href'), document.baseURI || location.href).href.replace(/\\/$/, '') : '';
  const childFrom = (anchor, order) => ({
    order,
    name: clean(anchor.innerText || anchor.textContent),
    url: href(anchor),
    column: 0,
    row: order,
    selector: '',
    method: 'dom-inspection'
  });
  const uniqueAnchors = anchors => {
    const seen = new Set();
    return anchors.filter(anchor => {
      const url = href(anchor).toLowerCase();
      if (!url || seen.has(url)) return false;
      seen.add(url);
      return true;
    });
  };

  const mobileRoot = document.querySelector('ul.mobil-view-menu');
  const parentItems = mobileRoot
    ? [...mobileRoot.children].filter(item => item.matches('li'))
    : [...document.querySelectorAll('ul.desktop-view-menu > li')];

  return parentItems.map((parentItem, parentIndex) => {
    const parentAnchor = parentItem.querySelector(':scope > a.menu-l');
    const parentName = clean(parentAnchor?.innerText || parentAnchor?.textContent);
    if (!parentName || /lcd buyback/i.test(parentName)) return null;
    const subChildren = [];
    const mobileGroups = [...parentItem.querySelectorAll('ul.other-brand-menu > li.category-list')];

    mobileGroups.forEach(group => {
      const titleAnchor = group.querySelector(':scope > .nav-title > a.product-main-menu, :scope > a.product-main-menu');
      const subName = clean(titleAnchor?.innerText || titleAnchor?.textContent);
      if (!subName) return;
      const titleUrl = href(titleAnchor);
      const anchors = uniqueAnchors([...group.querySelectorAll('a[href*="/shop/"]')])
        .filter(anchor => anchor !== titleAnchor && href(anchor) !== titleUrl);
      subChildren.push({
        order: subChildren.length + 1,
        name: subName,
        url: titleUrl,
        selector: '',
        method: 'dom-inspection',
        children: anchors.map((anchor, index) => childFrom(anchor, index + 1))
      });
    });

    if (!subChildren.length) {
      const tabs = [...parentItem.querySelectorAll('ul.tabs.vertical > li.tab-title > a[href^="#"]')];
      tabs.forEach(tab => {
        const subName = clean(tab.innerText || tab.textContent);
        const panelId = (tab.getAttribute('href') || '').slice(1);
        const panel = panelId ? parentItem.querySelector(`[id="${CSS.escape(panelId)}"]`) : null;
        const anchors = uniqueAnchors([...(panel || parentItem).querySelectorAll('a[href*="/shop/"]')]);
        if (!subName || !anchors.length) return;
        subChildren.push({
          order: subChildren.length + 1,
          name: subName,
          url: href(anchors[0]),
          selector: '',
          method: 'dom-inspection',
          children: anchors.map((anchor, index) => childFrom(anchor, index + 1))
        });
      });
    }

    if (!subChildren.length) {
      const anchors = uniqueAnchors([...parentItem.querySelectorAll('a[href*="/shop/"]')]);
      if (anchors.length) {
        subChildren.push({
          order: 1,
          name: parentName,
          url: href(anchors[0]),
          selector: '',
          method: 'dom-inspection',
          children: anchors.map((anchor, index) => childFrom(anchor, index + 1))
        });
      }
    }

    if (!subChildren.length) return null;
    return {
      order: parentIndex + 1,
      name: parentName,
      url: subChildren[0]?.url || location.origin,
      selector: '',
      method: 'dom-inspection',
      sub_children: subChildren
    };
  }).filter(Boolean);
}
"""


async def extract(page, config, args, output_dir, logger):
    hierarchy = await page.evaluate(TXPARTS_JS)
    logger.info("Extracted hierarchy parent_count=%s", len(hierarchy))
    return records_from_hierarchy(config, hierarchy)


def main() -> None:
    parser = build_arg_parser(CONFIG.output_slug)
    args = parser.parse_args()
    asyncio.run(run_site(CONFIG, args, extract))


if __name__ == "__main__":
    main()
