# Development Log

## Day 1 — Project setup
**Built:** repo skeleton (dags, plugins, scripts, sql, data/raw, data/processed, docker, docs), `.gitignore`, `.env.example`, `pyproject.toml`, `README.md` placeholder.
**Decisions:** used `uv` over pip for reproducible lockfile; kept `dags/` at root per Airflow convention.
**Notes:** source CSVs committed under `data/raw/` for self-contained repo.

## Day 2 — Verify data: population CSV
**Built:** `scripts/verify_population.py` — loads population CSV with pandas, prints a verification report (shape, columns, dtypes, nulls, duplicates, code format, population sanity, province list).
**Result:** CLEAN. 25 rows × 3 columns (`Province`, `Population`, `province_code`). No nulls, no duplicate names/codes. All codes match `^KH-\d+$`. Total = 17,280,543 (plausible for 2024).
**Notes:** pandas 3.x shows `str` dtype for strings (was `object` in pandas 2.x). Worth knowing for interviews.
**Commands:**
- `uv run python scripts/verify_population.py`

## Day 3 — Verify data: exchange rate CSV + source notes
**Built:**
- `scripts/verify_exchange_rate.py` — verifies the NBC USD/KHR file, designed to surface known defects.
- `docs/source-notes.md` — provenance doc for both sources (URL, access date, columns, quality issues, mitigations).

**Result:** USABLE WITH DOCUMENTED DEFECTS.
- 2,109 rows (28%) with inconsistent midpoint rounding → recompute `(purchase+sale)/2` downstream
- 16 rows with inverted bid/ask (purchase > sale), in date runs: 2004-04-02; 2006-12-02..03; 2008-05-23..25; 2010-05-13..16; + 6 more
- 49 missing days — April 2008 fully absent + month-end days in late 2007 / early 2008 + ~14 scattered
- `spread_market_day_x-1_over_oer_day_x_midpoint` semantics unknown — do not use until defined
- BOM on header handled via `encoding="utf-8-sig"`

**Commands:**
- `uv run python scripts/verify_exchange_rate.py`

## Day 4 — PostgreSQL (Docker) + dbt
**Built:**
- `docker/docker-compose.yml` — PostgreSQL 16-alpine, named volume `pgdata`, `pg_isready` healthcheck
- `docker/.env` — `POSTGRES_USER/PASSWORD/DB` (gitignored)
- `cambodia_dw/` — dbt project at **repo root** (not inside `docker/`)
- `C:\Users\ASUS\.dbt\profiles.yml` — dbt connection profile, **outside the repo** on purpose (contains password)

**Decisions:**
- Named volume (not bind mount) for `$PGDATA` — bind mounts on Windows cause UID / overlayfs perf issues
- Warehouse Postgres published on **host port 5434** (not 5432) because ports 5432 and 5433 are already taken by `cambodia_exchange_rate_pipeline-db-1` and `cambodia_registry_pg`
- `profiles.yml` in `~/.dbt/`, not repo — keeps password out of git
- `dbt_project.yml`'s `profile: 'cambodia_dw'` must match the top-level key in `profiles.yml` exactly

**Issues resolved:**
- Stale `pgdata` volume held old password → `docker compose down -v` + `up -d` reinitialized
- dbt hit wrong Postgres (localhost IPv6 → old container on 5432) → fixed with `host: 127.0.0.1` + `port: 5434`
- `dbt init` ran from `docker/` → project created in wrong place; `Move-Item .\cambodia_dw ..\cambodia_dw`
- `dbt debug` failed with `password auth failed` → matched `profiles.yml` to actual container's **host** port

**Verification:** `uv run dbt debug --project-dir cambodia_dw` → `All checks passed!`

**Commands to remember:**
- Start DB: `docker compose -f docker/docker-compose.yml up -d`
- Verify DB: `docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"` → look for `5434->5432/tcp`, `Up (healthy)`
- Verify dbt: `uv run dbt debug --project-dir cambodia_dw`
- **Three-port rule:** `host:container` in compose — LEFT number = what clients connect to (5434). `profiles.yml` port must match the LEFT number, not the container's 5432.

## Day 5 — Airflow
**Built:**
- `docker/airflow/docker-compose.yaml` — official Airflow 3.3.2 CeleryExecutor stack
- `docker/airflow/.env` — image tag, UID, project root, admin creds, **Fernet key**
- `logs/`, `config/` folders at repo root — mounted into Airflow containers

