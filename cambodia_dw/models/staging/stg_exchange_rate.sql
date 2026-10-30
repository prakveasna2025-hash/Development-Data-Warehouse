{{
    config(
        materialized='view',
    )
}}

-- Staging: raw.exchange_rate → 1:1 view with clean column names.
-- Grain: one row per trading date (7,531 rows).
-- No filtering, no joins, no aggregation.
--
-- Documented defects loaded AS-IS (Day 3, docs/source-notes.md):
--   - 16 inverted bid/ask rows (purchase > sale)
--   - 49 missing days (April 2008 fully absent + scattered)
--   - 2,109 midpoint rounding inconsistencies
--
-- The spread column has unknown semantics (see spread_value description).

SELECT
    date::date                                                       AS date,
    purchase::bigint                                                 AS purchase,
    sale::bigint                                                     AS sale,
    midpoint::double precision                                       AS midpoint,
    exchange_rate::double precision                                  AS exchange_rate,
    "spread_market_day_x-1_over_oer_day_x_midpoint"::double precision AS spread_value
FROM {{ source('raw', 'exchange_rate') }}


