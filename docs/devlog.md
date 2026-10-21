# Development Log

## Day 1 — Project setup
**Built:** repo skeleton (dags, plugins, scripts, sql, data/raw, data/processed, docker, docs), `.gitignore`, `.env.example`, `pyproject.toml`, `README.md` placeholder.
**Decisions:** used `uv` over pip for reproducible lockfile; kept `dags/` at root per Airflow convention.
**Notes:** source CSVs committed under `data/raw/` for self-contained repo.