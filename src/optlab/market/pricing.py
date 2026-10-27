"""Black-76 pricing on the futures price, implied volatility and Greeks (vectorised).

NIFTY options are European and cash settled. Pricing off the matching futures price (Black 1976)
avoids having to estimate the dividend yield and the funding rate separately; both are already
in the futures basis. Where no future expires with the option (weeklies), the forward is implied
from put-call parity at the strikes nearest the money.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.special import ndtr

Arr = NDArray[np.float64]


def _d1d2(f: Arr, k: Arr, t: Arr, sigma: Arr) -> tuple[Arr, Arr]:
    vol_t = sigma * np.sqrt(t)
    d1 = (np.log(f / k) + 0.5 * vol_t**2) / vol_t
    return d1, d1 - vol_t


def black76(
    f: ArrayLike, k: ArrayLike, t: ArrayLike, sigma: ArrayLike, is_call: ArrayLike, r: float = 0.0
) -> Arr:
    f_, k_, t_, s_ = (np.asarray(x, dtype=float) for x in (f, k, t, sigma))
    call = np.asarray(is_call, dtype=bool)
    d1, d2 = _d1d2(f_, k_, t_, s_)
    disc = np.exp(-r * t_)
    c = disc * (f_ * ndtr(d1) - k_ * ndtr(d2))
    p = disc * (k_ * ndtr(-d2) - f_ * ndtr(-d1))
    return np.where(call, c, p)


def delta(f: ArrayLike, k: ArrayLike, t: ArrayLike, sigma: ArrayLike, is_call: ArrayLike) -> Arr:
    f_, k_, t_, s_ = (np.asarray(x, dtype=float) for x in (f, k, t, sigma))
    d1, _ = _d1d2(f_, k_, t_, s_)
    return np.where(np.asarray(is_call, dtype=bool), ndtr(d1), ndtr(d1) - 1.0)


def implied_vol(
    price: ArrayLike,
    f: ArrayLike,
    k: ArrayLike,
    t: ArrayLike,
    is_call: ArrayLike,
    lo: float = 0.005,
    hi: float = 3.0,
    iters: int = 80,
) -> Arr:
    """Bisection on Black-76. Robust for deep OTM and very short expiries, where Newton steps on a
    near-zero vega overshoot. Returns NaN where the price is outside no-arbitrage bounds."""
    p, f_, k_, t_ = (np.asarray(x, dtype=float) for x in (price, f, k, t))
    call = np.asarray(is_call, dtype=bool)
    intrinsic = np.where(call, np.maximum(f_ - k_, 0.0), np.maximum(k_ - f_, 0.0))
    upper = np.where(call, f_, k_)
    valid = (p > intrinsic + 1e-9) & (p < upper) & (t_ > 0)
    a = np.full(p.shape, lo)
    b = np.full(p.shape, hi)
    for _ in range(iters):
        mid = 0.5 * (a + b)
        too_high = black76(f_, k_, t_, mid, call) > p
        b = np.where(too_high, mid, b)
        a = np.where(too_high, a, mid)
    sigma = 0.5 * (a + b)
    # a solution pinned at a bound means the price is not explained by any sensible volatility
    return np.where(valid & (sigma < hi * 0.999) & (sigma > lo * 1.001), sigma, np.nan)


def year_fraction(trade_date: ArrayLike, expiry: ArrayLike) -> Arr:
    """ACT/365 from one session's close to the expiry-day close (both are dates)."""
    td = np.asarray(trade_date, dtype="datetime64[D]")
    ex = np.asarray(expiry, dtype="datetime64[D]")
    return np.maximum((ex - td).astype(float), 0.0) / 365.0
