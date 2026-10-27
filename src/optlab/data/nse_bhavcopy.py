"""NSE F&O bhavcopy: download, parse and normalise the daily derivatives file.

NSE publishes one file per trading day with open, high, low, close, settlement price, volume and
open interest for every futures and options contract. Two formats exist:

* the legacy CSV (``fo<DDMONYYYY>bhav.csv.zip``), published up to 5 July 2024;
* the UDiFF CSV (``BhavCopy_NSE_FO_0_0_0_<YYYYMMDD>_F_0000.csv.zip``), from 8 July 2024.

Both are mapped onto one schema (``COLUMNS``). Two traps matter for backtesting:

1. In the legacy file an untraded contract still carries a CLOSE, carried over from an earlier day,
   with OPEN/HIGH/LOW set to zero. Those rows are kept but flagged ``traded = False`` so a backtest
   never fills against a price nobody traded at.
2. ``ClsPric`` in the UDiFF file (``CLOSE`` in the legacy one) is NSE's official closing price, a
   volume-weighted price over the last half hour for futures, not the last trade. It is a fair proxy
   for an exit placed in the final minutes; ``LastPric`` is noisier and is not used.
"""

from __future__ import annotations

import io
import logging
import zipfile
from collections.abc import Iterable, Iterator
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from optlab.data.http import HttpClient, NotFoundError

log = logging.getLogger(__name__)

UDIFF_START = date(2024, 7, 8)
SYMBOLS = ("NIFTY", "BANKNIFTY")
_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")

COLUMNS = [
    "trade_date",
    "symbol",
    "instrument",
    "expiry",
    "strike",
    "option_type",
    "open",
    "high",
    "low",
    "close",
    "settle",
    "contracts",
    "open_interest",
    "oi_change",
    "underlying",
    "lot_size",
    "traded",
]


def archive_url(d: date) -> str:
    if d >= UDIFF_START:
        return f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    mon = _MONTHS[d.month - 1]
    return (
        "https://nsearchives.nseindia.com/content/historical/DERIVATIVES/"
        f"{d.year}/{mon}/fo{d.day:02d}{mon}{d.year}bhav.csv.zip"
    )


def raw_path(raw_dir: Path, d: date) -> Path:
    return raw_dir / "nse_fo" / str(d.year) / f"{d:%Y%m%d}.csv.zip"


def daterange(start: date, end: date) -> Iterator[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def fetch(start: date, end: date, raw_dir: Path, client: HttpClient | None = None) -> dict[str, int]:
    """Download every available file in [start, end] into the raw cache. Re-runs skip cached days.

    Weekends are tried as well because NSE has held full Saturday sessions (budget days, disaster
    recovery drills); a 404 simply marks a non-trading day and is remembered in a marker file.
    """
    client = client or HttpClient()
    stats = {"downloaded": 0, "cached": 0, "holiday": 0}
    for d in daterange(start, end):
        target = raw_path(raw_dir, d)
        marker = target.with_suffix(".none")
        if target.exists():
            stats["cached"] += 1
            continue
        if marker.exists():
            stats["holiday"] += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            resp = client.get(archive_url(d))
        except NotFoundError:
            if d < date.today():
                marker.touch()
            stats["holiday"] += 1
            continue
        target.write_bytes(resp.content)
        stats["downloaded"] += 1
        log.info("fetched %s", d)
    return stats


def _read_zip(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        name = zf.namelist()[0]
        return pd.read_csv(io.BytesIO(zf.read(name)), dtype=str, keep_default_na=False)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str.strip(), errors="coerce")


def parse_legacy(raw: pd.DataFrame, symbols: Iterable[str] = SYMBOLS) -> pd.DataFrame:
    raw = raw.rename(columns=str.strip)
    df = raw[raw["INSTRUMENT"].isin(["OPTIDX", "FUTIDX"]) & raw["SYMBOL"].isin(list(symbols))]
    out = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(df["TIMESTAMP"], format="%d-%b-%Y"),
            "symbol": df["SYMBOL"],
            "instrument": df["INSTRUMENT"].map({"OPTIDX": "OPT", "FUTIDX": "FUT"}),
            "expiry": pd.to_datetime(df["EXPIRY_DT"], format="%d-%b-%Y"),
            "strike": _num(df["STRIKE_PR"]),
            "option_type": df["OPTION_TYP"].where(df["OPTION_TYP"].isin(["CE", "PE"])),
            "open": _num(df["OPEN"]),
            "high": _num(df["HIGH"]),
            "low": _num(df["LOW"]),
            "close": _num(df["CLOSE"]),
            "settle": _num(df["SETTLE_PR"]),
            "contracts": _num(df["CONTRACTS"]),
            "open_interest": _num(df["OPEN_INT"]),
            "oi_change": _num(df["CHG_IN_OI"]),
            "underlying": float("nan"),
            "lot_size": float("nan"),
        }
    )
    return _finish(out)


