from datetime import date
from pathlib import Path

import numpy as np

from optlab.execution.broker import OptionContract, Quote
from optlab.execution.orders import WorkingPolicy
from optlab.execution.paper import PaperBroker
from optlab.execution.runner import DeployConfig, classify_day, run_once, sessions_between
from optlab.strategies.event_premium import EventPremiumParams

EXPIRY = date(2026, 12, 8)
EVENT = date(2026, 12, 4)  # a Friday
P = EventPremiumParams(entry_offset=2, exit_offset=1, kinds=("rbi_mpc",), wing_em=3.0)


def test_session_counting_skips_weekends_and_holidays() -> None:
    assert sessions_between(date(2026, 12, 2), EVENT, set()) == 2
    assert sessions_between(date(2026, 12, 2), EVENT, {date(2026, 12, 3)}) == 1


def test_classify_entry_and_exit_days() -> None:
    assert classify_day(date(2026, 12, 2), [EVENT], P, set()) == ("entry", EVENT)
    assert classify_day(date(2026, 12, 3), [EVENT], P, set()) == ("exit", EVENT)
    assert classify_day(date(2026, 11, 30), [EVENT], P, set())[0] == "none"


def _market(spot: float = 23000.0) -> PaperBroker:
    strikes = np.arange(21000, 25050, 50)
    contracts = [
        OptionContract(f"NSE_FO|{t}{int(k)}", f"NIFTY {int(k)} {t}", "NIFTY", EXPIRY, float(k), t, 65)
        for k in strikes
        for t in ("CE", "PE")
    ]

    def price(c: OptionContract) -> float:
        intrinsic = max(spot - c.strike, 0) if c.option_type == "CE" else max(c.strike - spot, 0)
        raw = intrinsic + 100 * np.exp(-abs(c.strike - spot) / 150) + 0.5
        return round(round(raw / 0.05) * 0.05, 2)  # quotes sit on the 0.05 tick grid

    book = {c.instrument_key: c for c in contracts}

    def quotes(keys: list[str]) -> dict[str, Quote]:
        return {
            k: Quote(k, bid=price(book[k]) - 0.5, ask=price(book[k]) + 0.5, ltp=price(book[k])) for k in keys
        }

    return PaperBroker(quotes, lambda u, e: contracts, lambda u: [EXPIRY], lambda u: spot)


def _cfg() -> DeployConfig:
    return DeployConfig(
        enabled=True,
        symbol="NIFTY",
        params=P,
        lots=1,
        capital=150000,
        max_loss_fraction=0.3,
        policy=WorkingPolicy(wait_seconds=0, steps=2),
        holidays=[],
    )


def test_entry_then_exit_round_trip(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("optlab.execution.orders.time.sleep", lambda s: None)
    broker = _market()
    j = tmp_path / "j.duckdb"
    out = run_once(broker=broker, today=date(2026, 12, 2), config=_cfg(), journal_path=j, events=[EVENT])
    assert "entered" in out
    assert len(broker.positions()) == 4
    assert sorted(p.quantity for p in broker.positions()) == [-65, -65, 65, 65]
    out = run_once(broker=broker, today=date(2026, 12, 3), config=_cfg(), journal_path=j, events=[EVENT])
    assert "exited" in out
    assert broker.positions() == []


def test_disabled_and_dry_run(tmp_path: Path) -> None:
    cfg = _cfg()
    cfg.enabled = False
    assert "disabled" in run_once(
        broker=_market(), today=date(2026, 12, 2), config=cfg, journal_path=tmp_path / "a", events=[EVENT]
    )
    out = run_once(
        broker=_market(),
        today=date(2026, 12, 2),
        config=_cfg(),
        journal_path=tmp_path / "b",
        events=[EVENT],
        dry_run=True,
    )
    assert "dry_run" in out


def test_risk_budget_blocks_oversized_trade(tmp_path: Path) -> None:
    cfg = _cfg()
    cfg.max_loss_fraction = 0.01
    out = run_once(
        broker=_market(), today=date(2026, 12, 2), config=cfg, journal_path=tmp_path / "c", events=[EVENT]
    )
    assert "exceeds budget" in out
