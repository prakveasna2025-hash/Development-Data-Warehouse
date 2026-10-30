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

## Day 13 — Validation: schema and counts

**Built:**
- `sql/create_dim_province.sql` — canonical 25-province dimension, **seeded from controlled reference data**, not derived from raw. Surrogate key `province_key SERIAL`, natural key `province_code UNIQUE`, `province_name UNIQUE`.
- `sql/verify_population_join.sql` — forward join (unmatched = 0), sample enrichment, **name governance check** (source names must match canonical dimension names).
- `scripts/validate_warehouse.py` — 4-layer warehouse health check: schema contract, row count > 0, source-CSV reconciliation, dimension join integrity. Exits 1 on any failure. **Read-only — every query is SELECT.**

**Decisions:**
- **Canonical seed over derived-from-raw.** Dimension is the *spec*, not a consequence of raw. Governance requires reviewed changes; deriving from raw would let a bad CSV silently redefine the dimension.
- **`TEXT` not `VARCHAR` in the schema contract** — pandas 3.x `str` dtype maps to PostgreSQL `TEXT` via `to_sql`. TEXT and VARCHAR are storage-identical in Postgres; VARCHAR adds only a length check. Encode what the toolchain produces, not aspirational types.
- **Three testing layers made explicit:**
  1. Unit tests (functions, no DB) — future
  2. Data quality (`validators.py` — DataFrame, pre-load) — exists
  3. Warehouse health (`validate_warehouse.py` — DB state, post-load) — this script

**Verification:**
- `dim_province` = 25 rows, `unmatched_rows = 0` against `raw.population_by_province`
- Name governance query returns 0 rows — source province names match canonical names exactly
- Health check: 4/4 schema, 4/4 row count, 2/2 reconciliation, 2/2 dimension joins — `RESULT: ALL CHECKS PASSED`

**Interview line:** *"I have three testing layers — unit tests on pure functions, DataFrame validation before load, and warehouse health checks after load. The third caught two false positives on its first run: my schema contract expected VARCHAR but pandas 3.x writes TEXT. I fixed the contract, not the warehouse — TEXT is the idiomatic Postgres default and storage-equivalent to VARCHAR. The lesson: contracts should encode what the toolchain produces, not aspirational types, or you generate false alarms that train people to ignore alerts."*

**Commands:**
- Build dim: `Get-Content sql\create_dim_province.sql | docker exec -i cambodia_dw_postgres psql -U airflow -d airflow`
- Join verify: `Get-Content sql\verify_population_join.sql | docker exec -i cambodia_dw_postgres psql -U airflow -d airflow`
- Health check: `uv run python scripts\validate_warehouse.py` (requires `$env:WAREHOUSE_DB_URL`)



## Day 14 — Validation: duplicates, nulls, references

