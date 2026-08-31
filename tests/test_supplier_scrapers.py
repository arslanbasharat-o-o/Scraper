from bs4 import BeautifulSoup
from types import SimpleNamespace

from scrapers import gadgetfix_scraper_engine, phonelcdparts_scraper_engine, txparts_scraper_engine
from scrapers.gadgetfix_scraper_engine import (
    extract_items_from_soup as extract_gadgetfix_items,
    scrape_product_page as scrape_gadgetfix_product_page,
)
from scrapers.phonelcdparts_scraper_engine import extract_items_from_soup as extract_phonelcd_items
from scrapers.phonelcdparts_scraper_engine import _looks_like_block_page as phonelcd_looks_blocked
from scrapers.phonelcdparts_scraper_engine import is_category_page as is_phonelcd_category_page
from scrapers.phonelcdparts_scraper_engine import is_product_page as is_phonelcd_product_page
from scrapers.phonelcdparts_scraper_engine import scrape_product_page as scrape_phonelcd_product_page
from scrapers.txparts_scraper_engine import _looks_like_block_page as txparts_looks_blocked
from scrapers.xcell_scraper_engine import (
    extract_items_from_category_soup as extract_xcell_items,
    parse_xcell_product_detail_fast,
)
from scrapers.registry import detect_scraper_key


class FakeSession:
    def __init__(self, html):
        self.html = html
        self.gadgetfix_blocked = False
        self.gadgetfix_last_error = ""

    def get(self, url, **_kwargs):
        return FakeResponse(url, self.html)


class FakeResponse:
    def __init__(self, url, html):
        self.url = url
        self.text = html
        self.status_code = 200

    def raise_for_status(self):
        return None


def test_detects_new_supplier_domains():
    assert detect_scraper_key("https://www.mobilesentrix.com/replacement-parts/apple/iphone-parts") == "standard"
    assert detect_scraper_key("https://www.mobilesentrix.ca/replacement-parts/apple/iphone-parts") == "mobilesentrix_canada"
    assert detect_scraper_key("https://www.phonelcdparts.com/apple/best-sellers/qmax") == "phonelcdparts"
    assert detect_scraper_key("https://gadgetfix.com/category/iphone-1559.html") == "gadgetfix"
    assert detect_scraper_key("https://m.gadgetfix.com/category/iphone-1559.html") == "gadgetfix"
    assert detect_scraper_key("https://txpartscanada.ca/shop/iphone-15") == "txparts"


def test_security_script_words_do_not_hide_real_catalog_pages():
    valid_catalog = """
    <html><head><title>iPhone 15 Parts</title>
      <script>window.securityVendors = ['cloudflare', 'captcha'];</script>
    </head><body class="catalog-category-view">
      <form class="item product product-item product_addtocart_form">
        <a class="product-item-link" href="/iphone-15-screen">iPhone 15 Screen</a>
      </form>
    </body></html>
    """ + (" " * 200_000)
    challenge = '<html><head><title>Just a moment...</title></head><body><form id="challenge-form"></form></body></html>'

    assert phonelcd_looks_blocked(valid_catalog) is False
    assert txparts_looks_blocked(valid_catalog) is False
    assert phonelcd_looks_blocked(challenge) is True
    assert txparts_looks_blocked(challenge) is True


def test_txparts_listing_prefers_title_anchor_when_image_anchor_is_first():
    html = """
    <html><body>
      <div class="product">
        <a href="/product/lcd-assembly-for-iphone-17-pro-max-cof-120hz-1">
          <img src="https://admin.txpartscanada.ca/assets/products/compress/display.jpg" alt="">
        </a>
        <a href="/product/lcd-assembly-for-iphone-17-pro-max-cof-120hz-1">
          Lcd Assembly For Iphone 17 Pro Max Cof 120Hz
        </a>
        <span>$76.86</span>
      </div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")

    items = txparts_scraper_engine.extract_products_from_page(soup, "https://txpartscanada.ca/shop/iphone-17-pro-max")

    assert len(items) == 1
    assert items[0].title == "Lcd Assembly For Iphone 17 Pro Max Cof 120Hz"
    assert items[0].url == "https://txpartscanada.ca/product/lcd-assembly-for-iphone-17-pro-max-cof-120hz-1"
    assert items[0].original == 76.86


def test_txparts_slug_fallback_strips_duplicate_suffix_one():
    html = """
    <html><body>
      <div class="product">
        <a href="/product/premium-battery-replacement-for-iphone-17-pro-max-1">
          <img src="https://admin.txpartscanada.ca/assets/products/compress/battery.jpg" alt="">
        </a>
        <span>$66.46</span>
      </div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")

    items = txparts_scraper_engine.extract_products_from_page(soup, "https://txpartscanada.ca/shop/iphone-17-pro-max")

    assert len(items) == 1
    assert items[0].title == "Premium Battery Replacement For Iphone 17 Pro Max"
    assert items[0].url == "https://txpartscanada.ca/product/premium-battery-replacement-for-iphone-17-pro-max-1"


