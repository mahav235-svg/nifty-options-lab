"""One-minute candles for expired NIFTY options from Upstox's Expired Instruments API.

Needs an Upstox Plus plan and a daily access token (``optlab live login``). Upstox keeps about six
months of expiries, so this is for recent out-of-sample checks (for example, measuring how far a
15:20 fill sits from the bhavcopy close) rather than long backtests.

    from optlab.data.upstox_expired import download_expiry
    download_expiry(date(2026, 9, 29), strikes_around_atm=10)

Endpoints (Upstox docs, Oct 2026):
    GET /v2/expired-instruments/expiries?instrument_key=NSE_INDEX|Nifty 50
    GET /v2/expired-instruments/option/contract?instrument_key=...&expiry_date=YYYY-MM-DD
    GET /v2/expired-instruments/historical-candle/{expired_key}/1minute/{to}/{from}
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests

from optlab.execution.upstox import load_token
from optlab.paths import PROCESSED

log = logging.getLogger(__name__)
API = "https://api.upstox.com/v2/expired-instruments"
NIFTY = "NSE_INDEX|Nifty 50"


class ExpiredClient:
    def __init__(self, token: str | None = None, min_interval: float = 0.3) -> None:
        self.s = requests.Session()
        self.s.headers.update(
            {"Accept": "application/json", "Authorization": f"Bearer {token or load_token()}"}
        )
        self.min_interval = min_interval
        self._last = 0.0

    def _get(self, url: str, params: dict[str, str] | None = None) -> Any:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        r = self.s.get(url, params=params, timeout=30)
        body = r.json()
        if r.status_code != 200 or body.get("status") != "success":
            raise RuntimeError(f"GET {url}: HTTP {r.status_code} {body.get('errors')}")
        return body["data"]

    def expiries(self, underlying: str = NIFTY) -> list[date]:
        data = self._get(f"{API}/expiries", {"instrument_key": underlying})
        return sorted(date.fromisoformat(str(d)) for d in data)

    def contracts(self, expiry: date, underlying: str = NIFTY) -> pd.DataFrame:
        data = self._get(
            f"{API}/option/contract", {"instrument_key": underlying, "expiry_date": f"{expiry:%Y-%m-%d}"}
        )
        return pd.DataFrame(data)

    def candles(self, expired_key: str, start: date, end: date) -> pd.DataFrame:
        url = f"{API}/historical-candle/{quote(expired_key, safe='')}/1minute/{end:%Y-%m-%d}/{start:%Y-%m-%d}"
        data = self._get(url)
        rows = data.get("candles", []) if isinstance(data, dict) else []
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume", "oi"])
        df["ts"] = pd.to_datetime(df["ts"])
        return df.sort_values("ts")


def download_expiry(
    expiry: date,
    strikes_around_atm: int = 10,
    days_before: int = 7,
    client: ExpiredClient | None = None,
    out_dir: Path = PROCESSED,
) -> Path:
    """Save one-minute candles for the strikes nearest the money over the expiry's last week."""
    client = client or ExpiredClient()
    con = client.contracts(expiry)
    if con.empty:
        raise RuntimeError(f"no expired contracts returned for {expiry}")
    spot_ref = con["strike_price"].median()
    strikes = sorted(con["strike_price"].unique(), key=lambda k: abs(k - spot_ref))[
        : 2 * strikes_around_atm + 1
    ]
    frames = []
    for row in con[con["strike_price"].isin(strikes)].itertuples():
        c = client.candles(row.instrument_key, expiry - timedelta(days=days_before), expiry)
        c["strike"], c["option_type"] = row.strike_price, row.instrument_type
        frames.append(c)
        log.info("%s %s %s: %d bars", expiry, row.strike_price, row.instrument_type, len(c))
    target = out_dir / "intraday_options" / f"NIFTY_{expiry:%Y%m%d}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(frames, ignore_index=True).to_parquet(target, index=False)
    return target
