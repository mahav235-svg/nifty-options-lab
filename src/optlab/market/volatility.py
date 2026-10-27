"""Realised volatility estimators and the HAR forecast.

The variance risk premium filter compares option-implied volatility with a forecast of the
volatility that will actually be realised over the option's life. Two choices matter:

* the estimator: with daily OHLC only, Garman-Klass uses the intraday range and is several
  times more efficient than close-to-close; with one-minute bars (from 2022) we use 5-minute
  realised variance plus the squared overnight return;
* the forecast: HAR-RV (Corsi 2009) regresses next-period realised variance on its daily, weekly
  and monthly averages. It is simple, fits fast and is hard to beat out of sample.

The HAR fit is always expanding-window and uses only data up to the forecast date, so the
filter never sees the future.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def garman_klass(df: pd.DataFrame) -> pd.Series:
    """Daily variance from OHLC (open-to-close part) plus the squared overnight gap."""
    log_hl = np.log(df["high"] / df["low"])
    log_co = np.log(df["close"] / df["open"])
    intraday = 0.5 * log_hl**2 - (2 * np.log(2) - 1) * log_co**2
    overnight = np.log(df["open"] / df["close"].shift(1)) ** 2
    return (intraday + overnight.fillna(0.0)).rename("rv")


def close_to_close(close: pd.Series) -> pd.Series:
    return (np.log(close).diff() ** 2).rename("rv")


def intraday_rv(bars: pd.DataFrame, sample_minutes: int = 5) -> pd.Series:
    """Daily realised variance from one-minute bars, sampled every ``sample_minutes``, plus the
    squared overnight return (previous close to today's first bar)."""
    b = bars.set_index("ts")["close"]
    day = b.index.tz_convert("Asia/Kolkata").date
    out = {}
    prev_close = None
    for d, s in b.groupby(day):
        s = s.iloc[::sample_minutes]
        r = np.log(s).diff().dropna()
        rv = float((r**2).sum())
        if prev_close is not None:
            rv += float(np.log(s.iloc[0] / prev_close) ** 2)
        out[pd.Timestamp(d)] = rv
        prev_close = float(s.iloc[-1])
    return pd.Series(out, name="rv")


def har_features(rv: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rv_d": rv,
            "rv_w": rv.rolling(5).mean(),
            "rv_m": rv.rolling(22).mean(),
        }
    )


def har_forecast(
    rv: pd.Series, horizon: int, min_train: int = 500, refit_every: int = 21, exog: pd.Series | None = None
) -> pd.Series:
    """Expanding-window HAR forecast of the *average daily* variance over the next ``horizon`` days.

    The value on date t uses only information available at the close of t. ``exog`` (for example
    squared India VIX converted to daily variance) is added as an extra regressor (HAR-X).
    Returns annualised volatility.
    """
    feats = har_features(rv)
    if exog is not None:
        feats["x"] = exog.reindex(feats.index)
    target = rv[::-1].rolling(horizon).mean()[::-1].shift(-1)  # mean of rv over t+1..t+h
    data = feats.assign(y=target)
    out = pd.Series(np.nan, index=rv.index, name=f"har_vol_{horizon}d")
    beta: np.ndarray | None = None
    cols = list(feats.columns)
    idx = list(rv.index)
    for i in range(min_train, len(idx)):
        if beta is None or (i - min_train) % refit_every == 0:
            # train only on rows whose target window ended on or before t
            train = data.iloc[: i - horizon].dropna()
            if len(train) < min_train // 2:
                continue
            X = np.column_stack([np.ones(len(train)), train[cols].to_numpy()])
            beta, *_ = np.linalg.lstsq(X, train["y"].to_numpy(), rcond=None)
        row = feats.iloc[i]
        if row.isna().any():
            continue
        pred = float(beta[0] + row.to_numpy() @ beta[1:])
        out.iloc[i] = np.sqrt(max(pred, 1e-10) * TRADING_DAYS)
    return out


def vix_to_daily_variance(vix: pd.Series) -> pd.Series:
    return (vix / 100.0) ** 2 / TRADING_DAYS
