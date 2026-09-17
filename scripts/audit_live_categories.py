"""Reproducible, resumable live category audit. Does not write application histories."""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math, os, random, re, sys, threading, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin, urlparse
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['DATABASES_DIR'] = str(ROOT / '.tmp' / 'category-audit-dbs')
os.environ['AUTOMATION_SCHEDULER_DISABLED'] = '1'
os.environ['SCRAPER_LOCAL_BROWSER_MAX_WINDOWS'] = '1'
os.environ.setdefault('SCRAPER_LOCAL_BROWSER_CHALLENGE_WAIT_SECONDS', '5')
os.environ.setdefault('SCRAPER_LOCAL_BROWSER_WAIT_SECONDS', '0.3')
from bs4 import BeautifulSoup
from app import enrich_scraped_items
from scripts.test_live_all_scrapers import ENGINE_MODULES
from scrapers import detect_scraper_key
from scrapers.browser_fetcher import browser_fetch_mode, fetch_html, _looks_like_browser_challenge
SITES = ['mobilesentrix','mobilesentrix_canada','xcellparts','txparts','txparts_canada','parts4cells','phonelcdparts','gadgetfix']
RULES = {'add_percent':0,'percent_off':0,'absolute_off':0}
LOCK = threading.Lock()

def norm(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower()).strip()

def select_targets(count):
    selected=[]
    for site in SITES:
        rows=list(csv.DictReader((ROOT/'output'/site/'categories.csv').open(encoding='utf-8-sig')))
        unique={}
        for row in rows:
            url=(row.get('normalized_url') or row.get('child_url') or '').strip().rstrip('/')
            if not url.startswith('https://') or '#' in url or '/product/' in url: continue
            unique.setdefault(url, {'site':site,'url':url,'label':row.get('child_name') or row.get('sub_child_name') or row.get('parent_name'), 'engine':detect_scraper_key(url)})
        urls=sorted(unique)
        leaves=[u for u in urls if not any(v.startswith(u+'/') for v in urls if v != u)]
        # Deterministic, broad model coverage; reserve 20 slots for common Apple/Samsung categories.
        rng=random.Random(20260917)
        common=[u for u in leaves if re.search(r'iphone-(?:1[1-6])(?:/|$|-)|galaxy-s2[0-5](?:/|$|-)|ipad',u)]
        rng.shuffle(common)
        chosen=common[:min(20,count)]
        rest=[u for u in leaves if u not in chosen];rng.shuffle(rest)
        chosen += rest[:count-len(chosen)]
        if len(chosen)<count: raise RuntimeError(f'{site}: only {len(chosen)} category URLs')
        selected += [unique[u] for u in chosen]
    return selected

def independent_fetch(session,url):
    response=session.get(url,timeout=25,allow_redirects=True)
    html=response.text or ''
    if response.status_code != 200 or _looks_like_browser_challenge(html):
        result=fetch_html(url,timeout=35)
        return result.html,result.final_url,'browser'
    return html,str(response.url),'http'

def save_html(out,key,kind,html):
    path=out/'evidence'/f'{key}-{kind}.html.gz';path.parent.mkdir(exist_ok=True)
    with gzip.open(path,'wt',encoding='utf-8') as handle: handle.write(html)
    return str(path.relative_to(out))

