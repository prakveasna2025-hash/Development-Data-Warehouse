-- ============================================================================
-- dim_province: canonical province dimension (25 rows)
--
-- Seeded from controlled reference data, NOT derived from
-- raw.population_by_province. The dimension is the SPEC — it governs which
-- province codes are allowed in fact tables. Deriving it from facts would
-- make it circular (dim = SELECT DISTINCT from fact → cannot verify fact).
--
-- When provinces are added/renamed/split, this file changes via a reviewed
-- commit. That is the governance.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS dim;

DROP TABLE IF EXISTS dim.dim_province;

CREATE TABLE dim.dim_province (
    province_key    SERIAL       PRIMARY KEY,     -- surrogate key for SCD-future
    province_code   VARCHAR(8)   NOT NULL UNIQUE, -- natural key: 'KH-12'
    province_name   VARCHAR(64)  NOT NULL UNIQUE  -- canonical name
);

INSERT INTO dim.dim_province (province_code, province_name) VALUES
    ('KH-1',  'Banteay Meanchey'),
    ('KH-2',  'Battambang'),
    ('KH-3',  'Kampong Cham'),
    ('KH-4',  'Kampong Chhnang'),
    ('KH-5',  'Kampong Speu'),
    ('KH-6',  'Kampong Thom'),
    ('KH-7',  'Kampot'),
    ('KH-8',  'Kandal'),
    ('KH-9',  'Koh Kong'),
    ('KH-10', 'Kratie'),
    ('KH-11', 'Mondul Kiri'),
    ('KH-12', 'Phnom Penh'),
    ('KH-13', 'Preah Vihear'),
    ('KH-14', 'Prey Veng'),
    ('KH-15', 'Pursat'),
    ('KH-16', 'Ratanak Kiri'),
    ('KH-17', 'Siem Reap'),
    ('KH-18', 'Preah Sihanouk'),
    ('KH-19', 'Stung Treng'),
    ('KH-20', 'Svay Rieng'),
    ('KH-21', 'Takeo'),
    ('KH-22', 'Otdar Meanchey'),
    ('KH-23', 'Kep'),
    ('KH-24', 'Pailin'),
    ('KH-25', 'Tboung Khmum');

SELECT COUNT(*) AS dim_province_rows FROM dim.dim_province;
-- Expected: 25