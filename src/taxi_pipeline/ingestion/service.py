"""End-to-end source registration, raw loading, and run lifecycle orchestration."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from taxi_pipeline.database.models import TaxiZone, YellowTrip
from taxi_pipeline.ingestion.models import LoadCounts
from taxi_pipeline.ingestion.taxi_zones import load_taxi_zones
from taxi_pipeline.ingestion.yellow import load_yellow
from taxi_pipeline.metadata import (
    IngestionDecision,
    RunStatus,
    SkipReason,
    create_skipped_run,
    mark_run_failed,
    mark_run_succeeded,
    prepare_ingestion,
    start_run,
)
from taxi_pipeline.sources.models import SourceFileMetadata

DEFAULT_BATCH_SIZE = 50_000


class IngestionError(RuntimeError):
    """A raw source load failed after its run had started."""


@dataclass(frozen=True)
class IngestionResult:
    """Concise outcome for a completed or intentionally skipped attempt."""

    partition_key: str
    source_file_id: int
    run_id: int
    status: RunStatus
    rows_read: int
    rows_loaded: int
    status_reason: SkipReason | None = None


def ingest_source(
    engine: Engine,
    metadata: SourceFileMetadata,
    repository_root: Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> IngestionResult:
    """Ingest one validated source with file-level idempotency and rollback safety."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    with Session(engine) as session, session.begin():
        registration = prepare_ingestion(session, metadata)

    if registration.decision is not IngestionDecision.PROCEED:
        reason = {
            IngestionDecision.ALREADY_LOADED: SkipReason.ALREADY_LOADED,
            IngestionDecision.SOURCE_REVISION_BLOCKED: SkipReason.SOURCE_REVISION_DETECTED,
        }[registration.decision]
        with Session(engine) as session, session.begin():
            run = create_skipped_run(session, registration.source_file_id, reason)
            run_id = run.run_id
        return IngestionResult(
            partition_key=metadata.partition_key,
            source_file_id=registration.source_file_id,
            run_id=run_id,
            status=RunStatus.SKIPPED,
            rows_read=0,
            rows_loaded=0,
            status_reason=reason,
        )

    with Session(engine) as session, session.begin():
        run_id = start_run(session, registration.source_file_id).run_id

    path = repository_root / metadata.landing_path
    try:
        with Session(engine) as session, session.begin():
            ingested_at = datetime.now(UTC)
            counts, persisted_count = _load_and_count(
                session,
                metadata,
                path,
                source_file_id=registration.source_file_id,
                run_id=run_id,
                ingested_at=ingested_at,
                batch_size=batch_size,
            )
            _validate_counts(metadata, counts, persisted_count)
            mark_run_succeeded(
                session,
                run_id,
                rows_read=counts.rows_read,
                rows_loaded=counts.rows_loaded,
                warning_count=0,
                error_count=0,
            )
    except Exception as error:
        message = _safe_error_message(error)
        with Session(engine) as session, session.begin():
            mark_run_failed(session, run_id, message)
        raise IngestionError(message) from error

    return IngestionResult(
        partition_key=metadata.partition_key,
        source_file_id=registration.source_file_id,
        run_id=run_id,
        status=RunStatus.SUCCEEDED,
        rows_read=counts.rows_read,
        rows_loaded=counts.rows_loaded,
    )


def _load_and_count(
    session: Session,
    metadata: SourceFileMetadata,
    path: Path,
    *,
    source_file_id: int,
    run_id: int,
    ingested_at: datetime,
    batch_size: int,
) -> tuple[LoadCounts, int]:
    common = {
        "source_file_id": source_file_id,
        "pipeline_run_id": run_id,
        "ingested_at": ingested_at,
        "batch_size": batch_size,
    }
    if metadata.dataset_name == "yellow_tripdata":
        counts = load_yellow(session, path, **common)
        model = YellowTrip
    elif metadata.dataset_name == "taxi_zone_lookup":
        counts = load_taxi_zones(session, path, **common)
        model = TaxiZone
    else:
        raise ValueError(f"Unsupported ingestion dataset: {metadata.dataset_name}")

    persisted_count = session.scalar(
        select(func.count()).select_from(model).where(model.source_file_id == source_file_id)
    )
    return counts, persisted_count or 0


def _validate_counts(
    metadata: SourceFileMetadata,
    counts: LoadCounts,
    persisted_count: int,
) -> None:
    if metadata.row_count is None:
        raise ValueError("Registered source row count is required for raw ingestion")
    if counts.rows_read != metadata.row_count:
        raise ValueError(
            f"Row-count mismatch: read {counts.rows_read}, expected {metadata.row_count}"
        )
    if counts.rows_loaded != counts.rows_read or persisted_count != counts.rows_read:
        raise ValueError(
            "Row-count mismatch: "
            f"read {counts.rows_read}, copied {counts.rows_loaded}, persisted {persisted_count}"
        )


def _safe_error_message(error: Exception) -> str:
    detail = " ".join(str(error).split())
    if not detail:
        detail = error.__class__.__name__
    return f"Raw ingestion failed: {detail}"[:1000]
