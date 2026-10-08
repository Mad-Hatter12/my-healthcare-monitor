"""Bursa company announcements and shareholding changes.

Bursa Malaysia's own site blocks automated access, so announcements are read from
i3investor (klse.i3investor.com), which mirrors Bursa filings. Its robots.txt allows
these pages with a 5-second crawl delay, which we respect. Categories are assigned
here from announcement titles; they are not Bursa's own category labels.

Shareholding detail pages never change once published, so they are cached on disk
(cache/bursa_details.json) and each one is fetched only once.
"""
import html
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

BASE = "https://klse.i3investor.com"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
CRAWL_DELAY = 5.0          # seconds between requests (i3investor robots.txt)
MAX_AGE_DAYS = 365
CACHE = Path(__file__).parent / "cache" / "bursa_details.json"
MYT = timezone(timedelta(hours=8))

# Ordered: first match wins.
CATEGORIES = [
    ("Others", r"shareholding spread|public spread"),
    ("Shareholding", r"\bstakes?\b|substantial shareholder|shareholder interest|shareholding|"
                     r"director'?s?'? (share|interest)|interest in shares|ceased to be|buy-?back|treasury shares|"
                     r"\b(acquir|dispos|purchas|sell|sold|buy|bought)\w*\b[^.]{0,40}?\b[\d,.]+\s*(million\s*)?"
                     r"(?:[A-Za-z]+\s+){0,3}(shares|units|securities)|securities (disposal|acquisition)|"
                     r"position in|dealings? (in|outside)|\b(EPF|KWAP|Employees Provident Fund|Kumpulan Wang Persaraan)\b"),
    ("Results", r"quarterly|financial results?|interim results?|annual (audited )?(accounts|report)|results for"),
    ("Dividend / entitlement", r"dividend|entitlement|bonus issue|rights issue|book closure"),
    ("Meetings", r"\bAGM\b|\bEGM\b|general meeting|meeting results?"),
    ("Board / management", r"appoint|resign|cessation|re-?designat|chief executive|\bCEO\b|\bCFO\b|company secretary|"
                           r"chairman|chairperson|\bnames\b|committee|board of directors|"
                           r"change in (boardroom|audit committee|principal officer)"),
    ("Corporate proposal", r"proposal|proposed|private placement|placement|acquisition|disposal of|"
                           r"subscription|joint venture|\bMoU\b|memorandum|agreement|contract|award|tender|"
                           r"listing|consolidation|share split|warrants?|ESOS|\bESS\b"),
]
_cat_rx = [(c, re.compile(p, re.I)) for c, p in CATEGORIES]
_row_rx = re.compile(r"""\["(\d{4}-\d{2}-\d{2})","<a href='/web/announcement/detail/(\d+)'[^>]*>(.*?)</a>"\]""")


def classify(title):
    for cat, rx in _cat_rx:
        if rx.search(title):
            return cat
    return "Others"


def _get(url, session):
    r = session.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    return r.text


def fetch_list(code, session):
    """Announcements for one stock code: [{id, date, title, url, category}] newest first."""
    page = _get(f"{BASE}/web/stock/announcement/{code}", session)
    cutoff = (datetime.now(MYT) - timedelta(days=MAX_AGE_DAYS)).strftime("%Y-%m-%d")
    out = []
    for date, aid, title in _row_rx.findall(page):
        if date < cutoff:
            continue
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        out.append({"id": aid, "date": date, "title": title, "url": f"{BASE}/web/announcement/detail/{aid}",
                    "category": classify(title)})
    return out


def _lines(page):
    page = re.sub(r"(?s)<(script|style).*?</\1>", "", page)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", page))
    return [l.strip() for l in text.splitlines() if l.strip()]


def _num(s):
    s = s.replace(",", "").strip()
    return int(s) if re.fullmatch(r"-?\d+", s) else None


_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_DATE_RX = re.compile(rf"\b(\d{{1,2}}\s+(?:{_MONTHS})[a-z]*\.?\s+\d{{4}}|\d{{2}}/\d{{2}}/\d{{4}})\b", re.I)
_HOLDER_RX = re.compile(
    r"(Employees Provident Fund(?: Board)?|\bEPF\b|\bKWAP\b|Kumpulan Wang Persaraan(?: \(Diperbadankan\))?|"
    r"Lembaga Tabung Haji|Tabung Haji|\bLTAT\b|Lembaga Tabung Angkatan Tentera|Permodalan Nasional(?: Berhad)?|\bPNB\b|"
    r"Amanah Saham Bumiputera|Khazanah Nasional|Prudential|Eastspring|Great Eastern|AIA|Principal|Kenanga|AHAM|"
    r"Lim Kim Huat Holdings(?: Sdn Bhd)?|Sunway Berhad|Mitsui|Boustead|Chief Financial Officer|Chief Executive Officer|"
    r"Managing Director|Director)", re.I)
_UP = r"acqui|raises?|boosts?|expands?|increases?|buys?|bought|purchas|adds?|ups\b|tops? up|accumulat"
_DOWN = r"dispos|reduces?|trims?|cuts?|sells?|sold|pares?|lowers?|decreases?|offloads?|ceased"


