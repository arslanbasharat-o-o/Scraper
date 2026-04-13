"""Scraper engine package for all supported suppliers."""

from .registry import (
    DB_KEY_TO_SCRAPER_KEY,
    DEFAULT_SCRAPER_KEY,
    SCRAPER_CONFIG,
    detect_scraper_key,
    get_db_filename,
    get_db_key,
    split_urls_by_scraper,
)

__all__ = [
    'DB_KEY_TO_SCRAPER_KEY',
    'DEFAULT_SCRAPER_KEY',
    'SCRAPER_CONFIG',
    'detect_scraper_key',
    'get_db_filename',
    'get_db_key',
    'split_urls_by_scraper',
]
