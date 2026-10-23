SELECT province_code, "Province", "Population"
FROM raw.population_by_province
ORDER BY "Population" DESC
LIMIT 5;