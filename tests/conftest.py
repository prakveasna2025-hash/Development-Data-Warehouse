"""
Pytest fixtures — baseline DataFrames built from the real source CSVs.

Tests mutate copies of these to inject specific defects and verify the
validators catch them.
"""

from pathlib import Path

import pandas as pd
import pytest


DATA_DIR = Path(__file__).parent.parent / "data" / "raw"


@pytest.fixture
def valid_population_df() -> pd.DataFrame:
    """Baseline population DataFrame — 25 rows, clean."""
    return pd.read_csv(DATA_DIR / "population_by_province_2024.csv")


@pytest.fixture(scope="module")
def valid_exchange_df() -> pd.DataFrame:
    """Baseline exchange-rate DataFrame — 7,531 rows, includes documented defects."""
    return pd.read_csv(
        DATA_DIR / "khmer_riel_usd_exchange_rate_2003_2023.csv",
        encoding="utf-8-sig",
    ).assign(date=lambda d: pd.to_datetime(d["date"], format="%m/%d/%Y"))
