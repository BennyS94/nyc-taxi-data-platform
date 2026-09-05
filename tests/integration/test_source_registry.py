from dataclasses import replace

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from taxi_pipeline.database.models import SourceFile
from taxi_pipeline.metadata.source_registry import prepare_ingestion, register_source_file
from taxi_pipeline.metadata.statuses import IngestionDecision, SourceStatus
from taxi_pipeline.sources.models import SourceFileMetadata

pytestmark = pytest.mark.integration


def source_metadata(partition: str = "yellow/2025/02", checksum: str = "a" * 64):
    return SourceFileMetadata(
        dataset_name="yellow_tripdata",
        service_type="yellow",
        year=2025,
        month=2,
        partition_key=partition,
        source_url="https://example.test/yellow.parquet",
        landing_path="data/landing/yellow/2025/02.parquet",
        source_format="parquet",
        checksum_sha256=checksum,
        file_size_bytes=100,
        row_count=10,
        schema_fingerprint="f" * 64,
        schema_version="yellow_v2",
    )


def source_count(db_session) -> int:
    return db_session.scalar(select(func.count()).select_from(SourceFile))


def test_new_and_exact_ready_source_registration_is_idempotent(db_session):
    metadata = source_metadata()
    before = source_count(db_session)

    first = prepare_ingestion(db_session, metadata)
    second = prepare_ingestion(db_session, metadata)

    assert first.source_status is SourceStatus.READY
    assert first.decision is IngestionDecision.PROCEED
    assert first.is_new_registration
    assert second.source_file_id == first.source_file_id
    assert second.decision is IngestionDecision.PROCEED
    assert not second.is_new_registration
    assert source_count(db_session) == before + 1


def test_revision_is_preserved_blocked_and_idempotent(db_session):
    original = register_source_file(db_session, source_metadata())
    revision_metadata = replace(source_metadata(), checksum_sha256="b" * 64)

    revision = register_source_file(db_session, revision_metadata)
    repeated = register_source_file(db_session, revision_metadata)

    assert revision.source_file_id != original.source_file_id
    assert revision.source_status is SourceStatus.REVISION_DETECTED
    assert revision.decision is IngestionDecision.SOURCE_REVISION_BLOCKED
    assert repeated.source_file_id == revision.source_file_id
    assert not repeated.is_new_registration


def test_different_partition_registers_as_independent_ready_source(db_session):
    first = register_source_file(db_session, source_metadata())
    independent = register_source_file(
        db_session,
        replace(
            source_metadata(),
            partition_key="yellow/2025/03",
            landing_path="data/landing/yellow/2025/03.parquet",
        ),
    )

    assert independent.source_file_id != first.source_file_id
    assert independent.source_status is SourceStatus.READY
    assert independent.decision is IngestionDecision.PROCEED


def test_failed_registration_leaves_no_partial_source_row(db_session):
    before = source_count(db_session)
    invalid = replace(
        source_metadata(),
        partition_key="yellow/invalid",
        checksum_sha256="9" * 64,
        file_size_bytes=0,
    )

    with pytest.raises(IntegrityError):
        register_source_file(db_session, invalid)

    assert source_count(db_session) == before
