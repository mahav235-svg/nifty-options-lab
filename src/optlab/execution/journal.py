"""Append-only trade journal in DuckDB: every decision, order and fill the live runner makes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    ts TIMESTAMP, run_id VARCHAR, strategy VARCHAR, expiry DATE, action VARCHAR, reason VARCHAR, detail JSON);
CREATE TABLE IF NOT EXISTS orders (
    ts TIMESTAMP, run_id VARCHAR, order_id VARCHAR, instrument_key VARCHAR, symbol VARCHAR, side VARCHAR,
    quantity INTEGER, filled INTEGER, avg_price DOUBLE, status VARCHAR, mode VARCHAR);
"""


class Journal:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(path))
        self.con.execute(SCHEMA)

    def decision(
        self,
        run_id: str,
        strategy: str,
        expiry: Any,
        action: str,
        reason: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.con.execute(
            "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?)",
            [datetime.now(), run_id, strategy, expiry, action, reason, json.dumps(detail or {}, default=str)],
        )

    def order(
        self,
        run_id: str,
        order_id: str | None,
        instrument_key: str,
        symbol: str,
        side: str,
        quantity: int,
        filled: int,
        avg_price: float,
        status: str,
        mode: str,
    ) -> None:
        self.con.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                datetime.now(),
                run_id,
                order_id,
                instrument_key,
                symbol,
                side,
                quantity,
                filled,
                avg_price,
                status,
                mode,
            ],
        )

    def close(self) -> None:
        self.con.close()
