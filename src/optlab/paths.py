"""Filesystem layout. Everything under data/ is reproducible from the fetch scripts and is git-ignored."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("OPTLAB_ROOT", Path(__file__).resolve().parents[2]))
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
REPORTS = ROOT / "reports"
WAREHOUSE = DATA / "optlab.duckdb"


def ensure_dirs() -> None:
    for p in (RAW, PROCESSED, REPORTS):
        p.mkdir(parents=True, exist_ok=True)
