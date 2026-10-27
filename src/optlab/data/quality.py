"""Data-quality checks run after every build. Each check returns a short finding; none silently fixes data.

* sessions: trading days in the bhavcopy vs the index file (a missing day in either is a gap)
* stale rows: share of option rows with a close but no trades (legacy files carry old closes)
* forward vs spot: the implied forward should sit within a few tenths of a percent of spot
* IV sanity: share of traded near-the-money rows with a solvable implied volatility
* settlement: every expiry has an official index close
"""

from __future__ import annotations

import pandas as pd

from optlab.paths import PROCESSED


def report(symbol: str = "NIFTY") -> str:
    chain = pd.read_parquet(PROCESSED / "chain" / symbol)
    spot = pd.read_parquet(PROCESSED / "index" / f"{symbol}_daily.parquet")
    settle = pd.read_parquet(PROCESSED / f"settlements_{symbol}.parquet")
    lines = [
        f"{symbol} option chain: {len(chain):,} rows, {chain['trade_date'].min():%Y-%m-%d} to "
        f"{chain['trade_date'].max():%Y-%m-%d}"
    ]

    chain_days = set(chain["trade_date"].unique())
    spot_days = set(spot.loc[spot["date"] >= chain["trade_date"].min(), "date"])
    lines.append(
        f"sessions: {len(chain_days)} in bhavcopy, {len(spot_days)} in index file; "
        f"{len(spot_days - chain_days)} index-only, {len(chain_days - spot_days)} bhavcopy-only"
    )

    lines.append(f"untraded option rows (never filled against): {100 * (~chain['traded']).mean():.1f}%")

    per_day = chain.groupby("trade_date")[["forward", "spot"]].first()
    basis = (per_day["forward"] / per_day["spot"] - 1).abs()
    lines.append(
        f"|forward/spot - 1|: median {100 * basis.median():.3f}%, 99th pct {100 * basis.quantile(0.99):.3f}%"
    )

    ntm = chain[
        chain["traded"] & ((chain["strike"] / chain["forward"] - 1).abs() < 0.02) & (chain["dte"] > 0)
    ]
    lines.append(f"near-the-money traded rows with an implied vol: {100 * ntm['iv'].notna().mean():.1f}%")
    lines.append(
        f"ATM implied vol percentiles (5/50/95): "
        f"{ntm['iv'].quantile(0.05):.3f} / {ntm['iv'].median():.3f} / {ntm['iv'].quantile(0.95):.3f}"
    )

    missing = settle["settlement"].isna().sum()
    lines.append(f"expiries without a settlement price: {missing} of {len(settle)}")
    lots = chain.groupby(chain["expiry"].dt.year)["lot_size"].agg(lambda s: sorted(s.unique()))
    lines.append("lot sizes by expiry year: " + ", ".join(f"{y}: {v}" for y, v in lots.items()))
    return "\n".join(lines)
