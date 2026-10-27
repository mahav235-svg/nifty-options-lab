"""Round 2 runner (docs/research_plan.md, Round 2). Writes reports/summary_NIFTY_r2.csv and findings."""

from __future__ import annotations

import json
import logging
from dataclasses import replace

import numpy as np
import pandas as pd
from scipy import stats

from optlab.backtest import metrics
from optlab.backtest.engine import ExecutionModel, trades_frame
from optlab.data.features import load_events
from optlab.market.costs import Slippage
from optlab.paths import REPORTS, ROOT
from optlab.research.runner import _json, evaluate, load_book
from optlab.strategies.event_premium import EventPremiumParams, event_trades, placebo_trades

log = logging.getLogger(__name__)
N_TRIALS = 359


def welch_t(a: pd.Series, b: pd.Series) -> float:
    return (
        float(stats.ttest_ind(a, b, equal_var=False).statistic) if len(a) > 2 and len(b) > 2 else float("nan")
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    book, _ = load_book("NIFTY")
    events = load_events(ROOT / "configs" / "events.yaml")
    ex = ExecutionModel()
    grid = [
        EventPremiumParams(entry_offset=k, exit_offset=1, kinds=kinds)
        for k in (2, 3)
        for kinds in (("rbi_mpc",), ("rbi_mpc", "union_budget"))
    ]
    grid += [
        EventPremiumParams(entry_offset=1, exit_offset=0, kinds=kinds)
        for kinds in (("rbi_mpc",), ("rbi_mpc", "union_budget"))
    ]
    reference = [replace(p, wing_em=0.0) for p in grid]
    grid += [replace(p, wing_em=w) for p in grid[:4] for w in (2.0, 3.0)]

    rows, findings = [], {}
    placebo_cache: dict[tuple[int, float], pd.DataFrame] = {}
    for p in grid + reference:
        trades, missed = event_trades(book, events, p, ex)
        df = trades_frame(trades)
        df.to_parquet(REPORTS / "trades" / f"NIFTY_r2_{p.label()}.parquet", index=False)
        hold = p.entry_offset - p.exit_offset
        key = (hold, p.wing_em)
        if key not in placebo_cache:
            placebo_cache[key] = trades_frame(placebo_trades(book, events, p, ex))
        plac = placebo_cache[key]
        row = {
            "variant": p.label(),
            "missed_fills": missed,
            **evaluate(df, N_TRIALS),
            "placebo_n": len(plac),
            "placebo_mean_rs": float(plac["pnl_rs"].mean()) if len(plac) else np.nan,
            "diff_t_vs_placebo": welch_t(df["pnl_rs"], plac["pnl_rs"]) if len(df) and len(plac) else np.nan,
            "gross_mean_points": float(df["gross_points"].mean()) if len(df) else np.nan,
        }
        if len(df):
            pre = df[df["entry_date"] < pd.Timestamp("2024-11-20")]
            post = df[df["entry_date"] >= pd.Timestamp("2024-11-20")]
            row.update(
                {
                    "pre_nov2024_mean": float(pre["pnl_rs"].mean()),
                    "pre_n": len(pre),
                    "post_nov2024_mean": float(post["pnl_rs"].mean()) if len(post) else np.nan,
                    "post_n": len(post),
                }
            )
        if p in grid and len(df):
            ex2 = replace(ex, slippage=Slippage(multiplier=2.0))
            df2 = trades_frame(event_trades(book, events, p, ex2)[0])
            row["mean_rs_slip2x"] = float(df2["pnl_rs"].mean())
            row["t_slip2x"] = metrics.t_stat(df2["pnl_rs"])
        rows.append(row)
        log.info(
            "%s: n=%d mean=%.0f t=%.2f placebo=%.0f",
            p.label(),
            row.get("n", 0),
            row.get("mean_rs", np.nan),
            row.get("t_stat", np.nan),
            row["placebo_mean_rs"],
        )
    out = pd.DataFrame(rows)
    out.to_csv(REPORTS / "summary_NIFTY_r2.csv", index=False)
    findings["r2"] = out.to_dict(orient="records")
    path = REPORTS / "findings.json"
    merged = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    merged.update(findings)
    path.write_text(json.dumps(merged, indent=1, default=_json), encoding="utf-8")


if __name__ == "__main__":
    main()
