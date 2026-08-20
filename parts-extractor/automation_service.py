"""Automation discovery helpers for scheduled category scraping."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scrapers import SCRAPER_CONFIG
from scrapers.browser_fetcher import fetch_html as fetch_html_with_browser, should_use_browser_fetch


COMMON_NAV_SELECTORS = (
    'header a[href]',
    'nav a[href]',
    '.navigation a[href]',
    '.menu a[href]',
    '.menu-item a[href]',
    '.mega-menu a[href]',
    '.megamenu a[href]',
    '.navbar a[href]',
    '.header a[href]',
    '.vertical-menu a[href]',
    '.category-menu a[href]',
)

DISCOVERY_RULES = {
    'standard': {
        'home_url': 'https://www.mobilesentrix.com/',
        'allowed_prefixes': ('/replacement-parts/',),
    },
    'mobilesentrix_canada': {
        'home_url': 'https://www.mobilesentrix.ca/',
        'allowed_prefixes': ('/replacement-parts/',),
    },
    'xcell': {
        'home_url': 'https://xcellparts.com/',
        'allowed_prefixes': ('/product-category/',),
    },
    'txparts': {
        'home_url': 'https://txparts.com/',
        'allowed_prefixes': ('/shop/',),
    },
    'parts4cells': {
        'home_url': 'https://parts4cells.com/',
        'allowed_prefixes': (),
    },
    'phonelcdparts': {
        'home_url': 'https://www.phonelcdparts.com/',
        'allowed_prefixes': (),
    },
    'gadgetfix': {
        'home_url': 'https://gadgetfix.com/',
        'allowed_prefixes': ('/category/',),
    },
}

EXCLUDED_SUBSTRINGS = (
    '/cart',
    '/checkout',
    '/customer',
    '/account',
    '/login',
    '/register',
    '/wishlist',
    '/privacy',
    '/terms',
    '/returns',
    '/contact',
    '/about',
    '/support',
    '/blog',
    '/news',
    '/image-proxy',
    '/cdn-cgi/',
)

GENERIC_DISCOVERY_LABELS = {
    '',
    'view products',
    'shop now',
    'learn more',
    'read more',
    'forgot password',
    'skip to content',
}

STATIC_DISCOVERY_FALLBACKS = {
    'standard': {
        'iphone': [
            {'label': 'iPhone Parts', 'url': 'https://www.mobilesentrix.com/replacement-parts/apple/iphone-parts'},
        ],
    },
    'mobilesentrix_canada': {
        'iphone': [
            {'label': 'iPhone Parts', 'url': 'https://www.mobilesentrix.ca/replacement-parts/apple/iphone-parts'},
        ],
    },
    'xcell': {
        'iphone': [
            {'label': 'iPhone', 'url': 'https://xcellparts.com/product-category/apple/iphone'},
        ],
    },
    'parts4cells': {
        'iphone': [
            {'label': 'iPhone', 'url': 'https://parts4cells.com/apple/iphone.html'},
        ],
    },
    'phonelcdparts': {
        'iphone': [
            {'label': 'iPhone Parts', 'url': 'https://www.phonelcdparts.com/apple/iphone-parts'},
        ],
        'ipad': [
            {'label': 'iPad Parts', 'url': 'https://www.phonelcdparts.com/apple/ipad-parts'},
        ],
        'apple': [
            {'label': 'Apple Parts', 'url': 'https://www.phonelcdparts.com/apple'},
        ],
        'iwatch': [
            {'label': 'iWatch Parts', 'url': 'https://www.phonelcdparts.com/apple/iwatch-parts'},
        ],
        'watch': [
            {'label': 'iWatch Parts', 'url': 'https://www.phonelcdparts.com/apple/iwatch-parts'},
        ],
        'motorola': [
            {'label': 'Motorola Parts', 'url': 'https://www.phonelcdparts.com/motorola-parts.html'},
        ],
        'samsung': [
            {'label': 'Galaxy S Series Parts', 'url': 'https://www.phonelcdparts.com/samsung/galaxy-s-series-parts.html'},
            {'label': 'Galaxy Note Parts', 'url': 'https://www.phonelcdparts.com/samsung/galaxy-note-parts.html'},
        ],
        'google': [
            {'label': 'Google Pixel', 'url': 'https://www.phonelcdparts.com/google-pixel'},
        ],
        'pixel': [
            {'label': 'Google Pixel', 'url': 'https://www.phonelcdparts.com/google-pixel'},
        ],
        'refurbishing': [
            {'label': 'Refurbishing Tools', 'url': 'https://www.phonelcdparts.com/tools/refurbishing-tools'},
        ],
    },
    'gadgetfix': {
        'iphone': [
            {'label': 'iPhone', 'url': 'https://gadgetfix.com/category/iphone-1559.html'},
            {'label': 'Iphone 17e', 'url': 'https://gadgetfix.com/category/iphone-17e-2227.html'},
            {'label': 'Iphone 17 Pro Max', 'url': 'https://gadgetfix.com/category/iphone-17-pro-max-2209.html'},
            {'label': 'Iphone 17 Pro', 'url': 'https://gadgetfix.com/category/iphone-17-pro-2208.html'},
            {'label': 'Iphone Air', 'url': 'https://gadgetfix.com/category/iphone-air-2207.html'},
            {'label': 'Iphone 17', 'url': 'https://gadgetfix.com/category/iphone-17-2206.html'},
            {'label': 'Iphone 16e', 'url': 'https://gadgetfix.com/category/iphone-16e-2189.html'},
            {'label': 'Iphone 16 Pro Max', 'url': 'https://gadgetfix.com/category/iphone-16-pro-max-2152.html'},
            {'label': 'Iphone 16 Pro', 'url': 'https://gadgetfix.com/category/iphone-16-pro-2151.html'},
            {'label': 'Iphone 16 Plus', 'url': 'https://gadgetfix.com/category/iphone-16-plus-2150.html'},
            {'label': 'Iphone 16', 'url': 'https://gadgetfix.com/category/iphone-16-2149.html'},
            {'label': 'Iphone 15 Pro Max', 'url': 'https://gadgetfix.com/category/iphone-15-pro-max-2092.html'},
            {'label': 'Iphone 15 Pro', 'url': 'https://gadgetfix.com/category/iphone-15-pro-2091.html'},
            {'label': 'Iphone 15 Plus', 'url': 'https://gadgetfix.com/category/iphone-15-plus-2090.html'},
            {'label': 'Iphone 15', 'url': 'https://gadgetfix.com/category/iphone-15-2089.html'},
            {'label': 'Iphone 14 Pro Max', 'url': 'https://gadgetfix.com/category/iphone-14-pro-max-2051.html'},
            {'label': 'Iphone 14 Pro', 'url': 'https://gadgetfix.com/category/iphone-14-pro-2050.html'},
            {'label': 'Iphone 14 Plus', 'url': 'https://gadgetfix.com/category/iphone-14-plus-2049.html'},
            {'label': 'Iphone 14', 'url': 'https://gadgetfix.com/category/iphone-14-2048.html'},
            {'label': 'Iphone 13 Pro Max', 'url': 'https://gadgetfix.com/category/iphone-13-pro-max-1939.html'},
            {'label': 'Iphone 13 Pro', 'url': 'https://gadgetfix.com/category/iphone-13-pro-1938.html'},
            {'label': 'Iphone 13', 'url': 'https://gadgetfix.com/category/iphone-13-1937.html'},
            {'label': 'Iphone 13 Mini', 'url': 'https://gadgetfix.com/category/iphone-13-mini-1936.html'},
            {'label': 'Iphone 12 Pro Max', 'url': 'https://gadgetfix.com/category/iphone-12-pro-max-1859.html'},
            {'label': 'Iphone 12 Pro', 'url': 'https://gadgetfix.com/category/iphone-12-pro-1856.html'},
            {'label': 'Iphone 12', 'url': 'https://gadgetfix.com/category/iphone-12-1855.html'},
            {'label': 'Iphone 12 Mini', 'url': 'https://gadgetfix.com/category/iphone-12-mini-1858.html'},
            {'label': 'Iphone 11 Pro Max', 'url': 'https://gadgetfix.com/category/iphone-11-pro-max-1785.html'},
            {'label': 'Iphone 11 Pro', 'url': 'https://gadgetfix.com/category/iphone-11-pro-1784.html'},
            {'label': 'Iphone 11', 'url': 'https://gadgetfix.com/category/iphone-11-1778.html'},
            {'label': 'Iphone XS Max', 'url': 'https://gadgetfix.com/category/iphone-xs-max-1611.html'},
            {'label': 'Iphone XS', 'url': 'https://gadgetfix.com/category/iphone-xs-1706.html'},
            {'label': 'Iphone XR', 'url': 'https://gadgetfix.com/category/iphone-xr-1705.html'},
            {'label': 'Iphone X', 'url': 'https://gadgetfix.com/category/iphone-x-1652.html'},
            {'label': 'Iphone 8 Plus', 'url': 'https://gadgetfix.com/category/iphone-8-plus-1622.html'},
            {'label': 'Iphone 8', 'url': 'https://gadgetfix.com/category/iphone-8-1621.html'},
            {'label': 'Iphone 7 Plus', 'url': 'https://gadgetfix.com/category/iphone-7-plus-1595.html'},
            {'label': 'Iphone 7', 'url': 'https://gadgetfix.com/category/iphone-7-1594.html'},
            {'label': 'Iphone 6S Plus', 'url': 'https://gadgetfix.com/category/iphone-6s-plus-1541.html'},
            {'label': 'Iphone 6S', 'url': 'https://gadgetfix.com/category/iphone-6s-1540.html'},
            {'label': 'Iphone 6 Plus', 'url': 'https://gadgetfix.com/category/iphone-6-plus-1539.html'},
            {'label': 'Iphone 6', 'url': 'https://gadgetfix.com/category/iphone-6-1214.html'},
            {'label': 'Iphone SE 3rd Gen (2022)', 'url': 'https://gadgetfix.com/category/iphone-se-3rd-gen-2022-2047.html'},
            {'label': 'Iphone SE 2nd Gen (2020)', 'url': 'https://gadgetfix.com/category/iphone-se-2nd-gen-2020-1798.html'},
            {'label': 'Iphone SE 1st Gen (2016)', 'url': 'https://gadgetfix.com/category/iphone-se-1st-gen-2016-1580.html'},
            {'label': 'iPhone 5S', 'url': 'https://gadgetfix.com/category/iphone-5s-1277.html'},
            {'label': 'iPhone 5C', 'url': 'https://gadgetfix.com/category/iphone-5c-1278.html'},
            {'label': 'Iphone 5', 'url': 'https://gadgetfix.com/category/iphone-5-1189.html'},
            {'label': 'Iphone 4S', 'url': 'https://gadgetfix.com/category/iphone-4s-1184.html'},
        ],
    },
    'txparts': {
        'iphone': [
            {'label': 'iPhone 15', 'url': 'https://txparts.com/shop/iphone-15'},
        ],
    },
}


def _build_session(retries: int = 2, verify_ssl: bool = True) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=max(1, int(retries)),
        read=max(1, int(retries)),
        connect=max(1, int(retries)),
        backoff_factor=0.4,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(['GET', 'HEAD', 'OPTIONS']),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    session.verify = verify_ssl
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    })
    return session


def _normalize_text(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').strip().lower()).strip()


def _tokenize(value: str) -> set[str]:
    tokens = set()
    for token in _normalize_text(value).split():
        if not token:
            continue
        tokens.add(token)
        if len(token) > 4 and token.endswith('es'):
            tokens.add(token[:-2])
        elif len(token) > 3 and token.endswith('s'):
            tokens.add(token[:-1])
    return tokens


def _slug_to_label(value: str) -> str:
    cleaned = str(value or '').strip().strip('/')
    cleaned = cleaned[:-5] if cleaned.lower().endswith('.html') else cleaned
    cleaned = cleaned.split('/')[-1]
    cleaned = cleaned.replace('-', ' ').replace('_', ' ')
    return re.sub(r'\s+', ' ', cleaned).strip().title()


def _label_for_candidate(scraper_key: str, url: str, label: str) -> str:
    normalized_label = _normalize_text(label)
    if not label or normalized_label in GENERIC_DISCOVERY_LABELS:
        return _slug_to_label(urlparse(url).path)
    return label


def _clean_group_label(value: str) -> str:
    cleaned = re.sub(r'\s+', ' ', str(value or '').replace('NEW', '')).strip()
    return cleaned.strip(' /-')


def _gadgetfix_anchor_group_label(anchor) -> str:
    section = None
    for parent in anchor.parents:
        classes = set(parent.get('class', []) or [])
        if parent.name == 'div' and {'section', 'links'}.issubset(classes):
            section = parent
            break
    if section is None:
        return ''

    labels = []
    mega = section.find_parent('div', class_='mega-submenu')
    if mega:
        heading = mega.find('h2')
        if heading:
            labels.append(_clean_group_label(heading.get_text(' ', strip=True)))

    section_heading = section.find('h3')
    if section_heading:
        labels.append(_clean_group_label(section_heading.get_text(' ', strip=True)))

    labels = [label for label in labels if label]
    if not labels:
        return ''
    deduped = []
    for label in labels:
        if not deduped or _normalize_text(deduped[-1]) != _normalize_text(label):
            deduped.append(label)
    return ' / '.join(deduped)


def _canonical_url(url: str) -> str:
    parsed = urlparse(str(url or '').strip())
    path = parsed.path or '/'
    if path != '/' and path.endswith('/'):
        path = path.rstrip('/')
    return urlunparse((parsed.scheme, parsed.netloc, path, '', '', ''))


def _path_prefix(url: str) -> str:
    path = (urlparse(str(url or '')).path or '/').rstrip('/')
    if path.endswith('.html'):
        path = path[:-5]
    return path or '/'


def _path_depth(url: str) -> int:
    path = _path_prefix(url)
    return len([segment for segment in path.split('/') if segment])


def _url_for_path_prefix(source_url: str, path_prefix: str) -> str:
    parsed = urlparse(str(source_url or '').strip())
    path = str(path_prefix or '/').strip() or '/'
    if not path.startswith('/'):
        path = f'/{path}'
    return _canonical_url(urlunparse((parsed.scheme, parsed.netloc, path, '', '', '')))


def _query_prefix_from_url(url: str, query_tokens: set[str]) -> str:
    segments = [segment for segment in _path_prefix(url).split('/') if segment]
    if not segments or not query_tokens:
        return ''
    prefix_segments = []
    for segment in segments:
        prefix_segments.append(segment)
        segment_tokens = _tokenize(segment)
        if query_tokens & segment_tokens:
            return '/' + '/'.join(prefix_segments)
    return ''


def _same_domain(url: str, expected_host: str) -> bool:
    host = urlparse(url).netloc.lower().replace('www.', '')
    return bool(host) and (host == expected_host or host.endswith(f'.{expected_host}'))


def _fetch_html(url: str, *, retries: int = 2, verify_ssl: bool = True) -> str:
    if should_use_browser_fetch():
        return fetch_html_with_browser(url).html
    session = _build_session(retries=retries, verify_ssl=verify_ssl)
    response = session.get(url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    return response.text


def _is_candidate_link(scraper_key: str, url: str, host: str, label: str) -> bool:
    if not url or not _same_domain(url, host):
        return False

    lowered = url.lower()
    if lowered.startswith('mailto:') or lowered.startswith('tel:') or lowered.startswith('javascript:'):
        return False
    if any(fragment in lowered for fragment in EXCLUDED_SUBSTRINGS):
        return False

    path = (urlparse(url).path or '/').lower()
    rule = DISCOVERY_RULES.get(scraper_key, {})
    allowed_prefixes = tuple(rule.get('allowed_prefixes') or ())
    if allowed_prefixes and not any(path.startswith(prefix) for prefix in allowed_prefixes):
        return False

    if scraper_key == 'parts4cells' and path in {'', '/'}:
        return False
    if scraper_key == 'parts4cells' and any(token in path for token in ('/product/', '/catalog/', '/media/')):
        return False
    if scraper_key == 'phonelcdparts' and path in {'', '/'}:
        return False
    if scraper_key == 'phonelcdparts' and _path_depth(url) < 2:
        return False
    if scraper_key == 'phonelcdparts' and any(token in path for token in ('/checkout/', '/catalogsearch/', '/media/', '/static/')):
        return False
    if scraper_key == 'gadgetfix' and '/category/' not in path:
        return False
    if scraper_key == 'gadgetfix' and re.search(r'/category/\d+/.+/\d+/\d+\.html$', path):
        return False
    if scraper_key == 'txparts' and not label and _path_depth(url) > 3:
        return False
    return True


def _extract_candidate_links(scraper_key: str, page_url: str, html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, 'html.parser')
    host = urlparse(page_url).netloc.lower().replace('www.', '')
    anchors = []
    for selector in COMMON_NAV_SELECTORS:
        anchors.extend(soup.select(selector))
    if not anchors or scraper_key in {'phonelcdparts', 'gadgetfix'}:
        anchors = soup.select('a[href]')

    candidates: Dict[str, Dict[str, str]] = {}
    for anchor in anchors:
        href = str(anchor.get('href') or '').strip()
        if not href:
            continue
        absolute_url = _canonical_url(urljoin(page_url, href))
        label = re.sub(r'\s+', ' ', anchor.get_text(' ', strip=True) or '').strip()
        if not _is_candidate_link(scraper_key, absolute_url, host, label):
            continue
        label = _label_for_candidate(scraper_key, absolute_url, label)
        group_label = _gadgetfix_anchor_group_label(anchor) if scraper_key == 'gadgetfix' else ''
        existing = candidates.get(absolute_url)
        if existing and len(existing['label']) >= len(label) and (existing.get('group_label') or group_label):
            if group_label and not existing.get('group_label'):
                existing['group_label'] = group_label
            continue
        candidates[absolute_url] = {
            'label': label,
            'url': absolute_url,
            'group_label': group_label,
        }

    return list(candidates.values())


def _extract_sitemap_locs(xml_text: str) -> List[str]:
    return [
        re.sub(r'\s+', '', match.group(1)).strip()
        for match in re.finditer(r'<loc>\s*([^<]+?)\s*</loc>', str(xml_text or ''), re.I)
        if match.group(1).strip()
    ]


def _extract_sitemap_candidate_links(
    scraper_key: str,
    sitemap_url: str,
    *,
    retries: int,
    verify_ssl: bool,
    max_sitemaps: int = 3,
    max_urls: int = 1000,
) -> List[Dict[str, str]]:
    xml_text = _fetch_html(sitemap_url, retries=retries, verify_ssl=verify_ssl)
    locs = _extract_sitemap_locs(xml_text)
    if not locs:
        return []

    if any(loc.lower().endswith('.xml') for loc in locs[:10]):
        child_locs = []
        for child_sitemap in [loc for loc in locs if loc.lower().endswith('.xml')][:max_sitemaps]:
            try:
                child_xml = _fetch_html(child_sitemap, retries=retries, verify_ssl=verify_ssl)
            except Exception:
                continue
            child_locs.extend(_extract_sitemap_locs(child_xml))
            if len(child_locs) >= max_urls:
                break
        locs = child_locs[:max_urls]
    else:
        locs = locs[:max_urls]

    host = urlparse(sitemap_url).netloc.lower().replace('www.', '')
    candidates = []
    seen = set()
    for loc in locs:
        absolute_url = _canonical_url(loc)
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        label = _slug_to_label(urlparse(absolute_url).path)
        if not _is_candidate_link(scraper_key, absolute_url, host, label):
            continue
        candidates.append({
            'label': label,
            'url': absolute_url,
            'group_label': '',
        })
    return candidates


def _site_root(url: str) -> str:
    parsed = urlparse(str(url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    return urlunparse((parsed.scheme, parsed.netloc, '/', '', '', ''))


def _sitemap_url_for_root(root_url: str) -> str:
    root = _site_root(root_url)
    return urljoin(root, 'sitemap.xml') if root else ''


def _static_fallback_targets(scraper_key: str, query: str) -> List[Dict[str, str]]:
    query_tokens = _tokenize(query)
    fallback_groups = STATIC_DISCOVERY_FALLBACKS.get(scraper_key, {})
    targets = []
    for token, values in fallback_groups.items():
        if token in query_tokens or any(token in query_token or query_token in token for query_token in query_tokens):
            for value in values:
                targets.append({
                    'label': value['label'],
                    'url': value['url'],
                    'group_label': '',
                })
    return _dedupe_targets(targets)


def _rewrite_candidate_host(candidates: List[Dict[str, str]], target_root_url: str) -> List[Dict[str, str]]:
    target_root = _site_root(target_root_url)
    if not target_root:
        return candidates
    parsed_target = urlparse(target_root)
    rewritten = []
    for candidate in candidates:
        parsed = urlparse(candidate.get('url') or '')
        if not parsed.scheme or not parsed.netloc:
            rewritten.append(candidate)
            continue
        new_url = urlunparse((
            parsed_target.scheme,
            parsed_target.netloc,
            parsed.path,
            '',
            parsed.query,
            '',
        ))
        updated = dict(candidate)
        updated['url'] = _canonical_url(new_url)
        rewritten.append(updated)
    return rewritten


def _score_candidate(query: str, candidate: Dict[str, str]) -> int:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return 0
    label_text = _normalize_text(candidate.get('label'))
    group_text = _normalize_text(candidate.get('group_label'))
    path_text = _normalize_text(urlparse(candidate.get('url') or '').path)
    query_tokens = _tokenize(normalized_query)
    label_tokens = _tokenize(label_text)
    group_tokens = _tokenize(group_text)
    path_tokens = _tokenize(path_text)
    candidate_tokens = label_tokens | group_tokens | path_tokens
    overlap = len(query_tokens & candidate_tokens)
    score = overlap * 18
    if normalized_query and normalized_query in label_text:
        score += 90
    if normalized_query and normalized_query in group_text:
        score += 70
    if normalized_query and normalized_query in path_text:
        score += 80
    if query_tokens and query_tokens.issubset(path_tokens):
        score += 36
    if query_tokens and query_tokens.issubset(label_tokens):
        score += 28
    if query_tokens and query_tokens.issubset(group_tokens):
        score += 32
    if label_text.startswith(normalized_query):
        score += 12
    score -= _path_depth(candidate.get('url')) * 2
    return score


def _dedupe_targets(targets: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    deduped = []
    for target in targets:
        url = _canonical_url(target.get('url'))
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append({
            'label': str(target.get('label') or '').strip() or _slug_to_label(urlparse(url).path),
            'group_label': str(target.get('group_label') or '').strip(),
            'url': url,
        })
    return deduped


def _collect_root_and_targets(query: str, candidates: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    if not candidates:
        return [], []

    query_tokens = _tokenize(query)
    if not str(query or '').strip():
        ordered = sorted(candidates, key=lambda item: (_path_depth(item['url']), item['label'].lower()))
        return ordered[:12], ordered[:50]

    scored = []
    for candidate in candidates:
        score = _score_candidate(query, candidate)
        if score <= 0:
            continue
        scored.append((score, candidate))
    if not scored:
        return [], []

    scored.sort(key=lambda entry: (-entry[0], _path_depth(entry[1]['url']), entry[1]['label'].lower()))

    grouped_targets = []
    normalized_query = _normalize_text(query)
    for candidate in candidates:
        group_text = _normalize_text(candidate.get('group_label'))
        if not group_text:
            continue
        group_tokens = _tokenize(group_text)
        if normalized_query in group_text or (query_tokens and query_tokens.issubset(group_tokens)):
            grouped_targets.append(candidate)
    if len(grouped_targets) > 1:
        root_candidates = [
            candidate
            for _, candidate in scored
            if normalized_query in _normalize_text(candidate.get('label'))
            or normalized_query in _normalize_text(urlparse(candidate.get('url') or '').path)
        ]
        roots = _dedupe_targets(root_candidates[:6])
        if not roots:
            roots = [{
                'label': str(query or '').strip().title(),
                'group_label': '',
                'url': grouped_targets[0]['url'],
            }]
        return roots, _dedupe_targets(grouped_targets)

    synthetic_prefixes: Dict[str, List[Dict[str, str]]] = {}
    for _, candidate in scored:
        prefix = _query_prefix_from_url(candidate['url'], query_tokens)
        if not prefix:
            continue
        synthetic_prefixes.setdefault(prefix, []).append(candidate)

    if synthetic_prefixes:
        best_prefix, prefix_candidates = sorted(
            synthetic_prefixes.items(),
            key=lambda item: (-len(item[1]), item[0].count('/'), item[0])
        )[0]
        if len(prefix_candidates) > 1 and len(prefix_candidates) >= max(8, len(scored) // 5):
            prefix_targets = []
            for candidate in candidates:
                candidate_prefix = _path_prefix(candidate['url'])
                if candidate_prefix == best_prefix or candidate_prefix.startswith(f"{best_prefix}/"):
                    enriched = dict(candidate)
                    enriched['group_label'] = str(query or '').strip().title()
                    prefix_targets.append(enriched)
            if prefix_targets:
                root_source = prefix_candidates[0]
                synthetic_root = {
                    'label': str(query or '').strip().title(),
                    'group_label': '',
                    'url': _url_for_path_prefix(root_source['url'], best_prefix),
                }
                return [synthetic_root], _dedupe_targets(prefix_targets)

    max_score = scored[0][0]
    strong_roots = [
        candidate
        for score, candidate in scored
        if score >= max(18, max_score - 18)
    ]
    if not strong_roots:
        strong_roots = [scored[0][1]]

    min_depth = min(_path_depth(candidate['url']) for candidate in strong_roots)
    roots = [candidate for candidate in strong_roots if _path_depth(candidate['url']) == min_depth][:6]

    targets = []
    for candidate in candidates:
        candidate_prefix = _path_prefix(candidate['url'])
        matched_root = None
        for root in roots:
            root_prefix = _path_prefix(root['url'])
            if candidate_prefix == root_prefix or candidate_prefix.startswith(f"{root_prefix}/"):
                matched_root = root
                break
        if matched_root:
            enriched = dict(candidate)
            enriched['group_label'] = matched_root.get('label') or ''
            targets.append(enriched)

    if len(targets) <= len(roots):
        targets = [candidate for _, candidate in scored[:50]]

    return _dedupe_targets(roots), _dedupe_targets(targets)


def discover_category_targets(
    scraper_key: str,
    category_query: str,
    *,
    root_url: str = '',
    retries: int = 2,
    verify_ssl: bool = True,
    logger=None,
) -> Dict[str, object]:
    key = str(scraper_key or 'standard').strip().lower()
    if key not in DISCOVERY_RULES:
        key = 'standard'
    config = DISCOVERY_RULES[key]
    site_label = (SCRAPER_CONFIG.get(key) or SCRAPER_CONFIG['standard'])['label']
    discovery_url = str(root_url or config['home_url']).strip() or config['home_url']

    candidates = []
    try:
        html = _fetch_html(discovery_url, retries=retries, verify_ssl=verify_ssl)
        candidates = _extract_candidate_links(key, discovery_url, html)
    except Exception as exc:
        if logger:
            logger.warning(f"[automation] Failed to fetch discovery root {discovery_url}: {exc}")
    roots, targets = _collect_root_and_targets(category_query, candidates)

    if key in {'standard', 'mobilesentrix_canada', 'phonelcdparts'} and len(targets) <= len(roots):
        try:
            sitemap_url = (
                'https://www.phonelcdparts.com/sitemaps/sitemap.xml'
                if key == 'phonelcdparts'
                else _sitemap_url_for_root(discovery_url)
            )
            sitemap_candidates = _extract_sitemap_candidate_links(
                key,
                sitemap_url,
                retries=retries,
                verify_ssl=verify_ssl,
                max_sitemaps=5 if key in {'standard', 'mobilesentrix_canada'} else 3,
                max_urls=3000 if key in {'standard', 'mobilesentrix_canada'} else 1000,
            )
            if key == 'standard' and not sitemap_candidates and 'mobilesentrix.com' in discovery_url:
                ca_candidates = _extract_sitemap_candidate_links(
                    key,
                    'https://www.mobilesentrix.ca/sitemap.xml',
                    retries=retries,
                    verify_ssl=verify_ssl,
                    max_sitemaps=5,
                    max_urls=3000,
                )
                sitemap_candidates = _rewrite_candidate_host(ca_candidates, discovery_url)
            candidates.extend(sitemap_candidates)
            roots, targets = _collect_root_and_targets(category_query, candidates)
        except Exception as exc:
            if logger:
                logger.warning(f"[automation] Failed to load {site_label} sitemap: {exc}")

    fallback_targets = _static_fallback_targets(key, category_query)
    if key == 'phonelcdparts' and fallback_targets:
        expanded_candidates = []
        for root in fallback_targets[:3]:
            try:
                root_html = _fetch_html(root['url'], retries=retries, verify_ssl=verify_ssl)
                expanded_candidates.extend(_extract_candidate_links(key, root['url'], root_html))
            except Exception as exc:
                if logger:
                    logger.warning(f"[automation] Failed to expand {root['url']}: {exc}")
        expanded_candidates.extend(candidates)
        if len(expanded_candidates) > len(candidates):
            candidates = expanded_candidates
            roots, targets = _collect_root_and_targets(category_query, candidates)

    if roots and len(targets) <= len(roots):
        expanded_candidates = list(candidates)
        for root in roots[:4]:
            try:
                root_html = _fetch_html(root['url'], retries=retries, verify_ssl=verify_ssl)
                expanded_candidates.extend(_extract_candidate_links(key, root['url'], root_html))
            except Exception as exc:
                if logger:
                    logger.warning(f"[automation] Failed to expand {root['url']}: {exc}")
        roots, targets = _collect_root_and_targets(category_query, expanded_candidates)

    if not targets:
        if fallback_targets:
            roots = fallback_targets[:1]
            targets = fallback_targets
            candidates.extend(fallback_targets)

    if logger:
        logger.info(
            f"[automation] Discovery for {site_label} query '{category_query}' found "
            f"{len(targets)} target(s) from {len(candidates)} candidate link(s)"
        )

    return {
        'scraper_key': key,
        'site_label': site_label,
        'root_url': discovery_url,
        'query': str(category_query or '').strip(),
        'roots': roots,
        'targets': targets,
        'candidate_count': len(candidates),
    }
