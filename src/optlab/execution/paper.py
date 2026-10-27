"""Paper broker: real quotes from a data source, simulated fills.

Use it for the paper-trading phase before any real order is sent. A limit order fills when the
limit crosses the quote's far side (buy at or above ask, sell at or below bid) on the next status
check; otherwise it stays open. Positions and P&L are kept in memory and journaled by the runner.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from optlab.execution.broker import (
    OptionContract,
    OrderRequest,
    OrderStatus,
    OrderUpdate,
    Position,
    Quote,
    Side,
)


@dataclass
class _Order:
    req: OrderRequest
    status: OrderStatus = OrderStatus.OPEN
    filled: int = 0
    avg: float = 0.0


class PaperBroker:
    name = "paper"

    def __init__(
        self,
        quote_source: Callable[[list[str]], dict[str, Quote]],
        contracts: Callable[[str, date], list[OptionContract]],
        expiries: Callable[[str], list[date]],
        spot: Callable[[str], float],
        margin: float = 150_000.0,
        state_file: Path | None = None,
    ) -> None:
        self._quotes = quote_source
        self._contracts = contracts
        self._expiries = expiries
        self._spot = spot
        self._margin = margin
        self._orders: dict[str, _Order] = {}
        self._state_file = state_file
        self._positions: dict[str, tuple[int, float]] = {}
        if state_file is not None and state_file.exists():
            self._positions = {
                k: (int(q), float(a)) for k, (q, a) in json.loads(state_file.read_text()).items()
            }
        self._ids = itertools.count(1)

    def _save(self) -> None:
        if self._state_file is not None:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(self._positions))

    def option_contracts(self, underlying: str, expiry: date) -> list[OptionContract]:
        return self._contracts(underlying, expiry)

    def expiries(self, underlying: str) -> list[date]:
        return self._expiries(underlying)

    def quotes(self, keys: list[str]) -> dict[str, Quote]:
        return self._quotes(keys)

    def spot(self, underlying: str) -> float:
        return self._spot(underlying)

    def place(self, req: OrderRequest) -> str:
        oid = f"paper-{next(self._ids)}"
        self._orders[oid] = _Order(req)
        return oid

    def modify(self, order_id: str, limit_price: float) -> None:
        o = self._orders[order_id]
        if o.status is OrderStatus.OPEN:
            o.req.limit_price = limit_price

    def cancel(self, order_id: str) -> None:
        o = self._orders[order_id]
        if o.status is OrderStatus.OPEN:
            o.status = OrderStatus.CANCELLED

    def status(self, order_id: str) -> OrderUpdate:
        o = self._orders[order_id]
        if o.status is OrderStatus.OPEN:
            q = self._quotes([o.req.contract.instrument_key])[o.req.contract.instrument_key]
            crosses = (o.req.side is Side.BUY and q.ask > 0 and o.req.limit_price >= q.ask) or (
                o.req.side is Side.SELL and q.bid > 0 and o.req.limit_price <= q.bid
            )
            if crosses:
                o.status, o.filled, o.avg = OrderStatus.COMPLETE, o.req.quantity, o.req.limit_price
                sign = 1 if o.req.side is Side.BUY else -1
                key = o.req.contract.instrument_key
                qty, avg = self._positions.get(key, (0, 0.0))
                new_qty = qty + sign * o.filled
                self._positions[key] = (new_qty, o.avg if qty == 0 else avg)
                self._save()
        return OrderUpdate(order_id, o.status, o.filled, o.avg)

    def positions(self) -> list[Position]:
        return [Position(k, q, a) for k, (q, a) in self._positions.items() if q != 0]

    def available_margin(self) -> float:
        return self._margin