def product_evidence(html,url,item):
    soup=BeautifulSoup(html,'lxml')
    h1=soup.find('h1')
    title=h1.get_text(' ',strip=True) if h1 else ''
    products=[]
    def walk(obj):
        if isinstance(obj,list):
            for val in obj: walk(val)
        elif isinstance(obj,dict):
            typ=obj.get('@type',[]);typ=[typ] if isinstance(typ,str) else typ
            if 'Product' in typ: products.append(obj)
            if '@graph' in obj: walk(obj['@graph'])
    for script in soup.select('script[type="application/ld+json"]'):
        try: walk(json.loads(script.string or script.get_text()))
        except (ValueError,TypeError): pass
    matching=[p for p in products if str(p.get('url','')).rstrip('/')==url.rstrip('/')]
    product=(matching or (products if len(products)==1 else []) or [{}])[0]
    title=title or str(product.get('name') or '')
    source_skus=[str(product.get('sku') or '')]
    for node in soup.select('[itemprop="sku"], .sku .value, .sku_wrapper .sku, .product-detail-right .badge-sku span:last-child, dt, th, .product-detail-label'):
        if node.name in ('dt','th') or 'product-detail-label' in node.get('class',[]):
            if norm(node.get_text()) not in ('sku','product code','item number','part number'): continue
            node=node.find_next_sibling()
            if node is None: continue
        source_skus.append(node.get('content') or node.get_text(' ',strip=True))
    sku=str(item.get('sku') or (item.get('extra') or {}).get('sku') or '')
    # Text presence is separately labeled; structured SKU agreement is stronger evidence.
    sku_structured=bool(sku and any(norm(sku)==norm(v) for v in source_skus if v))
    sku_present=bool(sku and sku.lower() in html.lower())
    prices=[]
    offers=product.get('offers',[]);offers=[offers] if isinstance(offers,dict) else offers
    for offer in offers:
        if isinstance(offer,dict) and offer.get('price') is not None:
            try: prices.append(float(offer['price']))
            except (ValueError,TypeError): pass
    for node in soup.select('meta[itemprop="price"], .product-info-main [data-price-amount], .summary .price ins .amount, .summary .price > .amount, #product-price, .product-detail-right .price-box, [itemprop="price"]'):
        raw=node.get('content') or node.get('data-price-amount') or node.get('data-qtybasedgroupprice') or node.get_text(' ',strip=True)
        match=re.search(r'\d[\d,]*(?:\.\d+)?',raw)
        if match:
            try: prices.append(float(match[0].replace(',','')))
            except ValueError: pass
    actual=item.get('price_value',item.get('original'))
    price_match=any(abs(float(actual)-p)<0.011 for p in prices) if actual is not None and prices else None
    title_match=bool(title and (norm(title)==norm(item.get('title')) or SequenceMatcher(None,norm(title),norm(item.get('title'))).ratio()>=0.9))
    return {'live_title':title,'title_matches':title_match,'sku':sku,'sku_matches_structured':sku_structured,'sku_present_in_html':sku_present,'live_skus':[x for x in source_skus if x], 'scraped_price':actual,'live_prices':sorted(set(prices)),'price_matches':price_match,'price_unavailable':not prices}

