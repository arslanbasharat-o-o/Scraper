from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .common import SiteConfig, build_arg_parser, click_or_hover, records_from_hierarchy, run_site


@dataclass(slots=True)
class XCellPartsConfig(SiteConfig):
    BASE_URL: str = "https://xcellparts.com/"
    PARENT_NAV_SELECTOR: str = "#xcell-mm-i1 .xcell-mm__list"
    PARENT_ITEM_SELECTOR: str = "#xcell-mm-i1 .xcell-mm__list > li.xcell-mm__li.has-panel > a.xcell-mm__top"
    MEGA_MENU_SELECTOR: str = "#xcell-mm-i1 .xcell-mm__panel"
    SUB_CHILD_PANEL_SELECTOR: str = "#xcell-mm-i1 .xcell-mm__rail"
    SUB_CHILD_ITEM_SELECTOR: str = "#xcell-mm-i1 .xcell-mm__rail button.xcell-mm__rail-item"
    ACTIVE_SUB_CHILD_SELECTOR: str = ""
    CHILD_PANEL_SELECTOR: str = "#xcell-mm-i1 .xcell-mm__plp-panel"
    CHILD_LINK_SELECTOR: str = "#xcell-mm-i1 a.xcell-mm__plp-thumb[href], #xcell-mm-i1 a.xcell-mm__plp-group-head[href]"
    SCROLL_CONTAINER_SELECTOR: str = "#xcell-mm-i1 .xcell-mm__panel-scroll, #xcell-mm-i1 .xcell-mm__rail"
    MENU_CLOSE_SELECTOR: str = "body"
    SEARCH_SELECTOR: str = "header input[type='search'], header .xh-search"
    MOBILE_MENU_SELECTOR: str = "#xcell-header-drawer, .mobile-nav"


CONFIG = XCellPartsConfig(
    website="XCell Parts",
    website_url="https://xcellparts.com/",
    output_slug="xcellparts",
    base_url="https://xcellparts.com/",
    parent_nav_selector="#xcell-mm-i1 .xcell-mm__list",
    parent_item_selector="#xcell-mm-i1 .xcell-mm__list > li.xcell-mm__li.has-panel > a.xcell-mm__top",
    mega_menu_selector="#xcell-mm-i1 .xcell-mm__panel",
    sub_child_panel_selector="#xcell-mm-i1 .xcell-mm__rail",
    sub_child_item_selector="#xcell-mm-i1 .xcell-mm__rail button.xcell-mm__rail-item",
    active_sub_child_selector="",
    child_panel_selector="#xcell-mm-i1 .xcell-mm__plp-panel",
    child_link_selector="#xcell-mm-i1 a.xcell-mm__plp-thumb[href], #xcell-mm-i1 a.xcell-mm__plp-group-head[href]",
    scroll_container_selector="#xcell-mm-i1 .xcell-mm__panel-scroll, #xcell-mm-i1 .xcell-mm__rail",
    menu_close_selector="body",
    search_selector="header input[type='search'], header .xh-search",
    mobile_menu_selector="#xcell-header-drawer, .mobile-nav",
    parent_open_method="click",
    sub_child_activation_method="dom-inspection",
)