**Services (8):**
- `airflow-apiserver` — UI/API on **host 8080**
- `airflow-scheduler`, `airflow-dag-processor`, `airflow-worker`, `airflow-triggerer` — all internal
- `airflow-postgres` — **Airflow's own metadata DB, NOT the warehouse** — internal only (`5432/tcp`, no host publish)
- `airflow-redis` — Celery broker, internal only (`6379/tcp`)
- `airflow-init` — one-shot bootstrap, exits code 0 (normal)

**Decisions:**
- Used official standalone compose (not hand-written)
- `AIRFLOW_PROJ_DIR=../..` — makes mounts resolve to repo root, so `dags/` points at your real DAGs folder, not `docker/airflow/dags/`
- Airflow's Postgres and Redis are internal only → no collision with warehouse on 5434
- Fernet key generated once, stored in `docker/airflow/.env` — without it, saved Connections become unreadable after restart

**Issues resolved:**
- `FERNET_KEY is not set` warning — `.env` had `AIRFLOW__CORE__FERNET_KEY=...` but compose expects `${FERNET_KEY}` (short name); renamed → warning gone
- Containers didn't pick up `.env` change on `up -d` — Compose doesn't recreate on env-only changes → `down` + `up -d` (no `-v`) forces recreation
- `ModuleNotFoundError: cryptography` on host — was running `python`, not `uv run python` or container python

**Verification:**
- Mounts: `docker inspect airflow-airflow-apiserver-1 --format "{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}"` → all four resolve to `C:\User\cambodia-airflow-pipeline\<folder>`
- Fernet reached container: `docker exec airflow-airflow-apiserver-1 env | Select-String FERNET` → real value in both `FERNET_KEY` and `AIRFLOW__CORE__FERNET_KEY`
- UI loads: `http://localhost:8080` → `airflow` / `airflow`
- Regression: warehouse still `Up (healthy)` on 5434, `dbt debug` still `All checks passed!`

**Commands to remember:**
- Start Airflow: `docker compose -f docker/airflow/docker-compose.yaml up -d`
- Verify stack: `docker compose -f docker/airflow/docker-compose.yaml ps`
- Verify Fernet: `docker exec airflow-airflow-apiserver-1 env | Select-String FERNET`
- Verify mounts: `docker inspect airflow-airflow-apiserver-1 --format "{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}"`
- **Force recreate after `.env` change:** `docker compose down` then `up -d` (**never** `-v` unless you want to wipe metadata)

---

## Daily resume routine (full stack)

