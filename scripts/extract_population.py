"""
Population extractor — loads raw population CSV into the warehouse.

Reads:  data/raw/population_by_province_2024.csv
Writes: raw.population_by_province in the warehouse PostgreSQL

Requires WAREHOUSE_DB_URL environment variable. Set it before running:
  $env:WAREHOUSE_DB_URL = "postgresql+psycopg2://airflow:changeme@127.0.0.1:5434/airflow"

Run:  uv run python scripts/extract_population.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


CSV_PATH = Path("data/raw/population_by_province_2024.csv")
SCHEMA = "raw"
TABLE = "population_by_province"


def get_db_url() -> str:
    url = os.environ.get("WAREHOUSE_DB_URL")
    if not url:
        print("ERROR: WAREHOUSE_DB_URL is not set.", file=sys.stderr)
        print("Set it in PowerShell with:", file=sys.stderr)
        print(
            '  $env:WAREHOUSE_DB_URL = "postgresql+psycopg2://airflow:changeme@127.0.0.1:5434/airflow"',
            file=sys.stderr,
        )
        sys.exit(1)
    return url


def main() -> None:
    db_url = get_db_url()
    engine = create_engine(db_url)

    print("=" * 60)
    print("POPULATION EXTRACTOR")
    print("=" * 60)

    print(f"\n[1] Reading CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    print(f"    Rows: {len(df)}, Columns: {list(df.columns)}")

    print(f"\n[2] Ensuring schema '{SCHEMA}' exists")
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    print(f"\n[3] Writing to {SCHEMA}.{TABLE} (if_exists='replace')")
    df.to_sql(
        name=TABLE,
        con=engine,
        schema=SCHEMA,
        if_exists="replace",
        index=False,
    )

    print(f"\n[4] Verifying row count in warehouse")
    with engine.connect() as conn:
        count = conn.execute(
            text(f"SELECT COUNT(*) FROM {SCHEMA}.{TABLE}")).scalar()

    print(f"    Rows in {SCHEMA}.{TABLE}: {count}")

    if count == len(df):
        print(f"\n✓ Load succeeded — {count} rows.")
    else:
        print(
            f"\n✗ MISMATCH — expected {len(df)}, got {count}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)


if __name__ == "__main__":
    main()
