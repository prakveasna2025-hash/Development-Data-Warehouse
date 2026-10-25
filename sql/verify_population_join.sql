-- ============================================================================
-- Verify raw.population_by_province joins to dim.dim_province
-- ============================================================================

-- 1. Forward join: every fact must resolve to a dimension row
SELECT
    (SELECT COUNT(*) FROM raw.population_by_province)                                          AS fact_rows,
    (SELECT COUNT(*) FROM dim.dim_province)                                                     AS dim_rows,
    (SELECT COUNT(*) FROM raw.population_by_province p
       JOIN dim.dim_province d ON p.province_code = d.province_code)                            AS joined_rows,
    (SELECT COUNT(*) FROM raw.population_by_province p
       LEFT JOIN dim.dim_province d ON p.province_code = d.province_code
       WHERE d.province_code IS NULL)                                                           AS unmatched_rows;

-- 2. Sample: fact enriched with canonical dimension name
SELECT
    p.province_code,
    p."Province"   AS source_name,
    d.province_name AS dim_name,
    p."Population"
FROM raw.population_by_province p
JOIN dim.dim_province d ON p.province_code = d.province_code
ORDER BY p."Population" DESC
LIMIT 5;

-- 3. Name governance: source names should match canonical dimension names
SELECT
    p.province_code,
    p."Province"   AS source_name,
    d.province_name AS dim_name
FROM raw.population_by_province p
JOIN dim.dim_province d ON p.province_code = d.province_code
WHERE p."Province" <> d.province_name;
-- Expected: 0 rows. Any row here is a data quality issue that would corrupt
-- reports grouping by province name.