**Built:**
- `scripts/validate_warehouse.py` — expanded from 4 sections to 7. New: nulls per column, duplicates per natural-key column, explicit reference checks (`NOT IN (SELECT dim_col FROM dim)`) — distinct from join checks (which find orphans by outcome; reference checks find keys outside the dim's value set).
- `tests/conftest.py` — pytest fixtures: `valid_population_df` (25 rows), `valid_exchange_df` (7,531 rows, module-scope).
- `tests/test_validators.py` — 12 tests. Each starts from clean baseline, injects one defect, asserts the specific error. Covers: null, dup code, dup name, bad code format, missing set member, wrong row count, wrong sum, dup date, extra inverted row.
- `scripts/__init__.py` — makes `scripts/` importable as a package (needed for `from scripts.validators import ...`).

**Decisions:**
- **pytest as `--dev` dependency** — dev-only, not shipped in production images.
- **`pythonpath = ["."]` in `pyproject.toml`** — required because pytest doesn't put rootdir on `sys.path` by default. With `__init__.py`, this makes `from scripts.validators import ...` work consistently.
- **Reference check distinct from join check** — join finds facts with no dim match; reference finds fact keys outside the dim's value set. Same result here, different intent/message. Explicit reference checks read better in error output.
- **Per-column null/duplicate checks** — failure names the exact column, not just "row problem."

**Verification:**
- `uv run pytest tests/ -v` → **12 passed** in 0.11s
- `uv run python scripts/validate_warehouse.py` → **7 sections, ALL CHECKS PASSED**
- Manual corruption demo: corrupted CSV (dup row, null, bad code, dup code) → extractor aborted with 9 specific errors in one run, exit 1, warehouse count remained 25

**Interview line:** *"Testing validators is testing assertions. Each test builds a valid baseline, mutates one field, and asserts the specific failure message — not just 'validation failed' but 'duplicate province_code.' I also run periodic end-to-end demos: corrupt a source file, run the extractor, confirm it fails fast with multi-issue errors and the warehouse is untouched. The pytest tests are the durable artifact; the demo proves the wiring — that validation is actually invoked in the control flow, not just defined and ignored."*

**Commands:**
- Tests: `uv run pytest tests/ -v`
- Warehouse health: `uv run python scripts/validate_warehouse.py`
## Day 15 — DAG skeleton

**Built:**
- `dags/cambodia_pipeline_dag.py` — DAG `cambodia_pipeline`. Structure: `[extract_population, extract_exchange_rate] >> validate_warehouse` (fan-out/fan-in). All three callables raise `NotImplementedError("Wired on Day 16")` — **intentionally**.

**Decisions:**
- **Airflow 3.x import path** — `from airflow.providers.standard.operators.python import PythonOperator` (the `standard` provider package).
- **`schedule=None`** — manual trigger only, dev-appropriate.
- **`catchup=False`** — prevents ~365 backfill runs on activation (start_date is 2025-01-01).
- **Timezone-aware `start_date`** — `datetime(2025, 1, 1, tzinfo=timezone.utc)`.
- **`retries=1`, `retry_delay=1min`** — survives transient DB blips; more would hide real failures.
- **`doc_md=__doc__`** — module docstring rendered in UI.
- **Stubs instead of silent success** — a DAG that "succeeds" doing nothing lies; a `NotImplementedError` names exactly where the work stops.

**Verified:**
- `airflow dags list` → `cambodia_pipeline` registered, no import errors
- `airflow dags show cambodia_pipeline` → DOT graph confirms fan-out/fan-in
- UI Graph view displays correct structure

**Known blockers for Day 16 (not fixed yet):**
- **A. Import path** — extractors use `from validators import`, will fail inside Airflow worker
- **B. Env var** — `WAREHOUSE_DB_URL` not present in worker
- **C. Network** — `airflow_default` and `docker_default` are different Docker networks; worker can't reach warehouse on 5434
- **D. Data mount** — `data/raw/*.csv` not mounted into worker
- **E. Scripts mount** — `scripts/` not mounted into worker

**Interview line:** *"A DAG whose task succeeds without loading data is worse than one that fails loudly. Stub callables raising NotImplementedError('Wired on Day 16') tell the truth — the wiring isn't done."*

**Commands:**
- List DAGs: `docker exec airflow-airflow-scheduler-1 airflow dags list | Select-String cambodia`
- Structure: `docker exec airflow-airflow-scheduler-1 airflow dags show cambodia_pipeline`
- UI: `http://localhost:8080`

## Day 16 — Retries, logging, full run

**Built:**
- Structured logging in 3 scripts (extract_population.py, extract_exchange_rate.py, validate_warehouse.py) — Python logging module with timestamp, level, logger name
- docker/airflow/docker-compose.yaml — scripts/ and data/ volume mounts; shared_network external
- docker/docker-compose.yml — shared_network external
- docker/airflow/.env — WAREHOUSE_DB_URL, PYTHONPATH, AIRFLOW__CORE__LOAD_EXAMPLES=False (gitignored)
- dags/cambodia_pipeline_dag.py — real imports; retries=2, retry_delay=1min, retry_exponential_backoff=True, max_retry_delay=10min

**Decisions:**
- Two-endpoint rule: WAREHOUSE_DB_URL endpoint-relative — host 127.0.0.1:5434, worker cambodia_dw_postgres:5432
- External network over per-service networks — decouples the two compose files
- logging module over print — timestamps, levels, logger names in Task Log
- Exponential backoff — first retry catches blips, later ones catch slow recovery, capped at 10min
- AIRFLOW__CORE__LOAD_EXAMPLES=False — disables ~80 example DAGs

**Verification:**
- Each script from worker: extract_population 25 rows, extract_exchange_rate 7531 rows, validate_warehouse ALL CHECKS PASSED
- DAG triggered from UI → state=success, ~2 min end-to-end
- CLI action logger fix (metadata Postgres volume password): ALTER USER airflow WITH PASSWORD 'airflow'

**Interview line:** Connection strings are endpoint-relative: 127.0.0.1:5434 from host, cambodia_dw_postgres:5432 from container. Cross-container uses service name + internal port, resolved by Docker DNS.

**Commands:**
- Test script from worker: docker exec airflow-airflow-worker-1 python /opt/airflow/scripts/SCRIPT.py
- Trigger: UI at http://localhost:8080
- Check run: docker exec airflow-airflow-scheduler-1 airflow dags list-runs cambodia_pipeline --no-backfill

## Day 18 — Staging: exchange rate

**Built:**
- `cambodia_dw/models/staging/stg_exchange_rate.sql` — 1:1 view over `raw.exchange_rate`. Renames `spread_market_day_x-1_over_oer_day_x_midpoint` → `spread_value` (hyphens in source name require double quotes AND are unusable downstream). Explicit `::date` / `::bigint` / `::double precision` casts. Loads documented defects as-is (16 inverted rows, 49 missing days, 2,109 midpoint rounding).
- `cambodia_dw/models/staging/schema.yml` — 17 tests across all three staging models:
  - `stg_population`: not_null + unique on `province_code`, `province_name`; not_null on `population` (5 tests)
  - `stg_province`: not_null + unique on `province_key`, `province_code`, `province_name` (6 tests)
  - `stg_exchange_rate`: not_null + unique on `date`; not_null on `purchase`, `sale`, `midpoint`, `exchange_rate` (6 tests)
- `cambodia_dw/dbt_project.yml` — removed dead `example:` block (folder deleted Day 17, config was generating an unused-path warning on every `dbt run`).

**Decisions:**
- **Test scope = not_null + unique only.** No `relationships` (needs stg_dim_date first, out of today's scope). No `accepted_values` (ranges undefined for exchange rates). No custom tests for the Day 3 defects.
- **Day 3 defects are NOT tested in dbt.** `purchase > sale` on 16 rows would make `dbt test` fail on every run. Defect-count assertions live in `validators.py` (Day 14 — `EXPECTED_INVERTED_ROWS = 16`). dbt tests are structural contracts; validators pin known defects at expected counts. **Mixing them trains people to ignore test failures.**
- **`spread_value` neutral rename.** Source name is unusable (hyphens, requires quotes in every query). `spread_value` doesn't claim the formula is known — semantics still under investigation (Day 3, source-notes.md).
- **Kept `::double precision` for float columns.** Source is float (Day 10 — pandas `float64` → Postgres `double precision`). Casting float→numeric doesn't recover lost precision — the precision was lost upstream.

**Issues resolved:**
- **Unquoted hyphenated identifier** — `spread_market_day_x-1_over_oer_day_x_midpoint` parsed as subtraction (`spread_market_day_x - 1_over_...`) → `trailing junk after numeric literal` error. Fix: `"spread_market_day_x-1_over_oer_day_x_midpoint"` — same identifier-folding rule as Day 8 capitals, extended to punctuation.
- **Dead `example:` config** — `+enabled: false` on a folder that was deleted generated a warning on every `dbt run`. Removed.

**Verification:**
- `uv run dbt run --project-dir cambodia_dw` → `PASS=3 WARN=0 ERROR=0`, no unused-path warning
- `uv run dbt test --project-dir cambodia_dw` → `PASS=17 WARN=0 ERROR=0`
- `\dv dbt_dev_staging.*` → 3 views
- Sample query confirms `spread_value` column exists, no quotes needed downstream

**Interview lines:**
- *"Unquoted identifiers with hyphens are parsed as arithmetic — `spread_market_day_x-1_...` becomes subtraction. Always double-quote: `"spread_market_day_x-1_over_oer_day_x_midpoint"`. Same rule as capitals (Day 8): PostgreSQL folds unquoted identifiers to lowercase and treats punctuation as operators."*
- *"dbt tests are structural contracts — not_null, unique, relationships. Defect-count assertions (exactly 16 inverted rows) belong in validators, not dbt. Mixing them makes `dbt test` fail on every run, which trains people to ignore alerts."*
- *"`spread_value` neutral rename — doesn't claim the formula is known. Better than `spread_pct` or `spread_defined` (lies) or the original (unusable downstream)."*

**Commands:**
- Run: `uv run dbt run --project-dir cambodia_dw`
- Test: `uv run dbt test --project-dir cambodia_dw`
- Verify: `docker exec -it cambodia_dw_postgres psql -U airflow -d airflow -c "\dv dbt_dev_staging.*"`
