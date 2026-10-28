"""
Population extractor — loads raw population CSV into the warehouse.

Reads:  data/raw/population_by_province_2024.csv
Writes: raw.population_by_province in the warehouse PostgreSQL

Validation:
  - Source data is validated BEFORE load (fail-fast, no bad data written)
  - Loaded data is validated AFTER load (verify what's actually in the warehouse)

Requires WAREHOUSE_DB_URL environment variable. Set it before running:
  $env:WAREHOUSE_DB_URL = "postgresql+psycopg2://airflow:changeme@127.0.0.1:5434/airflow"

Run:  uv run python scripts/extract_population.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from scripts.validators import validate_population
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

CSV_PATH = Path("data/raw/population_by_province_2024.csv")
SCHEMA = "raw"
TABLE = "population_by_province"


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
    logger.info("POPULATION EXTRACTOR")
    logger.info("=" * 60)

    # 1. Read source
    logger.info(f"\n[1] Reading CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    logger.info(f"    Rows: {len(df)}, Columns: {list(df.columns)}")

    # 2. Validate SOURCE data (fail-fast, before writing)
    logger.info("\n[2] Validating source data")
    errors = validate_population(df)
    if errors:
        logger.error(f"    ✗ {len(errors)} validation failure(s):")
        for e in errors:
            logger.error(f"      - {e}")
        logger.error("\nAborting — no data written to warehouse.")
        sys.exit(1)
    logger.info("    ✓ Source passed all checks")

    # 3. Ensure schema
    logger.info(f"\n[3] Ensuring schema '{SCHEMA}' exists")
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    # 4. Load
    logger.info(f"\n[4] Writing to {SCHEMA}.{TABLE} (if_exists='replace')")
    df.to_sql(
        name=TABLE,
        con=engine,
        schema=SCHEMA,
        if_exists="replace",
        index=False,
    )

    # 5. Verify loaded data (read back from warehouse, validate again)
    logger.info("\n[5] Verifying loaded data in warehouse")
    loaded = pd.read_sql(f"SELECT * FROM {SCHEMA}.{TABLE}", engine)
    logger.info(f"    Rows read back: {len(loaded)}")

    errors = validate_population(loaded)
    if errors:
        logger.error(
            f"    ✗ {len(errors)} validation failure(s) on loaded data:")
        for e in errors:
            logger.error(f"      - {e}")
        logger.error("\nLoad is inconsistent with source — investigate.")
        sys.exit(1)
    logger.info("    ✓ Loaded data matches source expectations")

    if len(loaded) != len(df):
        logger.error(
            f"\n✗ Row count mismatch: source={len(df)}, warehouse={len(loaded)}",
            file=sys.stderr,
        )
        sys.exit(1)

    logger.info(f"\n✓ Load succeeded — {len(loaded)} rows validated.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
