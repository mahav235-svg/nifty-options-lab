import pandas as pd
import pytest

from optlab.backtest.engine import ChainBook, ExecutionModel, LegSpec, max_loss_per_unit, simulate
from optlab.market.costs import Slippage

CONDOR = [
    LegSpec("CE", 21700, -1),
    LegSpec("PE", 21500, -1),
    LegSpec("CE", 21800, 1),
    LegSpec("PE", 21400, 1),
]
ENTRY, EXPIRY = pd.Timestamp("2024-01-19"), pd.Timestamp("2024-01-25")


def test_max_loss_of_condor_and_naked() -> None:
    assert max_loss_per_unit(CONDOR, credit=53.0) == pytest.approx(100 - 53)
    assert max_loss_per_unit([LegSpec("CE", 21700, -1)], credit=60) == float("inf")


def test_hold_to_expiry_settles_at_intrinsic(book: ChainBook) -> None:
    ex = ExecutionModel(slippage=Slippage(multiplier=0.0), min_contracts=1)
    t = simulate(book, "test", "NIFTY", ENTRY, EXPIRY, CONDOR, ex)
    assert t is not None
    assert t.credit_points == pytest.approx(60 + 55 - 32 - 30)
    # settlement 21,750: the short 21,700 call loses 50, everything else expires worthless
    assert t.gross_points == pytest.approx(53 - 50)
    assert t.exit_kind == "expiry" and t.slippage_rs == 0
    assert t.pnl_rs == pytest.approx(3 * 75 - t.fees_rs)


def test_long_itm_leg_pays_exercise_stt(book: ChainBook) -> None:
    ex = ExecutionModel(slippage=Slippage(multiplier=0.0), min_contracts=1)
    t = simulate(book, "test", "NIFTY", ENTRY, EXPIRY, [LegSpec("CE", 21600, 1)], ex)
    assert t is not None
    exercise_stt = 0.00125 * 150 * 75  # intrinsic 150 at settlement
    assert t.fees_rs > exercise_stt
    assert t.gross_points == pytest.approx(150 - 100)


def test_untraded_leg_blocks_the_whole_structure(book: ChainBook) -> None:
    ex = ExecutionModel(min_contracts=5000)  # nothing traded that much
    assert simulate(book, "t", "NIFTY", ENTRY, EXPIRY, CONDOR, ex) is None


def test_early_exit_uses_exit_day_prices_and_slippage_both_ways(book: ChainBook) -> None:
    ex = ExecutionModel(min_contracts=1)
    t = simulate(book, "t", "NIFTY", ENTRY, EXPIRY, CONDOR, ex, exit_on=pd.Timestamp("2024-01-22"))
    assert t is not None and t.exit_kind == "close"
    assert t.gross_points == pytest.approx(53 * 0.2)  # every price fell 20%
    assert t.slippage_rs > 0


def test_untraded_long_wing_at_exit_is_sold_for_a_tick(book: ChainBook) -> None:
    # remove the 21,800 call from the exit day
    chain = book.chain[
        ~((book.chain["trade_date"] == pd.Timestamp("2024-01-22")) & (book.chain["strike"] == 21800.0))
    ]
    b2 = ChainBook(chain, book.settlement.reset_index())
    ex = ExecutionModel(slippage=Slippage(multiplier=0.0), min_contracts=1)
    t = simulate(b2, "t", "NIFTY", ENTRY, EXPIRY, CONDOR, ex, exit_on=pd.Timestamp("2024-01-22"))
    assert t is not None
    wing = next(i for i, f in enumerate(t.entry_fills) if f.strike == 21800.0)
    assert t.exit_values[wing] == 0.05
