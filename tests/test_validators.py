"""
Tests for scripts/validators.py.

Each test:
  1. Starts from a valid baseline (fixture)
  2. Injects one specific defect
  3. Asserts the specific error appears in the returned list

A passing test proves the validator catches that defect. A failing test
means either the validator has a bug or the expected error message changed.
"""

import pandas as pd
import pytest

from scripts.validators import validate_population, validate_exchange_rate


# ---------------------------------------------------------------------------
# Population
# ---------------------------------------------------------------------------
def test_validate_population_valid_baseline(valid_population_df):
    """A clean population DataFrame passes with no errors."""
    assert validate_population(valid_population_df) == []


def test_validate_population_detects_null(valid_population_df):
    df = valid_population_df.copy()
    df.loc[0, "Population"] = None
    errors = validate_population(df)
    assert any("null" in e.lower() for e in errors), errors


def test_validate_population_detects_duplicate_code(valid_population_df):
    df = valid_population_df.copy()
    df.loc[1, "province_code"] = df.loc[0, "province_code"]
    errors = validate_population(df)
    assert any("duplicate province_code" in e.lower() for e in errors), errors


def test_validate_population_detects_duplicate_name(valid_population_df):
    df = valid_population_df.copy()
    df.loc[1, "Province"] = df.loc[0, "Province"]
    errors = validate_population(df)
    assert any("duplicate province name" in e.lower() for e in errors), errors


def test_validate_population_detects_bad_code_format(valid_population_df):
    df = valid_population_df.copy()
    df.loc[0, "province_code"] = "KH-XX"
    errors = validate_population(df)
    assert any("KH-<digits>" in e for e in errors), errors


def test_validate_population_detects_missing_code(valid_population_df):
    df = valid_population_df.copy()
    df.loc[0, "province_code"] = "KH-99"   # valid format, wrong set member
    errors = validate_population(df)
    assert any("Unexpected province codes" in e for e in errors), errors
    assert any("Missing expected province codes" in e for e in errors), errors


def test_validate_population_detects_wrong_row_count(valid_population_df):
    df = valid_population_df.drop(index=0)
    errors = validate_population(df)
    assert any("Row count" in e for e in errors), errors


def test_validate_population_detects_wrong_sum(valid_population_df):
    df = valid_population_df.copy()
    df.loc[0, "Population"] = df.loc[0, "Population"] + 1
    errors = validate_population(df)
    assert any("Population sum" in e for e in errors), errors


# ---------------------------------------------------------------------------
# Exchange rate
# ---------------------------------------------------------------------------
def test_validate_exchange_rate_valid_baseline(valid_exchange_df):
    """The real source file (with its documented defects) passes."""
    assert validate_exchange_rate(valid_exchange_df.copy()) == []


def test_validate_exchange_rate_detects_null(valid_exchange_df):
    df = valid_exchange_df.copy()
    df.loc[0, "exchange_rate"] = None
    errors = validate_exchange_rate(df)
    assert any("null" in e.lower() for e in errors), errors


def test_validate_exchange_rate_detects_duplicate_date(valid_exchange_df):
    df = valid_exchange_df.copy()
    df.loc[1, "date"] = df.loc[0, "date"]
    errors = validate_exchange_rate(df)
    assert any("duplicate date" in e.lower() for e in errors), errors


def test_validate_exchange_rate_detects_changed_inverted_count(valid_exchange_df):
    df = valid_exchange_df.copy()
    # Force one more inverted row — purchase > sale where it previously wasn't
    mask = df["purchase"] <= df["sale"]
    idx = df[mask].index[0]
    df.loc[idx, "purchase"] = df.loc[idx, "sale"] + 100
    errors = validate_exchange_rate(df)
    assert any("Inverted" in e for e in errors), errors
