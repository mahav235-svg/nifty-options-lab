"""Broker interface used by the live runner, and the data types that cross it."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(StrEnum):
    OPEN = "open"
    COMPLETE = "complete"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


@dataclass(frozen=True)
class OptionContract:
    instrument_key: str  # e.g. "NSE_FO|43885"
    symbol: str  # trading symbol, e.g. "NIFTY 25000 CE 21 OCT 26"
    underlying: str
    expiry: date
    strike: float
    option_type: str  # "CE" / "PE"
    lot_size: int
    tick_size: float = 0.05
    freeze_qty: int | None = None


@dataclass(frozen=True)
class Quote:
    instrument_key: str
    bid: float
    ask: float
    ltp: float
    volume: float = 0.0
    oi: float = 0.0
    iv: float | None = None
    delta: float | None = None

    @property
    def mid(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return 0.5 * (self.bid + self.ask)
        return self.ltp

    @property
    def spread(self) -> float:
        return self.ask - self.bid if self.bid > 0 and self.ask > 0 else float("inf")


@dataclass
class OrderRequest:
    contract: OptionContract
    side: Side
    quantity: int  # units, a multiple of lot size
    limit_price: float
    tag: str = "optlab"


@dataclass
class OrderUpdate:
    order_id: str
    status: OrderStatus
    filled_qty: int
    avg_price: float
    message: str = ""
    at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class Position:
    instrument_key: str
    quantity: int  # signed units
    avg_price: float


class Broker(Protocol):
    name: str

    def option_contracts(self, underlying: str, expiry: date) -> list[OptionContract]: ...

    def expiries(self, underlying: str) -> list[date]: ...

    def quotes(self, keys: list[str]) -> dict[str, Quote]: ...

    def spot(self, underlying: str) -> float: ...

    def place(self, req: OrderRequest) -> str: ...

    def modify(self, order_id: str, limit_price: float) -> None: ...

    def cancel(self, order_id: str) -> None: ...

    def status(self, order_id: str) -> OrderUpdate: ...

    def positions(self) -> list[Position]: ...

    def available_margin(self) -> float: ...
