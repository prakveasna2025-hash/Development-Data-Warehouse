"""
Reusable data quality validators.

Each validate_* function takes a DataFrame and returns a list of failure
messages. An empty list means validation passed.
"""

from datetime import date as _date
import pandas as pd


# Business rules for the 2024 population snapshot.
# Static because the source is a one-off snapshot, not a live feed —
# if these values change, we want the pipeline to fail loudly.
EXPECTED_ROW_COUNT = 25
EXPECTED_PROVINCE_CODES = {f"KH-{i}" for i in range(1, 26)}
EXPECTED_POPULATION_SUM = 17_280_543


def validate_population(df: pd.DataFrame) -> list[str]:
    """Return list of failure messages for the population dataset. Empty = pass."""
    errors: list[str] = []

    # 1. Required columns
    required = {"Province", "Population", "province_code"}
    missing = required - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {missing}")
        return errors  # Can't check further without the columns

    # 2. Nulls
    for col, count in df.isna().sum().items():
        if count:
            errors.append(f"Column '{col}' has {count} null value(s)")

    # 3. Duplicate province names
    dup_names = int(df["Province"].duplicated().sum())
    if dup_names:
        errors.append(f"{dup_names} duplicate Province name(s)")

    # 4. Duplicate province codes
    dup_codes = int(df["province_code"].duplicated().sum())
    if dup_codes:
        errors.append(f"{dup_codes} duplicate province_code value(s)")

    # 5. Code format
    bad_codes = df.loc[~df["province_code"].astype(str).str.match(r"^KH-\d+$")]
    if len(bad_codes):
        errors.append(
            f"{len(bad_codes)} province_code(s) do not match KH-<digits>: "
            f"{bad_codes['province_code'].tolist()}"
        )

    # 6. Contiguity — all expected codes present, none extra
    present_codes = set(df["province_code"].astype(str))
    missing_codes = EXPECTED_PROVINCE_CODES - present_codes
    extra_codes = present_codes - EXPECTED_PROVINCE_CODES
    if missing_codes:
        errors.append(
            f"Missing expected province codes: {sorted(missing_codes)}")
    if extra_codes:
        errors.append(f"Unexpected province codes: {sorted(extra_codes)}")

    # 7. Row count
    if len(df) != EXPECTED_ROW_COUNT:
        errors.append(f"Row count is {len(df)}, expected {EXPECTED_ROW_COUNT}")

    # 8. Population dtype / positivity
    if not pd.api.types.is_integer_dtype(df["Population"]):
        errors.append(
            f"Population dtype is {df['Population'].dtype}, expected integer")
    non_positive = int((df["Population"] <= 0).sum())
    if non_positive:
        errors.append(f"{non_positive} non-positive Population value(s)")

    # 9. Sum sanity — exact match (static snapshot)
    total = int(df["Population"].sum())
    if total != EXPECTED_POPULATION_SUM:
        errors.append(
            f"Population sum is {total:,}, expected {EXPECTED_POPULATION_SUM:,}")

    return errors
# ============================================================================
# Exchange rate — strict-with-documented-exceptions
#
# The source has KNOWN defects (Day 3). Validation should:
#   - Pass when defects match documented counts (no new corruption)
#   - Fail when counts differ (source changed, or defects got fixed upstream)
# ============================================================================


EXPECTED_EXCHANGE_ROWS = 7531
EXPECTED_INVERTED_ROWS = 16    # Day 3: purchase > sale, in date runs
EXPECTED_MISSING_DAYS = 49    # Day 3: April 2008 fully absent + scattered
EXPECTED_EXCHANGE_MIN_DATE = _date(2003, 4, 1)
EXPECTED_EXCHANGE_MAX_DATE = _date(2023, 12, 31)

EXCHANGE_REQUIRED_COLUMNS = {
    "date",
    "purchase",
    "sale",
    "midpoint",
    "exchange_rate",
    "spread_market_day_x-1_over_oer_day_x_midpoint",
}

EXCHANGE_NUMERIC_COLUMNS = ["purchase", "sale", "midpoint", "exchange_rate"]


def validate_exchange_rate(df: pd.DataFrame) -> list[str]:
    """Return list of failure messages for the exchange-rate dataset. Empty = pass."""
    errors: list[str] = []

    # 1. Required columns
    missing = EXCHANGE_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {missing}")
        return errors

    # 2. Nulls
    for col, count in df.isna().sum().items():
        if count:
            errors.append(f"Column '{col}' has {count} null value(s)")

    # 3. Duplicate dates
    dup_dates = int(df["date"].duplicated().sum())
    if dup_dates:
        errors.append(f"{dup_dates} duplicate date value(s)")

    # 4. Date parsing — accept datetime64 or coerce string
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        parsed = pd.to_datetime(df["date"], format="%m/%d/%Y", errors="coerce")
        bad = int(parsed.isna().sum() - df["date"].isna().sum())
        if bad:
            errors.append(f"{bad} unparseable date value(s)")
    else:
        parsed = df["date"]

    # 5. Non-positive numeric values
    for col in EXCHANGE_NUMERIC_COLUMNS:
        n = int((df[col] <= 0).sum())
        if n:
            errors.append(f"Column '{col}': {n} non-positive value(s)")

    # 6. Row count — exact match expected
    if len(df) != EXPECTED_EXCHANGE_ROWS:
        errors.append(
            f"Row count is {len(df)}, expected {EXPECTED_EXCHANGE_ROWS}")

    # 7. Documented defect: inverted bid/ask — exact count expected
    inverted = int((df["purchase"] > df["sale"]).sum())
    if inverted != EXPECTED_INVERTED_ROWS:
        errors.append(
            f"Inverted bid/ask rows = {inverted}, expected {EXPECTED_INVERTED_ROWS} "
            f"(source drift or upstream fix — investigate before proceeding)"
        )

    # 8. Date range boundaries
    if parsed.notna().any():
        min_d = parsed.min().date()
        max_d = parsed.max().date()
        if min_d != EXPECTED_EXCHANGE_MIN_DATE:
            errors.append(
                f"Min date {min_d}, expected {EXPECTED_EXCHANGE_MIN_DATE}")
        if max_d != EXPECTED_EXCHANGE_MAX_DATE:
            errors.append(
                f"Max date {max_d}, expected {EXPECTED_EXCHANGE_MAX_DATE}")

        # 9. Documented defect: missing days — exact count expected
        expected_span = (parsed.max() - parsed.min()).days + 1
        missing_days = expected_span - len(df)
        if missing_days != EXPECTED_MISSING_DAYS:
            errors.append(
                f"Missing days = {missing_days}, expected {EXPECTED_MISSING_DAYS} "
                f"(gap size changed — investigate)"
            )

    return errors
