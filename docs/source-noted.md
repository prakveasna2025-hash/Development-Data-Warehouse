# Source Notes

Provenance and quality notes for every dataset used in this project.
Written at verification time, before any transformation is built on top of the data.

---

## 1. USD/KHR Exchange Rate (2003–2023)

| Field | Value |
|---|---|
| **File** | `data/raw/khmer_riel_usd_exchange_rate_2003_2023.csv` |
| **Originating institution** | National Bank of Cambodia (NBC) |
| **Download origin** | NBC website, directly |
| **URL** | Not recorded at download time. Same series is also published on data.gov.kh. |
| **Access date** | 2026-09-24 (as recorded; approximate) |
| **Format** | CSV, single file (renamed locally after download) |
| **Rows × columns** | 7,531 × 6 |
| **Date range** | 2003-04-01 → 2023-12-31 (daily) |
| **Encoding** | UTF-8 **with BOM** — must load with `encoding="utf-8-sig"` |

### Columns

| Column | Type (as loaded) | Nulls | Notes |
|---|---|---|---|
| `date` | str → `datetime64` | 0 | Format `%m/%d/%Y`; all 7,531 parse |
| `purchase` | int64 | 0 | Bank buy rate |
| `sale` | int64 | 0 | Bank sell rate |
| `midpoint` | float64 | 0 | **Inconsistent rounding — see issues** |
| `exchange_rate` | float64 | 0 | Reference rate |
| `spread_market_day_x-1_over_oer_day_x_midpoint` | float64 | 0 | **Semantics unknown — see issues** |

### Verification result: USABLE WITH DOCUMENTED DEFECTS

Verified on 2026-10-22 via `scripts/verify_exchange_rate.py`.

**Known issues:**

1. **Midpoint rounding inconsistent** — 2,109 of 7,531 rows (28%) store the midpoint rounded up when the exact value ends in `.5`; the rest preserve `.5`. Example: `2015-09-01` purchase=4098, sale=4105 → exact 4101.5, stored 4102. *Mitigation: do not trust the stored `midpoint`; recompute as `(purchase + sale) / 2` downstream.*
2. **Inverted bid/ask — 16 rows** where `purchase > sale`, occurring in consecutive-day runs (2004-04-02; 2006-12-02..03; 2008-05-23..25; 2010-05-13..16; and 6 more). All become normal spreads if purchase/sale are swapped. *Signature of data-entry error, not market behaviour.*
3. **Missing dates — 49 days.** April 2008 is entirely absent (~30 days), plus month-end days in late 2007 / early 2008 (2007-10-31, 2007-11-30, 2008-01-31, 2008-02-29, 2008-03-31), plus ~14 more scattered. *Time-series gaps; affects any day-over-day analysis.*
4. **Spread column semantics unknown.** Min −3.51, max 3.12, 922 negative values. Formula could not be reproduced from the data; matches one formula in early 2003 rows and not later. *Do not use until defined in NBC documentation.*

**Clean checks:** no nulls, no duplicate dates, no unparseable dates, no non-positive numeric values, BOM correctly handled.

---

## 2. Population by Province (Cambodia, 2024)

| Field | Value |
|---|---|
| **File** | `data/raw/population_by_province_2024.csv` |
| **Rows × columns** | 25 × 3 |
| **Columns** | `Province` (str), `Population` (int64), `province_code` (str) |
| **URL** | Not recorded |
| **Access date** | Not recorded |
| **Verification** | Passed all checks on Day 2 (`scripts/verify_population.py`) |

**Verification result: CLEAN.**

25 rows, one per province, no nulls, no duplicate names or codes, all codes match `^KH-\d+$`, all populations positive integers, total 17,280,543 — consistent with Cambodia's 2024 estimate.

*Provenance (URL / access date) not recorded at download time.*