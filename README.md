# SolidResource Feeds (Finviz + Premarket) → RSS

Production-ready scripts to generate **clean, filterable RSS feeds** for your automation stack.

## Feeds
- `finviz_rss.py` → `feeds/finviz_movers.xml` (intraday movers)
- `premarket_rss.py` → `feeds/premarket_movers.xml` (pre-market movers, best-effort)
- `combine_feeds.py` → `feeds/all.xml` (merge any feeds you host)

## Quick Start
```bash
pip install -r requirements.txt
python finviz_rss.py --config config.yaml --out feeds/finviz_movers.xml
python premarket_rss.py --config config.yaml --out feeds/premarket_movers.xml
```

Edit `config.yaml` to add your screener links and tune filters.

## Automate (GitHub Actions)
`.github/workflows/update_feeds.yml` runs every 30 min:
- builds both feeds
- commits updated XML
- ready for GitHub Pages/Netlify hosting

## Notes
- Respect site terms/robots.txt; this is for editorial workflows.
- Premarket HTML changes periodically; keep `premarket_rss.py` as "best effort" and adjust selectors if needed.
- Use your own **User-Agent** in `config.yaml` to avoid being blocked.
