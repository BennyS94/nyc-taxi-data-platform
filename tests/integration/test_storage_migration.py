from datetime import UTC, datetime

import pytest
from alembic.config import Config
from sqlalchemy import inspect, select

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


def test_storage_migration_round_trip(postgres_engine):
    config = Config("alembic.ini")
    try:
        command.downgrade(config, "20260906_04")
        columns = {column["name"] for column in inspect(postgres_engine).get_columns("source_files", schema="ops")}
        assert "storage_backend" not in columns
    finally:
        command.upgrade(config, "head")
    columns = {column["name"] for column in inspect(postgres_engine).get_columns("source_files", schema="ops")}
    assert {"storage_backend", "storage_uri", "storage_version_id", "stored_at"} <= columns
