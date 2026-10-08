"""Daily OHLCV history from TradingView's chart data feed (anonymous, delayed)."""
import json
import random
import re
import string

from websocket import create_connection

WS_URL = "wss://data.tradingview.com/socket.io/websocket?from=chart%2F&type=chart"
HEADERS = {"Origin": "https://www.tradingview.com"}


def _rid(prefix):
    return prefix + "".join(random.choices(string.ascii_lowercase, k=12))


def _frame(func, params):
    body = json.dumps({"m": func, "p": params}, separators=(",", ":"))
    return f"~m~{len(body)}~m~{body}"


def _messages(raw):
    for part in re.split(r"~m~\d+~m~", raw):
        if part:
            yield part


def history(symbol, bars=600, interval="1D", timeout=20):
    """Return list of (unix_ts, open, high, low, close, volume)."""
    ws = create_connection(WS_URL, header=HEADERS, timeout=timeout)
    cs = _rid("cs_")
    try:
        for f, p in [("set_auth_token", ["unauthorized_user_token"]),
                     ("chart_create_session", [cs, ""]),
                     ("resolve_symbol", [cs, "sds_sym_1", "=" + json.dumps({"symbol": symbol, "adjustment": "splits"})]),
                     ("create_series", [cs, "sds_1", "s1", "sds_sym_1", interval, bars, ""])]:
            ws.send(_frame(f, p))
        rows = {}
        while True:
            raw = ws.recv()
            for msg in _messages(raw):
                if msg.startswith("~h~"):
                    ws.send(f"~m~{len(msg)}~m~{msg}")
                    continue
                try:
                    j = json.loads(msg)
                except ValueError:
                    continue
                m = j.get("m")
                if m == "timescale_update":
                    for b in j["p"][1].get("sds_1", {}).get("s", []):
                        v = b["v"]
                        rows[int(v[0])] = (int(v[0]), *v[1:5], v[5] if len(v) > 5 else None)
                elif m in ("series_completed",):
                    return [rows[k] for k in sorted(rows)]
                elif m in ("symbol_error", "series_error", "critical_error", "protocol_error"):
                    raise RuntimeError(f"{symbol}: {m} {j.get('p')}")
    finally:
        ws.close()
