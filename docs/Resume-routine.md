# 0. Start Docker Desktop, wait for "Engine running"

# 1. Warehouse (Day 4)
docker compose -f docker/docker-compose.yml up -d

# 2. Airflow (Day 5)
docker compose -f docker/airflow/docker-compose.yaml up -d

# 3. Confirm all containers healthy
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 4. Confirm dbt connection
uv run dbt debug --project-dir cambodia_dw

# 5. Open UI (browser)
#    http://localhost:8080  → airflow / airflow

# Start Docker Desktop, wait for "Engine running"
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/airflow/docker-compose.yaml up -d
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
$env:WAREHOUSE_DB_URL = "postgresql+psycopg2://airflow:changeme@127.0.0.1:5434/airflow"
uv run dbt debug --project-dir cambodia_dw