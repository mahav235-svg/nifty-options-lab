"""Round 2: selling ATM premium before scheduled announcements ("calm before the storm").

The position is an iron fly (short ATM call and put, long wings one expected move away) on the
nearest expiry that falls after the event, opened at the close ``entry_offset`` sessions before the
event and closed at the close ``exit_offset`` sessions before it (``exit_offset = 0`` holds through
the announcement to the event day's close).

``placebo`` runs the identical rule on ordinary sessions: for every session not within ``buffer``
sessions of any scheduled event, open at that close and close ``entry_offset - exit_offset``
sessions later. The event effect is the difference between the two.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from optlab.backtest.engine import ChainBook, ExecutionModel, LegSpec, Trade, simulate


@dataclass(frozen=True)
class EventPremiumParams:
    entry_offset: int = 2
    exit_offset: int = 1
    kinds: tuple[str, ...] = ("rbi_mpc",)
    wing_em: float = 1.0  # 0 = naked straddle (research only: needs more margin than the account)
    min_tdte_at_exit: int = 1  # the option must still be alive at the exit close

    def label(self) -> str:
        w = "straddle" if self.wing_em == 0 else f"fly{self.wing_em:g}"
        return f"ev_{'+'.join(self.kinds)}_in{self.entry_offset}_out{self.exit_offset}_{w}"


def _legs(
    book: ChainBook, d: pd.Timestamp, expiry: pd.Timestamp, wing_em: float
) -> tuple[list[LegSpec], float] | None:
    a = book.atm(d, expiry)
    if a is None:
        return None
    k, em = float(a["atm_strike"]), float(a["straddle"])
    legs = [LegSpec("CE", k, -1), LegSpec("PE", k, -1)]
    if wing_em > 0:
        day = book.slice(d, expiry)
        assert day is not None
        traded = day[day["traded"]]
        calls = traded.loc[traded["option_type"] == "CE", "strike"]
        puts = traded.loc[traded["option_type"] == "PE", "strike"]
        up = calls[calls >= k + wing_em * em]
        dn = puts[puts <= k - wing_em * em]
        if up.empty or dn.empty:
            return None
        legs += [LegSpec("CE", float(up.min()), 1), LegSpec("PE", float(dn.max()), 1)]
    return legs, em


def _trade(
    book: ChainBook,
    entry: pd.Timestamp,
    exit_: pd.Timestamp,
    p: EventPremiumParams,
    ex: ExecutionModel,
    label: str,
    meta: dict[str, object],
    symbol: str = "NIFTY",
) -> Trade | None:
    live = [e for e in book.expiries_on.get(entry, []) if e >= exit_]
    if not live:
        return None
    expiry = min(live)
    built = _legs(book, entry, expiry, p.wing_em)
    if built is None:
        return None
    legs, em = built
    return simulate(
        book,
        label,
        symbol,
        entry,
        expiry,
        legs,
        ex,
        exit_on=exit_ if exit_ < expiry else None,
        meta={**meta, "em": em},
    )


def event_trades(
    book: ChainBook,
    events: dict[str, list[date]],
    p: EventPremiumParams,
    ex: ExecutionModel,
    symbol: str = "NIFTY",
) -> tuple[list[Trade], int]:
    """Returns (trades, number of events where the trade could not be filled at entry or exit)."""
    sessions = book.sessions
    trades: list[Trade] = []
    missed = 0
    for kind in p.kinds:
        for ev in events.get(kind, []):
            i = sessions.searchsorted(pd.Timestamp(ev))
            if i >= len(sessions) or i - p.entry_offset < 0:
                continue
            t = _trade(
                book,
                sessions[i - p.entry_offset],
                sessions[i - p.exit_offset],
                p,
                ex,
                p.label(),
                {"event": str(ev), "kind": kind},
                symbol,
            )
            if t is None:
                missed += 1
            else:
                trades.append(t)
    return trades, missed


def placebo_trades(
    book: ChainBook, events: dict[str, list[date]], p: EventPremiumParams, ex: ExecutionModel, buffer: int = 5
) -> list[Trade]:
    sessions = book.sessions
    ev_pos = sorted(
        {
            int(sessions.searchsorted(pd.Timestamp(d)))
            for k in ("rbi_mpc", "union_budget", "election_results")
            for d in events.get(k, [])
        }
    )
    hold = p.entry_offset - p.exit_offset
    trades = []
    for i in range(len(sessions) - hold):
        if any(abs(i - e) <= buffer or abs(i + hold - e) <= buffer for e in ev_pos):
            continue
        t = _trade(book, sessions[i], sessions[i + hold], p, ex, f"placebo_{p.label()}", {})
        if t is not None:
            trades.append(t)
    return trades
