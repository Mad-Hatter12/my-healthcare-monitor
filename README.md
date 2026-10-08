# Malaysia Healthcare Monitor

Local dashboard for Bursa-listed healthcare names, regional healthcare indices, and API/raw-material proxies.

## Run

```
./run.sh
```

Opens http://localhost:8050. Requires Python 3.9+; `run.sh` creates `.venv` and installs dependencies on first run.

## What's where

| File | Purpose |
|---|---|
| `config.py` | Universe: stocks, indices, commodity/FX proxies, news queries, topic tags. Edit this to add or remove names. |
| `server.py` | FastAPI server: `/api/quotes` (60s cache), `/api/history` (30 min cache), `/api/news` (15 min cache) |
| `tvhist.py` | Daily OHLCV history from TradingView's chart data feed |
| `static/index.html` | The dashboard (Overview, Companies, News, Commodities & FX) |

## Data sources

- **Quotes and history:** TradingView. Bursa data is delayed about 15 minutes, and futures about 10 minutes.
- **Charts:** TradingView Lightweight Charts. TradingView's embeddable widgets can't show Bursa (MYX) or SET symbols because of exchange licensing.
- **News:**
  - TradingView per-symbol headlines: Reuters and Dow Jones summaries of Bursa filings.
  - Google News RSS, Malaysia edition: per company, plus sector and policy themes.
  - Global news on APIs and drug supply.
- These are unofficial public endpoints, so they may change without notice. If a source fails, the server keeps showing the last good data and logs the error.

## Notes

- Apex Healthcare (7090) was delisted on 27 Jan 2026 after Quadria's take-private, so it's excluded.
- No liquid Singapore healthcare sector index is available, so the regional view covers MY, TH and ID.
- Bursa trading hours are shown, but public holidays aren't accounted for.
