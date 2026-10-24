"""
Reusable data quality validators.

Each validate_* function takes a DataFrame and returns a list of failure
messages. An empty list means validation passed.
"""

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