XCELL_JS = """
() => {
  const clean = s => (s || '')
    .replace(/\\b(new|sale)\\b/ig, ' ')
    .replace(/[×›»]/g, ' ')
    .replace(/\\s+/g, ' ')
    .trim();
  const validHref = href => href && !/^(javascript:|#?$)/i.test(href);
  const css = el => {
    if (!el) return '';
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    let n = el;
    for (let i = 0; n && n.nodeType === 1 && i < 6; i++, n = n.parentElement) {
      let p = n.tagName.toLowerCase();
      if (n.id) { p += '#' + CSS.escape(n.id); parts.unshift(p); break; }
      const cls = [...n.classList].slice(0, 4);
      if (cls.length) p += '.' + cls.map(c => CSS.escape(c)).join('.');
      parts.unshift(p);
    }
    return parts.join(' > ');
  };

  const inferSubUrl = (parentUrl, childUrl) => {
    try {
      const parent = new URL(parentUrl || location.href, location.href);
      const child = new URL(childUrl || '', location.href);
      const parentPath = parent.pathname.replace(/\\/+$/, '');
      const childPath = child.pathname.replace(/\\/+$/, '');
      if (!parentPath || !childPath.startsWith(parentPath + '/')) return '';
      const remainder = childPath.slice(parentPath.length + 1).split('/').filter(Boolean);
      if (!remainder.length) return '';
      return `${child.origin}${parentPath}/${remainder[0]}/`;
    } catch (_error) {
      return '';
    }
  };

  const pushChild = (sub, anchor, column, rowHint) => {
    const name = clean(anchor?.innerText || anchor?.textContent);
    const url = anchor?.href || '';
    if (!name || !validHref(url)) return rowHint;
    const key = `${name.toLowerCase()}|${url.replace(/\\/+$/, '').toLowerCase()}`;
    if (sub._seen.has(key)) return rowHint;
    sub._seen.add(key);
    const nextOrder = sub.children.length + 1;
    sub.children.push({
      order: nextOrder,
      name,
      url,
      column,
      row: rowHint,
      selector: css(anchor),
      method: 'dom-inspection'
    });
    return rowHint + 1;
  };

  const collectChildren = (sub, contentPanel) => {
    const splitPanels = [...contentPanel.querySelectorAll(':scope .xcell-mm__plp-split-detail > .xcell-mm__plp-split-panel')];
    if (splitPanels.length) {
      splitPanels.forEach((section, sectionIndex) => {
        let row = 1;
        const links = [...section.querySelectorAll(':scope > a.xcell-mm__plp-group-head[href], :scope .xcell-mm__plp-thumbs a.xcell-mm__plp-thumb[href]')];
        links.forEach(anchor => {
          row = pushChild(sub, anchor, sectionIndex + 1, row);
        });
      });
      return;
    }
    let row = 1;
    const links = [...contentPanel.querySelectorAll(':scope > a.xcell-mm__plp-group-head[href], :scope .xcell-mm__plp-thumbs a.xcell-mm__plp-thumb[href], :scope > a.xcell-mm__plp-thumb[href]')];
    links.forEach(anchor => {
      row = pushChild(sub, anchor, 1, row);
    });
  };

  const root = document.querySelector('#xcell-mm-i1.xcell-mm, #xcell-mm-i1, .xcell-mm.xcell-mm--plp');
  const parentItems = root
    ? [...root.querySelectorAll(':scope > .xcell-mm__bar .xcell-mm__list > li.xcell-mm__li.has-panel')]
    : [];
  const hierarchy = [];

  parentItems.forEach((parentItem, parentIndex) => {
    const parentAnchor = parentItem.querySelector(':scope > a.xcell-mm__top[href]');
    const parentName = clean(parentAnchor?.innerText || parentAnchor?.textContent);
    const parentUrl = parentAnchor?.href || '';
    if (!parentName || !validHref(parentUrl)) return;
    const panel = parentItem.querySelector(':scope > .xcell-mm__panel');
    const item = {
      order: parentIndex + 1,
      name: parentName,
      url: parentUrl,
      selector: css(parentAnchor),
      method: 'click',
      sub_children: []
    };
    if (!panel) {
      hierarchy.push(item);
      return;
    }

    const panelById = {};
    [...panel.querySelectorAll('.xcell-mm__plp-panel[id]')].forEach(contentPanel => {
      panelById[contentPanel.id] = contentPanel;
    });
    const railButtons = [...panel.querySelectorAll('.xcell-mm__plp-body > nav.xcell-mm__rail button.xcell-mm__rail-item')];
    let subOrder = 0;

    railButtons.forEach(button => {
      const subName = clean(button.innerText || button.textContent);
      const targetId = button.getAttribute('data-xcell-rail') || '';
      const contentPanel = panelById[targetId];
      if (!subName || !contentPanel) return;
      const firstChildLink = contentPanel.querySelector('a.xcell-mm__plp-thumb[href], a.xcell-mm__plp-group-head[href]');
      const sub = {
        order: ++subOrder,
        name: subName,
        url: inferSubUrl(parentUrl, firstChildLink?.href || ''),
        selector: css(button),
        method: 'dom-inspection',
        children: [],
        _seen: new Set()
      };
      collectChildren(sub, contentPanel);
      delete sub._seen;
      item.sub_children.push(sub);
    });

    if (!item.sub_children.length) {
      const directLinks = [...panel.querySelectorAll('.xcell-mm__plp a.xcell-mm__plp-thumb[href], .xcell-mm__plp a.xcell-mm__plp-group-head[href]')];
      if (directLinks.length) {
        const sub = {
          order: 1,
          name: parentName,
          url: parentUrl,
          selector: css(parentAnchor),
          method: 'dom-inspection',
          children: [],
          _seen: new Set()
        };
        directLinks.forEach(anchor => {
          if ((anchor.href || '').replace(/\\/+$/, '') === parentUrl.replace(/\\/+$/, '')) return;
          pushChild(sub, anchor, 1, sub.children.length + 1);
        });
        delete sub._seen;
        item.sub_children.push(sub);
      }
    }
    hierarchy.push(item);
  });
  return hierarchy;
}
"""


async def extract(page, config, args, output_dir, logger):
    count = await page.locator(config.parent_item_selector).count()
    logger.info("Detected %s parent menu items", count)
    for i in range(count):
        try:
            await click_or_hover(page, config.parent_item_selector, i, "hover", args.interaction_delay)
            if args.save_parent_screenshots:
                from .common import save_screenshot

                await save_screenshot(page, output_dir, f"xcell-parent-{i + 1}")
        except Exception as exc:
            logger.warning("Parent hover failed index=%s error=%s", i, exc)
    hierarchy = await page.evaluate(XCELL_JS)
    logger.info("Extracted hierarchy parent_count=%s", len(hierarchy))
    return records_from_hierarchy(config, hierarchy)


def main() -> None:
    parser = build_arg_parser(CONFIG.output_slug)
    args = parser.parse_args()
    asyncio.run(run_site(CONFIG, args, extract))


if __name__ == "__main__":
    main()
