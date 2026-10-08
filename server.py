"""Malaysia Healthcare Dashboard - local server.

Prices: TradingView scanner (delayed ~15 min for Bursa) + TradingView chart widgets in the browser.
News:   TradingView per-symbol wire headlines (Reuters / Dow Jones summaries of Bursa filings)
        + Google News RSS (The Edge, The Star, NST, Bernama, etc.) per company and per sector theme.

Run:  .venv/bin/python server.py   ->  http://localhost:8050
"""
import html
import re
import threading
import time
import urllib.parse
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

warnings.filterwarnings("ignore")

import feedparser
import requests
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse

from config import API_QUERIES, COMMODITIES, INDICES, SECTOR_QUERIES, STOCKS, TAGS
import tvhist

ROOT = Path(__file__).parent
PORT = 8050
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
TV_HEADERS = {**UA, "Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"}

QUOTE_TTL = 60          # seconds
NEWS_TTL = 15 * 60      # seconds
NEWS_MAX_AGE_DAYS = 120       # press / sector headlines
WIRE_MAX_AGE_DAYS = 730       # filing summaries: keep longer so chart markers cover 2Y

QUOTE_COLS = ["description", "close", "change", "change_abs", "Perf.W", "Perf.1M", "Perf.3M",
              "Perf.6M", "Perf.YTD", "Perf.Y", "price_52_week_high", "price_52_week_low",
              "market_cap_basic", "price_earnings_ttm", "dividends_yield_current", "volume",
              "relative_volume_10d_calc", "earnings_release_next_date", "currency", "update_mode",
              "total_shares_outstanding"]
QUOTE_KEYS = ["description", "close", "chg", "chg_abs", "w1", "m1", "m3", "m6", "ytd", "y1",
              "hi52", "lo52", "mcap", "pe", "dy", "volume", "rvol", "next_earnings", "currency",
              "update_mode", "shares"]

_cache = {"quotes": (0, None), "news": (0, None)}
_lock = threading.Lock()
_news_refreshing = threading.Event()


# ---------------------------------------------------------------- quotes
SYNTH = {x["symbol"]: x["synthetic"] for x in COMMODITIES if x.get("synthetic")}
PCT_KEYS = ["chg", "w1", "m1", "m3", "m6", "ytd", "y1"]


def _synth_quote(n, d):
    """Quote for num/den cross. Percent changes combine as (1+a)/(1+b)-1."""
    if not n.get("close") or not d.get("close"):
        return {}
    q = {"close": n["close"] / d["close"], "currency": "MYR", "update_mode": n.get("update_mode")}
    for k in PCT_KEYS:
        a, b = n.get(k), d.get(k)
        q[k] = ((1 + a / 100) / (1 + b / 100) - 1) * 100 if a is not None and b is not None else None
    return q


def fetch_quotes():
    tickers = [x["symbol"] for x in STOCKS + INDICES + COMMODITIES if x["symbol"] not in SYNTH]
    tickers += sorted({v for sy in SYNTH.values() for v in sy.values()} - set(tickers))
    r = requests.post("https://scanner.tradingview.com/global/scan",
                      json={"symbols": {"tickers": tickers}, "columns": QUOTE_COLS},
                      headers=TV_HEADERS, timeout=20)
    r.raise_for_status()
    out = {}
    for row in r.json().get("data", []):
        q = dict(zip(QUOTE_KEYS, row["d"]))
        # global scanner reports market_cap_basic in USD; rebuild it in local currency (MYR)
        if q.get("shares") and q.get("close"):
            q["mcap"] = q["close"] * q["shares"]
        out[row["s"]] = q
    for sym, sy in SYNTH.items():
        out[sym] = _synth_quote(out.get(sy["num"], {}), out.get(sy["den"], {}))
    return out


def get_quotes():
    ts, data = _cache["quotes"]
    if data is None or time.time() - ts > QUOTE_TTL:
        try:
            data = fetch_quotes()
            _cache["quotes"] = (time.time(), data)
            ts = time.time()
        except Exception as e:  # serve stale on failure
            if data is None:
                raise
            print("quote refresh failed:", e)
    return ts, data