```powershell
# 0. Start Docker Desktop, wait for "Engine running"

# 1. Warehouse (Day 4)
docker compose -f docker/docker-compose.yml up -d

# 2. Airflow (Day 5)
docker compose -f docker/airflow/docker-compose.yaml up -d

# 3. Confirm all containers healthy
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 4. Confirm dbt connection
uv run dbt debug --project-dir cambodia_dw

# 5. Open UI
#    http://localhost:8080  → airflow / airflow


## Day 8 — Population extractor

**Built:**
- `scripts/extract_population.py` — pandas extractor: reads `data/raw/population_by_province_2024.csv`, creates `raw` schema, writes to `raw.population_by_province`, verifies row count post-load.
- `sql/verify_population.sql` — independent psql verification query (top 5 by population).

**Decisions:**
- `to_sql(if_exists="replace", index=False)` — idempotent full refresh for static reference data (25 rows, 2024 snapshot). Not `append` (duplicates on re-run) or `fail` (errors on re-run).
- `index=False` — avoids writing pandas DataFrame index as a column.
- DB URL from `WAREHOUSE_DB_URL` env var (Option B — set per shell session), never hardcoded.
- Schema `raw` separate from `dbt_dev` — clear layering: raw = source-of-truth, dbt = transformed.
- Verification is a **separate** step (`sql/verify_population.sql`), not embedded in the extractor — separation of concerns.

**Notes:**
- pandas `to_sql` preserves DataFrame column names exactly → capitalized columns (`Province`, `Population`) require double-quoted references in psql. Unquoted identifiers fold to lowercase in PostgreSQL.
- PowerShell → `docker exec` → psql is a 3-layer quoting hazard. Solution: `.sql` file + `Get-Content | docker exec -i` — arguments survive intact, and the query is reusable.

**Commands:**
- Set URL: `$env:WAREHOUSE_DB_URL = "postgresql+psycopg2://airflow:changeme@127.0.0.1:5434/airflow"`
- Run: `uv run python scripts/extract_population.py`
- Verify: `Get-Content sql\verify_population.sql | docker exec -i cambodia_dw_postgres psql -U airflow -d airflow`

## Day 9 — Population validation and rerun

**Built:**
- `scripts/validators.py` — reusable `validate_population(df)` returning a list of failure messages. Checks: required columns, nulls, duplicate names, duplicate codes, code format, **code contiguity** (all 25 KH-1..KH-25 present), row count, integer dtype, positivity, exact population sum (17,280,543).
- `scripts/extract_population.py` — updated to validate **before** load (fail-fast, no bad data written) and **after** load (read back from warehouse, validate again).
- `sql/verify_no_duplicates.sql` — aggregate count query (25/25/25) + detail query (should return 0 rows).

**Decisions:**
- Validation lives in `validators.py`, not inline — reusable across DAG, unit tests, and CLI.
- Validator returns a **list** of all failures, not just the first — see everything wrong in one run.
- `EXPECTED_PROVINCE_CODES = {f"KH-{i}" for i in range(1, 26)}` — **contiguity check**, not just format. A gap (`KH-13` missing, `KH-26` present) passes regex but fails this.
- Exact population sum, not a range — static snapshot, not a live feed. If it changes, we want to know.
- Validate **loaded data** too (read back from warehouse) — proves the write didn't corrupt anything.

**Notes:**
- **Idempotency comes from `if_exists="replace"`**, not from a dedup step. Rerunning drops and recreates the table. The duplicate-check SQL is **proof** of idempotency, not the mechanism.
- Two-layer validation: pre-load (source) catches upstream corruption; post-load (warehouse) catches corruption introduced by the write.

**Commands:**
- Run: `uv run python scripts/extract_population.py` (twice, to prove idempotency)
- Duplicate check: `Get-Content sql\verify_no_duplicates.sql | docker exec -i cambodia_dw_postgres psql -U airflow -d airflow`

## Day 10 — Exchange-rate extractor + dim_date

**Built:**
- `scripts/extract_exchange_rate.py` — BOM handling, date parsing to `datetime64`, `to_sql(dtype={"date": Date})` to force PostgreSQL `DATE` (not `TIMESTAMP`), validation pre + post load.
- `scripts/validators.py` — added `validate_exchange_rate()` — **strict-with-documented-exceptions**.
- `sql/create_dim_date.sql` — `generate_series` date spine 2003-04-01 → 2023-12-31, integer surrogate key `date_key` (YYYYMMDD), computed attributes.
- `sql/verify_exchange_rate_join.sql` — forward join (unmatched = 0), sample enrichment, reverse join (missing days visible).

**Decisions:**
- **Load as-is** — the 16 inverted rows, 49 missing days, 2,109 midpoint inconsistencies are loaded, not cleaned. Raw layer is a faithful copy of source; cleaning belongs in dbt.
- **`dtype={"date": Date}`** — forced `DATE` type at `to_sql`. Alternative `.dt.date` (object dtype) rejected — keeps pandas column as `datetime64`, cleaner and faster.
- **Strict-with-documented-exceptions** — each known defect has an expected count (16, 49, 7531). Fails on drift, passes on known defects.
- **dim_date in `dim` schema** — separate from `raw` (source) and `dbt_dev` (transformed). Surrogate key + natural key both present.

**Verification:**
- `exchange_rows = 7531`, `joined_rows = 7531`, `unmatched_rows = 0` → every fact joins to dim_date
- Reverse `LEFT JOIN` reveals exactly the 49 documented missing days, confirming Day 3's analysis at the day level
- Leap day `2008-02-29` correctly modeled in dim_date (proves calendar reality handled)

**Interview line:** *"A fact table can't reveal its own gaps — 7,531 rows all look complete. A dimension gives you a completeness spec: LEFT JOIN from dim to fact reveals exactly which days are missing. That's the reverse-join diagnostic, not just a verification."*

**Commands:**
- Build dim: `Get-Content sql\create_dim_date.sql | docker exec -i cambodia_dw_postgres psql -U airflow -d airflow`
- Verify join: `Get-Content sql\verify_exchange_rate_join.sql | docker exec -i cambodia_dw_postgres psql -U airflow -d airflow`
- Extract: `uv run python scripts\extract_exchange_rate.py`