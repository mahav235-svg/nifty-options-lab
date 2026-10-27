"""Daily decision job for the deployed strategy (``optlab live run``), scheduled for about 15:15 IST.

The deployed strategy (configs/strategy.yaml) is the RBI pre-announcement iron fly. The job runs
every trading day and decides which of three things today is:

* entry day (``entry_offset`` sessions before an RBI MPC decision): open the iron fly;
* exit day (``exit_offset`` sessions before it): close it, unless it expires today, in which case
  it is left to cash settle at the close exactly as in the backtest;
* any other day: do nothing.

Before any order: the kill switch file, the ``enabled`` flag, an already-open position, a two-sided
quote on every leg, the maximum loss against the risk budget and the available margin are checked.
Every decision and order is written to the journal, and the open position's legs are recovered
from the journal on exit day, so the exit closes exactly what the entry opened.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from optlab.data.features import load_events
from optlab.execution.broker import Broker, OptionContract, Quote, Side
from optlab.execution.journal import Journal
from optlab.execution.orders import WorkingPolicy, execute_structure, work_order
from optlab.market.pricing import implied_vol
from optlab.paths import ROOT
from optlab.strategies.event_premium import EventPremiumParams

log = logging.getLogger(__name__)
CONFIG = ROOT / "configs" / "strategy.yaml"
JOURNAL = ROOT / "journal" / "journal.duckdb"
KILL_SWITCH = ROOT / "journal" / "KILL"


@dataclass
class DeployConfig:
    enabled: bool
    symbol: str
    params: EventPremiumParams
    lots: int
    capital: float
    max_loss_fraction: float
    policy: WorkingPolicy
    holidays: list[date]

    @classmethod
    def load(cls, path: Path = CONFIG) -> DeployConfig:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        p = raw["params"]
        params = EventPremiumParams(
            entry_offset=int(p["entry_offset"]),
            exit_offset=int(p["exit_offset"]),
            kinds=("rbi_mpc",),
            wing_em=float(p["wing_em"]),
        )
        return cls(
            enabled=bool(raw.get("enabled", False)),
            symbol=raw.get("symbol", "NIFTY"),
            params=params,
            lots=int(p.get("lots", 1)),
            capital=float(raw["capital"]),
            max_loss_fraction=float(raw["max_loss_fraction"]),
            policy=WorkingPolicy(**raw.get("execution", {})),
            holidays=[pd.Timestamp(d).date() for d in raw.get("holidays") or []],
        )


def sessions_between(start: date, end: date, holidays: set[date]) -> int:
    """Trading sessions strictly after ``start`` up to and including ``end`` (0 if end <= start)."""
    if end <= start:
        return 0
    return sum(1 for d in pd.bdate_range(start, end)[1:] if d.date() not in holidays)


def classify_day(
    today: date, events: list[date], p: EventPremiumParams, holidays: set[date]
) -> tuple[str, date | None]:
    """Return ("entry" | "exit" | "none", event date) for today."""
    for ev in sorted(e for e in events if e > today):
        gap = sessions_between(today, ev, holidays)
        if gap == p.entry_offset:
            return "entry", ev
        if gap == p.exit_offset:
            return "exit", ev
        if gap > p.entry_offset:
            break
    return "none", None


def chain_snapshot(broker: Broker, contracts: list[OptionContract], spot: float) -> pd.DataFrame:
    """Live chain near the money: mid prices, a two-sided-quote flag and the parity forward."""
    near = [c for c in contracts if abs(c.strike / spot - 1) < 0.10]
    quotes: dict[str, Quote] = broker.quotes([c.instrument_key for c in near])
    rows = []
    for c in near:
        q = quotes.get(c.instrument_key)
        if q is not None:
            rows.append(
                {
                    "strike": c.strike,
                    "option_type": c.option_type,
                    "mid": q.mid,
                    "bid": q.bid,
                    "ask": q.ask,
                    "two_sided": q.bid > 0 and q.ask > 0,
                    "key": c.instrument_key,
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    both = df[df["two_sided"]].pivot_table(index="strike", columns="option_type", values="mid").dropna()
    fwd = spot
    if not both.empty:
        gap = (both["CE"] - both["PE"]).abs().nsmallest(3)
        fwd = float((gap.index + both.loc[gap.index, "CE"] - both.loc[gap.index, "PE"]).median())
    df["forward"] = fwd
    return df


def fly_legs(
    snap: pd.DataFrame, wing_em: float
) -> tuple[list[tuple[float, str, int]], dict[str, float]] | None:
    """ATM iron fly with wings ``wing_em`` straddles away, exactly as in the backtest."""
    two = snap[snap["two_sided"]]
    piv = two.pivot_table(index="strike", columns="option_type", values="mid").dropna()
    if piv.empty:
        return None
    fwd = float(snap["forward"].iloc[0])
    k = float(piv.index[(abs(piv.index.to_numpy() - fwd)).argmin()])
    em = float(piv.loc[k, "CE"] + piv.loc[k, "PE"])
    calls = two.loc[two["option_type"] == "CE", "strike"]
    puts = two.loc[two["option_type"] == "PE", "strike"]
    up, dn = calls[calls >= k + wing_em * em], puts[puts <= k - wing_em * em]
    if up.empty or dn.empty:
        return None
    lc, lp = float(up.min()), float(dn.max())
    legs = [(k, "CE", -1), (k, "PE", -1), (lc, "CE", 1), (lp, "PE", 1)]
    mid = {(r.strike, r.option_type): r.mid for r in two.itertuples()}
    credit = mid[(k, "CE")] + mid[(k, "PE")] - mid[(lc, "CE")] - mid[(lp, "PE")]
    max_loss_pts = max(lc - k, k - lp) - credit
    return legs, {"atm": k, "em": em, "credit": credit, "max_loss_points": max_loss_pts, "forward": fwd}


def _broker_holidays(broker: Broker) -> set[date]:
    fn = getattr(broker, "holidays", None)
    try:
        return set(fn()) if callable(fn) else set()
    except Exception:  # the holiday call is best effort; the config list still applies
        log.warning("could not fetch the holiday calendar from the broker")
        return set()


def run_once(
    mode: str = "paper",
    dry_run: bool = False,
    broker: Broker | None = None,
    today: date | None = None,
    config: DeployConfig | None = None,
    journal_path: Path = JOURNAL,
    events: list[date] | None = None,
) -> str:
    cfg = config or DeployConfig.load()
    today = today or date.today()
    run_id = f"{today:%Y%m%d}-{uuid.uuid4().hex[:6]}"
    journal = Journal(journal_path)
    name = cfg.params.label()

    def done(action: str, reason: str, detail: dict[str, Any] | None = None, expiry: Any = None) -> str:
        journal.decision(run_id, name, expiry, action, reason, detail)
        journal.close()
        return f"[{run_id}] {action}: {reason}"

    if KILL_SWITCH.exists():
        return done("skip", "kill switch present")
    if not cfg.enabled:
        return done("skip", "strategy disabled in configs/strategy.yaml")
    broker = broker or _make_broker(mode)
    holidays = set(cfg.holidays) | _broker_holidays(broker)
    if events is None:
        events = load_events(ROOT / "configs" / "events.yaml").get("rbi_mpc", [])
    kind, event = classify_day(today, events, cfg.params, holidays)
    if kind == "none":
        return done("skip", "not an entry or exit day")
    if kind == "exit":
        return _exit(broker, journal, run_id, name, today, cfg, mode, dry_run, done)

    # ---- entry ----
    exit_day = today
    for _ in range(cfg.params.entry_offset - cfg.params.exit_offset):
        exit_day = (pd.Timestamp(exit_day) + pd.offsets.BDay(1)).date()
        while exit_day in holidays:
            exit_day = (pd.Timestamp(exit_day) + pd.offsets.BDay(1)).date()
    expiries = [e for e in broker.expiries(cfg.symbol) if e >= exit_day]
    if not expiries:
        return done("skip", "no expiry after the exit day")
    expiry = expiries[0]
    contracts = broker.option_contracts(cfg.symbol, expiry)
    live_keys = {c.instrument_key for e in expiries[:3] for c in broker.option_contracts(cfg.symbol, e)}
    if {p.instrument_key for p in broker.positions()} & live_keys:
        return done("skip", "a position in this underlying is already open", expiry=expiry)

    snap = chain_snapshot(broker, contracts, broker.spot(cfg.symbol))
    built = fly_legs(snap, cfg.params.wing_em) if not snap.empty else None
    if built is None:
        return done("skip", "could not build the iron fly from live quotes", expiry=expiry)
    legs, info = built
    lot = contracts[0].lot_size
    max_loss = info["max_loss_points"] * lot * cfg.lots
    budget = cfg.capital * cfg.max_loss_fraction
    t = max((expiry - today).days, 0) / 365 + 0.5 / 365
    atm_row = snap[(snap["strike"] == info["atm"])]
    info["atm_iv"] = float(
        pd.Series(
            implied_vol(
                atm_row["mid"].to_numpy(),
                info["forward"],
                atm_row["strike"].to_numpy(),
                t,
                (atm_row["option_type"] == "CE").to_numpy(),
            )
        ).mean()
    )
    detail = {**info, "event": str(event), "expiry": str(expiry), "max_loss_rs": max_loss, "lot_size": lot}
    if max_loss > budget:
        return done("skip", f"max loss Rs {max_loss:,.0f} exceeds budget Rs {budget:,.0f}", detail, expiry)
    if broker.available_margin() < 1.25 * max_loss:
        return done("skip", "available margin too low", detail, expiry)
    by_leg = {(c.strike, c.option_type): c for c in contracts}
    orders = [
        (by_leg[(k, t_)], Side.BUY if n > 0 else Side.SELL, abs(n) * lot * cfg.lots) for k, t_, n in legs
    ]
    detail["legs"] = [
        {"key": c.instrument_key, "symbol": c.symbol, "side": s.value, "qty": q} for c, s, q in orders
    ]
    if dry_run:
        return done("dry_run", "would enter", detail, expiry)
    results = execute_structure(broker, orders, cfg.policy, tag=f"optlab-{run_id}")
    for r in results:
        journal.order(
            run_id,
            r.order_id,
            r.contract.instrument_key,
            r.contract.symbol,
            r.side.value,
            r.quantity,
            r.filled,
            r.avg_price,
            r.status.value,
            mode,
        )
    ok = len(results) == len(orders) and all(r.filled == r.quantity for r in results)
    return done(
        "entered" if ok else "aborted",
        "all legs filled" if ok else "a leg failed; filled legs unwound",
        detail,
        expiry,
    )


def _exit(
    broker: Broker,
    journal: Journal,
    run_id: str,
    name: str,
    today: date,
    cfg: DeployConfig,
    mode: str,
    dry_run: bool,
    done: Any,
) -> str:
    row = journal.con.execute(
        "SELECT detail FROM decisions WHERE strategy = ? AND action = 'entered' ORDER BY ts DESC LIMIT 1",
        [name],
    ).fetchone()
    if row is None:
        return str(done("skip", "exit day but no entered position in the journal"))
    detail = json.loads(row[0])
    expiry = date.fromisoformat(detail["expiry"])
    held = {p.instrument_key: p.quantity for p in broker.positions()}
    legs = [leg for leg in detail["legs"] if held.get(leg["key"], 0) != 0]
    if not legs:
        return str(done("skip", "position already closed", expiry=expiry))
    if expiry == today:
        return str(done("hold", "expires today; left to cash settle at the close", expiry=expiry))
    contracts = {c.instrument_key: c for c in broker.option_contracts(cfg.symbol, expiry)}
    if dry_run:
        return str(done("dry_run", "would close", {"legs": legs}, expiry))
    # close shorts first: they carry the risk
    for leg in sorted(legs, key=lambda x: 0 if x["side"] == "SELL" else 1):
        back = Side.BUY if leg["side"] == "SELL" else Side.SELL
        r = work_order(
            broker, contracts[leg["key"]], back, int(leg["qty"]), cfg.policy, f"optlab-{run_id}-exit"
        )
        journal.order(
            run_id,
            r.order_id,
            leg["key"],
            leg["symbol"],
            back.value,
            int(leg["qty"]),
            r.filled,
            r.avg_price,
            r.status.value,
            mode,
        )
    remaining = [
        k
        for k, q in ((p.instrument_key, p.quantity) for p in broker.positions())
        if q != 0 and k in {leg["key"] for leg in legs}
    ]
    return str(
        done(
            "exited" if not remaining else "exit_incomplete",
            "all legs closed" if not remaining else f"still open: {remaining}",
            None,
            expiry,
        )
    )


def _make_broker(mode: str) -> Broker:
    from optlab.execution.paper import PaperBroker
    from optlab.execution.upstox import UpstoxBroker

    live = UpstoxBroker()
    if mode == "live":
        return live
    return PaperBroker(
        live.quotes,
        live.option_contracts,
        live.expiries,
        live.spot,
        state_file=ROOT / "journal" / "paper_positions.json",
    )
