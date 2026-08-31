import asyncio
from urllib.parse import quote

from scrapers.menu_map.common import BotasaurusPage
from scrapers.botasaurus_wrapper import Driver, browser


def evaluate_script(script, html, base_url, argument=None):
    document = f'<base href="{base_url}">{html}'
    data_url = f"data:text/html;charset=utf-8,{quote(document)}"

    @browser(
        headless=True,
        output=None,
        raise_exception=True,
        close_on_crash=True,
    )
    def evaluate(driver: Driver, data):
        driver.get(data["url"])
        page = BotasaurusPage(driver)
        return asyncio.run(page.evaluate(data["script"], data["argument"]))

    return evaluate({
        "url": data_url,
        "script": script,
        "argument": argument,
    })
