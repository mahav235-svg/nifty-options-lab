from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from optlab.backtest.engine import ChainBook


def chain_rows(
    trade_date: str,
    expiry: str,
    spot: float,
    prices: dict[tuple[float, str], float],
    contracts: float = 1000.0,
    lot: int = 75,
    tdte: int = 4,
    monthly: bool = False,
) -> list[dict[str, Any]]:
    rows = []
    for (k, t), px in prices.items():
        rows.append(
            {
                "trade_date": pd.Timestamp(trade_date),
                "expiry": pd.Timestamp(expiry),
                "strike": k,
                "option_type": t,
                "open": px,
                "high": px,
                "low": px,
                "close": px,
                "settle": px,
                "contracts": contracts,
                "open_interest": 1e5,
                "traded": contracts > 0,
                "lot_size": lot,
                "is_monthly": monthly,
                "spot": spot,
                "spot_open": spot,
                "forward": spot,
                "dte": 5,
                "tdte": tdte,
                "iv": 0.15,
                "delta": 0.5 if t == "CE" else -0.5,
            }
        )
    return rows


PRICES = {
    (21400.0, "PE"): 30.0,
    (21500.0, "PE"): 55.0,
    (21600.0, "PE"): 95.0,
    (21600.0, "CE"): 100.0,
    (21700.0, "CE"): 60.0,
    (21800.0, "CE"): 32.0,
}


@pytest.fixture
def book() -> ChainBook:
    """One weekly expiry on 2024-01-25; entry on 2024-01-19 with spot 21,600; settles at 21,750."""
    rows = chain_rows("2024-01-19", "2024-01-25", 21600.0, PRICES)
    rows += chain_rows("2024-01-22", "2024-01-25", 21650.0, {k: v * 0.8 for k, v in PRICES.items()}, tdte=3)
    chain = pd.DataFrame(rows)
    settlements = pd.DataFrame({"expiry": [pd.Timestamp("2024-01-25")], "settlement": [21750.0]})
    return ChainBook(chain, settlements)
