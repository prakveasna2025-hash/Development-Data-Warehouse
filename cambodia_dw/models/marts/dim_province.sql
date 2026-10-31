{{ config(materialized='table') }}

SELECT
    province_key::int    AS province_key,
    province_code::text  AS province_code,
    province_name::text  AS province_name
FROM {{ ref('province_reference') }}