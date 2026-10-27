"""Index candles from Upstox's historical-candle API (v3).

The historical-candle endpoint answers without an access token for listed instruments, which makes
it the simplest free source of one-minute NIFTY and India VIX bars (available from January 2022).
Daily bars go back much further (NIFTY to 2000, India VIX to 2008).

Minute requests are limited to about one month per call, so long ranges are split into
calendar months. Candles come back newest first; we return them oldest first, in IST.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from optlab.data.http import HttpClient

log = logging.getLogger(__name__)

BASE = "https://api.upstox.com/v3/historical-candle"
INSTRUMENTS = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "INDIAVIX": "NSE_INDEX|India VIX",
}
MINUTE_HISTORY_START = date(2022, 1, 1)


def _url(key: str, unit: str, interval: int, start: date, end: date) -> str:
    return f"{BASE}/{quote(key, safe='')}/{unit}/{interval}/{end:%Y-%m-%d}/{start:%Y-%m-%d}"


def _to_frame(candles: list[list[float | str]]) -> pd.DataFrame:
    df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume", "oi"])
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert("Asia/Kolkata")
    return df.drop(columns=["volume", "oi"]).sort_values("ts").reset_index(drop=True)


def _month_chunks(start: date, end: date) -> list[tuple[date, date]]:
    chunks = []
    cur = start
    while cur <= end:
        nxt = (cur.replace(day=1) + timedelta(days=32)).replace(day=1)
        chunks.append((cur, min(end, nxt - timedelta(days=1))))
        cur = nxt
    return chunks


def fetch_minutes(symbol: str, start: date, end: date, client: HttpClient | None = None) -> pd.DataFrame:
    client = client or HttpClient(min_interval=0.25)
    key = INSTRUMENTS[symbol]
    frames = []
    for a, b in _month_chunks(max(start, MINUTE_HISTORY_START), end):
        payload = client.get(_url(key, "minutes", 1, a, b)).json()
        candles = payload.get("data", {}).get("candles", [])
        if candles:
            frames.append(_to_frame(candles))
        log.info("%s %s..%s: %d bars", symbol, a, b, len(candles))
    if not frames:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close"])
    return pd.concat(frames, ignore_index=True).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


def fetch_daily(symbol: str, start: date, end: date, client: HttpClient | None = None) -> pd.DataFrame:
    client = client or HttpClient(min_interval=0.25)
    key = INSTRUMENTS[symbol]
    frames = []
    # daily requests are capped at roughly a decade; ask year by year to stay well inside it
    for year in range(start.year, end.year + 1):
        a, b = max(start, date(year, 1, 1)), min(end, date(year, 12, 31))
        candles = client.get(_url(key, "days", 1, a, b)).json().get("data", {}).get("candles", [])
        if candles:
            frames.append(_to_frame(candles))
    df = pd.concat(frames, ignore_index=True).drop_duplicates("ts").sort_values("ts")
    df["date"] = df["ts"].dt.tz_localize(None).dt.normalize()
    df = df.drop_duplicates("date", keep="last")
    return df.drop(columns="ts")[["date", "open", "high", "low", "close"]].reset_index(drop=True)


def save(df: pd.DataFrame, out_dir: Path, name: str) -> Path:
    target = out_dir / "index" / f"{name}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(target, index=False)
    return target
