"""Shared scraper metadata and routing helpers."""

from __future__ import annotations

from collections import OrderedDict
from urllib.parse import urlparse


SCRAPER_CONFIG = OrderedDict(
    [
        (
            'standard',
            {
                'db_key': 'mobilesentrix',
                'label': 'MobileSentrix',
                'domains': ('mobilesentrix.com',),
            },
        ),
        (
            'mobilesentrix_canada',
            {
                'db_key': 'mobilesentrix_ca',
                'label': 'MobileSentrix Canada',
                'domains': ('mobilesentrix.ca',),
            },
        ),
        (
            'xcell',
            {
                'db_key': 'xcellparts',
                'label': 'XCellParts',
                'domains': ('xcellparts.com',),
            },
        ),
        (
            'txparts',
            {
                'db_key': 'txparts',
                'label': 'TXParts',
                'domains': ('txparts.com', 'txpartscanada.ca'),
            },
        ),
        (
            'parts4cells',
            {
                'db_key': 'parts4cells',
                'label': 'Parts4Cells',
                'domains': ('parts4cells.com',),
            },
        ),
        (
            'phonelcdparts',
            {
                'db_key': 'phonelcdparts',
                'label': 'PhoneLCDParts',
                'domains': ('phonelcdparts.com',),
            },
        ),
        (
            'gadgetfix',
            {
                'db_key': 'gadgetfix',
                'label': 'GadgetFix',
                'domains': ('gadgetfix.com',),
            },
        ),
    ]
)

DEFAULT_SCRAPER_KEY = 'standard'
DB_KEY_TO_SCRAPER_KEY = {
    config['db_key']: scraper_key
    for scraper_key, config in SCRAPER_CONFIG.items()
}


def _normalize_host(value: str) -> str:
    return str(value or '').strip().lower().replace('www.', '')


def detect_scraper_key(value: str) -> str:
    """Detect the scraper key from a URL, hostname, or site label."""
    raw = str(value or '').strip()
    if not raw:
        return DEFAULT_SCRAPER_KEY

    host = _normalize_host(urlparse(raw).netloc or raw)
    for scraper_key, config in SCRAPER_CONFIG.items():
        for domain in config['domains']:
            normalized_domain = _normalize_host(domain)
            if host == normalized_domain or host.endswith(f'.{normalized_domain}') or normalized_domain in host:
                return scraper_key

    lowered = raw.lower()
    for scraper_key, config in SCRAPER_CONFIG.items():
        if config['db_key'] in lowered or config['label'].lower() in lowered:
            return scraper_key

    return DEFAULT_SCRAPER_KEY


def get_db_key(scraper_key: str) -> str:
    config = SCRAPER_CONFIG.get(scraper_key) or SCRAPER_CONFIG[DEFAULT_SCRAPER_KEY]
    return config['db_key']


def get_db_filename(scraper_key: str) -> str:
    return f"{get_db_key(scraper_key)}.db"


def split_urls_by_scraper(urls):
    grouped = OrderedDict()
    for scraper_key in SCRAPER_CONFIG.keys():
        grouped[scraper_key] = []

    for url in urls or []:
        grouped[detect_scraper_key(url)].append(url)

    return {key: value for key, value in grouped.items() if value}
