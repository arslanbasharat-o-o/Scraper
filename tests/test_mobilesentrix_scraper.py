from scrapers.scraper_engine import is_category_page, is_product_page, scrape_url
from scrapers.browser_fetcher import browser_fetch_mode
from bs4 import BeautifulSoup


class FakeResponse:
    def __init__(self, url, html, status_code=200):
        self.url = url
        self.text = html
        self.status_code = status_code
        self.headers = {"content-type": "text/html; charset=UTF-8"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, html):
        self.html = html
        self.calls = []

    def get(self, url, **_kwargs):
        self.calls.append(url)
        return FakeResponse(url, self.html)


def test_mobilesentrix_category_h1_is_not_misclassified_as_product():
    url = "https://www.mobilesentrix.ca/replacement-parts/samsung/galaxy-s-series/galaxy-s25-ultra"
    html = """
    <html>
      <head><title>Samsung S25 Ultra Parts - MobileSentrix Canada</title></head>
      <body>
        <h1 class="page-title"><span>Samsung Galaxy S25 Ultra Replacement Parts</span></h1>
        <ul class="product-listing">
          <li class="item">
            <a href="/screen-assembly-s25-ultra">
              <span>Samsung Galaxy S25 Ultra LCD Assembly</span>
            </a>
            <span data-price-amount="173.47"></span>
            <img src="/media/catalog/product/s25-screen.jpg" alt="S25 screen" />
          </li>
        </ul>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert is_category_page(soup) is True
    assert is_product_page(soup) is False

    with browser_fetch_mode(False):
        items = scrape_url(
            FakeSession(html),
            url,
            {"add_percent": 0, "percent_off": 0, "absolute_off": 0},
            crawl_pagination=True,
            max_pages=2,
            delay_ms=0,
        )

    assert len(items) == 1
    assert items[0].title == "Samsung Galaxy S25 Ultra LCD Assembly"
    assert items[0].url == "https://www.mobilesentrix.ca/screen-assembly-s25-ultra"
    assert items[0].price_value == 173.47


def test_mobilesentrix_product_detail_still_scrapes_as_product():
    url = "https://www.mobilesentrix.ca/screen-assembly-s25-ultra"
    html = """
    <html>
      <head><meta property="og:type" content="product" /></head>
      <body>
        <form id="product_addtocart_form">
          <h1><span data-ui-id="page-title-wrapper">Samsung Galaxy S25 Ultra LCD Assembly</span></h1>
          <span data-price-amount="173.47"></span>
          <span itemprop="sku">S25U-SCREEN</span>
          <img class="product-image-photo" src="/media/catalog/product/s25-screen.jpg" />
        </form>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert is_product_page(soup) is True

    with browser_fetch_mode(False):
        items = scrape_url(
            FakeSession(html),
            url,
            {"add_percent": 0, "percent_off": 0, "absolute_off": 0},
            crawl_pagination=True,
            max_pages=2,
            delay_ms=0,
        )

    assert len(items) == 1
    assert items[0].title == "Samsung Galaxy S25 Ultra LCD Assembly"
    assert items[0].price_value == 173.47
    assert items[0].sku == "S25U-SCREEN"
