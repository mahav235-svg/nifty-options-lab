"""Trade simulation on end-of-day option chains.

Execution model
---------------
* Entries and early exits fill at the day's official close price (NSE's close for derivatives is a
  volume-weighted price over the last half hour), worsened by a slippage allowance per unit. This
  corresponds to working orders in the final minutes, which is how the live runner trades.
* A leg can only be filled if the contract traded that day with at least ``min_contracts``
  contracts. If any leg fails, the whole structure is skipped: no partial structures, and no
  fills against stale prices.
* Positions held to expiry settle at intrinsic value against the index's official closing price
  on expiry day, which is how NSE settles index options. Long legs that finish in the money pay
  STT on intrinsic value; nothing else is charged at settlement.
* Costs (brokerage, STT, exchange, SEBI fee, stamp duty, GST) use the rates in force on the
  trade date (see ``market.costs``).

Look-ahead discipline: a strategy decides on date t using only rows with ``trade_date <= t``
and features computed from data up to t's close. The engine only reads expiry-day prices to
settle, after the decision.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from optlab.data.features import atm_row
from optlab.market.costs import UPSTOX, Broker, Slippage, exercise_cost, option_trade_cost


@dataclass(frozen=True)
class LegSpec:
    option_type: str  # "CE" or "PE"
    strike: float
    lots: int  # positive = long, negative = short


@dataclass
class Fill:
    option_type: str
    strike: float
    lots: int
    price: float  # quoted price (close)
    fill_price: float  # after slippage
    contracts_traded: float


@dataclass
class Trade:
    strategy: str
    symbol: str
    entry_date: date
    expiry: date
    exit_date: date
    exit_kind: str  # "expiry", "close", "open", "stop"
    lot_size: int
    lots: int
    spot_entry: float
    exit_ref: float  # settlement price or index close at exit
    entry_fills: list[Fill]
    exit_values: list[float]  # per-leg value per unit at exit
    credit_points: float  # net premium received per unit (negative = debit)
    max_loss_points: float  # worst case per unit for defined-risk structures (inf if undefined)
    gross_points: float  # P&L per unit before costs and slippage
    slippage_rs: float
    fees_rs: float
    pnl_rs: float  # net P&L for the position
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def units(self) -> int:
        return self.lot_size * self.lots

    @property
    def net_points(self) -> float:
        return self.pnl_rs / self.units

    @property
    def return_on_risk(self) -> float:
        """Net P&L divided by the maximum loss of the structure (defined-risk trades only)."""
        if not np.isfinite(self.max_loss_points) or self.max_loss_points <= 0:
            return float("nan")
        return self.pnl_rs / (self.max_loss_points * self.units)

    def as_row(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "symbol": self.symbol,
            "entry_date": pd.Timestamp(self.entry_date),
            "expiry": pd.Timestamp(self.expiry),
            "exit_date": pd.Timestamp(self.exit_date),
            "exit_kind": self.exit_kind,
            "lot_size": self.lot_size,
            "lots": self.lots,
            "spot_entry": self.spot_entry,
            "exit_ref": self.exit_ref,
            "credit_points": self.credit_points,
            "max_loss_points": self.max_loss_points,
            "gross_points": self.gross_points,
            "slippage_rs": self.slippage_rs,
            "fees_rs": self.fees_rs,
            "pnl_rs": self.pnl_rs,
            "net_points": self.net_points,
            "net_bps": 1e4 * self.net_points / self.spot_entry,
            "return_on_risk": self.return_on_risk,
            "legs": ";".join(
                f"{f.lots:+d}x{int(f.strike)}{f.option_type}@{f.price:.2f}" for f in self.entry_fills
            ),
            **{f"meta_{k}": v for k, v in self.meta.items()},
        }


class ChainBook:
    """Fast, lazy lookups into the option chain by (trade date, expiry).

    The chain is sorted once and the row range of every (date, expiry) block is recorded; a block
    is turned into a DataFrame (and a strike lookup) only when a strategy touches it.
    """

    def __init__(self, chain: pd.DataFrame, settlements: pd.DataFrame) -> None:
        c = chain.sort_values(["trade_date", "expiry", "strike", "option_type"]).reset_index(drop=True)
        self.chain = c
        td = c["trade_date"].to_numpy()
        ex = c["expiry"].to_numpy()
        change = np.r_[True, (td[1:] != td[:-1]) | (ex[1:] != ex[:-1])]
        starts = np.flatnonzero(change)
        ends = np.r_[starts[1:], len(c)]
        first = c.iloc[starts]
        self.blocks = pd.DataFrame(
            {
                "trade_date": first["trade_date"].to_numpy(),
                "expiry": first["expiry"].to_numpy(),
                "tdte": first["tdte"].to_numpy(),
                "dte": first["dte"].to_numpy(),
                "is_monthly": first["is_monthly"].to_numpy(),
                "start": starts,
                "end": ends,
            }
        )
        self._range = {
            (pd.Timestamp(d), pd.Timestamp(e)): (int(a), int(b))
            for d, e, a, b in zip(self.blocks["trade_date"], self.blocks["expiry"], starts, ends, strict=True)
        }
        self._meta = {
            (pd.Timestamp(d), pd.Timestamp(e)): (int(t), bool(m))
            for d, e, t, m in zip(
                self.blocks["trade_date"],
                self.blocks["expiry"],
                self.blocks["tdte"],
                self.blocks["is_monthly"],
                strict=True,
            )
        }
        self.settlement = settlements.set_index("expiry")["settlement"]
        self.sessions = pd.Index(sorted(c["trade_date"].unique()))
        self.expiries_on: dict[pd.Timestamp, list[pd.Timestamp]] = {
            pd.Timestamp(d): sorted(pd.Timestamp(x) for x in g["expiry"])
            for d, g in self.blocks.groupby("trade_date")
        }
        self._slices: dict[tuple[pd.Timestamp, pd.Timestamp], pd.DataFrame] = {}
        self._lookup: dict[tuple[pd.Timestamp, pd.Timestamp], dict[tuple[float, str], int]] = {}
        self._atm: dict[tuple[pd.Timestamp, pd.Timestamp], pd.Series | None] = {}

    def tdte(self, d: pd.Timestamp, expiry: pd.Timestamp) -> int:
        """Sessions left to expiry on ``d``, counting expiry day."""
        return self._meta[(d, expiry)][0]

    def is_monthly(self, d: pd.Timestamp, expiry: pd.Timestamp) -> bool:
        return self._meta[(d, expiry)][1]

    def slice(self, d: pd.Timestamp, expiry: pd.Timestamp) -> pd.DataFrame | None:
        key = (d, expiry)
        if key not in self._slices:
            rng = self._range.get(key)
            if rng is None:
                return None
            self._slices[key] = self.chain.iloc[rng[0] : rng[1]].reset_index(drop=True)
        return self._slices[key]

    def atm(self, d: pd.Timestamp, expiry: pd.Timestamp) -> pd.Series | None:
        """ATM strike, straddle price and IV for one expiry on one day (memoised)."""
        key = (d, expiry)
        if key not in self._atm:
            s = self.slice(d, expiry)
            self._atm[key] = atm_row(s) if s is not None else None
        return self._atm[key]

    def quote(
        self, d: pd.Timestamp, expiry: pd.Timestamp, strike: float, option_type: str
    ) -> dict[str, Any] | None:
        key = (d, expiry)
        s = self.slice(d, expiry)
        if s is None:
            return None
        if key not in self._lookup:
            self._lookup[key] = {
                (float(k), str(t)): i
                for i, (k, t) in enumerate(zip(s["strike"], s["option_type"], strict=True))
            }
        i = self._lookup[key].get((float(strike), option_type))
        if i is None:
            return None
        row: dict[str, Any] = s.iloc[i].to_dict()
        return row

    def next_session(self, d: pd.Timestamp) -> pd.Timestamp | None:
        i = self.sessions.searchsorted(d, side="right")
        return self.sessions[i] if i < len(self.sessions) else None


@dataclass
class ExecutionModel:
    slippage: Slippage = field(default_factory=Slippage)
    broker: Broker = UPSTOX
    min_contracts: float = 50.0


def _fill_legs(
    book: ChainBook,
    d: pd.Timestamp,
    expiry: pd.Timestamp,
    legs: Iterable[LegSpec],
    ex: ExecutionModel,
    price_field: str = "close",
    opening: bool = True,
) -> list[Fill] | None:
    fills = []
    for leg in legs:
        q = book.quote(d, expiry, leg.strike, leg.option_type)
        if q is None or not bool(q["traded"]) or float(q["contracts"]) < ex.min_contracts:
            if not opening and leg.lots > 0:
                # A long hedge leg with no trade on the exit day: assume it is sold for one tick.
                # Dropping the trade instead would quietly discard exits that went badly.
                fills.append(
                    Fill(leg.option_type, leg.strike, leg.lots, ex.slippage.tick, ex.slippage.tick, 0.0)
                )
                continue
            return None
        px = float(q[price_field])
        if not np.isfinite(px) or px <= 0:
            return None
        buying = (leg.lots > 0) == opening
        slip = ex.slippage.per_unit(px)
        fill_px = px + slip if buying else max(px - slip, 0.05)
        fills.append(Fill(leg.option_type, leg.strike, leg.lots, px, fill_px, float(q["contracts"])))
    return fills


def _intrinsic(option_type: str, strike: float, s: float) -> float:
    return max(s - strike, 0.0) if option_type == "CE" else max(strike - s, 0.0)


def max_loss_per_unit(legs: Iterable[LegSpec], credit: float) -> float:
    """Worst-case loss per unit at expiry for a static option structure (inf if unbounded)."""
    legs = list(legs)
    calls = sum(leg.lots for leg in legs if leg.option_type == "CE")
    if calls < 0:  # net short calls: unbounded upside loss
        return float("inf")
    strikes = sorted({leg.strike for leg in legs})
    grid = [0.0, *strikes, strikes[-1] * 2]
    payoff = [sum(leg.lots * _intrinsic(leg.option_type, leg.strike, s) for leg in legs) for s in grid]
    worst = min(payoff) + credit
    return max(-worst, 0.0)


def simulate(
    book: ChainBook,
    strategy: str,
    symbol: str,
    entry: pd.Timestamp,
    expiry: pd.Timestamp,
    legs: list[LegSpec],
    ex: ExecutionModel,
    lots: int = 1,
    exit_on: pd.Timestamp | None = None,
    exit_field: str = "close",
    meta: dict[str, Any] | None = None,
) -> Trade | None:
    """Open ``legs`` at ``entry``'s close; close at ``exit_on`` (``exit_field`` price) or hold to expiry."""
    fills = _fill_legs(book, entry, expiry, legs, ex, "close", opening=True)
    if fills is None:
        return None
    s0 = book.slice(entry, expiry)
    assert s0 is not None
    lot_size = int(s0["lot_size"].iloc[0])
    spot = float(s0["spot"].iloc[0])
    units = lot_size * lots
    d_entry = entry.date()

    credit = -sum(f.lots * f.price for f in fills)  # per unit, at quoted prices
    fees = sum(
        option_trade_cost(
            d_entry, f.fill_price, abs(f.lots) * units, "BUY" if f.lots > 0 else "SELL", ex.broker
        )
        for f in fills
    )
    slip = sum(abs(f.fill_price - f.price) * abs(f.lots) * units for f in fills)

    if exit_on is None or exit_on >= expiry:
        settle = float(book.settlement.get(expiry, np.nan))
        if not np.isfinite(settle):
            return None
        values = [_intrinsic(f.option_type, f.strike, settle) for f in fills]
        fees += sum(
            exercise_cost(expiry.date(), v, f.lots * units)
            for f, v in zip(fills, values, strict=True)
            if f.lots > 0 and v > 0
        )
        exit_date, exit_kind, exit_ref = expiry, "expiry", settle
    else:
        exits = _fill_legs(
            book,
            exit_on,
            expiry,
            [LegSpec(f.option_type, f.strike, f.lots) for f in fills],
            ex,
            exit_field,
            opening=False,
        )
        if exits is None:
            return None
        values = [e.price for e in exits]
        fees += sum(
            option_trade_cost(
                exit_on.date(), e.fill_price, abs(e.lots) * units, "SELL" if e.lots > 0 else "BUY", ex.broker
            )
            for e in exits
        )
        slip += sum(abs(e.fill_price - e.price) * abs(e.lots) * units for e in exits)
        s1 = book.slice(exit_on, expiry)
        exit_ref = float(s1["spot"].iloc[0]) if s1 is not None else float("nan")
        exit_date, exit_kind = exit_on, exit_field

    gross = sum(f.lots * (v - f.price) for f, v in zip(fills, values, strict=True))
    pnl = gross * units - slip - fees
    return Trade(
        strategy=strategy,
        symbol=symbol,
        entry_date=d_entry,
        expiry=expiry.date(),
        exit_date=exit_date.date(),
        exit_kind=exit_kind,
        lot_size=lot_size,
        lots=lots,
        spot_entry=spot,
        exit_ref=exit_ref,
        entry_fills=fills,
        exit_values=values,
        credit_points=credit,
        max_loss_points=max_loss_per_unit(legs, credit),
        gross_points=gross,
        slippage_rs=slip,
        fees_rs=fees,
        pnl_rs=pnl,
        meta=meta or {},
    )


def trades_frame(trades: Iterable[Trade | None]) -> pd.DataFrame:
    rows = [t.as_row() for t in trades if t is not None]
    return pd.DataFrame(rows)
