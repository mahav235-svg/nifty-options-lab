"""End-to-end data pipeline: raw downloads -> bhavcopy Parquet -> option chains -> features.

raw/nse_fo/YYYY/YYYYMMDD.csv.zip        exact files as published by NSE (never edited)
processed/fo_bhav/year=YYYY/            normalised NIFTY and BANKNIFTY contracts
processed/index/                        index and VIX bars from Upstox
processed/chain/{SYMBOL}/year=YYYY/     chains with forward, IV, delta, sessions to expiry
processed/features/                     one row per session, known at that close
processed/settlements_{SYMBOL}.parquet  expiry -> official settlement price
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from optlab.data import nse_bhavcopy, upstox_candles
from optlab.data.chain import build_chain, expiry_settlements, write_chain
from optlab.data.features import build_features, load_events
from optlab.paths import PROCESSED, RAW, ROOT

log = logging.getLogger(__name__)
SPOT_FILES = {"NIFTY": "NIFTY_daily", "BANKNIFTY": "BANKNIFTY_daily"}


def fetch_all(start: date, end: date) -> None:
    log.info("bhavcopy: %s", nse_bhavcopy.fetch(start, end, RAW))
    for sym in ("NIFTY", "BANKNIFTY", "INDIAVIX"):
        upstox_candles.save(upstox_candles.fetch_daily(sym, date(2008, 1, 1), end), PROCESSED, f"{sym}_daily")
    for sym in ("NIFTY", "INDIAVIX"):
        upstox_candles.save(upstox_candles.fetch_minutes(sym, date(2022, 1, 1), end), PROCESSED, f"{sym}_1m")


def load_bhav(symbol: str) -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED / "fo_bhav")
    df = df[df["symbol"] == symbol]
    # files for the overlap period (Jan to Jul 2024) exist in both formats; keep one row per contract-day
    return df.drop_duplicates(["trade_date", "instrument", "expiry", "strike", "option_type"], keep="last")


def load_spot(symbol: str) -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED / "index" / f"{SPOT_FILES[symbol]}.parquet")
    # Upstox returns two candles for a handful of 2015 dates; keep the later one
    return df.drop_duplicates("date", keep="last").reset_index(drop=True)


def build_chains(symbols: tuple[str, ...] = ("NIFTY", "BANKNIFTY")) -> None:
    for sym in symbols:
        bhav = load_bhav(sym)
        spot = load_spot(sym)
        chain = build_chain(bhav, spot, sym)
        write_chain(chain, PROCESSED, sym)
        expiry_settlements(spot, chain["expiry"]).to_parquet(
            PROCESSED / f"settlements_{sym}.parquet", index=False
        )
        log.info("%s chain: %d rows", sym, len(chain))


def load_chain(symbol: str) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "chain" / symbol)


def build_feature_table(symbol: str = "NIFTY") -> pd.DataFrame:
    chain = load_chain(symbol)
    spot = load_spot(symbol)
    vix = pd.read_parquet(PROCESSED / "index" / "INDIAVIX_daily.parquet").drop_duplicates("date", keep="last")
    feats = build_features(spot, vix, chain, load_events(ROOT / "configs" / "events.yaml"))
    target = PROCESSED / "features" / f"{symbol}_daily_features.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    feats.to_parquet(target, index=False)
    return feats
