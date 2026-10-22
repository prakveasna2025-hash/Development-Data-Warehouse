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


CSV_PATH = Path("data/raw/khmer_riel_usd_exchange_rate_2003_2023.csv")


def main() -> None:
    # 1. Load — encoding="utf-8-sig" strips the BOM on the header
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

    print("=" * 70)
    print("EXCHANGE RATE CSV VERIFICATION REPORT")
    print("=" * 70)

    # 2. Shape and columns
    print(f"\n[1] Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    print("    Columns (raw repr, so BOM/invisible chars are visible):")
    for c in df.columns:
        print(f"      {c!r}")

    # 3. Dtypes BEFORE date parsing
    print("\n[2] Dtypes as-loaded (before any conversion):")
    print(df.dtypes.to_string())

    # 4. Parse date explicitly
    parsed = pd.to_datetime(df["date"], format="%m/%d/%Y", errors="coerce")
    bad_dates = parsed.isna() & df["date"].notna()
    print(f"\n[3] Date parsing (format=%m/%d/%Y):")
    print(f"    Unparseable date values: {bad_dates.sum()}")
    print(f"    Min date: {parsed.min().date()}")
    print(f"    Max date: {parsed.max().date()}")
    print(f"    Dtype after parse: {parsed.dtype}")

    # 5. Nulls
    print("\n[4] Null counts per column:")
    print(df.isna().sum().to_string())

    # 6. Duplicate dates
    print("\n[5] Duplicate dates:")
    print(f"    Duplicate date values: {df['date'].duplicated().sum()}")

    # 7. Date gaps — is this a complete daily series?
    expected_days = (parsed.max() - parsed.min()).days + 1
    print("\n[6] Date continuity (expected daily series):")
    print(f"    Expected rows (if complete): {expected_days:,}")
    print(f"    Actual rows:                 {len(df):,}")
    print(f"    Missing days:                {expected_days - len(df):,}")

    # Show up to 10 sample missing dates so you can see the pattern
    full_range = pd.date_range(parsed.min(), parsed.max(), freq="D")
    missing = full_range.difference(pd.DatetimeIndex(parsed.dropna()))
    if len(missing):
        print(
            f"    First 10 missing dates: {[d.date().isoformat() for d in missing[:10]]}")

    # 8. Bid/ask sanity — purchase should be <= sale for a normal spread
    inverted = df[df["purchase"] > df["sale"]]
    print(f"\n[7] Inverted bid/ask (purchase > sale): {len(inverted)}")
    if len(inverted):
        print(inverted.head(10).to_string(index=False))

    # 9. Midpoint sanity: should equal (purchase + sale) / 2
    computed_mid = (df["purchase"] + df["sale"]) / 2
    mid_mismatch = (computed_mid - df["midpoint"]).abs() > 0.01
    print(
        f"\n[8] Rows where midpoint != (purchase+sale)/2: {mid_mismatch.sum()}")

    # 10. Non-positive / negative values in numeric columns
    numeric_cols = ["purchase", "sale", "midpoint", "exchange_rate"]
    print("\n[9] Non-positive values per numeric column:")
    for c in numeric_cols:
        n = (df[c] <= 0).sum()
        print(f"    {c}: {n}")

    # 11. The long-named spread column — summary
    spread_col = "spread_market_day_x-1_over_oer_day_x_midpoint"
    print(f"\n[10] '{spread_col}' summary:")
    print(f"     Min: {df[spread_col].min():.4f}")
    print(f"     Max: {df[spread_col].max():.4f}")
    print(f"     Negative rows: {(df[spread_col] < 0).sum()}")

    print("\n" + "=" * 70)
    print("END OF REPORT")
    print("=" * 70)


if __name__ == "__main__":
    main()
