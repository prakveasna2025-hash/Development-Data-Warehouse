{{
    config(
        materialized='view',
    )
}}

-- Staging: raw.population_by_province → snake_case + explicit types.
-- Grain: one row per province (25 rows).
-- No filtering, no joins, no aggregation — those belong downstream.

SELECT
    province_code            AS province_code,
    "Province"::text         AS province_name,
    "Population"::bigint     AS population
FROM {{ source('raw', 'population_by_province') }}