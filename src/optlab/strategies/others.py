"""The other pre-registered candidates (see docs/research_plan.md).

* ``put_spread``: trend-filtered short put spread on the monthly expiry (equity plus put premium).
* ``event_straddle``: long ATM straddle bought three sessions before an RBI MPC decision or the
  Union Budget and sold the session before it (implied-vol run-up, never held through the event).
* ``overnight_straddle``: short ATM straddle sold at the close and bought back at the next open
  (replication of the day/night asymmetry in Bhat, Pandey and Rao 2024).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from optlab.backtest.engine import ChainBook, ExecutionModel, LegSpec, Trade, simulate


@dataclass(frozen=True)
class PutSpreadParams:
    short_delta: float = 0.25
    width_em: float = 1.0
    trend_min: float | None = 0.0
    min_dte: int = 15


def put_spread(
    book: ChainBook, features: pd.DataFrame, p: PutSpreadParams, ex: ExecutionModel, symbol: str = "NIFTY"
) -> list[Trade]:
    feats = features.set_index("date")
    trades: list[Trade] = []
    blocks = book.blocks[book.blocks["is_monthly"]]
    monthly = sorted({pd.Timestamp(e) for e in blocks["expiry"].unique()})
    entries = []
    for e in monthly:
        nxt = book.next_session(e)
        if nxt is not None:
            entries.append(nxt)
    for d in entries:
        if d not in feats.index:
            continue
        f = feats.loc[d]
        if p.trend_min is not None and not (f["trend"] > p.trend_min):
            continue
        cands = [
            e for e in book.expiries_on.get(d, []) if book.is_monthly(d, e) and (e - d).days >= p.min_dte
        ]
        if not cands:
            continue
        expiry = min(cands)
        day = book.slice(d, expiry)
        assert day is not None
        day = day.reset_index()
        a = book.atm(d, expiry)
        puts = day[(day["option_type"] == "PE") & day["traded"] & day["delta"].notna()]
        if a is None or puts.empty:
            continue
        short = puts.iloc[np.argmin(np.abs(puts["delta"].abs() - p.short_delta))]
        k_short = float(short["strike"])
        target = k_short - p.width_em * float(a["straddle"])
        lower = puts[puts["strike"] <= target]
        if lower.empty:
            continue
        k_long = float(lower["strike"].max())
        legs = [LegSpec("PE", k_short, -1), LegSpec("PE", k_long, 1)]
        t = simulate(
            book,
            "put_spread",
            symbol,
            d,
            expiry,
            legs,
            ex,
            meta={"trend": float(f["trend"]), "vix": float(f["vix"]), "em": float(a["straddle"])},
        )
        if t is not None:
            trades.append(t)
    return trades


@dataclass(frozen=True)
class EventStraddleParams:
    entry_offset: int = 3  # sessions before the event
    exit_offset: int = 1
    kinds: tuple[str, ...] = ("rbi_mpc", "union_budget")
    vix_pct_max: float | None = None  # skip if VIX is above this rolling 1y percentile


def event_straddle(
    book: ChainBook,
    features: pd.DataFrame,
    events: dict[str, list[date]],
    p: EventStraddleParams,
    ex: ExecutionModel,
    symbol: str = "NIFTY",
) -> list[Trade]:
    feats = features.set_index("date")
    vix_pct = feats["vix"].rolling(252, min_periods=120).rank(pct=True)
    sessions = book.sessions
    trades: list[Trade] = []
    for kind in p.kinds:
        for ev in events.get(kind, []):
            i = sessions.searchsorted(pd.Timestamp(ev))
            if i >= len(sessions) or i - p.entry_offset < 0:
                continue
            entry, exit_ = sessions[i - p.entry_offset], sessions[i - p.exit_offset]
            if p.vix_pct_max is not None and not (vix_pct.get(entry, np.nan) <= p.vix_pct_max):
                continue
            cands = [e for e in book.expiries_on.get(entry, []) if e >= sessions[i]]
            if not cands:
                continue
            expiry = min(cands)
            a = book.atm(entry, expiry)
            if a is None:
                continue
            k = float(a["atm_strike"])
            legs = [LegSpec("CE", k, 1), LegSpec("PE", k, 1)]
            t = simulate(
                book,
                f"event_straddle:{kind}",
                symbol,
                entry,
                expiry,
                legs,
                ex,
                exit_on=exit_,
                meta={"event": str(ev), "kind": kind},
            )
            if t is not None:
                trades.append(t)
    return trades


def overnight_straddle(
    book: ChainBook, features: pd.DataFrame, ex: ExecutionModel, min_tdte: int = 2, symbol: str = "NIFTY"
) -> list[Trade]:
    """Sell the nearest-expiry ATM straddle at the close; buy it back at the next session's open."""
    trades: list[Trade] = []
    for d in book.sessions:
        nxt = book.next_session(d)
        if nxt is None:
            continue
        live = [e for e in book.expiries_on.get(d, []) if book.tdte(d, e) >= min_tdte]
        if not live:
            continue
        expiry = min(live)
        if expiry < nxt:
            continue
        a = book.atm(d, expiry)
        if a is None:
            continue
        k = float(a["atm_strike"])
        t = simulate(
            book,
            "overnight_straddle",
            symbol,
            d,
            expiry,
            [LegSpec("CE", k, -1), LegSpec("PE", k, -1)],
            ex,
            exit_on=nxt,
            exit_field="open",
        )
        if t is not None:
            trades.append(t)
    return trades
