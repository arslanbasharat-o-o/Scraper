from scrapers.menu_map.gadgetfix import GADGETFIX_JS
from scrapers.menu_map.mobilesentrix import MOBILESENTRIX_JS
from scrapers.menu_map.txparts import TXPARTS_JS
from scrapers.browser_fetcher import (
    MOBILESENTRIX_CANADA_POPUP_DISMISS_JS,
    _is_mobilesentrix_canada_url,
    _should_use_botasaurus_request_html,
)
from tests.botasaurus_test_utils import evaluate_script


def evaluate_menu(script, html, base_url):
    return evaluate_script(script, html, base_url)


def test_botasaurus_page_evaluate_accepts_selector_arguments_with_quotes():
    result = evaluate_script(
        "(selectors) => document.querySelectorAll(selectors[0]).length",
        """<nav role="navigation"><a href="/parts">Parts</a></nav>""",
        "https://www.mobilesentrix.ca/",
        ["[role='navigation']"],
    )

    assert result == 1


def test_mobilesentrix_uses_series_panels_as_sub_children():
    hierarchy = evaluate_menu(
        MOBILESENTRIX_JS,
        """
        <ul id="nav">
          <li>
            <a href="javascript:;">Motorola</a>
            <ul class="level0 slayouts-menu">
              <div class="main-menu-head"></div>
              <li class="sview-allmenu">
                <ul>
                  <li class="sview-li"><a href="javascript:;">Moto G Series</a></li>
                  <li class="sview-li"><a href="javascript:;">Moto E Series</a></li>
                </ul>
              </li>
              <li>
                <a href="javascript:;">Moto G Series</a>
                <ul class="sview-inul">
                  <li class="sview-row">
                    <a href="javascript:;">Moto G Series</a>
                    <ul>
                      <li><a href="/replacement-parts/motorola/g-series/g47">G47 (XT2625 / 2026)</a></li>
                      <li><a href="/replacement-parts/motorola/g-series/g37-power">G37 Power (XT2625 / 2026)</a></li>
                    </ul>
                  </li>
                  <li class="sview-row">
                    <ul>
                      <li><a href="/replacement-parts/motorola/g-series/g-power-2025">G Power (XT2515 / 2025)</a></li>
                    </ul>
                  </li>
                </ul>
              </li>
              <li>
                <a href="javascript:;">Moto E Series</a>
                <ul class="sview-inul">
                  <li class="sview-row">
                    <a href="javascript:;">Moto E Series</a>
                    <ul>
                      <li><a href="/replacement-parts/motorola/e-series/e-2025">E (XT2527 / 2025)</a></li>
                    </ul>
                  </li>
                </ul>
              </li>
            </ul>
          </li>
        </ul>
        """,
        "https://www.mobilesentrix.com/",
    )

    assert [group["name"] for group in hierarchy[0]["sub_children"]] == ["Moto G Series", "Moto E Series"]
    assert [child["name"] for child in hierarchy[0]["sub_children"][0]["children"]] == [
        "G47 (XT2625 / 2026)",
        "G37 Power (XT2625 / 2026)",
        "G Power (XT2515 / 2025)",
    ]


def test_txparts_keeps_real_parent_sub_child_and_model_levels():
    hierarchy = evaluate_menu(
        TXPARTS_JS,
        """
        <ul class="mobil-view-menu">
          <li>
            <a class="menu-l mobile-menu-category" href="#">Apple</a>
            <ul class="other-brand-menu accordion-menu">
              <li class="category-list">
                <div class="nav-title"><a class="product-link product-main-menu" href="/shop/iphone">iPhone</a></div>
                <ul><li><a href="/shop/iphone-17">iPhone 17</a></li><li><a href="/shop/iphone-16">iPhone 16</a></li></ul>
              </li>
              <li class="category-list">
                <div class="nav-title"><a class="product-link product-main-menu" href="/shop/ipad">iPad</a></div>
                <ul><li><a href="/shop/ipad-pro">iPad Pro</a></li></ul>
              </li>
            </ul>
          </li>
          <li>
            <a class="menu-l mobile-menu-category" href="#">Samsung</a>
            <ul class="other-brand-menu accordion-menu">
              <li class="category-list">
                <div class="nav-title"><a class="product-link product-main-menu" href="/shop/s-series">S Series</a></div>
                <ul><li><a href="/shop/galaxy-s25">Galaxy S25</a></li></ul>
              </li>
            </ul>
          </li>
        </ul>
        """,
        "https://txparts.com/",
    )

    assert [parent["name"] for parent in hierarchy] == ["Apple", "Samsung"]
    assert [group["name"] for group in hierarchy[0]["sub_children"]] == ["iPhone", "iPad"]
    assert hierarchy[0]["sub_children"][0]["children"][0]["name"] == "iPhone 17"


