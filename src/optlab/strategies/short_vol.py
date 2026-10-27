"""Defined-risk short-volatility structures held to expiry (the variance risk premium family).

One parameterisation covers the iron condor (short strikes away from the money), the iron fly
(short strikes at the money) and, with wings removed, the short strangle and straddle used only
as research baselines.

Strikes are set in units of the market's own expected move (EM, the at-the-money straddle price)
so the structure scales with volatility instead of using fixed point distances that mean very
different things at VIX 11 and VIX 30.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from optlab.backtest.engine import ChainBook, ExecutionModel, LegSpec, Trade, simulate
from optlab.data.features import atm_row


@dataclass(frozen=True)
class ShortVolParams:
    entry_tdte: int = 4  # sessions left to expiry at entry, counting expiry day (4 = 3 sessions held)
    short_em: float = 1.0  # short strikes at ATM +/- short_em x EM (0 = iron fly)
    wing_em: float = 1.0  # long wings a further wing_em x EM out (0 = no wings: baseline only)
    vrp_min: float = 0.0  # trade only if ATM IV / HAR forecast vol > vrp_min (0 = no filter)
    skip_events: bool = True  # skip if an RBI MPC, Budget or election count falls in the holding window
    trend_min: float | None = None  # trade only if close / SMA100 - 1 > trend_min
    monthly_only: bool = False
    lots: int = 1

    def label(self) -> str:
        parts = [
            f"tdte{self.entry_tdte}",
            f"s{self.short_em:g}",
            f"w{self.wing_em:g}",
            f"vrp{self.vrp_min:g}",
        ]
        if self.skip_events:
            parts.append("noev")
        if self.trend_min is not None:
            parts.append(f"tr{self.trend_min:g}")
        if self.monthly_only:
            parts.append("mo")
        return "_".join(parts)


def horizon_key(prefix: str, held: int, available: tuple[int, ...], suffix: str = "d") -> str:
    """Feature column for the smallest precomputed horizon covering ``held`` sessions."""
    h = next((x for x in available if x >= held), available[-1])
    return f"{prefix}{h}{suffix}"


def _nearest_strike(strikes: np.ndarray, target: float, side: str) -> float | None:
    """Closest listed strike at or beyond ``target`` (beyond = further from the money)."""
    cands = strikes[strikes >= target] if side == "up" else strikes[strikes <= target]
    if len(cands) == 0:
        return None
    return float(cands.min() if side == "up" else cands.max())


def build_legs(
    day: pd.DataFrame, p: ShortVolParams, a: pd.Series | None = None
) -> tuple[list[LegSpec], dict[str, float]] | None:
    a = atm_row(day) if a is None else a
    if a is None or not np.isfinite(a["straddle"]) or a["straddle"] <= 0:
        return None
    atm, em = float(a["atm_strike"]), float(a["straddle"])
    traded = day[day["traded"]]
    calls = np.sort(traded.loc[traded["option_type"] == "CE", "strike"].to_numpy())
    puts = np.sort(traded.loc[traded["option_type"] == "PE", "strike"].to_numpy())
    sc = atm if p.short_em == 0 else _nearest_strike(calls, atm + p.short_em * em, "up")
    sp = atm if p.short_em == 0 else _nearest_strike(puts, atm - p.short_em * em, "down")
    if sc is None or sp is None:
        return None
    legs = [LegSpec("CE", sc, -p.lots), LegSpec("PE", sp, -p.lots)]
    if p.wing_em > 0:
        lc = _nearest_strike(calls, sc + p.wing_em * em, "up")
        lp = _nearest_strike(puts, sp - p.wing_em * em, "down")
        if lc is None or lp is None or lc <= sc or lp >= sp:
            return None
        legs += [LegSpec("CE", lc, p.lots), LegSpec("PE", lp, p.lots)]
    return legs, {"atm": atm, "em": em, "atm_iv": float(a["atm_iv"])}


def run(
    book: ChainBook, features: pd.DataFrame, p: ShortVolParams, ex: ExecutionModel, symbol: str = "NIFTY"
) -> list[Trade]:
    feats = features.set_index("date")
    trades: list[Trade] = []
    blocks = book.blocks[book.blocks["tdte"] == p.entry_tdte]
    if p.monthly_only:
        blocks = blocks[blocks["is_monthly"]]
    held = p.entry_tdte - 1
    ev_col = horizon_key("event_in_", held, (1, 2, 3, 4, 5, 10, 20))
    har_col = horizon_key("har_vol_", held, (1, 2, 3, 4, 5, 20))
    for d, expiry in zip(blocks["trade_date"], blocks["expiry"], strict=True):
        d, expiry = pd.Timestamp(d), pd.Timestamp(expiry)
        if d not in feats.index:
            continue
        f = feats.loc[d]
        event = bool(f.get(ev_col, False))
        if p.skip_events and event:
            continue
        if p.trend_min is not None and not (f["trend"] > p.trend_min):
            continue
        day = book.slice(d, expiry)
        if day is None:
            continue
        built = build_legs(day, p, book.atm(d, expiry))
        if built is None:
            continue
        legs, info = built
        har = f.get(har_col, np.nan)
        vrp = info["atm_iv"] / har if np.isfinite(har) and har > 0 else np.nan
        if p.vrp_min > 0 and not (np.isfinite(vrp) and vrp > p.vrp_min):
            continue
        t = simulate(
            book,
            f"short_vol:{p.label()}",
            symbol,
            d,
            expiry,
            legs,
            ex,
            meta={
                **info,
                "vrp": vrp,
                "event_in_hold": event,
                "vix": float(f["vix"]),
                "trend": float(f["trend"]),
                **{k: v for k, v in asdict(p).items() if k != "lots"},
            },
        )
        if t is not None:
            trades.append(t)
    return trades


def derive_filtered(base: pd.DataFrame, vrp_min: float, skip_events: bool) -> pd.DataFrame:
    """Apply the entry filters to an unfiltered run. Identical to running with the filters on,
    because filters only decide whether a trade is opened; they never change its legs."""
    keep = pd.Series(True, index=base.index)
    if vrp_min > 0:
        keep &= base["meta_vrp"] > vrp_min
    if skip_events:
        keep &= ~base["meta_event_in_hold"].astype(bool)
    return base[keep].reset_index(drop=True)
