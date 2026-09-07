"""Airflow import and structure checks for the monthly TLC DAG."""

import ast
import os
from itertools import pairwise
from pathlib import Path

import pytest

if os.name == "nt":
    pytest.skip("Airflow DAG imports require a POSIX runtime", allow_module_level=True)

pytest.importorskip("airflow")

from airflow.models import DagBag

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DAG_PATH = Path(
    os.environ.get(
        "TEST_DAG_PATH",
        REPOSITORY_ROOT / "dags" / "tlc_monthly_pipeline.py",
    )
)
EXPECTED_TASK_IDS = {
    "resolve_partition",
    "ensure_taxi_zones",
    "ensure_yellow_loaded",
    "quality_yellow",
    "ensure_green_loaded",
    "quality_green",
    "dbt_build",
    "pipeline_complete",
}
ORDERED_TASK_IDS = [
    "resolve_partition",
    "ensure_taxi_zones",
    "ensure_yellow_loaded",
    "quality_yellow",
    "ensure_green_loaded",
    "quality_green",
    "dbt_build",
    "pipeline_complete",
]


@pytest.fixture(scope="module")
def monthly_dag():
    dag_bag = DagBag(dag_folder=str(DAG_PATH))
    assert dag_bag.import_errors == {}
    return dag_bag.dags["tlc_monthly_pipeline"]


def test_dag_identity_and_runtime_limits(monthly_dag):
    assert monthly_dag is not None
    assert monthly_dag.dag_id == "tlc_monthly_pipeline"
    assert monthly_dag.catchup is False
    assert monthly_dag.max_active_runs == 1


def test_dag_has_expected_tasks_and_sequential_dependencies(monthly_dag):
    assert set(monthly_dag.task_ids) == EXPECTED_TASK_IDS
    for upstream_id, downstream_id in pairwise(ORDERED_TASK_IDS):
        assert downstream_id in monthly_dag.get_task(upstream_id).downstream_task_ids


def test_manual_year_and_month_parameters_are_available(monthly_dag):
    assert {"year", "month"}.issubset(monthly_dag.params)
    assert monthly_dag.params["year"] is None
    assert monthly_dag.params["month"] is None


def test_dag_import_defines_no_tabular_payloads():
    tree = ast.parse(DAG_PATH.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert imported_roots.isdisjoint({"pandas", "pyarrow", "polars"})
