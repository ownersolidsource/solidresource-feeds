#!/usr/bin/env python3
"""
Premarket RSS with multi-source fallback and hardened error handling.
"""
import argparse, sys, os, re, datetime as dt, xml.etree.ElementTree as ET, yaml
from urllib.parse import urlparse
from email.utils import format_datetime
from bs4 import BeautifulSoup
from utils import parse_money_like, parse_percent, clean_text, fetch

def _pick_table_with_headers(soup):
    best, mx = None, 0
    for t in soup.find_all('table'):
        ths = t.find_all('th')
        trs = t.find_all('tr')
        if ths and len(trs) > mx and len(trs) > 5:
            best, mx = t, len(trs)
    return best

def _normalize_row(ticker, raw_row, price_keys=('last','price'), chg_keys=('% change','change %','change'), vol_keys=('volume',)):
    def first_key(d, keys):
        for k in keys:
            if k and k in d and d[k]: return d[k]
        return None
    price = parse_money_like(first_key(raw_row, price_keys) or '')
    chg   = parse_percent(first_key(raw_row, chg_keys) or '')
    vol   = parse_money_like(first_key(raw_row, vol_keys) or '')
    return {'ticker': ticker, '_p': price or 0.0, '_c': chg or 0.0, '_v': vol or 0.0, 'raw': raw_row}

def parse_marketwatch(html):
    soup = BeautifulSoup(html, 'lxml')
    tbl = _pick_table_with_headers(soup)
    if not tbl: return []
    # header
    header = []
    for tr in tbl.find_all('tr'):
        ths = tr.find_all('th')
        if ths:
            header = [clean_text(th.get_text()) for th in ths]
            break
    rows = []
    for tr in tbl.find_all('tr'):
        tds = tr.find_all('td')
        if not tds: continue
        row = {}
        for i, td in enumerate(tds):
            key = header[i].lower() if i < len(header) else f'col{i}'
            row[key] = clean_text(td.get_text())
        sym = row.get('symbol') or row.get('ticker') or row.get('name') or ''
        ticker = sym.split(' ')[0].upper()
        if ticker and re.match(r'^[A-Z\.]{1,6}$', ticker):
            rows.append(_normalize_row(ticker, row))
    return rows

def parse_nasdaq(html):
    soup = BeautifulSoup(html, 'lxml')
    tbl = _pick_table_with_headers(soup)
    if not tbl:
        tb = soup.find('tbody')
        if tb and tb.find_all('tr'):
            tbl = tb.parent
    if not tbl: return []
    header = []
    for tr in tbl.find_all('tr'):
        ths = tr.find_all('th')
        if ths:
            header = [clean_text(th.get_text()) for th in ths]
            break
    rows = []
    for tr in tbl.find_all('tr'):
        tds = tr.find_all('td')
        if not tds: continue
        row = {}
        for i, td in enumerate(tds):
            key = header[i].lower() if i < len(header) else f'col{i}'
            row[key] = clean_text(td.get_text())
        sym = row.get('symbol') or row.get('ticker') or row.get('company') or ''
        ticker = sym.split(' ')[0].upper()
        if ticker and re.match(r'^[A-Z\.]{1,6}$', ticker):
            rows.append(_normalize_row(ticker, row))
    return rows

