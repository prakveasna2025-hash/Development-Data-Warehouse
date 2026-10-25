"""
Warehouse health check — run AFTER extraction, against actual warehouse state.

Unlike scripts/validators.py (which validates DataFrames BEFORE load), this
script validates the WAREHOUSE ITSELF, AFTER load. Three layers of testing
in a real DE stack:

  1. Unit tests        — functions, no DB
  2. Data quality      — validators.py, on DataFrames, pre-load
  3. Warehouse health  — this script, on DB state, post-load

Checks:
  [1] Schema     — required columns and PostgreSQL types per table
  [2] Row counts — every table has > 0 rows
  [3] Reconciliation — source CSV row count == warehouse row count
  [4] Dim joins  — every fact row resolves to a dimension row

Exit codes: 0 = all pass, 1 = any failure.

Requires WAREHOUSE_DB_URL. Run:  uv run python scripts/validate_warehouse.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


def get_db_url() -> str:
    url = os.environ.get("WAREHOUSE_DB_URL")
    if not url:
        print("ERROR: WAREHOUSE_DB_URL is not set.", file=sys.stderr)
        print('  $env:WAREHOUSE_DB_URL = "postgresql+psycopg2://airflow:changeme@127.0.0.1:5434/airflow"', file=sys.stderr)
        sys.exit(1)
    return url


# ---------------------------------------------------------------------------
# Contracts — the schema these tables are SUPPOSED to have.
# When these change, that change is a reviewed commit to this file.
# ---------------------------------------------------------------------------
EXPECTED_SCHEMAS = {
    "raw.population_by_province": {
        "Province": "text",
        "Population": "bigint",
        "province_code": "text",
    },
    "raw.exchange_rate": {
        "date": "date",
        "purchase": "bigint",
        "sale": "bigint",
        "midpoint": "double precision",
        "exchange_rate": "double precision",
        "spread_market_day_x-1_over_oer_day_x_midpoint": "double precision",
    },
    "dim.dim_date": {
        "date_key": "integer",
        "date": "date",
        "year": "smallint",
        "quarter": "smallint",
        "month": "smallint",
        "month_name": "character varying",
        "day": "smallint",
        "day_of_week": "smallint",
        "day_name": "character varying",
        "is_weekend": "boolean",
        "is_month_start": "boolean",
        "is_month_end": "boolean",
    },
    "dim.dim_province": {
        "province_key": "integer",
        "province_code": "character varying",
        "province_name": "character varying",
    },
}

SOURCE_CSVS = {
    "raw.population_by_province": "data/raw/population_by_province_2024.csv",
    "raw.exchange_rate":          "data/raw/khmer_riel_usd_exchange_rate_2003_2023.csv",
}

CSV_ENCODINGS = {
    "raw.exchange_rate": "utf-8-sig",   # BOM on the date header
}

DIM_JOIN_CHECKS = [
    {
        "name": "population → dim_province",
        "fact": "raw.population_by_province",
        "dim": "dim.dim_province",
        "fact_key": "province_code",
        "dim_key": "province_code",
    },
    {
        "name": "exchange_rate → dim_date",
        "fact": "raw.exchange_rate",
        "dim": "dim.dim_date",
        "fact_key": "date",
        "dim_key": "date",
    },
]


# ---------------------------------------------------------------------------
# Checks — each returns a list of error strings (empty = pass)
# ---------------------------------------------------------------------------
def check_schema(engine, table: str, expected: dict) -> list[str]:
    schema, name = table.split(".")
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = :t"
        ), {"s": schema, "t": name}).fetchall()
    actual = {r[0]: r[1] for r in rows}
    if not actual:
        return [f"{table}: does not exist"]
    errors = []
    for col, exp_type in expected.items():
        if col not in actual:
            errors.append(f"{table}: missing column '{col}'")
        elif actual[col] != exp_type:
            errors.append(
                f"{table}.{col}: type='{actual[col]}', expected='{exp_type}'")
    for col in actual:
        if col not in expected:
            errors.append(f"{table}: unexpected column '{col}'")
    return errors


def check_row_count(engine, table: str) -> list[str]:
    with engine.connect() as conn:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
    return [] if count > 0 else [f"{table}: 0 rows (expected > 0)"]


def check_reconciliation(engine, table: str, csv_path: str) -> list[str]:
    path = Path(csv_path)
    if not path.exists():
        return [f"{table}: source CSV '{csv_path}' not found"]
    encoding = CSV_ENCODINGS.get(table, "utf-8")
    source_rows = len(pd.read_csv(path, encoding=encoding))
    with engine.connect() as conn:
        warehouse_rows = conn.execute(
            text(f"SELECT COUNT(*) FROM {table}")).scalar()
    if source_rows != warehouse_rows:
        return [f"{table}: source={source_rows}, warehouse={warehouse_rows}"]
    return []


def check_dim_join(engine, chk: dict) -> list[str]:
    sql = (
        f"SELECT COUNT(*) FROM {chk['fact']} f "
        f"LEFT JOIN {chk['dim']} d ON f.{chk['fact_key']} = d.{chk['dim_key']} "
        f"WHERE d.{chk['dim_key']} IS NULL"
    )
    with engine.connect() as conn:
        unmatched = conn.execute(text(sql)).scalar()
    return [] if unmatched == 0 else [f"{chk['name']}: {unmatched} unmatched fact rows"]


# ---------------------------------------------------------------------------
def main() -> None:
    engine = create_engine(get_db_url())
    all_errors: list[str] = []

    print("=" * 70)
    print("WAREHOUSE HEALTH CHECK")
    print("=" * 70)

    print("\n[1] Schema checks")
    for table, expected in EXPECTED_SCHEMAS.items():
        errs = check_schema(engine, table, expected)
        if errs:
            for e in errs:
                print(f"    ✗ {e}", file=sys.stderr)
            all_errors.extend(errs)
        else:
            print(f"    ✓ {table}")

    print("\n[2] Row-count checks (must be > 0)")
    for table in EXPECTED_SCHEMAS:
        errs = check_row_count(engine, table)
        if errs:
            for e in errs:
                print(f"    ✗ {e}", file=sys.stderr)
            all_errors.extend(errs)
        else:
            with engine.connect() as conn:
                n = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"    ✓ {table}: {n:,} rows")

    print("\n[3] Reconciliation (source CSV count == warehouse count)")
    for table, csv_path in SOURCE_CSVS.items():
        errs = check_reconciliation(engine, table, csv_path)
        if errs:
            for e in errs:
                print(f"    ✗ {e}", file=sys.stderr)
            all_errors.extend(errs)
        else:
            print(f"    ✓ {table}  ==  {csv_path}")

    print("\n[4] Dimension join checks (unmatched = 0)")
    for chk in DIM_JOIN_CHECKS:
        errs = check_dim_join(engine, chk)
        if errs:
            for e in errs:
                print(f"    ✗ {e}", file=sys.stderr)
            all_errors.extend(errs)
        else:
            print(f"    ✓ {chk['name']}")

    print("\n" + "=" * 70)
    if all_errors:
        print(f"RESULT: {len(all_errors)} FAILURE(S)", file=sys.stderr)
        print("=" * 70)
        sys.exit(1)
    print("RESULT: ALL CHECKS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
