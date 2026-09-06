"""Monthly Airflow orchestration for the local NYC TLC data platform."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from airflow.sdk import DAG, Param, get_current_context, task

PROJECT_ROOT = Path(os.environ.get("TAXI_PIPELINE_ROOT", "/opt/airflow/project"))
DBT_PROJECT_DIR = Path(
    os.environ.get("DBT_PROJECT_DIR", PROJECT_ROOT / "dbt" / "taxi_analytics")
)

DEFAULT_ARGS = {
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


with DAG(
    dag_id="tlc_monthly_pipeline",
    description="Load and validate one Yellow and Green TLC month, then build dbt models.",
    schedule="0 6 10 * *",
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    params={
        "year": Param(None, type=["null", "integer"], minimum=1000, maximum=9999),
        "month": Param(None, type=["null", "integer"], minimum=1, maximum=12),
    },
    tags=["nyc-tlc", "monthly"],
) as dag:

    @task
    def resolve_partition() -> dict[str, int | str]:
        from taxi_pipeline.orchestration import resolve_month

        context = get_current_context()
        logical_date = context.get("logical_date") or context["dag_run"].logical_date
        params = context["params"]
        return resolve_month(logical_date, year=params["year"], month=params["month"])

    @task
    def ensure_taxi_zones(partition: dict[str, Any]) -> dict[str, Any]:
        from taxi_pipeline.orchestration import ensure_taxi_zones_loaded

        del partition
        return ensure_taxi_zones_loaded(PROJECT_ROOT)

    @task
    def ensure_yellow_loaded(
        partition: dict[str, Any],
        zones: dict[str, Any],
    ) -> dict[str, Any]:
        from taxi_pipeline.orchestration import ensure_trip_month_loaded

        del zones
        return ensure_trip_month_loaded(
            "yellow", partition["year"], partition["month"], PROJECT_ROOT
        )

    @task
    def quality_yellow(
        partition: dict[str, Any],
        ingestion: dict[str, Any],
    ) -> dict[str, Any]:
        from taxi_pipeline.orchestration import run_partition_quality

        del ingestion
        return run_partition_quality("yellow", partition["year"], partition["month"])

    @task
    def ensure_green_loaded(
        partition: dict[str, Any],
        yellow_quality: dict[str, Any],
    ) -> dict[str, Any]:
        from taxi_pipeline.orchestration import ensure_trip_month_loaded

        del yellow_quality
        return ensure_trip_month_loaded(
            "green", partition["year"], partition["month"], PROJECT_ROOT
        )

    @task
    def quality_green(
        partition: dict[str, Any],
        ingestion: dict[str, Any],
    ) -> dict[str, Any]:
        from taxi_pipeline.orchestration import run_partition_quality

        del ingestion
        return run_partition_quality("green", partition["year"], partition["month"])

    @task
    def dbt_build(green_quality: dict[str, Any]) -> dict[str, str]:
        from taxi_pipeline.orchestration import run_dbt_build

        del green_quality
        return run_dbt_build(DBT_PROJECT_DIR)

    @task
    def pipeline_complete(
        partition: dict[str, Any],
        dbt_result: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "partition_label": partition["partition_label"],
            "status": dbt_result["status"],
        }

    target = resolve_partition()
    zones_result = ensure_taxi_zones(target)
    yellow_result = ensure_yellow_loaded(target, zones_result)
    yellow_quality_result = quality_yellow(target, yellow_result)
    green_result = ensure_green_loaded(target, yellow_quality_result)
    green_quality_result = quality_green(target, green_result)
    dbt_result = dbt_build(green_quality_result)
    pipeline_complete(target, dbt_result)