def parse_yahoo(html):
    soup = BeautifulSoup(html, 'lxml')
    tbl = _pick_table_with_headers(soup)
    rows = []
    if tbl:
        header = []
        for tr in tbl.find_all('tr'):
            ths = tr.find_all('th')
            if ths:
                header = [clean_text(th.get_text()) for th in ths]
                break
        for tr in tbl.find_all('tr'):
            tds = tr.find_all('td')
            if not tds: continue
            row = {}
            for i, td in enumerate(tds):
                key = header[i].lower() if i < len(header) else f'col{i}'
                row[key] = clean_text(td.get_text())
            sym = row.get('symbol') or row.get('ticker') or row.get('name') or ''
            ticker = sym.split(' ')[0].upper()
            if ticker and re.match(r'^[A-Z\.]{1,6}$', ticker):
                rows.append(_normalize_row(ticker, row))
    # fallback: data-symbol hints
    if not rows:
        for a in soup.select('[data-symbol]'):
            t = (a.get('data-symbol') or '').upper()
            if t and re.match(r'^[A-Z\.]{1,6}$', t):
                parent = a.find_parent('tr') or a.find_parent('li') or a.parent
                rowtxt = clean_text(parent.get_text()) if parent else ''
                rows.append({'ticker': t, '_p': 0.0, '_c': 0.0, '_v': 0.0, 'raw': {'raw': rowtxt}})
    return rows

def build_rss(items, title, link, description, max_items=120):
    rss = ET.Element('rss', version='2.0')
    ch = ET.SubElement(rss, 'channel')
    ET.SubElement(ch, 'title').text = title
    ET.SubElement(ch, 'link').text = link
    ET.SubElement(ch, 'description').text = description
    now = dt.datetime.utcnow()
    ET.SubElement(ch, 'lastBuildDate').text = format_datetime(now)
    ET.SubElement(ch, 'pubDate').text = format_datetime(now)
    items_sorted = sorted(items, key=lambda r: abs(r.get('_c', 0)), reverse=True)[:max_items]
    for r in items_sorted:
        t = r.get('ticker','').upper()
        title_txt = f"{t} {r.get('_c',0):.2f}% — ${r.get('_p',0):.2f} | Vol {int(r.get('_v',0)):,}"
        it = ET.SubElement(ch, 'item')
        ET.SubElement(it, 'title').text = title_txt
        ET.SubElement(it, 'link').text = link
        raw = r.get('raw', {})
        desc = "\n".join([f"{k.title()}: {v}" for k,v in raw.items() if v]) if isinstance(raw, dict) else str(raw)
        ET.SubElement(it, 'description').text = desc
        ET.SubElement(it, 'pubDate').text = format_datetime(now)
        guid = ET.SubElement(it, 'guid'); guid.set('isPermaLink','false'); guid.text = f"{t}-{now.strftime('%Y%m%d%H%M%S')}"
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding='unicode')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='config.yaml')
    ap.add_argument('--out', default='feeds/premarket_movers.xml')
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, 'r', encoding='utf-8'))
    ua = cfg.get('user_agent', 'Mozilla/5.0')
    timeout = int(cfg.get('timeout_sec', 20))

    prim = cfg.get('premarket_sources', [])
    backup = cfg.get('premarket_sources_backup', [])
    sources = prim + backup

    items = []
    for src in sources:
        url = src.get('url'); name = src.get('name','source')
        if not url:
            continue
        host = urlparse(url).netloc.lower()
        try:
            html = fetch(url, ua, timeout)
            if 'marketwatch' in host:
                rows = parse_marketwatch(html)
            elif 'nasdaq.com' in host:
                rows = parse_nasdaq(html)
            elif 'yahoo.com' in host:
                rows = parse_yahoo(html)
            else:
                rows = parse_marketwatch(html)

            print(f"[OK] {name}: {len(rows)} rows")
            if rows:
                items.extend(rows)
                # ✅ EARLY EXIT: we got data, no need to risk another request hanging
                break

        except Exception as e:
            print(f"[ERROR] {name}: {e}", file=sys.stderr)
            continue


    if not items:
        print("[WARN] No premarket items parsed from any source.", file=sys.stderr)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    feed_url = cfg.get('feeds',{}).get('premarket', cfg.get('site_url'))
    xml = build_rss(items, title="SolidResource — Pre-Market Movers", link=feed_url, description="Pre-market movers with multi-source fallback")
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(xml)
    print(f"[OK] wrote {args.out}")

if __name__ == "__main__":
    main()
