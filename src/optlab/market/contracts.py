"""Contract specifications that change over time: lot sizes and expiry classification.

Lot size is taken from the contract record when the exchange file provides it (UDiFF bhavcopy,
from July 2024). For older files it comes from the NSE circular schedule below, keyed on the
contract's expiry date, because during each transition old and new lot sizes traded side by side.

Sources (NSE circulars): FAOP47854 (31 Mar 2021), FAOP61415 (2 Apr 2024), FAOP64625 (18 Oct 2024),
FAOP70616 (3 Oct 2025). BANKNIFTY 2020 change from broker bulletins.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

# (first expiry date carrying the new lot, lot); applies to expiries on or after the date
_NIFTY_LOTS: list[tuple[date, int]] = [
    (date(2000, 1, 1), 75),
    (date(2021, 7, 29), 50),  # July 2021 monthly; weeklies from Aug 2021
    (date(2024, 5, 2), 25),  # first weekly at 25; Apr 2024 monthly (25 Apr) stayed at 50
    (date(2025, 1, 2), 75),  # first weekly at 75 after SEBI's Rs 15 lakh minimum
    (date(2026, 1, 6), 65),  # first weekly at 65
]
_NIFTY_WEEKLY_AT_50_FROM = date(2021, 8, 5)

_BANKNIFTY_LOTS: list[tuple[date, int]] = [
    (date(2000, 1, 1), 20),
    (date(2020, 7, 30), 25),
    (date(2023, 7, 27), 15),
    (date(2025, 2, 26), 30),
    (date(2025, 7, 31), 35),
    (date(2026, 1, 27), 30),
]


def _schedule_lookup(schedule: list[tuple[date, int]], expiry: date) -> int:
    lot = schedule[0][1]
    for start, size in schedule:
        if expiry >= start:
            lot = size
    return lot


def lot_size(symbol: str, expiry: date, is_monthly: bool = True) -> int:
    """Lot size for a contract, from the circular schedule."""
    if symbol == "NIFTY":
        lot = _schedule_lookup(_NIFTY_LOTS, expiry)
        # July 2021: the monthly moved to 50 but the July weeklies stayed at 75
        if lot == 50 and not is_monthly and expiry < _NIFTY_WEEKLY_AT_50_FROM:
            return 75
        # April 2024: the 25 Apr monthly stayed at 50 even though trading moved to 25 on 26 Apr
        return lot
    if symbol == "BANKNIFTY":
        return _schedule_lookup(_BANKNIFTY_LOTS, expiry)
    raise ValueError(f"no lot schedule for {symbol}")


def monthly_expiries(expiries: pd.Series) -> set[pd.Timestamp]:
    """The monthly expiry is the last listed expiry of each calendar month.

    This is robust to every weekday change NSE has made (Thursday, Wednesday for BANKNIFTY,
    Tuesday from September 2025) and to holiday shifts, because it is derived from the expiries
    that actually traded rather than from a rule.
    """
    s = pd.Series(pd.to_datetime(expiries.unique()))
    return set(s.groupby([s.dt.year, s.dt.month]).max())


def fill_lot_sizes(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing ``lot_size`` (legacy files) from the schedule and add ``is_monthly``."""
    out = df.copy()
    monthly: dict[str, set[pd.Timestamp]] = {}
    for sym, grp in out.groupby("symbol"):
        monthly[str(sym)] = monthly_expiries(grp["expiry"])
    out["is_monthly"] = [e in monthly[str(s)] for s, e in zip(out["symbol"], out["expiry"], strict=True)]
    missing = out["lot_size"].isna()
    if missing.any():
        keys = out.loc[missing, ["symbol", "expiry", "is_monthly"]].drop_duplicates()
        lots = {
            (r.symbol, r.expiry, r.is_monthly): lot_size(str(r.symbol), r.expiry.date(), bool(r.is_monthly))
            for r in keys.itertuples(index=False)
        }
        out.loc[missing, "lot_size"] = [
            lots[(s, e, m)]
            for s, e, m in zip(
                out.loc[missing, "symbol"],
                out.loc[missing, "expiry"],
                out.loc[missing, "is_monthly"],
                strict=True,
            )
        ]
    out["lot_size"] = out["lot_size"].astype(int)
    return out
