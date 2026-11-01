{{ config(materialized='table') }}

-- Transactional fact: one row per trading date.
-- Join to dim_date via surrogate key (date_key) — natural key kept for BI convenience.
-- Defects loaded as-is (Day 3): 16 inverted rows, 49 missing days, 2,109 midpoint inconsistencies.
-- spread_value semantics UNKNOWN — do not use downstream.

SELECT
    d.date_key::int                              AS date_key,
    e.date::date                                 AS date,
    e.purchase::bigint                           AS purchase,
    e.sale::bigint                               AS sale,
    e.midpoint::double precision                 AS midpoint,
    e.exchange_rate::double precision            AS exchange_rate,
    e.spread_value::double precision             AS spread_value
FROM {{ ref('stg_exchange_rate') }} e
JOIN {{ ref('dim_date') }} d
    ON e.date = d.date