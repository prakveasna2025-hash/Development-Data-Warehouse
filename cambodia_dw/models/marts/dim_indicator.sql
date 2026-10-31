{{ config(materialized='table') }}

SELECT
    indicator_key::int           AS indicator_key,
    indicator_code::text         AS indicator_code,
    indicator_name::text         AS indicator_name,
    indicator_unit::text         AS indicator_unit,
    indicator_grain::text        AS indicator_grain,
    indicator_source_table::text AS indicator_source_table,
    description::text            AS description
FROM {{ ref('indicator_reference') }}