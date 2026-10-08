"""Build a static copy of the dashboard (for GitHub Pages).

Fetches quotes, news and price history once and writes them as JSON next to the page:
    site/index.html, site/data/{config,quotes,news}.json, site/data/history/<symbol>.json
Exits non-zero if quotes can't be fetched, so a failed run never replaces a good deployment.
"""
import json
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import bursa
import server
from config import COMMODITIES, INDICES, STOCKS

ROOT = Path(__file__).parent
OUT = ROOT / "site"


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":")))


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    data = OUT / "data"
    now = time.time()

    write(data / "config.json", {"stocks": STOCKS, "indices": INDICES, "commodities": COMMODITIES})

    quotes = server.fetch_quotes()
    if len(quotes) < len(STOCKS):
        sys.exit(f"quotes incomplete: got {len(quotes)} symbols")
    write(data / "quotes.json", {"updated": now, "quotes": quotes})
    print(f"quotes: {len(quotes)} symbols")

    news = server.fetch_news()
    write(data / "news.json", {"updated": now, **news})
    print(f"news: {len(news['items'])} items, {len(news['errors'])} errors")

    try:
        b = bursa.fetch_all(STOCKS, max_details=60)
        write(data / "bursa.json", {"updated": now, **b})
    except Exception as e:  # announcements are optional: keep building without them
        print("bursa failed:", e)
        write(data / "bursa.json", {"updated": 0, "items": [], "errors": [str(e)], "pending_details": 0})

    syms = [x["symbol"] for x in STOCKS + INDICES + COMMODITIES]

    def hist(sym):
        for attempt in range(4):
            try:
                return sym, server.get_history(sym)
            except Exception as e:  # e.g. 429 rate limit: back off and retry
                err = e
                time.sleep(5 * (attempt + 1))
        return sym, err

    failed = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for sym, res in ex.map(hist, syms):
            if isinstance(res, Exception):
                failed.append(f"{sym}: {res}")
                continue
            write(data / "history" / (re.sub(r"[^A-Za-z0-9]", "_", sym) + ".json"), {"symbol": sym, "bars": res})
    print(f"history: {len(syms) - len(failed)}/{len(syms)} symbols", *failed, sep="\n  ")
    if len(failed) == len(syms):
        sys.exit("all history requests failed")

    page = (ROOT / "static" / "index.html").read_text()
    page = page.replace("<script>\n// Data endpoints", "<script>window.MHM_STATIC = true;</script>\n<script>\n// Data endpoints", 1)
    assert "MHM_STATIC = true" in page, "static flag injection failed"
    (OUT / "index.html").write_text(page)
    (OUT / ".nojekyll").write_text("")
    print("built", OUT)


if __name__ == "__main__":
    main()
