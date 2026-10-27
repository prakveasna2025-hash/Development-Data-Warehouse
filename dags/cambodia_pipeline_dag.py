"""
Cambodia data pipeline DAG — skeleton.

Structure:
  [extract_population, extract_exchange] ──► validate_warehouse

The two extracts run in parallel; validate_warehouse waits for both.
"""

from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def extract_population(**context) -> None:
    """Extract population CSV → raw.population_by_province. (Wired Day 16.)"""
    raise NotImplementedError("Wired on Day 16")


def extract_exchange_rate(**context) -> None:
    """Extract exchange-rate CSV → raw.exchange_rate. (Wired Day 16.)"""
    raise NotImplementedError("Wired on Day 16")


def validate_warehouse(**context) -> None:
    """Run warehouse health check. (Wired Day 16.)"""
    raise NotImplementedError("Wired on Day 16")


with DAG(
    dag_id="cambodia_pipeline",
    description="Cambodia data pipeline — extract population + exchange rate, validate warehouse",
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=1),
    },
    tags=["cambodia", "dev"],
    doc_md=__doc__,
) as dag:
    t_extract_population = PythonOperator(
        task_id="extract_population",
        python_callable=extract_population,
    )
    t_extract_exchange = PythonOperator(
        task_id="extract_exchange_rate",
        python_callable=extract_exchange_rate,
    )
    t_validate = PythonOperator(
        task_id="validate_warehouse",
        python_callable=validate_warehouse,
    )

    [t_extract_population, t_extract_exchange] >> t_validate
