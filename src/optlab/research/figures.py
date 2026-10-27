"""Figures for reports/RESULTS.md (static PNGs, light surface)."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from optlab.paths import REPORTS

SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"  # categorical slots 1-3, validated for CVD separation


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def event_study() -> None:
    series = [
        ("NIFTY, RBI decisions (round 2 test)", "NIFTY_r2_ev_rbi_mpc_in2_out1_fly3.parquet", BLUE),
        ("BANKNIFTY, RBI decisions (confirmation C1)", "C1_banknifty_rbi.parquet", ORANGE),
        ("NIFTY, FOMC decisions (confirmation C2)", "C2_nifty_fomc.parquet", AQUA),
    ]
    fig, ax = plt.subplots(figsize=(8.5, 4.6), facecolor=SURFACE)
    _style(ax)
    for label, fname, color in series:
        d = pd.read_parquet(REPORTS / "trades" / fname).sort_values("entry_date")
        cum = d["pnl_rs"].cumsum().reset_index(drop=True) / 1000
        ax.plot(range(1, len(cum) + 1), cum, color=color, linewidth=2)
        ax.annotate(
            label,
            (len(cum), cum.iloc[-1]),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=8.5,
            color=INK,
        )
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.set_xlabel("event number (chronological, 2018 to 2026)", color=MUTED, fontsize=9)
    ax.set_ylabel("cumulative net P&L, Rs thousand (1 lot)", color=MUTED, fontsize=9)
    ax.set_title(
        "Pre-announcement iron fly: cumulative net P&L per event", loc="left", color=INK, fontsize=11
    )
    ax.set_xlim(0, 75)
    fig.tight_layout()
    fig.savefig(REPORTS / "fig_event_study.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def gross_vs_cost() -> None:
    rows = []
    for s in (0.0, 0.5, 0.75, 1.0, 1.25):
        d = pd.read_parquet(REPORTS / "trades" / f"NIFTY_h1_tdte2_s{s:g}_w1_vrp0.parquet")
        units = d["lot_size"] * d["lots"]
        rows.append(
            {
                "short": "ATM" if s == 0 else f"{s:g} EM",
                "gross": d["gross_points"].mean(),
                "cost": ((d["fees_rs"] + d["slippage_rs"]) / units).mean(),
            }
        )
    t = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(7.5, 4.2), facecolor=SURFACE)
    _style(ax)
    x = range(len(t))
    w = 0.36
    b1 = ax.bar([i - w / 2 - 0.01 for i in x], t["gross"], width=w, color=BLUE, label="gross edge per trade")
    b2 = ax.bar(
        [i + w / 2 + 0.01 for i in x], t["cost"], width=w, color=ORANGE, label="fees + slippage per trade"
    )
    ax.bar_label(b1, fmt="%.1f", fontsize=8, color=INK, padding=2)
    ax.bar_label(b2, fmt="%.1f", fontsize=8, color=INK, padding=2)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.set_xticks(list(x), [f"short at {v}" for v in t["short"]])
    ax.set_ylabel("index points per unit", color=MUTED, fontsize=9)
    ax.set_title(
        "Weekly iron condor, entered the session before expiry: edge vs cost",
        loc="left",
        color=INK,
        fontsize=11,
    )
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK, loc="upper left")
    fig.tight_layout()
    fig.savefig(REPORTS / "fig_gross_vs_cost.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


if __name__ == "__main__":
    event_study()
    gross_vs_cost()