def _mixed_title(title):
    """Headline says the stake was adjusted/changed without saying which way."""
    return (re.search(r"adjust|modif|change|rebalanc", title, re.I)
            and not re.search(_UP, title, re.I) and not re.search(_DOWN, title, re.I))


def _iso(d):
    d = d.strip().replace(".", "")
    for fmt in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(d, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def parse_detail(page, title=""):
    """Best-effort shareholding facts from an announcement page plus its headline (no prose is kept).

    i3investor's pages are auto-generated with varying layouts, so each field is found by pattern:
    {holder, type: Acquired/Disposed/Changed, shares, date, pct_after}. Missing fields are None.
    """
    L = _lines(page)
    try:
        start = next(i for i, l in enumerate(L) if title and l.startswith(title[:40])) + 1
    except StopIteration:
        start = 0
    end = L.index("Related Stocks") if "Related Stocks" in L[start:] else len(L)
    body = " ".join(L[start:end])
    body = re.sub(r"^Date:\s*\d{1,2}\s+\w+\s+\d{4}\s*", "", body)   # drop the page's own publish date

    out = {"holder": None, "type": None, "shares": None, "date": None, "pct_after": None}
    m = _HOLDER_RX.search(title) or _HOLDER_RX.search(body)
    if m:
        h = m.group(1)
        out["holder"] = {"EPF": "Employees Provident Fund", "KWAP": "KWAP", "LTAT": "LTAT", "PNB": "PNB"}.get(h.upper(), h.strip())

    up, down = re.search(_UP, title, re.I), re.search(_DOWN, title, re.I)
    if not (up or down) and re.search(r"adjust|modif|change|rebalanc", title, re.I):
        up = down = True                       # mixed or unspecified -> "Changed"
    elif not (up or down):
        up, down = re.search(_UP, body, re.I), re.search(_DOWN, body, re.I)
        if up and down:   # both appear in the text: take whichever comes first
            up, down = (up, None) if up.start() < down.start() else (None, down)
    out["type"] = "Acquired" if up and not down else "Disposed" if down and not up else "Changed"

    m = re.search(r"([\d,.]+)\s*(million)?\s*(?:ordinary\s*)?(?:shares|units|securities)", title, re.I) or \
        re.search(r"(?:Number of Securities|No\.? of Securities|Shares (?:acquired|disposed))\s*([\d,]{4,})()", body, re.I) or \
        re.search(r"([\d,]{5,})\s*()(?:ordinary\s*)?(?:shares|units)", body, re.I)
    if m:
        try:
            out["shares"] = int(float(m.group(1).replace(",", "")) * (1e6 if m.group(2) else 1))
        except ValueError:
            pass

    m = re.search(r"(?:Date of Change|Change date|Date of Transaction)\s*" + _DATE_RX.pattern, body, re.I) or _DATE_RX.search(body)
    if m:
        out["date"] = _iso(m.group(1))

    m = re.search(r"\bto\s+(\d{1,2}(?:\.\d+)?)\s*%", title) or re.search(r"(\d{1,2}\.\d{1,3})\s*(?:%|percent)", body)
    if m:
        out["pct_after"] = float(m.group(1))
    return out


def _load_cache():
    try:
        return json.loads(CACHE.read_text())
    except Exception:
        return {}


def _save_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, separators=(",", ":")))


def fetch_all(stocks, max_details=40, log=print):
    """Announcements for all stocks plus shareholding details (cached; at most max_details new fetches)."""
    session = requests.Session()
    cache = _load_cache()
    items, errors = [], []
    last = 0.0

    def polite_get(url):
        nonlocal last
        wait = CRAWL_DELAY - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        try:
            return _get(url, session)
        finally:
            last = time.time()

    for s in stocks:
        if not s.get("code"):
            continue
        wait = CRAWL_DELAY - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        try:
            anns = fetch_list(s["code"], session)
            for a in anns:
                a["symbol"] = s["symbol"]
            items.extend(anns)
        except Exception as e:
            errors.append(f"{s['short']}: {e}")
        finally:
            last = time.time()

    fetched = 0
    for a in sorted(items, key=lambda x: x["date"], reverse=True):
        if a["category"] != "Shareholding":
            continue
        if a["id"] not in cache:
            if fetched >= max_details:
                continue
            try:
                cache[a["id"]] = parse_detail(polite_get(a["url"]), a["title"])
                fetched += 1
            except Exception as e:
                errors.append(f"detail {a['id']}: {e}")
                continue
        a["detail"] = dict(cache[a["id"]])
        if _mixed_title(a["title"]):
            a["detail"]["type"] = "Changed"
    _save_cache(cache)
    items.sort(key=lambda x: (x["date"], x["id"]), reverse=True)
    pending = sum(1 for a in items if a["category"] == "Shareholding" and "detail" not in a)
    log(f"bursa: {len(items)} announcements, {fetched} new shareholding details, {pending} pending, {len(errors)} errors")
    return {"items": items, "errors": errors, "pending_details": pending}
