"""
Exchange-rate extractor — loads raw NBC USD/KHR CSV into the warehouse.

Reads:  data/raw/khmer_riel_usd_exchange_rate_2003_2023.csv
Writes: raw.exchange_rate in the warehouse PostgreSQL

Note on defects: this source has DOCUMENTED defects (Day 3, docs/source-notes.md):
  - 16 inverted bid/ask rows
  - 49 missing days (April 2008 fully absent + scattered)
  - 2,109 rows with inconsistent midpoint rounding
  - spread column semantics unknown
These are loaded AS-IS. Cleaning belongs in dbt, not in raw extraction.

Load strategy: TRUNCATE + INSERT (not DROP + CREATE).
Preserves dependent views — dbt staging models (stg_exchange_rate) depend on
raw.exchange_rate, and DROP TABLE would be blocked by them.

Requires WAREHOUSE_DB_URL environment variable. Set it before running:
  $env:WAREHOUSE_DB_URL = "postgresql+psycopg2://airflow:changeme@127.0.0.1:5434/airflow"

Run:  uv run python scripts/extract_exchange_rate.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text, Date

from scripts.validators import validate_exchange_rate
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

CSV_PATH = Path("data/raw/khmer_riel_usd_exchange_rate_2003_2023.csv")
SCHEMA = "raw"
TABLE = "exchange_rate"


def get_db_url() -> str:
    url = os.environ.get("WAREHOUSE_DB_URL")
    if not url:
        logger.error("ERROR: WAREHOUSE_DB_URL is not set.")
        logger.info("Set it in PowerShell with:")
        logger.error(
            '  $env:WAREHOUSE_DB_URL = "postgresql+psycopg2://airflow:changeme@127.0.0.1:5434/airflow"'
        )
        sys.exit(1)
    return url


def main() -> None:
    db_url = get_db_url()
    engine = create_engine(db_url)

    logger.info("=" * 60)
    logger.info("EXCHANGE RATE EXTRACTOR")
    logger.info("=" * 60)

    # 1. Read — encoding="utf-8-sig" strips the BOM on the 'date' header
    logger.info(f"\n[1] Reading CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    logger.info(f"    Rows: {len(df)}, Columns: {len(df.columns)}")

    # 2. Normalize date column to datetime64 (kept as datetime64, cast to DATE on write)
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y")
    logger.info(
        f"    Date column parsed to {df['date'].dtype} — will be written as DATE")

    # 3. Validate source (fail-fast, before writing)
    logger.info("\n[2] Validating source data")
    errors = validate_exchange_rate(df)
    if errors:
        logger.error(f"    ✗ {len(errors)} validation failure(s):")
        for e in errors:
            logger.error(f"      - {e}")
        logger.error("\nAborting — no data written to warehouse.")
        sys.exit(1)
    logger.info(
        "    ✓ Source passed all checks (including documented defect counts)")

    # 4. Ensure schema
    logger.info(f"\n[3] Ensuring schema '{SCHEMA}' exists")
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    # 5. Load — TRUNCATE + INSERT preserves dependent dbt views.
    # dtype=Date only applies on first creation; existing tables keep their DATE type.
    qualified = f"{SCHEMA}.{TABLE}"
    logger.info(
        f"\n[4] Writing to {qualified} (TRUNCATE + INSERT, preserves dependent views)")
    with engine.begin() as conn:
        exists = conn.execute(
            text(f"SELECT to_regclass('{qualified}')")
        ).scalar()
    if not exists:
        logger.info("    Table does not exist — creating (first run)")
        df.to_sql(
            name=TABLE,
            con=engine,
            schema=SCHEMA,
            if_exists="replace",
            index=False,
            dtype={"date": Date},
        )
    else:
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {qualified}"))
        df.to_sql(
            name=TABLE,
            con=engine,
            schema=SCHEMA,
            if_exists="append",
            index=False,
        )

    # 6. Read back and validate
    logger.info("\n[5] Verifying loaded data in warehouse")
    loaded = pd.read_sql(f"SELECT * FROM {qualified}", engine)
    logger.info(f"    Rows read back: {len(loaded)}")

    loaded_errors = validate_exchange_rate(loaded)
    if loaded_errors:
        logger.error(
            f"    ✗ {len(loaded_errors)} validation failure(s) on loaded data:"
        )
        for e in loaded_errors:
            logger.error(f"      - {e}")
        sys.exit(1)
    logger.info("    ✓ Loaded data matches source expectations")

    if len(loaded) != len(df):
        logger.error(
            f"\n✗ Row count mismatch: source={len(df)}, warehouse={len(loaded)}"
        )
        sys.exit(1)

    logger.info(f"\n✓ Load succeeded — {len(loaded)} rows validated.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()