def test_txparts_canada_accepts_canadian_domain_links():
    hierarchy = evaluate_menu(
        TXPARTS_JS,
        """
        <ul class="mobil-view-menu">
          <li>
            <a class="menu-l mobile-menu-category" href="#">Apple</a>
            <ul class="other-brand-menu accordion-menu">
              <li class="category-list">
                <div class="nav-title"><a class="product-link product-main-menu" href="/shop/iphone">iPhone</a></div>
                <ul><li><a href="/shop/iphone-17">iPhone 17</a></li></ul>
              </li>
            </ul>
          </li>
        </ul>
        """,
        "https://txpartscanada.ca/",
    )

    assert hierarchy[0]["url"] == "https://txpartscanada.ca/shop/iphone"
    assert hierarchy[0]["sub_children"][0]["children"][0]["url"] == "https://txpartscanada.ca/shop/iphone-17"


def test_gadgetfix_keeps_brand_series_and_model_levels():
    hierarchy = evaluate_menu(
        GADGETFIX_JS,
        """
        <div class="mega-menu"><ul>
          <li class="menu-item">
            <a href="/category/apple-1228.html">Apple</a>
            <div class="mega-submenu"><div class="submenu-content">
              <div class="section links">
                <h3><a href="/category/iphone-1559.html">iPhone</a></h3>
                <ul><li><a href="/category/iphone-17-2001.html">iPhone 17</a></li><li><a href="/category/iphone-16-2002.html">iPhone 16</a></li></ul>
              </div>
              <div class="section links">
                <h3><a href="/category/iwatch-1638.html">iWatch</a></h3>
                <ul><li><a href="/category/series-9-2010.html">Series 9</a></li></ul>
              </div>
            </div></div>
          </li>
          <li class="menu-item">
            <a href="/category/google-1552.html">Google</a>
            <div class="mega-submenu"><div class="section links">
              <h3><a href="/category/pixel-series-1553.html">Pixel Series</a></h3>
              <ul><li><a href="/category/pixel-10-1554.html">Pixel 10</a></li></ul>
            </div></div>
          </li>
        </ul></div>
        """,
        "https://gadgetfix.com/",
    )

    assert [parent["name"] for parent in hierarchy] == ["Apple", "Google"]
    assert [group["name"] for group in hierarchy[0]["sub_children"]] == ["iPhone", "iWatch"]
    assert hierarchy[1]["sub_children"][0]["children"][0]["name"] == "Pixel 10"


def test_canada_location_prompt_stays_on_canadian_store():
    assert _is_mobilesentrix_canada_url("https://www.mobilesentrix.ca/example") is True
    assert _is_mobilesentrix_canada_url("https://www.mobilesentrix.com/example") is False
    result = evaluate_script(
        f"""
        () => {{
          const dismissed = {MOBILESENTRIX_CANADA_POPUP_DISMISS_JS};
          return [dismissed, document.querySelectorAll('#location-dialog').length];
        }}
        """,
        """
        <div role="dialog" id="location-dialog">
          <h2>Welcome to MobileSentrix Canada!</h2>
          <p>We noticed you're in United States.</p>
          <a href="https://www.mobilesentrix.com">Go to mobilesentrix.com</a>
          <div id="stay" role="button" onclick="document.querySelector('#location-dialog').remove()">Or stay on mobilesentrix.ca</div>
        </div>
        """,
        "https://www.mobilesentrix.ca/",
    )
    assert result == [True, 0]


def test_botasaurus_request_html_fast_path_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SCRAPER_BOTASAURUS_REQUEST_HTML", raising=False)
    monkeypatch.delenv("BOTASAURUS_REQUEST_HTML", raising=False)

    assert _should_use_botasaurus_request_html() is False

    monkeypatch.setenv("SCRAPER_BOTASAURUS_REQUEST_HTML", "1")
    assert _should_use_botasaurus_request_html() is True
