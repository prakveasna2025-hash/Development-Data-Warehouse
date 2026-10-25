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

from validators import validate_population

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

    # 1. Read source
    print(f"\n[1] Reading CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    print(f"    Rows: {len(df)}, Columns: {list(df.columns)}")

    # 2. Validate SOURCE data (fail-fast, before writing)
    print("\n[2] Validating source data")
    errors = validate_population(df)
    if errors:
        print(f"    ✗ {len(errors)} validation failure(s):", file=sys.stderr)
        for e in errors:
            print(f"      - {e}", file=sys.stderr)
        print("\nAborting — no data written to warehouse.", file=sys.stderr)
        sys.exit(1)
    print("    ✓ Source passed all checks")

    # 3. Ensure schema
    print(f"\n[3] Ensuring schema '{SCHEMA}' exists")
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    # 4. Load
    print(f"\n[4] Writing to {SCHEMA}.{TABLE} (if_exists='replace')")
    df.to_sql(
        name=TABLE,
        con=engine,
        schema=SCHEMA,
        if_exists="replace",
        index=False,
    )

    # 5. Verify loaded data (read back from warehouse, validate again)
    print("\n[5] Verifying loaded data in warehouse")
    loaded = pd.read_sql(f"SELECT * FROM {SCHEMA}.{TABLE}", engine)
    print(f"    Rows read back: {len(loaded)}")

    errors = validate_population(loaded)
    if errors:
        print(
            f"    ✗ {len(errors)} validation failure(s) on loaded data:", file=sys.stderr)
        for e in errors:
            print(f"      - {e}", file=sys.stderr)
        print("\nLoad is inconsistent with source — investigate.", file=sys.stderr)
        sys.exit(1)
    print("    ✓ Loaded data matches source expectations")

    if len(loaded) != len(df):
        print(
            f"\n✗ Row count mismatch: source={len(df)}, warehouse={len(loaded)}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\n✓ Load succeeded — {len(loaded)} rows validated.")
    print("=" * 60)


if __name__ == "__main__":
    main()
