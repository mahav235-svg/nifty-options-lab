"""Daily feature table: one row per session, every column known at that session's close.

Columns
-------
spot_*            index OHLC (official values)
vix               India VIX close
rv_gk             Garman-Klass daily variance (with overnight gap)
har_vol_{h}d      expanding-window HAR-X forecast of annualised vol over the next h sessions
atm_iv_near       ATM implied vol of the nearest expiry with at least 1 session left after today
near_expiry       that expiry; near_tdte its sessions left (counting expiry day)
em_near           ATM straddle price of that expiry (the market's expected move, in points)
atm_iv_month      ATM implied vol of the next monthly expiry at least 15 calendar days away
sma_100, trend    100-day simple moving average and close / sma_100 - 1
event_in_{h}d     a scheduled event (RBI MPC, Budget, election count) in the next h sessions
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from optlab.market.volatility import garman_klass, har_forecast, vix_to_daily_variance

EVENT_KINDS = ("rbi_mpc", "union_budget", "election_results")


def load_events(path: Path) -> dict[str, list[date]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {k: sorted(pd.to_datetime(v).date) for k, v in raw.items()}


def atm_row(chain_day: pd.DataFrame) -> pd.Series | None:
    """ATM strike (nearest the forward) with both legs traded; returns iv and straddle price."""
    both = chain_day[chain_day["traded"]].pivot_table(
        index="strike", columns="option_type", values=["close", "iv"], aggfunc="first"
    )
    if both.empty or ("close", "CE") not in both or ("close", "PE") not in both:
        return None
    both = both.dropna()
    if both.empty:
        return None
    fwd = float(chain_day["forward"].iloc[0])
    k = both.index[np.argmin(np.abs(both.index.to_numpy() - fwd))]
    r = both.loc[k]
    return pd.Series(
        {
            "atm_strike": k,
            "straddle": r[("close", "CE")] + r[("close", "PE")],
            "atm_iv": np.nanmean([r[("iv", "CE")], r[("iv", "PE")]]),
            "forward": fwd,
        }
    )


def option_features(chain: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for d, day in chain.groupby("trade_date"):
        live = day[day["tdte"] >= 2]  # at least one session after today
        if live.empty:
            continue
        near = live["expiry"].min()
        a = atm_row(live[live["expiry"] == near])
        month = live[(live["is_monthly"]) & (live["dte"] >= 15)]
        m = atm_row(month[month["expiry"] == month["expiry"].min()]) if not month.empty else None
        rows.append(
            {
                "date": d,
                "near_expiry": near,
                "near_tdte": int(live.loc[live["expiry"] == near, "tdte"].iloc[0]),
                "atm_iv_near": a["atm_iv"] if a is not None else np.nan,
                "em_near": a["straddle"] if a is not None else np.nan,
                "atm_strike_near": a["atm_strike"] if a is not None else np.nan,
                "atm_iv_month": m["atm_iv"] if m is not None else np.nan,
            }
        )
    return pd.DataFrame(rows)


def build_features(
    spot: pd.DataFrame,
    vix: pd.DataFrame,
    chain: pd.DataFrame,
    events: dict[str, list[date]],
    horizons: tuple[int, ...] = (1, 2, 3, 4, 5, 20),
) -> pd.DataFrame:
    s = spot.set_index("date").sort_index()
    sessions = pd.DatetimeIndex(sorted(chain["trade_date"].unique()))
    s = s[s.index.isin(sessions) | (s.index < sessions.min())]
    f = pd.DataFrame(index=s.index)
    f[["spot_open", "spot_high", "spot_low", "spot_close"]] = s[["open", "high", "low", "close"]]
    f["vix"] = vix.set_index("date")["close"].reindex(f.index).ffill()
    f["rv_gk"] = garman_klass(s)
    exog = vix_to_daily_variance(f["vix"])
    for h in horizons:
        f[f"har_vol_{h}d"] = har_forecast(f["rv_gk"], horizon=h, exog=exog)
    f["sma_100"] = f["spot_close"].rolling(100).mean()
    f["trend"] = f["spot_close"] / f["sma_100"] - 1
    f["ret_1d"] = np.log(f["spot_close"]).diff()

    opt = option_features(chain).set_index("date")
    f = f.join(opt, how="left")
    f = f[f.index.isin(sessions)]

    all_events = sorted({pd.Timestamp(d) for k in EVENT_KINDS for d in events.get(k, [])})
    pos = {d: i for i, d in enumerate(f.index)}
    ev_pos = np.array([f.index.searchsorted(e) for e in all_events])
    for h in (1, 2, 3, 4, 5, 10, 20):
        flag = np.zeros(len(f), dtype=bool)
        for i in pos.values():
            flag[i] = bool(((ev_pos > i) & (ev_pos <= i + h)).any())
        f[f"event_in_{h}d"] = flag
    f.index.name = "date"
    return f.reset_index()
