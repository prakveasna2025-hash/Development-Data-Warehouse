"""
Warehouse health check — run AFTER extraction, against actual warehouse state.

Unlike scripts/validators.py (which validates DataFrames BEFORE load), this
script validates the WAREHOUSE ITSELF, AFTER load. Three layers of testing
in a real DE stack:

  1. Unit tests        — functions, no DB
  2. Data quality      — validators.py, on DataFrames, pre-load
  3. Warehouse health  — this script, on DB state, post-load

Checks:
  [1] Schema          — required columns and PostgreSQL types per table
  [2] Row counts      — every table has > 0 rows
  [3] Reconciliation  — source CSV row count == warehouse row count
  [4] Dimension joins — every fact row resolves to a dimension row
  [5] Nulls           — no NULL values in NOT-NULL-intent columns
  [6] Duplicates      — no duplicate values in natural-key columns
  [7] References      — fact keys are a subset of dimension keys

Exit codes: 0 = all pass, 1 = any failure.

Requires WAREHOUSE_DB_URL. Run:  uv run python scripts/validate_warehouse.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def get_db_url() -> str:
    url = os.environ.get("WAREHOUSE_DB_URL")
    if not url:
        logger.error("ERROR: WAREHOUSE_DB_URL is not set.")
        logger.error(
            '  $env:WAREHOUSE_DB_URL = "postgresql+psycopg2://airflow:changeme@127.0.0.1:5434/airflow"'
        )
        sys.exit(1)
    return url


# ---------------------------------------------------------------------------
# Contracts — what these tables are SUPPOSED to have.
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
    "raw.exchange_rate": "data/raw/khmer_riel_usd_exchange_rate_2003_2023.csv",
}

CSV_ENCODINGS = {
    "raw.exchange_rate": "utf-8-sig",
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
# [5] Null checks — columns that MUST NOT contain NULLs.
# ---------------------------------------------------------------------------
NULL_CHECKS = {
    "raw.population_by_province": ["Province", "Population", "province_code"],
    "raw.exchange_rate": ["date", "purchase", "sale", "midpoint", "exchange_rate"],
    "dim.dim_date": ["date", "date_key", "year", "month", "day"],
    "dim.dim_province": ["province_code", "province_name"],
}

# ---------------------------------------------------------------------------
# [6] Duplicate checks — columns that MUST be UNIQUE.
# ---------------------------------------------------------------------------
DUPLICATE_CHECKS = {
    "raw.population_by_province": ["Province", "province_code"],
    "raw.exchange_rate": ["date"],
    "dim.dim_date": ["date", "date_key"],
    "dim.dim_province": ["province_code", "province_name"],
}

# ---------------------------------------------------------------------------
# [7] Reference checks — fact keys MUST be a subset of dimension keys.
# (Explicit set-membership; complements the join check which finds
# orphaned rows. NOT IN fails if dim has NULLs, but dim keys are NOT NULL.)
# ---------------------------------------------------------------------------
REFERENCE_CHECKS = [
    {
        "name": "raw.population_by_province.province_code ⊆ dim.dim_province",
        "fact": "raw.population_by_province",
        "fact_col": "province_code",
        "dim": "dim.dim_province",
        "dim_col": "province_code",
    },
    {
        "name": "raw.exchange_rate.date ⊆ dim.dim_date",
        "fact": "raw.exchange_rate",
        "fact_col": "date",
        "dim": "dim.dim_date",
        "dim_col": "date",
    },
]


# ---------------------------------------------------------------------------
# Checks — each returns a list of error strings (empty = pass)
# ---------------------------------------------------------------------------
def check_schema(engine, table: str, expected: dict) -> list[str]:
    schema, name = table.split(".")
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t"
            ),
            {"s": schema, "t": name},
        ).fetchall()
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


def check_nulls(engine, table: str, columns: list[str]) -> list[str]:
    errors = []
    with engine.connect() as conn:
        for col in columns:
            n = conn.execute(
                text(f'SELECT COUNT(*) FROM {table} WHERE "{col}" IS NULL')
            ).scalar()
            if n:
                errors.append(f"{table}.{col}: {n} NULL row(s)")
    return errors


def check_duplicates(engine, table: str, columns: list[str]) -> list[str]:
    errors = []
    with engine.connect() as conn:
        for col in columns:
            n = conn.execute(
                text(
                    f'SELECT COUNT(*) FROM ('
                    f'  SELECT "{col}" FROM {table} '
                    f'  GROUP BY "{col}" HAVING COUNT(*) > 1'
                    f') AS dups'
                )
            ).scalar()
            if n:
                errors.append(f"{table}.{col}: {n} duplicated value(s)")
    return errors


def check_reference(engine, chk: dict) -> list[str]:
    sql = (
        f"SELECT COUNT(*) FROM {chk['fact']} f "
        f"WHERE f.{chk['fact_col']} NOT IN "
        f"(SELECT {chk['dim_col']} FROM {chk['dim']})"
    )
    with engine.connect() as conn:
        orphans = conn.execute(text(sql)).scalar()
    return [] if orphans == 0 else [f"{chk['name']}: {orphans} key(s) not in dimension"]


# ---------------------------------------------------------------------------
def main() -> None:
    engine = create_engine(get_db_url())
    all_errors: list[str] = []

    logger.info("=" * 70)
    logger.info("WAREHOUSE HEALTH CHECK")
    logger.info("=" * 70)

    logger.info("\n[1] Schema checks")
    for table, expected in EXPECTED_SCHEMAS.items():
        errs = check_schema(engine, table, expected)
        if errs:
            for e in errs:
                logger.error(f"    ✗ {e}")
            all_errors.extend(errs)
        else:
            logger.info(f"    ✓ {table}")

    logger.info("\n[2] Row-count checks (must be > 0)")
    for table in EXPECTED_SCHEMAS:
        errs = check_row_count(engine, table)
        if errs:
            for e in errs:
                logger.error(f"    ✗ {e}")
            all_errors.extend(errs)
        else:
            with engine.connect() as conn:
                n = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table}")).scalar()
            logger.info(f"    ✓ {table}: {n:,} rows")

    logger.info("\n[3] Reconciliation (source CSV count == warehouse count)")
    for table, csv_path in SOURCE_CSVS.items():
        errs = check_reconciliation(engine, table, csv_path)
        if errs:
            for e in errs:
                logger.error(f"    ✗ {e}")
            all_errors.extend(errs)
        else:
            logger.info(f"    ✓ {table}  ==  {csv_path}")

    logger.info("\n[4] Dimension join checks (unmatched = 0)")
    for chk in DIM_JOIN_CHECKS:
        errs = check_dim_join(engine, chk)
        if errs:
            for e in errs:
                logger.error(f"    ✗ {e}")
            all_errors.extend(errs)
        else:
            logger.info(f"    ✓ {chk['name']}")

    logger.info("\n[5] Null checks")
    for table, cols in NULL_CHECKS.items():
        errs = check_nulls(engine, table, cols)
        if errs:
            for e in errs:
                logger.error(f"    ✗ {e}")
            all_errors.extend(errs)
        else:
            logger.info(f"    ✓ {table}")

    logger.info("\n[6] Duplicate checks")
    for table, cols in DUPLICATE_CHECKS.items():
        errs = check_duplicates(engine, table, cols)
        if errs:
            for e in errs:
                logger.error(f"    ✗ {e}")
            all_errors.extend(errs)
        else:
            logger.info(f"    ✓ {table}")

    logger.info("\n[7] Reference checks (fact keys ⊆ dimension keys)")
    for chk in REFERENCE_CHECKS:
        errs = check_reference(engine, chk)
        if errs:
            for e in errs:
                logger.error(f"    ✗ {e}")
            all_errors.extend(errs)
        else:
            logger.info(f"    ✓ {chk['name']}")

    logger.info("\n" + "=" * 70)
    if all_errors:
        logger.error(f"RESULT: {len(all_errors)} FAILURE(S)")
        logger.error("=" * 70)
        sys.exit(1)
    logger.info("RESULT: ALL CHECKS PASSED")
    logger.info("\n" + "=" * 70)


if __name__ == "__main__":
    main()