def test_txparts_slug_fallback_strips_repeated_duplicate_suffix_one():
    html = """
    <html><body>
      <div class="product">
        <a href="/product/motherboard-flex-cable-connected-to-lcd-for-galaxy-a30-a305-flex-1-1">
          <img src="https://admin.txpartscanada.ca/assets/products/compress/flex.jpg" alt="">
        </a>
        <span>$4.00</span>
      </div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")

    items = txparts_scraper_engine.extract_products_from_page(soup, "https://txpartscanada.ca/shop/a30-a305-2019")

    assert len(items) == 1
    assert items[0].title == "Motherboard Flex Cable Connected To Lcd For Galaxy A30 A305 Flex"


def test_xcellparts_fallback_extracts_product_anchor_cards():
    html = """
    <html><body>
      <main class="catalog-grid">
        <div class="catalog-card">
          <a href="/product/outter-oled-assembly-without-frame-for-samsung-zfold-7-5g/">
            <img src="/wp-content/uploads/zfold7.jpg" alt="Outer OLED Assembly for Samsung ZFold 7 5G">
          </a>
          <div class="catalog-card__body">
            <a href="/product/outter-oled-assembly-without-frame-for-samsung-zfold-7-5g/">
              Outer OLED Assembly for Samsung ZFold 7 5G
            </a>
            <span class="price">$88.50</span>
          </div>
        </div>
      </main>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")

    items = extract_xcell_items(soup, "https://xcellparts.com/product-category/samsung/galaxy-z-series/", {}, None)

    assert len(items) == 1
    assert items[0].title == "Outer OLED Assembly for Samsung ZFold 7 5G"
    assert items[0].url == "https://xcellparts.com/product/outter-oled-assembly-without-frame-for-samsung-zfold-7-5g/"
    assert items[0].image_url == "https://xcellparts.com/wp-content/uploads/zfold7.jpg"
    assert items[0].original == 88.5


