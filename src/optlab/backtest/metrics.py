"""Performance statistics, with the corrections needed to avoid fooling ourselves.

* ``summary``: per-trade and annualised figures, tail risk (CVaR, worst trade, share of P&L lost
  in the worst 5% of trades) and drawdown on a fixed-capital equity curve.
* ``bootstrap_ci``: a stationary block bootstrap of the mean, so clustered losses (volatility
  regimes) widen the interval as they should.
* ``deflated_sharpe``: Bailey and Lopez de Prado (2014). The probability that the true Sharpe
  ratio is above zero after accounting for the number of strategy variants tried, skewness and
  fat tails. Short-volatility returns are heavily left-skewed, which this penalises.
* ``pbo``: probability of backtest overfitting via combinatorially symmetric cross-validation
  (Bailey, Borwein, Lopez de Prado and Zhu 2017).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy import stats

EULER = 0.5772156649015329


def sharpe(x: Sequence[float] | np.ndarray) -> float:
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) < 2 or a.std(ddof=1) == 0:
        return float("nan")
    return float(a.mean() / a.std(ddof=1))


def t_stat(x: Sequence[float] | np.ndarray) -> float:
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    return sharpe(a) * math.sqrt(len(a)) if len(a) > 1 else float("nan")


def cvar(x: Sequence[float] | np.ndarray, alpha: float = 0.05) -> float:
    """Mean of the worst ``alpha`` share of outcomes."""
    a = np.sort(np.asarray(x, dtype=float))
    k = max(1, math.ceil(alpha * len(a)))
    return float(a[:k].mean())


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float((equity - peak).min())


def summary(trades: pd.DataFrame, capital: float = 150_000.0, pnl_col: str = "pnl_rs") -> dict[str, float]:
    """Statistics for a set of trades, one position at a time on a fixed capital base."""
    if trades.empty:
        return {"n": 0}
    t = trades.sort_values("exit_date")
    pnl = t[pnl_col].to_numpy(dtype=float)
    years = max((t["exit_date"].max() - t["entry_date"].min()).days / 365.25, 1e-9)
    per_year = len(t) / years
    equity = capital + pd.Series(pnl, index=t["exit_date"]).cumsum()
    worst5 = np.sort(pnl)[: max(1, math.ceil(0.05 * len(pnl)))]
    gains = pnl[pnl > 0].sum()
    return {
        "n": float(len(t)),
        "trades_per_year": per_year,
        "mean_rs": float(pnl.mean()),
        "median_rs": float(np.median(pnl)),
        "hit_rate": float((pnl > 0).mean()),
        "avg_win_rs": float(pnl[pnl > 0].mean()) if (pnl > 0).any() else 0.0,
        "avg_loss_rs": float(pnl[pnl <= 0].mean()) if (pnl <= 0).any() else 0.0,
        "worst_rs": float(pnl.min()),
        "cvar5_rs": cvar(pnl),
        "worst5pct_share_of_gains": float(-worst5.sum() / gains) if gains > 0 else float("inf"),
        "total_rs": float(pnl.sum()),
        "annual_return_pct": float(100 * pnl.sum() / capital / years),
        "sharpe_per_trade": sharpe(pnl),
        "sharpe_annual": sharpe(pnl) * math.sqrt(per_year),
        "t_stat": t_stat(pnl),
        "skew": float(stats.skew(pnl)) if len(pnl) > 2 else float("nan"),
        "kurtosis": float(stats.kurtosis(pnl, fisher=False)) if len(pnl) > 3 else float("nan"),
        "max_drawdown_rs": max_drawdown(equity),
        "max_drawdown_pct": float(100 * max_drawdown(equity) / capital),
        "fees_share_of_gross": float(
            (t["fees_rs"].sum() + t["slippage_rs"].sum())
            / max(abs((t["gross_points"] * t["lot_size"] * t["lots"]).sum()), 1e-9)
        ),
    }


def bootstrap_ci(
    x: Sequence[float] | np.ndarray, n_boot: int = 5000, block: int = 4, alpha: float = 0.05, seed: int = 7
) -> tuple[float, float]:
    """Stationary block bootstrap (Politis and Romano) confidence interval for the mean."""
    a = np.asarray(x, dtype=float)
    n = len(a)
    if n < 5:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    p = 1.0 / block
    means = np.empty(n_boot)
    for b in range(n_boot):
        idx = np.empty(n, dtype=int)
        idx[0] = rng.integers(n)
        for i in range(1, n):
            idx[i] = rng.integers(n) if rng.random() < p else (idx[i - 1] + 1) % n
        means[b] = a[idx].mean()
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def expected_max_sharpe(n_trials: int, var_sharpe: float) -> float:
    """Expected maximum of ``n_trials`` Sharpe ratios drawn under the null of zero skill."""
    if n_trials <= 1:
        return 0.0
    z1 = stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1 - 1.0 / (n_trials * math.e))
    return math.sqrt(var_sharpe) * ((1 - EULER) * z1 + EULER * z2)


def deflated_sharpe(
    returns: Sequence[float] | np.ndarray, n_trials: int, trial_sharpes: Sequence[float] | None = None
) -> float:
    """Probability that the true per-period Sharpe ratio exceeds the best one expected by luck.

    ``trial_sharpes`` (the Sharpe ratios of all variants tried) gives the dispersion of the null;
    without it a conservative default variance of 1/T is used.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    t = len(r)
    if t < 10:
        return float("nan")
    sr = sharpe(r)
    var_sr = (
        float(np.var(trial_sharpes, ddof=1))
        if trial_sharpes is not None and len(trial_sharpes) > 1
        else 1.0 / t
    )
    sr0 = expected_max_sharpe(n_trials, var_sr)
    g3 = stats.skew(r)
    g4 = stats.kurtosis(r, fisher=False)
    denom = math.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr**2, 1e-12))
    return float(stats.norm.cdf((sr - sr0) * math.sqrt(t - 1) / denom))


def pbo(perf: pd.DataFrame, n_splits: int = 8) -> float:
    """Probability of backtest overfitting.

    ``perf`` has one column per strategy variant and one row per period (for example monthly
    P&L). The rows are cut into ``n_splits`` blocks; for every way of choosing half the blocks as
    in-sample, the best in-sample variant is ranked out of sample. PBO is the share of splits in
    which that variant lands in the bottom half out of sample.
    """
    m = perf.to_numpy(dtype=float)
    blocks = np.array_split(np.arange(len(m)), n_splits)
    below = 0
    total = 0
    for chosen in itertools.combinations(range(n_splits), n_splits // 2):
        is_idx = np.concatenate([blocks[i] for i in chosen])
        oos_idx = np.concatenate([blocks[i] for i in range(n_splits) if i not in chosen])
        is_score = np.nanmean(m[is_idx], axis=0) / (np.nanstd(m[is_idx], axis=0) + 1e-12)
        oos_score = np.nanmean(m[oos_idx], axis=0) / (np.nanstd(m[oos_idx], axis=0) + 1e-12)
        best = int(np.nanargmax(is_score))
        rank = stats.rankdata(oos_score)[best] / (m.shape[1] + 1)
        below += int(rank <= 0.5)
        total += 1
    return below / total if total else float("nan")
