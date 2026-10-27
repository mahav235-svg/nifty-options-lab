"""Round 2 confirmation tests C1 and C2 (docs/research_plan.md). The rule is frozen; nothing is tuned here."""

from __future__ import annotations

import json
import logging

import pandas as pd

from optlab.backtest import metrics
from optlab.backtest.engine import ExecutionModel, trades_frame
from optlab.data.features import load_events
from optlab.paths import REPORTS, ROOT
from optlab.research.runner import _json, evaluate, load_book
from optlab.strategies.event_premium import EventPremiumParams, event_trades

FROZEN = EventPremiumParams(entry_offset=2, exit_offset=1, kinds=("rbi_mpc",), wing_em=3.0)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    events = load_events(ROOT / "configs" / "events.yaml")
    ex = ExecutionModel()
    out = {}

    bbook, _ = load_book("BANKNIFTY")
    c1, c1_missed = event_trades(bbook, events, FROZEN, ex, symbol="BANKNIFTY")
    c1_df = trades_frame(c1)

    nbook, _ = load_book("NIFTY")
    # FOMC decisions land after the NSE close; the first reacting NSE session is the next one
    sessions = nbook.sessions
    impact = []
    for d in events["fomc"]:
        i = sessions.searchsorted(pd.Timestamp(d), side="right")
        if i < len(sessions):
            impact.append(sessions[i].date())
    c2, c2_missed = event_trades(
        nbook,
        {"fomc_impact": impact},
        EventPremiumParams(entry_offset=2, exit_offset=1, kinds=("fomc_impact",), wing_em=3.0),
        ex,
    )
    c2_df = trades_frame(c2)

    for name, df, missed in (("C1_banknifty_rbi", c1_df, c1_missed), ("C2_nifty_fomc", c2_df, c2_missed)):
        df.to_parquet(REPORTS / "trades" / f"{name}.parquet", index=False)
        out[name] = {**evaluate(df, n_trials=1), "missed_fills": missed}
    pooled = pd.concat([c1_df.assign(src="C1"), c2_df.assign(src="C2")], ignore_index=True)
    # pool in units of return on risk: the two indices have different lot sizes and point values
    ror = pooled.sort_values("entry_date")["return_on_risk"].to_numpy()
    lo, hi = metrics.bootstrap_ci(ror, n_boot=4000)
    out["pooled_return_on_risk"] = {
        "n": len(ror),
        "mean": float(ror.mean()),
        "t": metrics.t_stat(ror),
        "ci_lo": lo,
        "ci_hi": hi,
    }
    path = REPORTS / "findings.json"
    merged = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    merged["confirmation"] = out
    path.write_text(json.dumps(merged, indent=1, default=_json), encoding="utf-8")
    print(json.dumps(out, indent=1, default=_json))


if __name__ == "__main__":
    main()
