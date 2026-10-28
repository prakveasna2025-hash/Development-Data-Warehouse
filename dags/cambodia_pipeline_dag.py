"""
Cambodia data pipeline DAG — fully wired.

Structure:
  [extract_population, extract_exchange] ──► validate_warehouse

The two extracts run in parallel; validate_warehouse waits for both.
"""

from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Import the real scripts
from scripts.extract_population import main as extract_population_main
from scripts.extract_exchange_rate import main as extract_exchange_rate_main
from scripts.validate_warehouse import main as validate_warehouse_main


def extract_population(**context) -> None:
    """Extract population CSV → raw.population_by_province."""
    extract_population_main()


def extract_exchange_rate(**context) -> None:
    """Extract exchange-rate CSV → raw.exchange_rate."""
    extract_exchange_rate_main()


def validate_warehouse(**context) -> None:
    """Run warehouse health check."""
    validate_warehouse_main()


with DAG(
    dag_id="cambodia_pipeline",
    description="Cambodia data pipeline — extract population + exchange rate, validate warehouse",
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=1),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=10),
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