def test_xcellparts_extracts_new_rendered_link_grid_without_product_classes():
    html = """
    <html><body>
      <main>
        <section class="grid">
          <div class="cell">
            <a href="/product/oled-assembly-compatible-for-iphone-15-pro-premium-2/">
              <img src="/wp-content/uploads/ip15pro.jpg" alt="">
            </a>
            <a href="/product/oled-assembly-compatible-for-iphone-15-pro-premium-2/">
              LCD ASSEMBLY COMPATIBLE FOR IPHONE 15 PRO (PREMIUM)
            </a>
            <span>$135.00</span>
          </div>
          <div class="cell">
            <a href="/product/oled-assembly-compatible-for-iphone-15-pro-soft-oled/">
              <img src="/wp-content/uploads/ip15pro-soft.jpg" alt="">
            </a>
            <a href="/product/oled-assembly-compatible-for-iphone-15-pro-soft-oled/">
              OLED ASSEMBLY COMPATIBLE FOR IPHONE 15 PRO (SOFT OLED)
            </a>
            <span>$95.00</span>
          </div>
        </section>
      </main>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")

    items = extract_xcell_items(soup, "https://xcellparts.com/product-category/apple/iphone/iphone-15-pro/", {}, None)

    assert len(items) == 2
    assert items[0].title == "LCD ASSEMBLY COMPATIBLE FOR IPHONE 15 PRO (PREMIUM)"
    assert items[0].url == "https://xcellparts.com/product/oled-assembly-compatible-for-iphone-15-pro-premium-2/"
    assert items[0].image_url == "https://xcellparts.com/wp-content/uploads/ip15pro.jpg"
    assert items[0].original == 135.0
    assert items[1].title == "OLED ASSEMBLY COMPATIBLE FOR IPHONE 15 PRO (SOFT OLED)"
    assert items[1].original == 95.0


def test_xcellparts_fast_detail_parser_extracts_required_metadata_without_dom():
    html = """
    <html><head>
      <link rel="canonical" href="https://xcellparts.com/product/iphone-15-screen/">
      <meta name="description" content="Premium replacement display for repair shops.">
      <meta property="og:image" content="https://xcellparts.com/uploads/iphone-15.jpg">
    </head><body>
      <h1 class="product_title entry-title">iPhone 15 Premium OLED Assembly</h1>
      <span class="woocommerce-Price-amount amount"><bdi><span>$</span>89.50</bdi></span>
      <span class="xcell-pdp-copy" data-xcell-copy="IP15-OLED-PREM">SKU</span>
      <p class="stock in-stock">12 in stock</p>
      <div class="woocommerce-product-details__short-description"><p>Bright OLED panel with frame.</p></div>
    </body></html>
    """

    item = parse_xcell_product_detail_fast(html, "https://xcellparts.com/product/iphone-15-screen/", {})

    assert item is not None
    assert item.title == "iPhone 15 Premium OLED Assembly"
    assert item.sku == "IP15-OLED-PREM"
    assert item.original == 89.5
    assert item.stock_status == "12 in stock"
    assert item.description == "Bright OLED panel with frame."
    assert item.image_url.endswith("/uploads/iphone-15.jpg")


def test_phonelcdparts_hyva_listing_card_extracts_product_fields():
    html = """
    <ol>
      <li class="item product product-item">
        <a href="https://www.phonelcdparts.com/iphone-11-lcd-assembly-with-plate-incell-qv7"
           class="product photo product-item-photo"
           title="LCD Assembly with Steel Plate for iPhone 11 (Aftermarket Incell / QV7)">
          <img class="object-contain product-image-photo"
               src="https://www.phonelcdparts.com/media/catalog/product/cache/phone.jpg"
               alt="Purchase the LCD Assembly with Steel Plate for iPhone 11" />
        </a>
        <a class="product-item-link"
           href="https://www.phonelcdparts.com/iphone-11-lcd-assembly-with-plate-incell-qv7"
           title="LCD Assembly with Steel Plate for iPhone 11 (Aftermarket Incell / QV7)">
          LCD Assembly with Steel Plate for iPhone 11 (Aftermarket Incell / QV7)
        </a>
        <span data-price-type="finalPrice" data-price-amount="14.5" class="price-wrapper">$14.50</span>
        <span x-text="$store.cart.getQty('11\\u002DQV7\\u002DINC')"></span>
      </li>
    </ol>
    """
    soup = BeautifulSoup(html, "html.parser")

    items = extract_phonelcd_items(soup, "https://www.phonelcdparts.com/apple/best-sellers/qmax", {}, None)

    assert len(items) == 1
    assert items[0].title == "LCD Assembly with Steel Plate for iPhone 11 (Aftermarket Incell / QV7)"
    assert items[0].url == "https://www.phonelcdparts.com/iphone-11-lcd-assembly-with-plate-incell-qv7"
    assert items[0].image_url.endswith("/phone.jpg")
    assert items[0].original == 14.5
    assert items[0].sku == "11-QV7-INC"


def test_phonelcdparts_parent_category_expands_direct_child_categories():
    parent_url = "https://www.phonelcdparts.com/apple/best-sellers/qmax"
    child_url = f"{parent_url}/apple-batteries"
    parent_html = f"""
    <html><body class="catalog-category-view"><main>
      <a href="{child_url}"><button>View Products</button></a>
    </main></body></html>
    """
    child_html = """
    <html><body class="catalog-category-view">
      <ol><li class="item product product-item">
        <a class="product-item-link" href="/qmax-iphone-battery" title="QMAX iPhone Battery">QMAX iPhone Battery</a>
        <span data-price-amount="19.5">$19.50</span>
        <span data-product-sku="QMAX-IP-BAT"></span>
      </li></ol>
    </body></html>
    """

    class MappingSession(FakeSession):
        def __init__(self):
            super().__init__("")
            self.responses = {parent_url: parent_html, child_url: child_html}

        def get(self, url, **_kwargs):
            return FakeResponse(url, self.responses[url])

    items = phonelcdparts_scraper_engine.scrape_url(
        MappingSession(),
        parent_url,
        {},
        crawl_pagination=True,
        max_pages=1,
        delay_ms=0,
    )

    assert len(items) == 1
    assert items[0].title == "QMAX iPhone Battery"
    assert items[0].sku == "QMAX-IP-BAT"


def test_phonelcdparts_product_page_ignores_related_product_cards():
    soup = BeautifulSoup(
        """
        <html><body class="catalog-product-view">
          <form id="product_addtocart_form"><h1>iPhone 15 Screen</h1></form>
          <form class="item product product-item product_addtocart_form">
            <a href="/related-screen">Related Screen</a>
          </form>
        </body></html>
        """,
        "html.parser",
    )

    assert is_phonelcd_product_page(soup) is True
    assert is_phonelcd_category_page(soup) is False


def test_phonelcdparts_product_detail_prefers_main_sku_and_price_metadata(monkeypatch):
    html = """
    <html><body class="catalog-product-view">
      <meta property="product:price:amount" content="21">
      <form id="product_addtocart_form" data-sku="15-QV6-INC">
        <h1 class="page-title"><span class="base">iPhone 15 Screen</span></h1>
      </form>
      <form class="item product product-item" data-sku="RELATED-SKU">
        <span data-price-amount="14"></span>
      </form>
      <meta property="og:image" content="/images/iphone-15.jpg">
    </body></html>
    """

    monkeypatch.setattr(
        phonelcdparts_scraper_engine,
        "fetch_html_with_browser",
        lambda *_args, **_kwargs: SimpleNamespace(html=html),
    )
    item = scrape_phonelcd_product_page(FakeSession(html), "https://www.phonelcdparts.com/iphone-15-screen", {}, None)

    assert item.sku == "15-QV6-INC"
    assert item.original == 21.0


def test_gadgetfix_category_extracts_product_cards_and_skips_category_links():
    html = """
    <html><body>
      <nav><a href="/category/iphone-1559.html">iPhone</a></nav>
      <ul class="products">
        <li class="product">
          <a href="/lcd-display-screen-touch-screen-digitizer-frame-assembly-parts-for-iphone-4s-6511.html">
            <img src="/images/iphone-4s.jpg" alt="LCD Display Screen Touch Screen Digitizer Frame Assembly Parts for Iphone 4S">
          </a>
          <span class="price">$8.95 $8.95</span>
          <h6>
            <a href="/lcd-display-screen-touch-screen-digitizer-frame-assembly-parts-for-iphone-4s-6511.html">
              LCD Display Screen Touch Screen Digitizer Frame Assembly Parts for Iphone 4S
            </a>
          </h6>
        </li>
      </ul>
      <div class="pagination"><a href="/category/iphone-1559/2.html">&gt;&gt;</a></div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")

    items = extract_gadgetfix_items(soup, "https://gadgetfix.com/category/iphone-1559.html", {}, None)

    assert len(items) == 1
    assert items[0].title == "LCD Display Screen Touch Screen Digitizer Frame Assembly Parts for Iphone 4S"
    assert items[0].url == "https://gadgetfix.com/lcd-display-screen-touch-screen-digitizer-frame-assembly-parts-for-iphone-4s-6511.html"
    assert items[0].image_url == "https://gadgetfix.com/images/iphone-4s.jpg"
    assert items[0].original == 8.95


