{{ config(materialized='table') }}

-- Snapshot fact: one row per province per snapshot year.
-- Source provides only 2024. When more years arrive, add rows — no schema change.
-- Join to dim_province via surrogate key (province_key) — natural key kept for BI convenience.

SELECT
    p.province_key::int       AS province_key,
    p.province_code::text     AS province_code,
    p.province_name::text     AS province_name,
    2024::smallint            AS snapshot_year,
    pop.population::bigint    AS population
FROM {{ ref('stg_population') }} pop
JOIN {{ ref('dim_province') }} p
    ON pop.province_code = p.province_code