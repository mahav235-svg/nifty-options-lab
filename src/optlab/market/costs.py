"""Transaction costs for NSE index derivatives, by date.

Every statutory rate here changed at least once between 2018 and 2026, and the April 2026 STT
increase alone moves the break-even of a short-premium strategy materially, so costs are looked
up for the trade date rather than fixed. Rates are fractions (0.001 = 0.1%).

Sources: STT from NSE/FATAX/56235 and the 2024 and 2026 Budget memoranda; exchange charges from
NSE/FA/46730, 56129, 73061; stamp duty and SEBI fee from broker charge pages; see
docs/costs.md for the full table with links.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Rates:
    stt_option_sell: float  # on premium, sell side
    stt_exercise: float  # on intrinsic value of long ITM options settled at expiry
    stt_future_sell: float
    exch_option: float  # on premium, both sides
    exch_future: float
    sebi_fee: float = 10 / 1e7  # Rs 10 per crore
    stamp_option_buy: float = 0.00003
    stamp_future_buy: float = 0.00002
    gst: float = 0.18


# (effective from, rates); a period runs until the next entry's start date
_SCHEDULE: list[tuple[date, Rates]] = [
    (date(2000, 1, 1), Rates(0.0005, 0.00125, 0.0001, 0.00050, 0.000019)),
    (date(2021, 1, 1), Rates(0.0005, 0.00125, 0.0001, 0.00053, 0.000020)),
    (date(2023, 4, 1), Rates(0.000625, 0.00125, 0.000125, 0.000505, 0.000020)),
    (date(2024, 10, 1), Rates(0.001, 0.00125, 0.0002, 0.0003553, 0.0000183)),
    (date(2026, 3, 1), Rates(0.001, 0.00125, 0.0002, 0.0003553, 0.0000183)),
    (date(2026, 4, 1), Rates(0.0015, 0.0015, 0.0005, 0.0003553, 0.0000183)),
]


def rates_on(d: date) -> Rates:
    current = _SCHEDULE[0][1]
    for start, r in _SCHEDULE:
        if d >= start:
            current = r
    return current


@dataclass(frozen=True)
class Broker:
    """Per-order brokerage. Upstox Basic and Groww charge a flat Rs 20 per executed F&O order."""

    name: str = "upstox"
    per_order: float = 20.0
    future_pct_cap: float = 0.0005  # Upstox: Rs 20 or 0.05%, whichever is lower, for futures

    def option_order(self) -> float:
        return self.per_order

    def future_order(self, turnover: float) -> float:
        return min(self.per_order, self.future_pct_cap * turnover)


UPSTOX = Broker()


def option_trade_cost(d: date, premium: float, qty: int, side: str, broker: Broker = UPSTOX) -> float:
    """All-in cost in rupees for one option order (premium per unit, qty in units)."""
    r = rates_on(d)
    turnover = premium * qty
    brokerage = broker.option_order()
    exch = r.exch_option * turnover
    sebi = r.sebi_fee * turnover
    stt = r.stt_option_sell * turnover if side == "SELL" else 0.0
    stamp = r.stamp_option_buy * turnover if side == "BUY" else 0.0
    gst = r.gst * (brokerage + exch + sebi)
    return brokerage + exch + sebi + stt + stamp + gst


def exercise_cost(d: date, intrinsic: float, qty: int) -> float:
    """STT charged on a long ITM option settled at expiry (no brokerage: no order is placed)."""
    return rates_on(d).stt_exercise * intrinsic * qty


def future_trade_cost(d: date, price: float, qty: int, side: str, broker: Broker = UPSTOX) -> float:
    r = rates_on(d)
    turnover = price * qty
    brokerage = broker.future_order(turnover)
    exch = r.exch_future * turnover
    sebi = r.sebi_fee * turnover
    stt = r.stt_future_sell * turnover if side == "SELL" else 0.0
    stamp = r.stamp_future_buy * turnover if side == "BUY" else 0.0
    gst = r.gst * (brokerage + exch + sebi)
    return brokerage + exch + sebi + stt + stamp + gst


@dataclass(frozen=True)
class Slippage:
    """Execution cost beyond fees, as a price concession per unit on each fill.

    Bhavcopy has no quotes, so this is an assumption: half a typical spread plus one tick,
    with the spread growing with option price. ``multiplier`` is the stress-test knob.
    """

    tick: float = 0.05
    pct_of_price: float = 0.005
    min_ticks: float = 1.0
    multiplier: float = 1.0

    def per_unit(self, price: float) -> float:
        half_spread = max(self.min_ticks * self.tick, self.pct_of_price * price)
        return self.multiplier * (half_spread + self.tick)
