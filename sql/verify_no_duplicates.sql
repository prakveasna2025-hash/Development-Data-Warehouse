-- Aggregate counts: for a healthy 1-province-per-row dataset, all three
-- numbers must be 25.
SELECT
  COUNT(*)                           AS total_rows,
  COUNT(DISTINCT province_code)      AS distinct_codes,
  COUNT(DISTINCT "Province")         AS distinct_names
FROM raw.population_by_province;

-- Duplicate detail: should return zero rows.
SELECT province_code, COUNT(*) AS duplicate_count
FROM raw.population_by_province
GROUP BY province_code
HAVING COUNT(*) > 1;