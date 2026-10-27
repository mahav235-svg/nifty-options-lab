"""Command line interface: ``optlab --help``."""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True, help="NIFTY options research and execution.")
data_app = typer.Typer(no_args_is_help=True, help="Download and build the data layers.")
live_app = typer.Typer(no_args_is_help=True, help="Paper and live execution.")
app.add_typer(data_app, name="data")
app.add_typer(live_app, name="live")


@app.callback()
def _setup(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@data_app.command("fetch")
def fetch(start: str = "2018-01-01", end: str = "") -> None:
    """Download NSE bhavcopies and Upstox index candles (cached; re-runs only fetch new days)."""
    from optlab.pipeline import fetch_all

    fetch_all(date.fromisoformat(start), date.fromisoformat(end) if end else date.today())


@data_app.command("build")
def build() -> None:
    """Raw files -> bhavcopy Parquet -> option chains -> daily features."""
    from optlab.data.nse_bhavcopy import build as build_bhav
    from optlab.paths import PROCESSED, RAW
    from optlab.pipeline import build_chains, build_feature_table

    build_bhav(RAW, PROCESSED)
    build_chains()
    feats = build_feature_table("NIFTY")
    typer.echo(f"features: {len(feats)} sessions")


@data_app.command("check")
def check() -> None:
    """Data-quality report: gaps, stale prices, forward vs spot, IV sanity."""
    from optlab.data.quality import report

    typer.echo(report())


@app.command()
def sql(query: str) -> None:
    """Run SQL against the DuckDB views (fo_bhav, nifty_chain, features, ...)."""
    from optlab.data.warehouse import query as run

    typer.echo(run(query).to_string(max_rows=60))


@app.command()
def research(only: str = "") -> None:
    """Run the pre-registered research plan; writes reports/."""
    from optlab.research.runner import main

    main(["--only", only] if only else [])


@live_app.command("login")
def login() -> None:
    """Print the Upstox login URL, then exchange the code you paste back for a day token."""
    import os

    from optlab.execution.upstox import exchange_code, login_url

    cid, secret = os.environ["UPSTOX_API_KEY"], os.environ["UPSTOX_API_SECRET"]
    redirect = os.environ.get("UPSTOX_REDIRECT_URI", "http://127.0.0.1:5000/callback")
    typer.echo(
        "Open this URL, sign in, and copy the `code` parameter from the redirect:\n"
        + login_url(cid, redirect)
    )
    code = typer.prompt("code")
    exchange_code(code.strip(), cid, secret, redirect)
    typer.echo("token saved")


@live_app.command("run")
def run(
    mode: Annotated[str, typer.Option(help="paper or live")] = "paper",
    dry_run: Annotated[bool, typer.Option(help="decide and log, place nothing")] = False,
) -> None:
    """Run today's decision for the deployed strategy (meant to be scheduled at 15:15 IST)."""
    from optlab.execution.runner import run_once

    typer.echo(run_once(mode=mode, dry_run=dry_run))


if __name__ == "__main__":
    app()
