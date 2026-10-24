-- ============================================================================
-- Verify raw.exchange_rate joins to dim.dim_date
-- ============================================================================

-- 1. Aggregate counts
SELECT
    (SELECT COUNT(*) FROM raw.exchange_rate)                                         AS exchange_rows,
    (SELECT COUNT(*) FROM dim.dim_date)                                              AS dim_date_rows,
    (SELECT COUNT(*) FROM raw.exchange_rate r
       JOIN dim.dim_date d ON r.date = d.date)                                       AS joined_rows,
    (SELECT COUNT(*) FROM raw.exchange_rate r
       LEFT JOIN dim.dim_date d ON r.date = d.date
       WHERE d.date IS NULL)                                                         AS unmatched_rows;

-- 2. Sample: recent exchange rates enriched with dim_date attributes
SELECT
    r.date,
    d.year,
    d.quarter,
    d.month_name,
    d.day_name,
    d.is_weekend,
    r.purchase,
    r.sale
FROM raw.exchange_rate r
JOIN dim.dim_date d ON r.date = d.date
ORDER BY r.date DESC
LIMIT 5;

-- 3. The 49 missing days — visible as dim_date rows with no exchange rate
SELECT d.date, d.day_name
FROM dim.dim_date d
LEFT JOIN raw.exchange_rate r ON r.date = d.date
WHERE r.date IS NULL
ORDER BY d.date
LIMIT 15;