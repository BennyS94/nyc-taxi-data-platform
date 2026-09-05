"""Explicit pipeline-run lifecycle operations."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from taxi_pipeline.database.models import PipelineRun
from taxi_pipeline.metadata.source_registry import get_source_file, mark_source_loaded
from taxi_pipeline.metadata.statuses import (
    MetadataStateError,
    RunStatus,
    SkipReason,
    SourceStatus,
)


def start_run(session: Session, source_file_id: int) -> PipelineRun:
    """Create a new running attempt for a ready source file."""
    source_file = get_source_file(session, source_file_id)
    if source_file.status != SourceStatus.READY.value:
        raise MetadataStateError(
            f"Cannot start run for source {source_file_id} with status {source_file.status}"
        )
    run = PipelineRun(
        **_source_dimensions(source_file),
        started_at=datetime.now(UTC),
        status=RunStatus.RUNNING.value,
    )
    session.add(run)
    session.flush()
    return run


def mark_run_succeeded(
    session: Session,
    run_id: int,
    *,
    rows_read: int | None = None,
    rows_loaded: int | None = None,
    warning_count: int | None = None,
    error_count: int | None = None,
) -> PipelineRun:
    """Atomically finish a running load and mark its ready source loaded."""
    run = _get_running_run(session, run_id)
    if run.source_file_id is None:
        raise MetadataStateError(f"Run {run_id} has no source file")

    finished_at = datetime.now(UTC)
    mark_source_loaded(session, run.source_file_id, loaded_at=finished_at)
    run.status = RunStatus.SUCCEEDED.value
    run.finished_at = finished_at
    run.status_reason = None
    run.rows_read = rows_read
    run.rows_loaded = rows_loaded
    run.warning_count = warning_count
    run.error_count = error_count
    run.error_message = None
    session.flush()
    return run


def mark_run_failed(session: Session, run_id: int, error_message: str) -> PipelineRun:
    """Finish a running attempt as failed while leaving its source ready."""
    if not error_message.strip():
        raise ValueError("error_message must not be empty")
    run = _get_running_run(session, run_id)
    run.status = RunStatus.FAILED.value
    run.finished_at = datetime.now(UTC)
    run.status_reason = None
    run.error_message = error_message
    session.flush()
    return run


def create_skipped_run(
    session: Session,
    source_file_id: int,
    reason: str | SkipReason,
) -> PipelineRun:
    """Record an intentional non-ingestion attempt for a terminal source decision."""
    try:
        skip_reason = SkipReason(reason)
    except ValueError as error:
        raise MetadataStateError(f"Unknown skip reason: {reason}") from error

    source_file = get_source_file(session, source_file_id)
    required_status = {
        SkipReason.ALREADY_LOADED: SourceStatus.LOADED,
        SkipReason.SOURCE_REVISION_DETECTED: SourceStatus.REVISION_DETECTED,
    }[skip_reason]
    if source_file.status != required_status.value:
        raise MetadataStateError(
            f"Skip reason {skip_reason.value} is invalid for source status {source_file.status}"
        )

    timestamp = datetime.now(UTC)
    run = PipelineRun(
        **_source_dimensions(source_file),
        started_at=timestamp,
        finished_at=timestamp,
        status=RunStatus.SKIPPED.value,
        status_reason=skip_reason.value,
        rows_loaded=0,
    )
    session.add(run)
    session.flush()
    return run


def get_run(session: Session, run_id: int) -> PipelineRun:
    """Load a pipeline run or raise a clear operational metadata error."""
    run = session.get(PipelineRun, run_id)
    if run is None:
        raise MetadataStateError(f"Unknown run ID: {run_id}")
    return run


def _get_running_run(session: Session, run_id: int) -> PipelineRun:
    run = get_run(session, run_id)
    if run.status != RunStatus.RUNNING.value:
        raise MetadataStateError(f"Run {run_id} is terminal with status {run.status}")
    return run


def _source_dimensions(source_file) -> dict:
    return {
        "dataset_name": source_file.dataset_name,
        "service_type": source_file.service_type,
        "source_year": source_file.source_year,
        "source_month": source_file.source_month,
        "source_file_id": source_file.source_file_id,
    }
