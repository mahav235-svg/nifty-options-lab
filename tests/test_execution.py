from datetime import date

from optlab.execution.broker import OptionContract, OrderStatus, Quote, Side
from optlab.execution.orders import WorkingPolicy, execute_structure, round_to_tick, work_order
from optlab.execution.paper import PaperBroker

C1 = OptionContract("NSE_FO|1", "NIFTY 22000 CE", "NIFTY", date(2026, 10, 20), 22000, "CE", 65)
C2 = OptionContract("NSE_FO|2", "NIFTY 21000 PE", "NIFTY", date(2026, 10, 20), 21000, "PE", 65)


def _broker(quotes: dict[str, Quote]) -> PaperBroker:
    return PaperBroker(
        lambda keys: {k: quotes[k] for k in keys}, lambda u, e: [C1, C2], lambda u: [], lambda u: 22000.0
    )


def _no_sleep(seconds: float) -> None:
    return None


def test_round_to_tick_is_never_more_aggressive() -> None:
    assert round_to_tick(10.03, 0.05, Side.BUY) == 10.0
    assert round_to_tick(10.03, 0.05, Side.SELL) == 10.05


def test_order_walks_from_mid_to_touch_and_fills() -> None:
    b = _broker({"NSE_FO|1": Quote("NSE_FO|1", bid=10.0, ask=11.0, ltp=10.5)})
    r = work_order(b, C1, Side.BUY, 65, WorkingPolicy(steps=4, wait_seconds=0), "t", sleep=_no_sleep)
    assert r.status is OrderStatus.COMPLETE and r.avg_price == 11.0


def test_wide_spread_is_refused() -> None:
    b = _broker({"NSE_FO|1": Quote("NSE_FO|1", bid=1.0, ask=9.0, ltp=5.0)})
    r = work_order(
        b, C1, Side.BUY, 65, WorkingPolicy(max_spread_ticks=10, wait_seconds=0), "t", sleep=_no_sleep
    )
    assert r.status is OrderStatus.REJECTED and r.order_id is None


def test_failed_short_leg_unwinds_the_long() -> None:
    quotes = {
        "NSE_FO|1": Quote("NSE_FO|1", bid=10.0, ask=10.5, ltp=10.2),
        "NSE_FO|2": Quote("NSE_FO|2", bid=0.0, ask=0.0, ltp=5.0),
    }  # no bid, so the sell never fills
    b = _broker(quotes)
    policy = WorkingPolicy(wait_seconds=0, max_spread_ticks=10**9)
    res = execute_structure(b, [(C2, Side.SELL, 65), (C1, Side.BUY, 65)], policy, "t", sleep=_no_sleep)
    assert res[0].side is Side.BUY and res[0].filled == 65  # long leg goes first
    assert res[1].filled == 0
    assert b.positions() == []  # the long was sold back


def test_round_to_tick_survives_float_error() -> None:
    assert round_to_tick(1.85, 0.05, Side.BUY) == 1.85
    assert round_to_tick(0.15, 0.05, Side.SELL) == 0.15