def test_gadgetfix_product_detail_extracts_sku_stock_and_price(monkeypatch):
    html = """
    <html><body>
      <h1>USA proximity light sensor power button flex cable ribbon parts for iphone 4S</h1>
      <p>Item: 351309772511 Condition: New Availability: In Stock Brand: Unbranded</p>
      <p>Compatible with: iphone 4S</p>
      <p>What you get: 1 x iphone 4S proximity sensor flex</p>
      <p>Price: $7.45 $7.45</p>
      <img src="/images/proximity.jpg">
    </body></html>
    """

    monkeypatch.setattr(
        gadgetfix_scraper_engine,
        "fetch_html_with_browser",
        lambda *_args, **_kwargs: SimpleNamespace(html=html),
    )
    item = scrape_gadgetfix_product_page(FakeSession(html), "https://gadgetfix.com/usa-proximity-6554.html", {}, None)

    assert item.title == "USA proximity light sensor power button flex cable ribbon parts for iphone 4S"
    assert item.sku == "351309772511"
    assert item.stock_status == "In Stock"
    assert item.original == 7.45
    assert item.image_url == "https://gadgetfix.com/images/proximity.jpg"


def test_gadgetfix_product_detail_uses_metadata_when_h1_is_empty(monkeypatch):
    html = """
    <html>
      <head><meta property="og:title" content="Incell Display for iPhone 15"></head>
      <body>
        <h1></h1>
        <p>Item: 10269 Condition: New Availability: In Stock Brand: Unbranded</p>
        <p>Price: $18.95</p>
        <img src="/images/iphone-15.jpg">
      </body>
    </html>
    """

    monkeypatch.setattr(
        gadgetfix_scraper_engine,
        "fetch_html_with_browser",
        lambda *_args, **_kwargs: SimpleNamespace(html=html),
    )
    item = scrape_gadgetfix_product_page(FakeSession(html), "https://gadgetfix.com/incell-display-10269.html", {}, None)

    assert item.title == "Incell Display for iPhone 15"
    assert item.sku == "10269"
    assert item.original == 18.95
