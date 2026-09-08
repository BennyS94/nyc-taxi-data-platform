import os
from datetime import UTC, datetime

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select

from alembic import command
from taxi_pipeline.database.models import SourceFile

pytestmark = pytest.mark.integration


def test_storage_columns_default_local_and_accept_s3_metadata(db_session):
    source = SourceFile(
        dataset_name="yellow_tripdata",
        service_type="yellow",
        source_year=2025,
        source_month=1,
        partition_key="yellow/2025/01/storage-migration",
        source_url="https://example.test/yellow.parquet",
        landing_path="data/landing/yellow/2025/01.parquet",
        checksum_sha256="d" * 64,
        file_size_bytes=10,
        status="ready",
    )
    db_session.add(source)
    db_session.flush()
    assert source.storage_backend == "local"
    assert source.storage_uri is None

    source.storage_backend = "s3"
    source.storage_uri = f"s3://bucket/landing/yellow/2025/01/{'d' * 64}.parquet"
    source.storage_version_id = "version-1"
    source.stored_at = datetime.now(UTC)
    db_session.flush()
    persisted = db_session.scalar(
        select(SourceFile).where(SourceFile.source_file_id == source.source_file_id)
    )
    assert persisted.storage_backend == "s3"


def test_storage_migration_round_trip_preserves_application_database(
    db_session, disposable_database_url
):
    sentinel_uri = f"s3://bucket/landing/yellow/2025/02/{'e' * 64}.parquet"
    sentinel = SourceFile(
        dataset_name="yellow_tripdata",
        service_type="yellow",
        source_year=2025,
        source_month=2,
        partition_key="yellow/2025/02/migration-safety-sentinel",
        source_url="https://example.test/yellow-sentinel.parquet",
        landing_path="data/landing/yellow/2025/02.parquet",
        checksum_sha256="e" * 64,
        file_size_bytes=10,
        status="ready",
        storage_backend="s3",
        storage_uri=sentinel_uri,
        storage_version_id="durable-version",
        stored_at=datetime.now(UTC),
    )
    db_session.add(sentinel)
    db_session.flush()
    sentinel_id = sentinel.source_file_id

    config = Config("alembic.ini")
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = disposable_database_url
    migration_engine = create_engine(disposable_database_url)
    try:
        command.upgrade(config, "head")
        command.downgrade(config, "20260906_04")
        columns = {
            column["name"]
            for column in inspect(migration_engine).get_columns("source_files", schema="ops")
        }
        assert "storage_backend" not in columns
        command.upgrade(config, "head")
        columns = {
            column["name"]
            for column in inspect(migration_engine).get_columns("source_files", schema="ops")
        }
    finally:
        migration_engine.dispose()
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url

    assert {"storage_backend", "storage_uri", "storage_version_id", "stored_at"} <= columns

    db_session.expire_all()
    preserved = db_session.get(SourceFile, sentinel_id)
    assert preserved is not None
    assert preserved.storage_backend == "s3"
    assert preserved.storage_uri == sentinel_uri
    assert preserved.storage_version_id == "durable-version"