def parse_udiff(raw: pd.DataFrame, symbols: Iterable[str] = SYMBOLS) -> pd.DataFrame:
    df = raw[raw["FinInstrmTp"].isin(["IDO", "IDF"]) & raw["TckrSymb"].isin(list(symbols))]
    lot = _num(df["NewBrdLotQty"])
    out = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(df["TradDt"], format="%Y-%m-%d"),
            "symbol": df["TckrSymb"],
            "instrument": df["FinInstrmTp"].map({"IDO": "OPT", "IDF": "FUT"}),
            # the actual expiry, which differs from XpryDt when the scheduled day is a holiday
            "expiry": pd.to_datetime(
                df["FininstrmActlXpryDt"].where(df["FininstrmActlXpryDt"] != "", df["XpryDt"]),
                format="%Y-%m-%d",
            ),
            "strike": _num(df["StrkPric"]),
            "option_type": df["OptnTp"].where(df["OptnTp"].isin(["CE", "PE"])),
            "open": _num(df["OpnPric"]),
            "high": _num(df["HghPric"]),
            "low": _num(df["LwPric"]),
            "close": _num(df["ClsPric"]),
            "settle": _num(df["SttlmPric"]),
            "contracts": _num(df["TtlTradgVol"]),
            "open_interest": _num(df["OpnIntrst"]),
            "oi_change": _num(df["ChngInOpnIntrst"]),
            "underlying": _num(df["UndrlygPric"]),
            "lot_size": lot,
        }
    )
    return _finish(out)


def _finish(out: pd.DataFrame) -> pd.DataFrame:
    out.loc[out["instrument"] == "FUT", "strike"] = float("nan")
    out["traded"] = (out["contracts"].fillna(0) > 0) & (out["open"].fillna(0) > 0)
    out["option_type"] = out["option_type"].astype("string")
    out["symbol"] = out["symbol"].astype("string")
    out["instrument"] = out["instrument"].astype("string")
    return out[COLUMNS].reset_index(drop=True)


def parse_file(path: Path, symbols: Iterable[str] = SYMBOLS) -> pd.DataFrame:
    raw = _read_zip(path)
    if "FinInstrmTp" in raw.columns:
        return parse_udiff(raw, symbols)
    return parse_legacy(raw, symbols)


def build(raw_dir: Path, out_dir: Path, years: Iterable[int] | None = None) -> list[Path]:
    """Parse cached zips into one Parquet file per year (``out_dir/fo_bhav/year=YYYY/data.parquet``)."""
    base = raw_dir / "nse_fo"
    written: list[Path] = []
    year_dirs = sorted(p for p in base.iterdir() if p.is_dir()) if base.exists() else []
    for ydir in year_dirs:
        year = int(ydir.name)
        if years is not None and year not in set(years):
            continue
        frames = []
        for zp in sorted(ydir.glob("*.csv.zip")):
            try:
                frames.append(parse_file(zp))
            except (zipfile.BadZipFile, KeyError, ValueError) as exc:
                log.error("could not parse %s: %s", zp, exc)
        if not frames:
            continue
        df = pd.concat(frames, ignore_index=True).sort_values(
            ["trade_date", "symbol", "instrument", "expiry", "strike", "option_type"]
        )
        target = out_dir / "fo_bhav" / f"year={year}" / "data.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(target, index=False)
        written.append(target)
        log.info("wrote %s (%d rows)", target, len(df))
    return written
