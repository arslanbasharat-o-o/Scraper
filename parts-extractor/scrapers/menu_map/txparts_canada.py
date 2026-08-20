from __future__ import annotations

import asyncio

from .common import build_arg_parser, run_site
from .txparts import TXPartsConfig, extract


CONFIG = TXPartsConfig(
    website="TXParts Canada",
    website_url="https://txpartscanada.ca/",
    output_slug="txparts_canada",
    base_url="https://txpartscanada.ca/",
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


def main() -> None:
    parser = build_arg_parser(CONFIG.output_slug)
    args = parser.parse_args()
    asyncio.run(run_site(CONFIG, args, extract))


if __name__ == "__main__":
    main()
