#!/usr/bin/env python3
"""
Generate RSS from one or more Finviz screeners.
"""
import argparse, datetime as dt, xml.etree.ElementTree as ET, yaml, re, sys
from email.utils import format_datetime
from bs4 import BeautifulSoup
from utils import parse_money_like, parse_percent, clean_text, fetch

def choose_table(soup):
    tables = soup.find_all('table')
    best, mx = None, 0
    for t in tables:
        trs = t.find_all('tr')
        if len(trs) > mx and len(trs) > 5:
            best, mx = t, len(trs)
    return best

def table_rows(table):
    # header
    header = []
    for tr in table.find_all('tr'):
        ths = tr.find_all('th')
        if ths:
            header = [clean_text(th.get_text()) for th in ths]
            header_row = tr
            break
    rows = []
    for tr in table.find_all('tr'):
        tds = tr.find_all('td')
        if not tds: continue
        row = {}
        for i, td in enumerate(tds):
            key = header[i].lower() if i < len(header) else f'col{i}'
            row[key] = clean_text(td.get_text())
            if key in ('ticker','symbol','sym') and not row.get('link'):
                a = td.find('a', href=True)
                if a: row['link'] = a['href']
        if not row.get('ticker'):
            for v in list(row.values())[:3]:
                if re.match(r'^[A-Z\.]{1,6}$', v or ''):
                    row['ticker'] = v; break
        rows.append(row)
    return rows

def apply_filters(rows, fcfg):
    out = []
    for r in rows:
        t = r.get('ticker','').upper()
        if fcfg.get('require_ticker') and not t: continue
        p = parse_money_like(r.get('price') or r.get('last'))
        c = parse_percent(r.get('change') or r.get('chg'))
        v = parse_money_like(r.get('volume'))
        m = parse_money_like(r.get('market cap') or r.get('marketcap'))
        if p is not None and p < float(fcfg.get('min_price',0)): continue
        if c is not None and abs(c) < float(fcfg.get('min_change_pct_abs',0)): continue
        if v is not None and v < float(fcfg.get('min_volume',0)): continue
        if m is not None and m < float(fcfg.get('min_market_cap_usd',0)): continue
        r['_p']=p or 0; r['_c']=c or 0; r['_v']=v or 0; r['_m']=m or 0
        out.append(r)
    return out

def build_rss(items, title, link, description, max_items=150):
    rss = ET.Element('rss', version='2.0')
    ch = ET.SubElement(rss, 'channel')
    ET.SubElement(ch, 'title').text = title
    ET.SubElement(ch, 'link').text = link
    ET.SubElement(ch, 'description').text = description
    now = dt.datetime.utcnow()
    ET.SubElement(ch, 'lastBuildDate').text = format_datetime(now)
    ET.SubElement(ch, 'pubDate').text = format_datetime(now)
    for r in sorted(items, key=lambda x: abs(x.get('_c',0)), reverse=True)[:max_items]:
        t = r.get('ticker','').upper()
        title_txt = f"{t} {r.get('_c',0):.2f}% — ${r.get('_p',0):.2f} | Vol {int(r.get('_v',0)):,} | MCap {int(r.get('_m',0)):,}"
        item = ET.SubElement(ch, 'item')
        ET.SubElement(item, 'title').text = title_txt
        ET.SubElement(item, 'link').text = r.get('link') or (f"https://finviz.com/quote.ashx?t={t}" if t else link)
        desc = []
        for k,v in r.items():
            if k.startswith('_') or k in ('ticker','link'): continue
            if v: desc.append(f"{k.title()}: {v}")
        ET.SubElement(item, 'description').text = "\n".join(desc) if desc else "Finviz screener result"
        ET.SubElement(item, 'pubDate').text = format_datetime(now)
        guid = ET.SubElement(item, 'guid'); guid.set('isPermaLink','false'); guid.text = f"{t}-{now.strftime('%Y%m%d%H%M%S')}"
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding='unicode')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='config.yaml')
    ap.add_argument('--out', default='feeds/finviz_movers.xml')
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, 'r', encoding='utf-8'))
    ua = cfg.get('user_agent','Mozilla/5.0')
    timeout = int(cfg.get('timeout_sec',20))
    items = []
    for src in cfg.get('finviz_sources', []):
        try:
            html = fetch(src['url'], ua, timeout)
            soup = BeautifulSoup(html, 'lxml')
            tbl = choose_table(soup)
            if not tbl: 
                print(f"[WARN] no table for {src['name']}", file=sys.stderr); 
                continue
            rows = table_rows(tbl)
            items.extend(rows)
            print(f"[OK] {src['name']}: {len(rows)} rows")
        except Exception as e:
            print(f"[ERROR] {src['name']}: {e}", file=sys.stderr)
    filtered = apply_filters(items, cfg.get('filters', {}))
    print(f"[OK] after filters: {len(filtered)} items")
    feed_url = cfg.get('feeds',{}).get('finviz_intraday', cfg.get('site_url'))
    xml = build_rss(filtered, title="SolidResource — Intraday Movers (Finviz)", link=feed_url, description="High-momentum stocks from Finviz", max_items=int(cfg.get('max_items',150)))
    open(args.out,'w',encoding='utf-8').write(xml)
    print(f"[OK] wrote {args.out}")

if __name__ == "__main__":
    main()
