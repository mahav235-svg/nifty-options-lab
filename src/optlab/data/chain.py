"""Daily option-chain layer: one row per (trade date, expiry, strike, type) with derived fields.

Added on top of the raw bhavcopy rows:

* ``spot``: index close (official close; the settlement reference on expiry day),
* ``forward``: the futures close when a future expires with the option, otherwise the forward
  implied by put-call parity at the strikes nearest the money,
* ``dte`` (calendar days) and ``tdte`` (trading sessions left, counting expiry day),
* ``iv`` and ``delta`` from Black-76 on the forward, for traded rows only,
* ``lot_size`` and ``is_monthly``.

Rows whose option did not trade that day keep ``traded = False`` and get no IV; strategies must
not fill against them.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from optlab.market.contracts import fill_lot_sizes
from optlab.market.pricing import delta, implied_vol

log = logging.getLogger(__name__)


def _parity_forward(opts: pd.DataFrame) -> pd.Series:
    """Forward per (trade_date, expiry) from C - P = F - K at the three strikes where |C - P| is smallest."""
    traded = opts[opts["traded"]]
    calls = traded[traded["option_type"] == "CE"][["trade_date", "expiry", "strike", "close"]]
    puts = traded[traded["option_type"] == "PE"][["trade_date", "expiry", "strike", "close"]]
    both = calls.merge(puts, on=["trade_date", "expiry", "strike"], suffixes=("_c", "_p"))
    both["gap"] = (both["close_c"] - both["close_p"]).abs()
    both["fwd"] = both["strike"] + both["close_c"] - both["close_p"]
    best = both.sort_values("gap").groupby(["trade_date", "expiry"]).head(3)
    return best.groupby(["trade_date", "expiry"])["fwd"].median()


def actual_expiry(expiry: pd.Series, sessions: pd.Index) -> pd.Series:
    """Map scheduled expiry dates to the session the contract actually expired on.

    When the scheduled day is a holiday NSE moves expiry to the previous trading day, but the
    legacy bhavcopy keeps showing the scheduled date (30 Mar 2023 expired on 29 Mar). Using the
    scheduled date would settle against a non-existent close and miscount sessions to expiry.
    """
    vals = sessions.values
    pos = np.searchsorted(vals, expiry.values, side="right") - 1
    mapped = vals[np.clip(pos, 0, len(vals) - 1)]
    # contracts expiring after the last session in the data keep their scheduled date
    return pd.Series(np.where(expiry.values > vals[-1], expiry.values, mapped), index=expiry.index)


def build_chain(bhav: pd.DataFrame, spot_daily: pd.DataFrame, symbol: str) -> pd.DataFrame:
    df = bhav[bhav["symbol"] == symbol].copy()
    all_sessions = pd.Index(sorted(df["trade_date"].unique()))
    df["expiry"] = actual_expiry(df["expiry"], all_sessions).astype(df["expiry"].dtype)
    df = fill_lot_sizes(df)
    opts = df[df["instrument"] == "OPT"].copy()
    futs = df[(df["instrument"] == "FUT") & df["traded"]][["trade_date", "expiry", "close"]].rename(
        columns={"close": "fut_close"}
    )

    spot = spot_daily.rename(columns={"date": "trade_date", "close": "spot", "open": "spot_open"})[
        ["trade_date", "spot", "spot_open"]
    ]
    opts = opts.merge(spot, on="trade_date", how="left")
    opts = opts.merge(futs, on=["trade_date", "expiry"], how="left")
    parity = _parity_forward(opts).rename("parity_fwd").reset_index()
    opts = opts.merge(parity, on=["trade_date", "expiry"], how="left")
    opts["forward"] = opts["fut_close"].fillna(opts["parity_fwd"]).fillna(opts["spot"])

    sessions = pd.Index(sorted(df["trade_date"].unique()))
    pos = pd.Series(np.arange(len(sessions)), index=sessions)
    expiry_pos = np.searchsorted(sessions.values, opts["expiry"].values)  # expiry is a session
    opts["tdte"] = expiry_pos - pos.reindex(opts["trade_date"]).to_numpy() + 1
    opts["dte"] = (opts["expiry"] - opts["trade_date"]).dt.days

    t = np.maximum(opts["dte"].to_numpy(dtype=float), 0.0) / 365.0
    ok = opts["traded"].to_numpy() & (t > 0)
    call = (opts["option_type"] == "CE").to_numpy()
    iv = np.full(len(opts), np.nan)
    iv[ok] = implied_vol(
        opts["close"].to_numpy()[ok],
        opts["forward"].to_numpy()[ok],
        opts["strike"].to_numpy()[ok],
        t[ok],
        call[ok],
    )
    opts["iv"] = iv
    opts["delta"] = np.where(
        np.isnan(iv),
        np.nan,
        delta(opts["forward"], opts["strike"], np.maximum(t, 1e-6), np.nan_to_num(iv, nan=0.2), call),
    )
    keep = [
        "trade_date",
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
        "traded",
        "lot_size",
        "is_monthly",
        "spot",
        "spot_open",
        "forward",
        "dte",
        "tdte",
        "iv",
        "delta",
    ]
    return opts[keep].sort_values(["trade_date", "expiry", "strike", "option_type"]).reset_index(drop=True)


def write_chain(chain: pd.DataFrame, out_dir: Path, symbol: str) -> list[Path]:
    paths = []
    for year, part in chain.groupby(chain["trade_date"].dt.year):
        target = out_dir / "chain" / symbol / f"year={year}" / "data.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        part.to_parquet(target, index=False)
        paths.append(target)
    return paths


def expiry_settlements(spot_daily: pd.DataFrame, expiries: pd.Series) -> pd.DataFrame:
    """Final settlement price for each expiry: the index's official close on expiry day."""
    s = spot_daily.set_index("date")["close"]
    exp = pd.Series(sorted(pd.to_datetime(expiries.unique())))
    return pd.DataFrame({"expiry": exp, "settlement": s.reindex(exp).to_numpy()})
