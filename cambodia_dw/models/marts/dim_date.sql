{{ config(materialized='table') }}

WITH dates AS (
    SELECT generate_series(
        '2003-04-01'::date,
        '2023-12-31'::date,
        '1 day'::interval
    )::date AS date
)
SELECT
    TO_CHAR(date, 'YYYYMMDD')::int                                       AS date_key,
    date                                                                 AS date,
    EXTRACT(YEAR    FROM date)::smallint                                 AS year,
    EXTRACT(QUARTER FROM date)::smallint                                 AS quarter,
    EXTRACT(MONTH   FROM date)::smallint                                 AS month,
    TO_CHAR(date, 'FMMonth')                                             AS month_name,
    EXTRACT(DAY     FROM date)::smallint                                 AS day,
    EXTRACT(DOW     FROM date)::smallint                                 AS day_of_week,
    TO_CHAR(date, 'FMDay')                                               AS day_name,
    (EXTRACT(DOW FROM date) IN (0, 6))::boolean                          AS is_weekend,
    (date = DATE_TRUNC('month', date)::date)::boolean                    AS is_month_start,
    (date = (DATE_TRUNC('month', date) + INTERVAL '1 month - 1 day')::date)::boolean AS is_month_end
FROM dates