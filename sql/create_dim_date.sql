-- ============================================================================
-- dim_date: one row per calendar date, 2003-04-01 → 2023-12-31
-- Range matches raw.exchange_rate's coverage.
-- Re-runnable: DROP + CREATE — safe because nothing depends on it yet.
-- If FKs ever reference dim_date, switch to TRUNCATE + INSERT.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS dim;

DROP TABLE IF EXISTS dim.dim_date;

CREATE TABLE dim.dim_date (
    date_key        INTEGER   PRIMARY KEY,      -- YYYYMMDD
    date            DATE      NOT NULL UNIQUE,  -- the join key
    year            SMALLINT  NOT NULL,
    quarter         SMALLINT  NOT NULL,         -- 1-4
    month           SMALLINT  NOT NULL,         -- 1-12
    month_name      VARCHAR(10) NOT NULL,
    day             SMALLINT  NOT NULL,         -- 1-31
    day_of_week     SMALLINT  NOT NULL,         -- 0=Sunday ... 6=Saturday (Postgres DOW)
    day_name        VARCHAR(10) NOT NULL,
    is_weekend      BOOLEAN   NOT NULL,
    is_month_start  BOOLEAN   NOT NULL,
    is_month_end    BOOLEAN   NOT NULL
);

INSERT INTO dim.dim_date
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER                     AS date_key,
    d::DATE                                             AS date,
    EXTRACT(YEAR    FROM d)::SMALLINT                   AS year,
    EXTRACT(QUARTER FROM d)::SMALLINT                   AS quarter,
    EXTRACT(MONTH   FROM d)::SMALLINT                   AS month,
    TO_CHAR(d, 'FMMonth')                               AS month_name,
    EXTRACT(DAY     FROM d)::SMALLINT                   AS day,
    EXTRACT(DOW     FROM d)::SMALLINT                   AS day_of_week,
    TO_CHAR(d, 'FMDay')                                 AS day_name,
    EXTRACT(DOW FROM d) IN (0, 6)                       AS is_weekend,
    d = DATE_TRUNC('month', d)::DATE                    AS is_month_start,
    d = (DATE_TRUNC('month', d) + INTERVAL '1 month - 1 day')::DATE AS is_month_end
FROM generate_series(
    '2003-04-01'::DATE,
    '2023-12-31'::DATE,
    '1 day'::INTERVAL
) AS d;

-- Sanity check
SELECT COUNT(*) AS dim_date_rows FROM dim.dim_date;
-- Expected: 7580 (the "expected rows if complete" from Day 3's report)