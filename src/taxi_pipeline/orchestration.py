"""Airflow-neutral operations for the monthly TLC workflow."""

import logging
import os
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from taxi_pipeline.database import get_engine
from taxi_pipeline.ingestion import IngestionResult, ingest_source
from taxi_pipeline.landing import ensure_local, inspect_source
from taxi_pipeline.metadata import RunStatus, SkipReason
from taxi_pipeline.quality import find_latest_successful_run, run_quality_checks
from taxi_pipeline.sources import green_trip_source, taxi_zone_source, yellow_trip_source

LOGGER = logging.getLogger(__name__)


class SourceRevisionError(RuntimeError):
    """A known partition changed after an immutable version was loaded."""


def resolve_month(
    logical_date: date | datetime,
    *,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, int | str]:
    """Resolve an explicit month or the deterministic two-month scheduled lag."""
    if (year is None) != (month is None):
        raise ValueError("Manual runs must provide both year and month")
    if year is not None and month is not None:
        if isinstance(year, bool) or not isinstance(year, int) or not 1000 <= year <= 9999:
            raise ValueError("year must be a four-digit integer")
        if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
            raise ValueError("month must be an integer between 1 and 12")
        target_year, target_month = year, month
    else:
        month_index = logical_date.year * 12 + logical_date.month - 3
        target_year, zero_based_month = divmod(month_index, 12)
        target_month = zero_based_month + 1

    return {
        "year": target_year,
        "month": target_month,
        "partition_label": f"{target_year:04d}-{target_month:02d}",
    }


def ensure_taxi_zones_loaded(repository_root: Path) -> dict[str, Any]:
    """Download, inspect, register, and idempotently ingest the Taxi Zone lookup."""
    return _ensure_loaded(taxi_zone_source(), repository_root)


def ensure_trip_month_loaded(
    service_type: str,
    year: int,
    month: int,
    repository_root: Path,
) -> dict[str, Any]:
    """Download, inspect, register, and idempotently ingest one trip partition."""
    resolvers = {"yellow": yellow_trip_source, "green": green_trip_source}
    try:
        source = resolvers[service_type](year, month)
    except KeyError as error:
        raise ValueError(f"Unsupported service type: {service_type}") from error
    return _ensure_loaded(source, repository_root)


def run_partition_quality(service_type: str, year: int, month: int) -> dict[str, Any]:
    """Evaluate quality for the latest successful load of an exact partition."""
    engine = get_engine()
    try:
        with Session(engine) as session, session.begin():
            run_id = find_latest_successful_run(
                session,
                service_type=service_type,
                year=year,
                month=month,
            )
            summary = run_quality_checks(session, run_id)
    finally:
        engine.dispose()

    result = {
        "partition_key": summary.partition_key,
        "run_id": summary.run_id,
        "rows_checked": summary.rows_checked,
        "check_count": summary.check_count,
        "warnings_violated": summary.warnings_violated,
        "errors_violated": summary.errors_violated,
    }
    LOGGER.info(
        "Quality completed partition=%s run_id=%s checks=%s warnings=%s errors=%s",
        summary.partition_key,
        summary.run_id,
        summary.check_count,
        summary.warnings_violated,
        summary.errors_violated,
    )
    return result


def run_dbt_build(project_dir: Path) -> dict[str, str]:
    """Build the existing dbt project and surface its output to task logs."""
    resolved_project_dir = project_dir.resolve()
    subprocess.run(
        [
            "dbt",
            "build",
            "--project-dir",
            str(resolved_project_dir),
            "--profiles-dir",
            str(resolved_project_dir),
        ],
        cwd=resolved_project_dir,
        env=os.environ.copy(),
        check=True,
    )
    LOGGER.info("dbt build completed project_dir=%s", resolved_project_dir)
    return {"status": "succeeded", "project_dir": str(resolved_project_dir)}


def _ensure_loaded(source, repository_root: Path) -> dict[str, Any]:
    ensure_local(source, repository_root)
    metadata = inspect_source(source, repository_root)
    engine = get_engine()
    try:
        ingestion = ingest_source(engine, metadata, repository_root)
    finally:
        engine.dispose()
    _raise_for_source_revision(ingestion)

    decision = (
        "already_loaded"
        if ingestion.status_reason is SkipReason.ALREADY_LOADED
        else "loaded"
    )
    result = {
        "partition_key": ingestion.partition_key,
        "source_file_id": ingestion.source_file_id,
        "ingestion_run_id": ingestion.run_id,
        "decision": decision,
        "status": ingestion.status.value,
        "rows_loaded": ingestion.rows_loaded,
    }
    LOGGER.info(
        "Ingestion completed partition=%s source_file_id=%s run_id=%s decision=%s status=%s",
        ingestion.partition_key,
        ingestion.source_file_id,
        ingestion.run_id,
        decision,
        ingestion.status.value,
    )
    return result


def _raise_for_source_revision(result: IngestionResult) -> None:
    if (
        result.status is RunStatus.SKIPPED
        and result.status_reason is SkipReason.SOURCE_REVISION_DETECTED
    ):
        raise SourceRevisionError(
            f"Source revision requires review for {result.partition_key} "
            f"(source_file_id={result.source_file_id}, run_id={result.run_id})"
        )
