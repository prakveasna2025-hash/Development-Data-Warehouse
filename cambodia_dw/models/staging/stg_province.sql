{{
    config(
        materialized='view',
    )
}}

-- Staging: dim.dim_province → consistent naming + typed.
-- Grain: one row per province (25 rows).
-- This is a pass-through — dim_province is already well-formed (Day 13).
-- Value: downstream models reference stg_province and don't need to know
-- whether a source lives in raw or dim.

SELECT
    province_key            AS province_key,
    province_code           AS province_code,
    province_name::text     AS province_name
FROM {{ source('dim', 'dim_province') }}