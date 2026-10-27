"""Runs the pre-registered research plan and writes the evidence to ``reports/``.

    python -m optlab.research.runner            # everything
    python -m optlab.research.runner --only h1  # one hypothesis

Outputs (all reproducible from the data layers):
    reports/trades/{variant}.parquet      every trade of every variant
    reports/summary_{hypothesis}.csv      one row per variant
    reports/walkforward_h1.csv            selection log
    reports/RESULTS.md                    the write-up numbers
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from optlab.backtest import metrics
from optlab.backtest.engine import ChainBook, ExecutionModel, trades_frame
from optlab.backtest.walkforward import WalkForward
from optlab.data.features import load_events
from optlab.market.costs import Slippage
from optlab.paths import PROCESSED, REPORTS, ROOT
from optlab.pipeline import load_chain
from optlab.strategies import intraday_momentum, others, short_vol

log = logging.getLogger(__name__)
N_TRIALS = 345  # fixed in docs/research_plan.md

REGIMES = [
    ("pre_nov2024", pd.Timestamp("2000-01-01"), pd.Timestamp("2024-11-19")),
    ("single_weekly_thu", pd.Timestamp("2024-11-20"), pd.Timestamp("2025-08-31")),
    ("tuesday_expiry", pd.Timestamp("2025-09-01"), pd.Timestamp("2100-01-01")),
]


def load_book(symbol: str) -> tuple[ChainBook, pd.DataFrame]:
    chain = load_chain(symbol)
    settlements = pd.read_parquet(PROCESSED / f"settlements_{symbol}.parquet")
    feats = pd.read_parquet(PROCESSED / "features" / f"{symbol}_daily_features.parquet")
    return ChainBook(chain, settlements), feats


def h1_grid() -> list[short_vol.ShortVolParams]:
    grid = []
    for tdte, s, w, vrp, ev in itertools.product(
        (2, 3, 4, 5), (0.0, 0.5, 0.75, 1.0, 1.25), (0.5, 1.0), (0.0, 1.0, 1.15, 1.3), (True, False)
    ):
        grid.append(
            short_vol.ShortVolParams(entry_tdte=tdte, short_em=s, wing_em=w, vrp_min=vrp, skip_events=ev)
        )
    return grid


def regime_split(df: pd.DataFrame, col: str = "pnl_rs") -> dict[str, dict[str, float]]:
    out = {}
    for name, a, b in REGIMES:
        part = df[(df["entry_date"] >= a) & (df["entry_date"] <= b)]
        out[name] = {
            "n": len(part),
            "mean": float(part[col].mean()) if len(part) else float("nan"),
            "total": float(part[col].sum()),
            "t": metrics.t_stat(part[col]) if len(part) > 2 else float("nan"),
        }
    return out


def evaluate(
    df: pd.DataFrame, n_trials: int = N_TRIALS, trial_sharpes: list[float] | None = None
) -> dict[str, Any]:
    if df.empty:
        return {"n": 0}
    s = metrics.summary(df)
    lo, hi = metrics.bootstrap_ci(df.sort_values("entry_date")["pnl_rs"].to_numpy(), n_boot=2000)
    s.update(
        {
            "ci_lo": lo,
            "ci_hi": hi,
            "deflated_sharpe": metrics.deflated_sharpe(df["pnl_rs"].to_numpy(), n_trials, trial_sharpes),
            "mean_ror": float(df["return_on_risk"].mean()) if "return_on_risk" in df else float("nan"),
        }
    )
    return s


def run_h1(
    book: ChainBook, feats: pd.DataFrame, ex: ExecutionModel, out: Path, symbol: str = "NIFTY"
) -> dict[str, pd.DataFrame]:
    """All 320 H1 variants. The 40 structures are simulated once without filters; the filtered
    variants are subsets of those trades (filters only gate entry, so this is exact)."""
    results: dict[str, pd.DataFrame] = {}
    rows = []
    structures = sorted({(p.entry_tdte, p.short_em, p.wing_em) for p in h1_grid()})
    for tdte, s_em, w_em in structures:
        base_p = short_vol.ShortVolParams(
            entry_tdte=tdte, short_em=s_em, wing_em=w_em, vrp_min=0.0, skip_events=False
        )
        base = trades_frame(short_vol.run(book, feats, base_p, ex, symbol))
        log.info("%s structure tdte=%d s=%g w=%g: %d trades", symbol, tdte, s_em, w_em, len(base))
        for p in h1_grid():
            if (p.entry_tdte, p.short_em, p.wing_em) != (tdte, s_em, w_em):
                continue
            df = short_vol.derive_filtered(base, p.vrp_min, p.skip_events) if not base.empty else base
            results[p.label()] = df
            if not df.empty:
                df.to_parquet(out / "trades" / f"{symbol}_h1_{p.label()}.parquet", index=False)
            rows.append(
                {
                    "variant": p.label(),
                    "entry_tdte": p.entry_tdte,
                    "short_em": p.short_em,
                    "wing_em": p.wing_em,
                    "vrp_min": p.vrp_min,
                    "skip_events": p.skip_events,
                    **metrics.summary(df),
                }
            )
    pd.DataFrame(rows).to_csv(out / f"summary_{symbol}_h1.csv", index=False)
    return results


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["h1", "h2", "h3", "h4", "h5", "bank"], default=None)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    out = REPORTS
    (out / "trades").mkdir(parents=True, exist_ok=True)
    ex = ExecutionModel()
    book, feats = load_book("NIFTY")
    events = load_events(ROOT / "configs" / "events.yaml")
    findings: dict[str, Any] = {}

    if args.only in (None, "h1"):
        variants = run_h1(book, feats, ex, out)
        sharpes = [metrics.sharpe(v["pnl_rs"]) for v in variants.values() if len(v) > 10]
        oos, picks = WalkForward().run(variants)
        picks.to_csv(out / "walkforward_h1.csv", index=False)
        oos.to_parquet(out / "trades" / "NIFTY_h1_walkforward_oos.parquet", index=False)
        findings["h1_walkforward"] = evaluate(oos, trial_sharpes=sharpes)
        findings["h1_walkforward_regimes"] = regime_split(oos)
        # stress: re-run the selected variants with 2x and 3x slippage
        for mult in (2.0, 3.0):
            ex2 = replace(ex, slippage=Slippage(multiplier=mult))
            stressed = {}
            for name in picks["variant"].dropna().unique():
                p = next(q for q in h1_grid() if q.label() == name)
                base_p = replace(p, vrp_min=0.0, skip_events=False)
                base = trades_frame(short_vol.run(book, feats, base_p, ex2))
                stressed[name] = short_vol.derive_filtered(base, p.vrp_min, p.skip_events)
            s_oos, _ = WalkForward().run(stressed)
            findings[f"h1_walkforward_slip{mult:g}x"] = evaluate(s_oos, trial_sharpes=sharpes)
        # PBO across the grid on monthly return-on-risk
        monthly = {
            k: v.set_index("entry_date")["return_on_risk"].resample("ME").sum()
            for k, v in variants.items()
            if len(v) > 50
        }
        perf = pd.DataFrame(monthly).fillna(0.0)
        findings["h1_pbo"] = metrics.pbo(perf) if perf.shape[1] > 2 else float("nan")

    if args.only in (None, "h2"):
        rows = []
        for sd, w, tr in itertools.product((0.20, 0.25, 0.30), (0.75, 1.0), (None, 0.0)):
            ps = others.PutSpreadParams(short_delta=sd, width_em=w, trend_min=tr)
            df = trades_frame(others.put_spread(book, feats, ps, ex))
            name = f"ps_d{sd}_w{w}_tr{tr}"
            df.to_parquet(out / "trades" / f"NIFTY_h2_{name}.parquet", index=False)
            rows.append({"variant": name, **evaluate(df)})
        pd.DataFrame(rows).to_csv(out / "summary_NIFTY_h2.csv", index=False)

    if args.only in (None, "h3"):
        rows = []
        kinds_sets = {"rbi": ("rbi_mpc",), "budget": ("union_budget",), "both": ("rbi_mpc", "union_budget")}
        for off, (kname, kinds) in itertools.product((2, 3, 5), kinds_sets.items()):
            es = others.EventStraddleParams(entry_offset=off, kinds=kinds)
            df = trades_frame(others.event_straddle(book, feats, events, es, ex))
            name = f"ev_off{off}_{kname}"
            df.to_parquet(out / "trades" / f"NIFTY_h3_{name}.parquet", index=False)
            rows.append({"variant": name, **evaluate(df)})
        pd.DataFrame(rows).to_csv(out / "summary_NIFTY_h3.csv", index=False)

    if args.only in (None, "h4"):
        df = trades_frame(others.overnight_straddle(book, feats, ex))
        df.to_parquet(out / "trades" / "NIFTY_h4_overnight.parquet", index=False)
        findings["h4_net"] = evaluate(df)
        findings["h4_gross_points_mean"] = float(df["gross_points"].mean()) if len(df) else float("nan")

    if args.only in (None, "h5"):
        bars = pd.read_parquet(PROCESSED / "index" / "NIFTY_1m.parquet")
        rows = []
        for th in (0.0, 0.25, 0.5):
            df = intraday_momentum.run(bars, intraday_momentum.MomentumParams(threshold_sd=th))
            df.to_parquet(out / "trades" / f"NIFTY_h5_th{th}.parquet", index=False)
            s = metrics.summary(df.assign(gross_points=df["gross_points"]))
            s["gross_mean_points"] = float(df["gross_points"].mean()) if len(df) else float("nan")
            s["gross_t"] = metrics.t_stat(df["gross_points"]) if len(df) > 2 else float("nan")
            rows.append({"variant": f"mom_th{th}", **s})
        pd.DataFrame(rows).to_csv(out / "summary_NIFTY_h5.csv", index=False)

    if args.only in (None, "bank"):
        # out-of-market check: the walk-forward-selected NIFTY variants, unchanged, on BANKNIFTY
        bbook, bfeats = load_book("BANKNIFTY")
        picks_path = out / "walkforward_h1.csv"
        names = pd.read_csv(picks_path)["variant"].dropna().unique() if picks_path.exists() else []
        rows = []
        for name in names:
            p = next(q for q in h1_grid() if q.label() == name)
            df = trades_frame(short_vol.run(bbook, bfeats, p, ex, "BANKNIFTY"))
            df = df[df["entry_date"] <= pd.Timestamp("2024-11-13")]  # BANKNIFTY weeklies ended
            df.to_parquet(out / "trades" / f"BANKNIFTY_h1_{name}.parquet", index=False)
            rows.append({"variant": name, **evaluate(df)})
        pd.DataFrame(rows).to_csv(out / "summary_BANKNIFTY_h1.csv", index=False)

    path = out / "findings.json"
    merged = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    merged.update(findings)
    path.write_text(json.dumps(merged, indent=1, default=_json), encoding="utf-8")


def _json(o: Any) -> Any:
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return str(o)


if __name__ == "__main__":
    main()
