#!/usr/bin/env python3
"""
batch_feed.py — produce one RSS item containing a list of all tickers
"""
import feedparser, xml.etree.ElementTree as ET, datetime as dt
from email.utils import format_datetime
import argparse

def batch_summary(urls, out):
    all_tickers = []
    for u in urls:
        f = feedparser.parse(u)
        for e in f.entries:
            # Example format: "AAPL +2.1% — $180.32"
            t = e.get("title", "")
            if t:
                all_tickers.append(t)

    if not all_tickers:
        return

    rss = ET.Element("rss", version="2.0")
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = "SolidResource — Combined Movers (Batch)"
    ET.SubElement(ch, "link").text = "https://solidresource.com"
    ET.SubElement(ch, "description").text = "One combined list of all Finviz + Premarket movers"
    now = dt.datetime.utcnow()
    ET.SubElement(ch, "pubDate").text = format_datetime(now)

    # Join all tickers into one description block
    ET.SubElement(ch, "item")
    item = ET.SubElement(ch, "item")
    ET.SubElement(item, "title").text = f"Market Movers — {now.strftime('%Y-%m-%d %H:%M UTC')}"
    ET.SubElement(item, "description").text = "\n".join(all_tickers)
    ET.SubElement(item, "pubDate").text = format_datetime(now)
    ET.SubElement(item, "guid").text = f"solidresource-{now.strftime('%Y%m%d%H%M')}"

    with open(out, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(ET.tostring(rss, encoding="unicode"))

    print(f"[OK] wrote batch feed with {len(all_tickers)} tickers → {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="feeds/batch.xml")
    p.add_argument("urls", nargs="+")
    a = p.parse_args()
    batch_summary(a.urls, a.out)
