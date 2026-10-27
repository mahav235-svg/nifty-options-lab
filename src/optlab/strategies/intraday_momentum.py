"""H5: last-half-hour momentum on NIFTY futures, from one-minute index bars (2022 onward).

Signal at 14:59: the return from the previous close to 14:59 (Gao et al. 2018 use the first
half-hour; Baltussen et al. 2021 the rest-of-day return; we test the latter). Trade one futures
lot in the signal's direction at 15:00 and exit at 15:29.

Futures P&L in points is approximated by the index's move over the same half hour; the basis
barely changes in 29 minutes. Costs use the futures schedule (STT on the sell leg, exchange,
stamp duty, brokerage) plus a slippage allowance of one tick plus a fraction of a point.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from optlab.market.contracts import lot_size
from optlab.market.costs import UPSTOX, Broker, future_trade_cost


@dataclass(frozen=True)
class MomentumParams:
    threshold_sd: float = 0.0  # trade only if |signal| > threshold_sd x rolling 60-day sd of the signal
    entry: str = "15:00"
    exit: str = "15:29"
    slippage_points: float = 1.0  # per side, NIFTY futures (tick 0.05 but the book moves at the close)


def daily_signals(bars: pd.DataFrame) -> pd.DataFrame:
    b = bars.copy()
    b["ts"] = pd.to_datetime(b["ts"])
    b["date"] = b["ts"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None).dt.normalize()
    b["hm"] = b["ts"].dt.tz_convert("Asia/Kolkata").dt.strftime("%H:%M")
    piv = b.pivot_table(index="date", columns="hm", values="close", aggfunc="last")
    out = pd.DataFrame(index=piv.index)
    out["close_prev"] = piv["15:29"].shift(1) if "15:29" in piv else np.nan
    out["p_1459"] = piv.get("14:59")
    out["p_1500"] = piv.get("15:00")
    out["p_1529"] = piv.get("15:29")
    out["signal"] = np.log(out["p_1459"] / out["close_prev"])
    out["target"] = np.log(out["p_1529"] / out["p_1500"])
    return out.dropna()


def run(bars: pd.DataFrame, p: MomentumParams, broker: Broker = UPSTOX) -> pd.DataFrame:
    s = daily_signals(bars)
    sd = s["signal"].rolling(60, min_periods=40).std().shift(1)
    rows = []
    for d, r in s.iterrows():
        if not np.isfinite(sd.get(d, np.nan)):
            continue
        if abs(r["signal"]) <= p.threshold_sd * sd[d]:
            continue
        side = 1 if r["signal"] > 0 else -1
        lot = lot_size("NIFTY", d.date())
        entry, exit_ = r["p_1500"], r["p_1529"]
        gross = side * (exit_ - entry) * lot
        slip = 2 * p.slippage_points * lot
        fees = future_trade_cost(
            d.date(), entry, lot, "BUY" if side > 0 else "SELL", broker
        ) + future_trade_cost(d.date(), exit_, lot, "SELL" if side > 0 else "BUY", broker)
        rows.append(
            {
                "entry_date": d,
                "exit_date": d,
                "side": side,
                "lot_size": lot,
                "lots": 1,
                "gross_points": side * (exit_ - entry),
                "slippage_rs": slip,
                "fees_rs": fees,
                "pnl_rs": gross - slip - fees,
                "spot_entry": entry,
                "signal": r["signal"],
            }
        )
    return pd.DataFrame(rows)
