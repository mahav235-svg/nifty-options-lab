"""Working limit orders into a fill.

Options books are thin away from the money, and a market order can fill several ticks through the
touch. Each leg is worked as a limit order: start at the mid, then step towards the far side of
the spread a few times, and give up (cancel) if the order still has not filled. The step count and
wait are small because the runner trades in the final minutes before 15:30.

Legs are sent long legs first: the broker then sees a hedged position when the short legs arrive,
which keeps the margin requirement at the defined-risk level instead of the naked one.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from optlab.execution.broker import (
    Broker,
    OptionContract,
    OrderRequest,
    OrderStatus,
    OrderUpdate,
    Quote,
    Side,
)

log = logging.getLogger(__name__)


def round_to_tick(price: float, tick: float, side: Side) -> float:
    """Round towards a less aggressive price (down for buys, up for sells).

    The ratio is rounded to 6 places first: 1.85 / 0.05 is 36.99999... in floating point, and
    flooring that would quietly move a buy at the ask one tick below it.
    """
    steps = round(price / tick, 6)
    n = math.floor(steps) if side is Side.BUY else math.ceil(steps)
    return round(max(n * tick, tick), 2)


@dataclass
class WorkingPolicy:
    steps: int = 4  # repricing steps from mid to the far touch
    wait_seconds: float = 8.0  # wait per step
    max_spread_ticks: int = 40  # refuse to trade a leg wider than this


@dataclass
class LegResult:
    contract: OptionContract
    side: Side
    quantity: int
    filled: int
    avg_price: float
    order_id: str | None
    status: OrderStatus


def work_order(
    broker: Broker,
    contract: OptionContract,
    side: Side,
    quantity: int,
    policy: WorkingPolicy,
    tag: str,
    sleep: Callable[[float], None] = time.sleep,
) -> LegResult:
    q: Quote = broker.quotes([contract.instrument_key])[contract.instrument_key]
    if q.spread / contract.tick_size > policy.max_spread_ticks:
        log.warning("spread too wide on %s (%.2f); not trading", contract.symbol, q.spread)
        return LegResult(contract, side, quantity, 0, 0.0, None, OrderStatus.REJECTED)
    far = q.ask if side is Side.BUY else q.bid
    prices = [q.mid + (far - q.mid) * i / policy.steps for i in range(policy.steps + 1)]
    prices = [round_to_tick(p, contract.tick_size, side) for p in prices]
    order_id = broker.place(OrderRequest(contract, side, quantity, prices[0], tag))
    update: OrderUpdate = broker.status(order_id)
    for price in prices[1:]:
        sleep(policy.wait_seconds)
        update = broker.status(order_id)
        if update.status in (OrderStatus.COMPLETE, OrderStatus.REJECTED, OrderStatus.CANCELLED):
            break
        broker.modify(order_id, price)
    else:
        sleep(policy.wait_seconds)
        update = broker.status(order_id)
    if update.status not in (OrderStatus.COMPLETE, OrderStatus.REJECTED, OrderStatus.CANCELLED):
        broker.cancel(order_id)
        update = broker.status(order_id)
    return LegResult(contract, side, quantity, update.filled_qty, update.avg_price, order_id, update.status)


def execute_structure(
    broker: Broker,
    legs: list[tuple[OptionContract, Side, int]],
    policy: WorkingPolicy,
    tag: str,
    sleep: Callable[[float], None] = time.sleep,
) -> list[LegResult]:
    """Execute legs long-first. If any leg fails, unwind what was filled so no naked short remains."""
    ordered = sorted(legs, key=lambda x: 0 if x[1] is Side.BUY else 1)
    results: list[LegResult] = []
    for contract, side, qty in ordered:
        r = work_order(broker, contract, side, qty, policy, tag, sleep)
        results.append(r)
        if r.filled < qty:
            log.error("leg %s %s filled %d/%d; unwinding", side, contract.symbol, r.filled, qty)
            unwind(broker, results, policy, tag, sleep)
            break
    return results


def unwind(
    broker: Broker,
    results: list[LegResult],
    policy: WorkingPolicy,
    tag: str,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    # close shorts first (they carry the risk), then longs
    for r in sorted(results, key=lambda x: 0 if x.side is Side.SELL else 1):
        if r.filled > 0:
            back = Side.BUY if r.side is Side.SELL else Side.SELL
            work_order(broker, r.contract, back, r.filled, policy, f"{tag}-unwind", sleep)