# ---------------------------------------------------------------- news
_tag_res = [(t, re.compile(p, re.I)) for t, p in TAGS]
_alias_res = [(s["symbol"], re.compile(r"\b(" + "|".join(re.escape(a) for a in s["aliases"]) + r")\b", re.I))
              for s in STOCKS]


_my_rx = re.compile(r"\b(Malaysia\w*|Bursa|ringgit|RM\d|MOH|KKM|Dzulkefly|Budget 2027|Sabah|Sarawak|Penang|Johor|Selangor|Kuala Lumpur)\b", re.I)
_my_sources = re.compile(r"(The Star|NST|New Straits|Bernama|The Edge|Malay Mail|Free Malaysia|CodeBlue|BusinessToday|"
                         r"Sinar|The Sun|Malaysiakini|Malaysian Reserve|Astro Awani|Business Times|theedgemalaysia|"
                         r"Focus Malaysia|Vulcan Post|Daily Express|Borneo Post|The Vibes|Dayak Daily)", re.I)


_pharma_rx = re.compile(r"\b(pharma\w*|drugs?|medicines?|ingredients?|heparin|generics?|antibiotics?|paracetamol|"
                        r"penicillin|vitamin|KSM|raw materials?|shortage|biosimilar|insulin|API makers?|bulk drug)\b", re.I)


_noise_rx = re.compile(r"(IndexBox|Samco|siam\.in|AD HOC NEWS|Stocks? To Buy|Market To 20\d\d|Market Outlook)", re.I)


def norm_title(t):
    t = re.sub(r"^\[[^\]]*\]\s*", "", t)  # drop "[UPDATED]" style prefixes
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()[:90]


def enrich(item, forced_symbol=None):
    text = item["title"]
    syms = {sym for sym, rx in _alias_res if rx.search(text)}
    if forced_symbol:
        syms.add(forced_symbol)
    item["symbols"] = sorted(syms)
    item["tags"] = [t for t, rx in _tag_res if rx.search(text)]
    return item


def tv_headlines(symbol):
    url = "https://news-headlines.tradingview.com/v2/headlines?" + urllib.parse.urlencode(
        {"client": "web", "lang": "en", "symbol": symbol})
    r = requests.get(url, headers=TV_HEADERS, timeout=15)
    r.raise_for_status()
    items = r.json().get("items", [])
    out = []
    for x in items:
        link = x.get("link") or ("https://www.tradingview.com" + x["storyPath"] if x.get("storyPath") else None)
        prov = {"reuters": "Reuters", "dow-jones": "Dow Jones"}.get(x.get("provider"), x.get("provider", "TradingView"))
        out.append(enrich({"title": x["title"], "url": link, "source": prov, "ts": int(x["published"]),
                           "feed": "wire"}, forced_symbol=symbol))
    return out


def google_news(query, forced_symbol=None, kind="press"):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query + " when:90d", "hl": "en-MY", "gl": "MY", "ceid": "MY:en"})
    r = requests.get(url, headers=UA, timeout=15)
    r.raise_for_status()
    f = feedparser.parse(r.content)
    out = []
    for e in f.entries:
        title = html.unescape(e.title)
        source = e.get("source", {}).get("title") if e.get("source") else None
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        try:
            ts = int(parsedate_to_datetime(e.published).timestamp())
        except Exception:
            continue
        item = enrich({"title": title, "url": e.link, "source": source or "Google News", "ts": ts,
                       "feed": kind}, forced_symbol=None)
        # company query: only keep if the headline actually names the company (Google is fuzzy)
        if forced_symbol and forced_symbol not in item["symbols"]:
            continue
        # sector query: keep Malaysia-relevant stories only
        if kind == "sector" and not (_my_rx.search(title) or _my_sources.search(item["source"])):
            continue
        if kind == "api" and (not _pharma_rx.search(title) or _noise_rx.search(item["source"] + " " + title)):
            continue
        if kind == "api" and "Supply chain / API" not in item["tags"]:
            item["tags"].append("Supply chain / API")
        out.append(item)
    return out


