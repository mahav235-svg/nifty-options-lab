import numpy as np
import pandas as pd

from optlab.backtest import metrics
from optlab.backtest.walkforward import WalkForward


def test_cvar_and_sharpe() -> None:
    x = np.array([1.0] * 19 + [-10.0])
    assert metrics.cvar(x, 0.05) == -10.0
    assert np.isnan(metrics.sharpe([1, 1, 1]))


def test_deflated_sharpe_falls_with_more_trials() -> None:
    r = np.random.default_rng(1).normal(0.1, 1.0, 300)
    assert metrics.deflated_sharpe(r, 1) > metrics.deflated_sharpe(r, 300)


def test_pbo_low_for_a_dominant_variant() -> None:
    perf = pd.DataFrame(np.random.default_rng(2).normal(0, 1, (96, 6)))
    perf[0] += 1.5  # one genuinely better variant
    assert metrics.pbo(perf) < 0.2


def test_bootstrap_ci_contains_mean() -> None:
    x = np.random.default_rng(3).normal(1.0, 1.0, 200)
    lo, hi = metrics.bootstrap_ci(x, n_boot=500)
    assert lo < x.mean() < hi


def _trades(start: str, n: int, value: float, sd: float = 0.01) -> pd.DataFrame:
    d = pd.date_range(start, periods=n, freq="7D")
    noise = np.random.default_rng(0).normal(0, sd, n)
    return pd.DataFrame(
        {"entry_date": d, "exit_date": d + pd.Timedelta(days=3), "return_on_risk": value + noise}
    )


def test_walk_forward_uses_only_past_trades() -> None:
    good_then_bad = pd.concat([_trades("2018-01-01", 165, 0.1), _trades("2021-03-01", 150, -0.1)])
    steady = _trades("2018-01-01", 320, 0.02, sd=0.05)
    oos, picks = WalkForward(start=pd.Timestamp("2021-01-01")).run({"a": good_then_bad, "b": steady})
    assert picks.iloc[0]["variant"] == "a"  # chosen on 2018-2020 history
    assert picks.iloc[-1]["variant"] == "b"  # switches once a's recent record turns
    assert (oos["entry_date"] >= pd.Timestamp("2021-01-01")).all()
