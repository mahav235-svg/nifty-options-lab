"""DuckDB views over the Parquet layers, plus a few SQL helpers.

The warehouse holds no copies: views point at the Parquet files, so rebuilding a layer is just
rewriting files. Analysis can then be done in SQL (``optlab sql "select ..."``) or pandas.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from optlab.paths import PROCESSED, ROOT, WAREHOUSE

SQL_DIR = ROOT / "sql"


def connect(path: Path = WAREHOUSE, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path), read_only=read_only)
    if not read_only:
        create_views(con)
    return con


def create_views(con: duckdb.DuckDBPyConnection, processed: Path = PROCESSED) -> None:
    p = processed.as_posix()
    views = {
        "fo_bhav": f"read_parquet('{p}/fo_bhav/year=*/data.parquet', hive_partitioning = true)",
        "nifty_chain": f"read_parquet('{p}/chain/NIFTY/year=*/data.parquet', hive_partitioning = true)",
        "banknifty_chain": (
            f"read_parquet('{p}/chain/BANKNIFTY/year=*/data.parquet', hive_partitioning = true)"
        ),
        "nifty_daily": f"read_parquet('{p}/index/NIFTY_daily.parquet')",
        "banknifty_daily": f"read_parquet('{p}/index/BANKNIFTY_daily.parquet')",
        "vix_daily": f"read_parquet('{p}/index/INDIAVIX_daily.parquet')",
        "nifty_1m": f"read_parquet('{p}/index/NIFTY_1m.parquet')",
        "vix_1m": f"read_parquet('{p}/index/INDIAVIX_1m.parquet')",
        "features": f"read_parquet('{p}/features/NIFTY_daily_features.parquet')",
    }
    for name, source in views.items():
        target = source.split("'")[1].split("*")[0]
        if Path(target).exists() or Path(target).parent.exists():
            con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM {source}")
    for sql_file in sorted(SQL_DIR.glob("*.sql")):
        try:
            con.execute(sql_file.read_text(encoding="utf-8"))
        except duckdb.Error:
            # a view whose inputs have not been built yet; it will be created on the next connect
            continue


def query(sql: str, params: list[object] | None = None) -> pd.DataFrame:
    with connect() as con:
        return con.execute(sql, params or []).df()
