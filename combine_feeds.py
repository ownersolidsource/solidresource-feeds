#!/usr/bin/env python3
import argparse, datetime as dt, xml.etree.ElementTree as ET, feedparser
from email.utils import format_datetime

def combine(out_path, feed_urls, title="SolidResource — Combined Feed", link="https://solidresource.com", description="Merged feed"):
    entries = []
    for url in feed_urls:
        fp = feedparser.parse(url)
        entries.extend(fp.entries)
    # sort newest first
    entries.sort(key=lambda e: getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None) or dt.datetime.utcnow().timetuple(), reverse=True)
    rss = ET.Element('rss', version='2.0')
    ch = ET.SubElement(rss, 'channel')
    ET.SubElement(ch, 'title').text = title
    ET.SubElement(ch, 'link').text = link
    ET.SubElement(ch, 'description').text = description
    now = dt.datetime.utcnow()
    ET.SubElement(ch, 'lastBuildDate').text = format_datetime(now)
    ET.SubElement(ch, 'pubDate').text = format_datetime(now)
    for e in entries[:200]:
        it = ET.SubElement(ch, 'item')
        ET.SubElement(it, 'title').text = getattr(e, 'title', 'Untitled')
        ET.SubElement(it, 'link').text = getattr(e, 'link', link)
        ET.SubElement(it, 'description').text = getattr(e, 'summary', '')
        pub = getattr(e, 'published_parsed', None) or getattr(e, 'updated_parsed', None)
        if pub:
            ET.SubElement(it, 'pubDate').text = format_datetime(dt.datetime(*pub[:6]))
    xml = ET.tostring(rss, encoding='utf-8')
    with open(out_path, 'wb') as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml)
    print(f"[OK] Wrote combined feed to {out_path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='feeds/all.xml')
    ap.add_argument('urls', nargs='+')
    args = ap.parse_args()
    combine(args.out, args.urls)

if __name__ == "__main__":
    main()
