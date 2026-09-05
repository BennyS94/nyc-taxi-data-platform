"""PostgreSQL-backed immutable source-file registration."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from taxi_pipeline.database.models import SourceFile
from taxi_pipeline.metadata.statuses import (
    MetadataStateError,
    SourceRegistrationResult,
    SourceStatus,
    decision_for_source_status,
)
from taxi_pipeline.sources.models import SourceFileMetadata


def register_source_file(
    session: Session,
    metadata: SourceFileMetadata,
) -> SourceRegistrationResult:
    """Register or reuse one source version within the caller's transaction."""
    existing = _find_exact_version(session, metadata)
    if existing is not None:
        return _registration_result(existing, is_new=False)

    partition_exists = session.scalar(
        select(SourceFile.source_file_id)
        .where(SourceFile.partition_key == metadata.partition_key)
        .limit(1)
    )
    status = SourceStatus.REVISION_DETECTED if partition_exists else SourceStatus.READY
    source_file = SourceFile(
        dataset_name=metadata.dataset_name,
        service_type=metadata.service_type,
        source_year=metadata.year,
        source_month=metadata.month,
        partition_key=metadata.partition_key,
        source_url=metadata.source_url,
        landing_path=metadata.landing_path,
        checksum_sha256=metadata.checksum_sha256,
        file_size_bytes=metadata.file_size_bytes,
        row_count=metadata.row_count,
        schema_fingerprint=metadata.schema_fingerprint,
        status=status.value,
        validated_at=datetime.now(UTC),
    )

    try:
        with session.begin_nested():
            session.add(source_file)
            session.flush()
    except IntegrityError:
        raced_version = _find_exact_version(session, metadata)
        if raced_version is None:
            raise
        return _registration_result(raced_version, is_new=False)

    return _registration_result(source_file, is_new=True)


def prepare_ingestion(
    session: Session,
    metadata: SourceFileMetadata,
) -> SourceRegistrationResult:
    """Register source metadata and return the authoritative ingestion decision."""
    return register_source_file(session, metadata)


def get_source_file(session: Session, source_file_id: int) -> SourceFile:
    """Load a source file or raise a clear operational metadata error."""
    source_file = session.get(SourceFile, source_file_id)
    if source_file is None:
        raise MetadataStateError(f"Unknown source file ID: {source_file_id}")
    return source_file


def _find_exact_version(
    session: Session,
    metadata: SourceFileMetadata,
) -> SourceFile | None:
    return session.scalar(
        select(SourceFile).where(
            SourceFile.partition_key == metadata.partition_key,
            SourceFile.checksum_sha256 == metadata.checksum_sha256,
        )
    )


def _registration_result(source_file: SourceFile, *, is_new: bool) -> SourceRegistrationResult:
    try:
        status = SourceStatus(source_file.status)
    except ValueError as error:
        raise MetadataStateError(f"Unknown source status: {source_file.status}") from error
    if source_file.source_file_id is None:
        raise MetadataStateError("Source registration did not produce an ID")
    return SourceRegistrationResult(
        source_file_id=source_file.source_file_id,
        source_status=status,
        decision=decision_for_source_status(status),
        is_new_registration=is_new,
    )
