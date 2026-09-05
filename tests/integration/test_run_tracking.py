from dataclasses import replace

import pytest

from taxi_pipeline.database.models import SourceFile
from taxi_pipeline.metadata.runs import (
    create_skipped_run,
    mark_run_failed,
    mark_run_succeeded,
    start_run,
)
from taxi_pipeline.metadata.source_registry import mark_source_loaded, register_source_file
from taxi_pipeline.metadata.statuses import (
    IngestionDecision,
    MetadataStateError,
    RunStatus,
    SkipReason,
    SourceStatus,
)
from taxi_pipeline.sources.models import SourceFileMetadata

pytestmark = pytest.mark.integration


def metadata(checksum: str = "2" * 64) -> SourceFileMetadata:
    return SourceFileMetadata(
        dataset_name="yellow_tripdata",
        service_type="yellow",
        year=2025,
        month=4,
        partition_key="yellow/2025/04",
        source_url="https://example.test/yellow.parquet",
        landing_path="data/landing/yellow/2025/04.parquet",
        source_format="parquet",
        checksum_sha256=checksum,
        file_size_bytes=100,
        row_count=10,
        schema_fingerprint="f" * 64,
        schema_version="yellow_v2",
    )


def ready_source(db_session):
    return register_source_file(db_session, metadata())


def test_start_and_success_update_run_and_source_together(db_session):
    registered = ready_source(db_session)
    run = start_run(db_session, registered.source_file_id)

    assert run.status == RunStatus.RUNNING.value
    assert run.started_at is not None
    assert run.finished_at is None

    succeeded = mark_run_succeeded(
        db_session,
        run.run_id,
        rows_read=10,
        rows_loaded=10,
        warning_count=1,
        error_count=0,
    )
    source = db_session.get(SourceFile, registered.source_file_id)

    assert succeeded.status == RunStatus.SUCCEEDED.value
    assert succeeded.finished_at is not None
    assert succeeded.rows_read == 10
    assert succeeded.rows_loaded == 10
    assert succeeded.error_message is None
    assert source.status == SourceStatus.LOADED.value
    assert source.loaded_at == succeeded.finished_at
    assert register_source_file(db_session, metadata()).decision is IngestionDecision.ALREADY_LOADED


def test_failure_leaves_source_ready_and_retry_creates_new_run(db_session):
    registered = ready_source(db_session)
    failed_run = start_run(db_session, registered.source_file_id)
    mark_run_failed(db_session, failed_run.run_id, "controlled load failure")

    source = db_session.get(SourceFile, registered.source_file_id)
    assert failed_run.status == RunStatus.FAILED.value
    assert failed_run.finished_at is not None
    assert failed_run.error_message == "controlled load failure"
    assert source.status == SourceStatus.READY.value

    retry = start_run(db_session, registered.source_file_id)
    assert retry.run_id != failed_run.run_id
    assert retry.status == RunStatus.RUNNING.value
    assert failed_run.status == RunStatus.FAILED.value


def test_already_loaded_skip_is_recorded_without_error(db_session):
    registered = ready_source(db_session)
    mark_source_loaded(db_session, registered.source_file_id)

    run = create_skipped_run(
        db_session,
        registered.source_file_id,
        SkipReason.ALREADY_LOADED,
    )

    assert run.status == RunStatus.SKIPPED.value
    assert run.status_reason == SkipReason.ALREADY_LOADED.value
    assert run.finished_at is not None
    assert run.rows_loaded == 0
    assert run.error_message is None


def test_source_revision_skip_and_loaded_transition_block(db_session):
    ready_source(db_session)
    revision = register_source_file(db_session, replace(metadata(), checksum_sha256="3" * 64))

    run = create_skipped_run(
        db_session,
        revision.source_file_id,
        SkipReason.SOURCE_REVISION_DETECTED,
    )

    assert run.status == RunStatus.SKIPPED.value
    assert run.status_reason == SkipReason.SOURCE_REVISION_DETECTED.value
    assert run.rows_loaded == 0
    with pytest.raises(MetadataStateError, match="Cannot mark source"):
        mark_source_loaded(db_session, revision.source_file_id)


def test_terminal_runs_reject_further_completion(db_session):
    registered = ready_source(db_session)
    failed = start_run(db_session, registered.source_file_id)
    mark_run_failed(db_session, failed.run_id, "failed")
    with pytest.raises(MetadataStateError, match="terminal"):
        mark_run_succeeded(db_session, failed.run_id)

    retry = start_run(db_session, registered.source_file_id)
    mark_run_succeeded(db_session, retry.run_id)
    with pytest.raises(MetadataStateError, match="terminal"):
        mark_run_failed(db_session, retry.run_id, "cannot reopen")


def test_skipped_run_is_terminal_and_cannot_be_started_for_loaded_source(db_session):
    registered = ready_source(db_session)
    mark_source_loaded(db_session, registered.source_file_id)
    skipped = create_skipped_run(
        db_session,
        registered.source_file_id,
        SkipReason.ALREADY_LOADED,
    )

    with pytest.raises(MetadataStateError, match="terminal"):
        mark_run_succeeded(db_session, skipped.run_id)
    with pytest.raises(MetadataStateError, match="Cannot start run"):
        start_run(db_session, registered.source_file_id)


def test_success_rejects_non_ready_source_without_partially_finishing_run(db_session):
    registered = ready_source(db_session)
    run = start_run(db_session, registered.source_file_id)
    source = db_session.get(SourceFile, registered.source_file_id)
    source.status = SourceStatus.REVISION_DETECTED.value
    db_session.flush()

    with pytest.raises(MetadataStateError, match="Cannot mark source"):
        mark_run_succeeded(db_session, run.run_id)

    assert run.status == RunStatus.RUNNING.value
    assert run.finished_at is None
