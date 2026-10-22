"""
Verification script for the population CSV.

Loads data/raw/population_by_province_2024.csv and prints a report
answering: does this file have the shape, types, and values our pipeline
will assume?

Run:  uv run python scripts/verify_population.py
"""

from pathlib import Path

import pandas as pd


CSV_PATH = Path("data/raw/population_by_province_2024.csv")


def main() -> None:
    # 1. Load
    df = pd.read_csv(CSV_PATH)

    print("=" * 60)
    print("POPULATION CSV VERIFICATION REPORT")
    print("=" * 60)

    # 2. Shape and columns
    print(f"\n[1] Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    print(f"    Columns: {list(df.columns)}")

    # 3. Data types
    print("\n[2] Data types:")
    print(df.dtypes.to_string())

    # 4. Nulls per column
    print("\n[3] Null counts per column:")
    print(df.isna().sum().to_string())

    # 5. Duplicates on the two key fields
    print("\n[4] Duplicates:")
    print(f"    Duplicate province names: {df['Province'].duplicated().sum()}")
    print(f"    Duplicate province codes: {df['province_code'].duplicated().sum()}")

    # 6. Province code format
    pattern = r"^KH-\d+$"
    bad_codes = df.loc[~df["province_code"].astype(str).str.match(pattern)]
    print(f"\n[5] Codes not matching KH-<digits>: {len(bad_codes)}")
    if len(bad_codes):
        print(bad_codes[["Province", "province_code"]].to_string(index=False))

    # 7. Population sanity
    print("\n[6] Population summary:")
    print(f"    Min:   {df['Population'].min():,}")
    print(f"    Max:   {df['Population'].max():,}")
    print(f"    Total: {df['Population'].sum():,}")
    print(f"    Non-positive values: {(df['Population'] <= 0).sum()}")

    # 8. Province names (full list)
    print("\n[7] All 25 province names (sorted):")
    for name in sorted(df["Province"].unique()):
        print(f"    - {name}")

    print("\n" + "=" * 60)
    print("END OF REPORT")
    print("=" * 60)


if __name__ == "__main__":
    main()