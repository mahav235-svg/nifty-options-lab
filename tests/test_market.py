from datetime import date

import numpy as np
import pytest

from optlab.market.contracts import lot_size
from optlab.market.costs import Slippage, exercise_cost, option_trade_cost, rates_on
from optlab.market.pricing import black76, delta, implied_vol


def test_black76_put_call_parity_and_iv_roundtrip() -> None:
    f, k, t, s = 22000.0, np.array([21000.0, 22000.0, 23000.0]), 7 / 365, 0.14
    c = black76(f, k, t, s, True)
    p = black76(f, k, t, s, False)
    assert np.allclose(c - p, f - k, atol=1e-8)
    assert np.allclose(implied_vol(c, f, k, t, True), s, atol=1e-6)
    assert np.allclose(implied_vol(p, f, k, t, False), s, atol=1e-6)


def test_iv_is_nan_outside_arbitrage_bounds() -> None:
    assert np.isnan(implied_vol(np.array([0.5]), 22000.0, 21000.0, 7 / 365, True))[0]  # below intrinsic
    assert np.isnan(implied_vol(np.array([10.0]), 22000.0, 22000.0, 0.0, True))[0]  # expired


def test_delta_signs() -> None:
    assert 0.4 < float(delta(22000, 22000, 0.02, 0.15, True)) < 0.6
    assert -0.6 < float(delta(22000, 22000, 0.02, 0.15, False)) < -0.4


@pytest.mark.parametrize(
    ("expiry", "monthly", "lot"),
    [
        (date(2019, 6, 27), True, 75),
        (date(2021, 7, 22), False, 75),
        (date(2021, 7, 29), True, 50),
        (date(2024, 4, 25), True, 50),
        (date(2024, 5, 2), False, 25),
        (date(2025, 1, 2), False, 75),
        (date(2026, 1, 6), False, 65),
    ],
)
def test_nifty_lot_schedule(expiry: date, monthly: bool, lot: int) -> None:
    assert lot_size("NIFTY", expiry, monthly) == lot


def test_stt_regimes() -> None:
    assert rates_on(date(2022, 6, 1)).stt_option_sell == 0.0005
    assert rates_on(date(2024, 10, 1)).stt_option_sell == 0.001
    assert rates_on(date(2026, 4, 1)).stt_option_sell == 0.0015
    assert rates_on(date(2026, 4, 1)).stt_future_sell == 0.0005


def test_option_cost_breakdown() -> None:
    # sell 75 units at 100 on 2 Jan 2025: turnover 7,500
    cost = option_trade_cost(date(2025, 1, 2), 100.0, 75, "SELL")
    brokerage, exch, sebi, stt = 20.0, 0.0003553 * 7500, 7500 / 1e6, 0.001 * 7500
    assert cost == pytest.approx(brokerage + exch + sebi + stt + 0.18 * (brokerage + exch + sebi))
    buy = option_trade_cost(date(2025, 1, 2), 100.0, 75, "BUY")
    assert buy < cost  # no STT on buys, only stamp duty
    assert exercise_cost(date(2026, 5, 5), 50.0, 65) == pytest.approx(0.0015 * 50 * 65)


def test_slippage_floor_and_scaling() -> None:
    s = Slippage()
    assert s.per_unit(2.0) == pytest.approx(0.05 + 0.05)
    assert s.per_unit(200.0) == pytest.approx(1.0 + 0.05)
    assert Slippage(multiplier=2).per_unit(200.0) == pytest.approx(2.1)


def test_holiday_expiry_maps_to_previous_session() -> None:
    import pandas as pd

    from optlab.data.chain import actual_expiry

    sessions = pd.Index(pd.to_datetime(["2023-03-28", "2023-03-29", "2023-03-31"]))
    exp = pd.Series(pd.to_datetime(["2023-03-30", "2023-03-29", "2023-04-27"]))
    out = actual_expiry(exp, sessions)
    assert list(out) == list(pd.to_datetime(["2023-03-29", "2023-03-29", "2023-04-27"]))
