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
    if scraper_key == 'txparts' and not label and _path_depth(url) > 3:
        return False
    return True


def _extract_candidate_links(scraper_key: str, page_url: str, html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, 'html.parser')
    host = urlparse(page_url).netloc.lower().replace('www.', '')
    anchors = []
    for selector in COMMON_NAV_SELECTORS:
        anchors.extend(soup.select(selector))
    if not anchors:
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
        if not label:
            label = _slug_to_label(urlparse(absolute_url).path)
        existing = candidates.get(absolute_url)
        if existing and len(existing['label']) >= len(label):
            continue
        candidates[absolute_url] = {
            'label': label,
            'url': absolute_url,
            'group_label': '',
        }

    return list(candidates.values())


def _score_candidate(query: str, candidate: Dict[str, str]) -> int:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return 0
    label_text = _normalize_text(candidate.get('label'))
    path_text = _normalize_text(urlparse(candidate.get('url') or '').path)
    query_tokens = _tokenize(normalized_query)
    label_tokens = _tokenize(label_text)
    path_tokens = _tokenize(path_text)
    candidate_tokens = label_tokens | path_tokens
    overlap = len(query_tokens & candidate_tokens)
    score = overlap * 18
    if normalized_query and normalized_query in label_text:
        score += 90
    if normalized_query and normalized_query in path_text:
        score += 80
    if query_tokens and query_tokens.issubset(path_tokens):
        score += 36
    if query_tokens and query_tokens.issubset(label_tokens):
        score += 28
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
        if len(prefix_candidates) > 1:
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
                    'url': root_source['url'],
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

    root_prefixes = {_path_prefix(root['url']) for root in roots}
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

    html = _fetch_html(discovery_url, retries=retries, verify_ssl=verify_ssl)
    candidates = _extract_candidate_links(key, discovery_url, html)
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