def audit(task,out,max_pages):
    started=time.monotonic();result={**task,'started_at':datetime.now(timezone.utc).isoformat()}
    key=hashlib.sha256(task['url'].encode()).hexdigest()[:16]; result['key']=key
    module=ENGINE_MODULES[task['engine']];session,_=module.build_session(retries=1,verify_ssl=True,use_curl=True)
    try:
        items=[];attempts=[]
        for browser in (False,True):
            try:
                with browser_fetch_mode(browser):
                    items=module.scrape_url(session,task['url'],RULES,True,max_pages,100,None)
                errors=[getattr(session,f'{prefix}_last_error','') for prefix in ['mobilesentrix','xcell','txparts','parts4cells','phonelcdparts','gadgetfix']]
                errors=[x for x in errors if x]
                errors += [getattr(i,'price_text','error row') for i in items if getattr(i,'source','')=='error']
                attempts.append({'browser_requested':browser,'items':len(items),'errors':errors})
                if items and not errors: break
            except Exception as exc: attempts.append({'browser_requested':browser,'error':str(exc)})
        result['attempts']=attempts
        snapshots=[asdict(i) for i in items if getattr(i,'title','') and getattr(i,'url','') and getattr(i,'source','')!='error']
        result['item_count']=len(snapshots)
        result['duplicate_urls']=len(snapshots)-len({x['url'] for x in snapshots})
        result['invalid_rows']=[i for i,x in enumerate(snapshots) if not x['url'].startswith('https://') or (x.get('price_value',x.get('original')) is not None and (not math.isfinite(float(x.get('price_value',x.get('original')))) or float(x.get('price_value',x.get('original')))<0))]
        (out/'items').mkdir(exist_ok=True)
        (out/'items'/f'{key}.json').write_text(json.dumps(snapshots,ensure_ascii=False),encoding='utf-8')
        html,final,transport=independent_fetch(session,task['url'])
        result['category_evidence']=save_html(out,key,'category',html)
        result['category_final_url']=final
        soup=BeautifulSoup(html,'lxml'); text=soup.get_text(' ',strip=True).lower()
        result['category_title']=soup.title.get_text(' ',strip=True) if soup.title else ''
        result['live_empty_message']=bool(re.search(r'we can.t find products|no products (?:were found|found|available|matching)|there are no products|no items found',text))
        if not snapshots:
            result['status']='VERIFIED_EMPTY' if result['live_empty_message'] else 'FAIL_NO_PRODUCTS'
        else:
            candidate=next(i for i in items if getattr(i,'title','') and getattr(i,'url','') and getattr(i,'source','')!='error')
            listing=asdict(candidate)
            enriched,_=enrich_scraped_items([candidate],RULES,retries=1,verify_ssl=True,use_curl=True,enrich_details=True,use_browser=False)
            sample=asdict(enriched[0]);result['sample']=sample
            detail,detail_url,detail_transport=independent_fetch(session,sample['url'])
            result['product_evidence']=save_html(out,key,'product',detail)
            result['verification']=product_evidence(detail,detail_url,sample)
            links={urljoin(final,a['href']).split('#')[0].rstrip('/') for a in soup.select('a[href]')}
            result['sample_on_live_category']=listing['url'].split('#')[0].rstrip('/') in links
            check=result['verification']
            ok=(check['title_matches'] and check['sku_present_in_html'] and check['price_matches'] is not False and result['sample_on_live_category'] and not result['duplicate_urls'] and not result['invalid_rows'])
            result['status']='VERIFIED' if ok and check['price_matches'] else ('VERIFIED_PRICE_UNAVAILABLE' if ok else 'FAIL_VERIFICATION')
            last=attempts[-1]
            if last.get('errors') or last.get('error'): result['status']='FAIL_INCOMPLETE'
    except Exception as exc:
        result['status']='FAIL_EXCEPTION';result['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if callable(getattr(session,'close',None)): session.close()
    result['seconds']=round(time.monotonic()-started,2)
    with LOCK:
        with (out/'results.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(result,ensure_ascii=False)+'\n')
        print(f"{task['site']} {result['status']} items={result.get('item_count',0)} {result['seconds']}s {task['url']}",flush=True)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--count',type=int,default=50);parser.add_argument('--workers',type=int,default=4);parser.add_argument('--max-pages',type=int,default=100);parser.add_argument('--out',default='output/live-audit-20260917');parser.add_argument('--retry-failed',action='store_true');args=parser.parse_args()
    out=ROOT/args.out;out.mkdir(parents=True,exist_ok=True)
    manifest=out/'manifest.json'
    if manifest.exists(): tasks=json.loads(manifest.read_text(encoding='utf-8'))
    else:
        tasks=select_targets(args.count);manifest.write_text(json.dumps(tasks,indent=2),encoding='utf-8')
    existing={}
    if (out/'results.jsonl').exists():
        for line in (out/'results.jsonl').read_text(encoding='utf-8').splitlines():
            row=json.loads(line);existing[row['url']]=row
    pending=[t for t in tasks if t['url'] not in existing or (args.retry_failed and existing[t['url']]['status'].startswith('FAIL'))]
    def site_worker(site):
        for task in pending:
            if task['site']==site: audit(task,out,args.max_pages)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(site_worker,site) for site in SITES]): future.result()
    latest={}
    for line in (out/'results.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line);latest[row['url']]=row
    summary={site:dict(Counter(r['status'] for r in latest.values() if r['site']==site)) for site in SITES}
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
    return int(any(r['status'].startswith('FAIL') for r in latest.values()))
if __name__=='__main__':raise SystemExit(main())
