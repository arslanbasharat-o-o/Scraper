from __future__ import annotations

import asyncio

from .common import build_arg_parser, run_site
from .mobilesentrix import MobileSentrixConfig, extract


CONFIG = MobileSentrixConfig(
    website="MobileSentrix Canada",
    website_url="https://www.mobilesentrix.ca/",
    output_slug="mobilesentrix_canada",
    base_url="https://www.mobilesentrix.ca/",
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


def main() -> None:
    parser = build_arg_parser(CONFIG.output_slug)
    args = parser.parse_args()
    asyncio.run(run_site(CONFIG, args, extract))


if __name__ == "__main__":
    main()