def fetch_news():
    jobs = []
    for s in STOCKS:
        jobs.append((tv_headlines, (s["symbol"],)))
        q = " OR ".join(f'"{a}"' for a in s["aliases"][:3])
        jobs.append((google_news, (q, s["symbol"])))
    for q in SECTOR_QUERIES:
        jobs.append((google_news, (q, None, "sector")))
    for q in API_QUERIES:
        jobs.append((google_news, (q, None, "api")))

    items, errors = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [(ex.submit(fn, *args), fn.__name__, args[0]) for fn, args in jobs]
        for fut, name, arg in futs:
            try:
                items.extend(fut.result())
            except Exception as e:
                errors.append(f"{name}({arg}): {e}")

    now = time.time()
    seen, merged = {}, []
    for it in sorted(items, key=lambda x: (x["feed"] != "wire", -x["ts"])):
        max_age = WIRE_MAX_AGE_DAYS if it["feed"] == "wire" else NEWS_MAX_AGE_DAYS
        if it["ts"] < now - max_age * 86400:
            continue
        k = norm_title(it["title"])
        if k in seen:  # merge symbol/tag info into the first copy
            first = seen[k]
            first["symbols"] = sorted(set(first["symbols"]) | set(it["symbols"]))
            first["tags"] = sorted(set(first["tags"]) | set(it["tags"]))
            continue
        seen[k] = it
        merged.append(it)
    merged.sort(key=lambda x: -x["ts"])
    if errors:
        print("news errors:", *errors, sep="\n  ")
    return {"items": merged, "errors": errors}


def _refresh_news():
    try:
        data = fetch_news()
        _cache["news"] = (time.time(), data)
    finally:
        _news_refreshing.clear()


def get_news():
    ts, data = _cache["news"]
    stale = data is None or time.time() - ts > NEWS_TTL
    if stale and not _news_refreshing.is_set():
        _news_refreshing.set()
        if data is None:
            _refresh_news()  # first load: block
        else:
            threading.Thread(target=_refresh_news, daemon=True).start()  # serve stale, refresh behind
    return _cache["news"]


# ---------------------------------------------------------------- history
HIST_TTL = 30 * 60
ALLOWED = {x["symbol"] for x in STOCKS + INDICES + COMMODITIES}
_hist = {}
_hist_locks = {sym: threading.Lock() for sym in ALLOWED}


def _fetch_hist(symbol):
    sy = SYNTH.get(symbol)
    if not sy:
        return [{"t": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4], "v": r[5]}
                for r in tvhist.history(symbol, bars=800)]
    num, den = tvhist.history(sy["num"], bars=800), tvhist.history(sy["den"], bars=800)
    day = lambda t: datetime.fromtimestamp(t, timezone.utc).date()
    dmap = {day(r[0]): r for r in den}
    out = []
    for r in num:
        dr = dmap.get(day(r[0]))
        if dr and dr[4]:
            c = r[4] / dr[4]
            o = r[1] / dr[1] if dr[1] else c
            out.append({"t": r[0], "o": o, "h": max(o, c), "l": min(o, c), "c": c, "v": None})
    return out


def get_history(symbol):
    with _hist_locks[symbol]:
        ts, data = _hist.get(symbol, (0, None))
        if data is None or time.time() - ts > HIST_TTL:
            try:
                data = _fetch_hist(symbol)
                _hist[symbol] = (time.time(), data)
            except Exception as e:
                if data is None:
                    raise
                print("history refresh failed:", symbol, e)
        return data


# ---------------------------------------------------------------- app
app = FastAPI(title="MY Healthcare Dashboard")


@app.get("/api/config")
def api_config():
    return {"stocks": STOCKS, "indices": INDICES, "commodities": COMMODITIES}


@app.get("/api/quotes")
def api_quotes():
    try:
        ts, data = get_quotes()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    return {"updated": ts, "quotes": data}


@app.get("/api/news")
def api_news():
    ts, data = get_news()
    return {"updated": ts, **(data or {"items": [], "errors": []})}


@app.get("/api/history")
def api_history(symbol: str = Query(...)):
    if symbol not in ALLOWED:
        return JSONResponse({"error": "unknown symbol"}, status_code=404)
    try:
        return {"symbol": symbol, "bars": get_history(symbol)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


if __name__ == "__main__":
    threading.Thread(target=get_news, daemon=True).start()  # warm the news cache
    print(f"Dashboard: http://localhost:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
