"""Walk-forward selection over a fixed grid of pre-registered variants.

Every variant's trades are computed once over the whole history (each trade only uses data up
to its own entry). Selection then happens on a calendar: at each re-selection date, the variant
with the best score on the trailing ``lookback`` window is chosen and only its trades that *enter*
in the following ``step`` window are kept. The stitched out-of-sample record is what we judge.

Scoring uses return on risk (net P&L / maximum loss), so trades with different lot sizes and
volatility levels are comparable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from optlab.backtest.metrics import sharpe

Score = Callable[[pd.Series], float]


def score_sharpe(x: pd.Series) -> float:
    return sharpe(x.to_numpy()) if len(x) >= 10 else -np.inf


def score_mean_over_cvar(x: pd.Series) -> float:
    if len(x) < 10:
        return -np.inf
    worst = np.sort(x.to_numpy())[: max(1, int(np.ceil(0.05 * len(x))))].mean()
    return float(x.mean() / abs(worst)) if worst < 0 else float("inf")


@dataclass(frozen=True)
class WalkForward:
    lookback_days: int = 3 * 365
    step_months: int = 6
    start: pd.Timestamp = field(default_factory=lambda: pd.Timestamp("2021-01-01"))
    min_trades: int = 15
    value_col: str = "return_on_risk"

    def run(
        self, trades_by_variant: dict[str, pd.DataFrame], score: Score = score_sharpe
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Return (out-of-sample trades, selection log)."""
        end = max(df["entry_date"].max() for df in trades_by_variant.values() if not df.empty)
        picks = []
        oos = []
        t = self.start
        while t <= end:
            nxt = t + pd.DateOffset(months=self.step_months)
            best, best_score = None, -np.inf
            for name, df in trades_by_variant.items():
                if df.empty:
                    continue
                # trades that both entered and settled before the decision date
                hist = df[
                    (df["entry_date"] >= t - pd.Timedelta(days=self.lookback_days)) & (df["exit_date"] < t)
                ]
                if len(hist) < self.min_trades:
                    continue
                s = score(hist[self.value_col])
                if s > best_score:
                    best, best_score = name, s
            picks.append({"from": t, "to": nxt, "variant": best, "score": best_score})
            if best is not None and best_score > 0:
                df = trades_by_variant[best]
                oos.append(df[(df["entry_date"] >= t) & (df["entry_date"] < nxt)].assign(selected=best))
            t = nxt
        oos_df = pd.concat(oos, ignore_index=True) if oos else pd.DataFrame()
        return oos_df, pd.DataFrame(picks)
