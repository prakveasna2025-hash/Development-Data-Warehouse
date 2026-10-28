"""
Verification script for the NBC exchange rate CSV.

Loads data/raw/khmer_riel_usd_exchange_rate_2003_2023.csv and prints a
report answering: does this file have the shape, types, and values our
pipeline will assume?

Note: this file is KNOWN to have (suspected) issues:
  - BOM character on the 'date' header
  - possible missing dates (e.g. April 2008)
  - possible inverted bid/ask rows
The report is designed to confirm or rule out each.

Run:  uv run python scripts/verify_exchange_rate.py
"""

from pathlib import Path

import pandas as pd
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


CSV_PATH = Path("data/raw/khmer_riel_usd_exchange_rate_2003_2023.csv")


def main() -> None:
    # 1. Load — encoding="utf-8-sig" strips the BOM on the header
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

    logger.info("=" * 70)
    logger.info("EXCHANGE RATE CSV VERIFICATION REPORT")
    logger.info("=" * 70)

    # 2. Shape and columns
    logger.info(f"\n[1] Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    logger.info("    Columns (raw repr, so BOM/invisible chars are visible):")
    for c in df.columns:
        logger.info(f"      {c!r}")

    # 3. Dtypes BEFORE date parsing
    logger.info("\n[2] Dtypes as-loaded (before any conversion):")
    logger.info(df.dtypes.to_string())

    # 4. Parse date explicitly
    parsed = pd.to_datetime(df["date"], format="%m/%d/%Y", errors="coerce")
    bad_dates = parsed.isna() & df["date"].notna()
    logger.info(f"\n[3] Date parsing (format=%m/%d/%Y):")
    logger.info(f"    Unparseable date values: {bad_dates.sum()}")
    logger.info(f"    Min date: {parsed.min().date()}")
    logger.info(f"    Max date: {parsed.max().date()}")
    logger.info(f"    Dtype after parse: {parsed.dtype}")

    # 5. Nulls
    logger.info("\n[4] Null counts per column:")
    logger.info(df.isna().sum().to_string())

    # 6. Duplicate dates
    logger.info("\n[5] Duplicate dates:")
    logger.info(f"    Duplicate date values: {df['date'].duplicated().sum()}")

    # 7. Date gaps — is this a complete daily series?
    expected_days = (parsed.max() - parsed.min()).days + 1
    logger.info("\n[6] Date continuity (expected daily series):")
    logger.info(f"    Expected rows (if complete): {expected_days:,}")
    logger.info(f"    Actual rows:                 {len(df):,}")
    logger.info(
        f"    Missing days:                {expected_days - len(df):,}")

    # Show up to 10 sample missing dates so you can see the pattern
    full_range = pd.date_range(parsed.min(), parsed.max(), freq="D")
    missing = full_range.difference(pd.DatetimeIndex(parsed.dropna()))
    if len(missing):
        logger.info(
            f"    First 10 missing dates: {[d.date().isoformat() for d in missing[:10]]}")

    # 8. Bid/ask sanity — purchase should be <= sale for a normal spread
    inverted = df[df["purchase"] > df["sale"]]
    logger.info(f"\n[7] Inverted bid/ask (purchase > sale): {len(inverted)}")
    if len(inverted):
        logger.info(inverted.head(10).to_string(index=False))

    # 9. Midpoint sanity: should equal (purchase + sale) / 2
    computed_mid = (df["purchase"] + df["sale"]) / 2
    mid_mismatch = (computed_mid - df["midpoint"]).abs() > 0.01
    logger.info(
        f"\n[8] Rows where midpoint != (purchase+sale)/2: {mid_mismatch.sum()}")

    # 10. Non-positive / negative values in numeric columns
    numeric_cols = ["purchase", "sale", "midpoint", "exchange_rate"]
    logger.info("\n[9] Non-positive values per numeric column:")
    for c in numeric_cols:
        n = (df[c] <= 0).sum()
        logger.info(f"    {c}: {n}")

    # 11. The long-named spread column — summary
    spread_col = "spread_market_day_x-1_over_oer_day_x_midpoint"
    logger.info(f"\n[10] '{spread_col}' summary:")
    logger.info(f"     Min: {df[spread_col].min():.4f}")
    logger.info(f"     Max: {df[spread_col].max():.4f}")
    logger.info(f"     Negative rows: {(df[spread_col] < 0).sum()}")

    logger.info("\n" + "=" * 70)
    logger.info("END OF REPORT")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
