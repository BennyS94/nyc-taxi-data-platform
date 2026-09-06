"""Tests for Airflow-neutral monthly orchestration operations."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from taxi_pipeline.ingestion import IngestionResult
from taxi_pipeline.metadata import RunStatus, SkipReason
from taxi_pipeline.orchestration import (
    SourceRevisionError,
    _raise_for_source_revision,
    resolve_month,
    run_dbt_build,
)


@pytest.mark.parametrize(
    ("logical_date", "expected"),
    [
        (datetime(2025, 4, 10, tzinfo=UTC), (2025, 2)),
        (datetime(2025, 1, 10, tzinfo=UTC), (2024, 11)),
    ],
)
def test_resolve_month_uses_two_month_lag(logical_date, expected):
    result = resolve_month(logical_date)

    assert (result["year"], result["month"]) == expected
    assert result["partition_label"] == f"{expected[0]:04d}-{expected[1]:02d}"


def test_resolve_month_prefers_complete_manual_parameters():
    result = resolve_month(datetime(2026, 9, 1, tzinfo=UTC), year=2025, month=2)

    assert result == {"year": 2025, "month": 2, "partition_label": "2025-02"}


@pytest.mark.parametrize(
    ("year", "month"),
    [(2025, None), (None, 2), (999, 2), (2025, 13), (True, 2)],
)
def test_resolve_month_rejects_invalid_manual_parameters(year, month):
    with pytest.raises(ValueError):
        resolve_month(datetime(2026, 9, 1, tzinfo=UTC), year=year, month=month)


def test_source_revision_is_an_orchestration_failure():
    result = IngestionResult(
        partition_key="yellow/2025/02",
        source_file_id=12,
        run_id=34,
        status=RunStatus.SKIPPED,
        rows_read=0,
        rows_loaded=0,
        status_reason=SkipReason.SOURCE_REVISION_DETECTED,
    )

    with pytest.raises(SourceRevisionError, match="yellow/2025/02"):
        _raise_for_source_revision(result)


def test_already_loaded_is_not_an_orchestration_failure():
    result = IngestionResult(
        partition_key="green/2025/02",
        source_file_id=56,
        run_id=78,
        status=RunStatus.SKIPPED,
        rows_read=0,
        rows_loaded=0,
        status_reason=SkipReason.ALREADY_LOADED,
    )

    _raise_for_source_revision(result)


def test_run_dbt_build_uses_existing_project(monkeypatch, tmp_path: Path):
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr("taxi_pipeline.orchestration.subprocess.run", run)

    result = run_dbt_build(tmp_path)

    command = run.call_args.args[0]
    assert command[:2] == ["dbt", "build"]
    assert command.count(str(tmp_path.resolve())) == 2
    assert run.call_args.kwargs["check"] is True
    assert result["status"] == "succeeded"
