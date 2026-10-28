"""
Verification script for the population CSV.

Loads data/raw/population_by_province_2024.csv and prints a report
answering: does this file have the shape, types, and values our pipeline
will assume?

Run:  uv run python scripts/verify_population.py
"""

from pathlib import Path

import pandas as pd
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

CSV_PATH = Path("data/raw/population_by_province_2024.csv")


def main() -> None:
    # 1. Load
    df = pd.read_csv(CSV_PATH)

    logger.info("=" * 60)
    logger.info("POPULATION CSV VERIFICATION REPORT")
    logger.info("=" * 60)

    # 2. Shape and columns
    logger.info(f"\n[1] Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    logger.info(f"    Columns: {list(df.columns)}")

    # 3. Data types
    logger.info("\n[2] Data types:")
    logger.info(df.dtypes.to_string())

    # 4. Nulls per column
    logger.info("\n[3] Null counts per column:")
    logger.info(df.isna().sum().to_string())

    # 5. Duplicates on the two key fields
    logger.info("\n[4] Duplicates:")
    logger.info(
        f"    Duplicate province names: {df['Province'].duplicated().sum()}")
    logger.info(
        f"    Duplicate province codes: {df['province_code'].duplicated().sum()}")

    # 6. Province code format
    pattern = r"^KH-\d+$"
    bad_codes = df.loc[~df["province_code"].astype(str).str.match(pattern)]
    logger.info(f"\n[5] Codes not matching KH-<digits>: {len(bad_codes)}")
    if len(bad_codes):
        logger.info(
            bad_codes[["Province", "province_code"]].to_string(index=False))

    # 7. Population sanity
    logger.info("\n[6] Population summary:")
    logger.info(f"    Min:   {df['Population'].min():,}")
    logger.info(f"    Max:   {df['Population'].max():,}")
    logger.info(f"    Total: {df['Population'].sum():,}")
    logger.info(f"    Non-positive values: {(df['Population'] <= 0).sum()}")

    # 8. Province names (full list)
    logger.info("\n[7] All 25 province names (sorted):")
    for name in sorted(df["Province"].unique()):
        logger.info(f"    - {name}")

    logger.info("\n" + "=" * 60)
    logger.info("END OF REPORT")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
