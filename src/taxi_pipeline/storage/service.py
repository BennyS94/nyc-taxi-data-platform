"""Application services connecting source acquisition, S3, and operational metadata."""

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from taxi_pipeline.database import get_engine
from taxi_pipeline.database.models import SourceFile
from taxi_pipeline.landing import ensure_local, inspect_source
from taxi_pipeline.sources.models import SourceFileMetadata, SourcePartition
from taxi_pipeline.storage.backends import S3LandingStorage, StorageResult, build_storage


@dataclass(frozen=True)
class PreparedSource:
    metadata: SourceFileMetadata
    storage: StorageResult


def prepare_source(source: SourcePartition, repository_root: Path) -> PreparedSource:
    """Materialize or acquire, validate, and durably store one source."""
    storage = build_storage()
    destination = _destination(repository_root, source.landing_path)
    if isinstance(storage, S3LandingStorage) and not destination.exists():
        _recover_partition_if_known(storage, source.partition_key, repository_root)
    ensure_local(source, repository_root)
    metadata = inspect_source(source, repository_root)
    stored = storage.store(metadata, destination)
    return PreparedSource(metadata, stored)


def persist_storage_metadata(
    engine: Engine,
    source_file_id: int,
    storage: StorageResult,
) -> None:
    """Attach verified storage details without changing ingestion status."""
    with Session(engine) as session, session.begin():
        source = session.get(SourceFile, source_file_id)
        if source is None:
            raise ValueError(f"Unknown source file ID: {source_file_id}")
        source.storage_backend = storage.backend
        source.storage_uri = storage.uri
        source.storage_version_id = storage.version_id
        source.stored_at = storage.stored_at


def sync_source(source_file_id: int, repository_root: Path) -> StorageResult:
    """Upload and record one registered local source version."""
    storage = build_storage()
    if not isinstance(storage, S3LandingStorage):
        raise ValueError("storage sync requires LANDING_BACKEND=s3")  # noqa: TRY004
    engine = get_engine()
    try:
        with Session(engine) as session:
            source = session.get(SourceFile, source_file_id)
            if source is None:
                raise ValueError(f"Unknown source file ID: {source_file_id}")
            metadata = _metadata_from_record(source)
        result = storage.store(
            metadata,
            _destination(repository_root, metadata.landing_path),
        )
        persist_storage_metadata(engine, source_file_id, result)
        return result
    finally:
        engine.dispose()


def find_source_file_id(service: str, year: int | None, month: int | None) -> int:
    """Resolve the latest registered version for a CLI storage sync."""
    if service == "zones":
        partition_key = "reference/taxi_zones"
    elif service in {"yellow", "green"} and year is not None and month is not None:
        partition_key = f"{service}/{year:04d}/{month:02d}"
    else:
        raise ValueError("monthly storage sync requires year and month")
    engine = get_engine()
    try:
        with Session(engine) as session:
            source_file_id = session.scalar(
                select(SourceFile.source_file_id)
                .where(SourceFile.partition_key == partition_key)
                .order_by(SourceFile.source_file_id.desc())
                .limit(1)
            )
            if source_file_id is None:
                raise ValueError(f"No registered source for {partition_key}")
            return source_file_id
    finally:
        engine.dispose()


def sync_all_sources(repository_root: Path) -> list[tuple[int, StorageResult]]:
    """Sync all registered versions whose deterministic local file exists."""
    engine = get_engine()
    try:
        with Session(engine) as session:
            sources = list(session.scalars(select(SourceFile).order_by(SourceFile.source_file_id)))
    finally:
        engine.dispose()
    results = []
    for source in sources:
        if _destination(repository_root, source.landing_path).is_file():
            results.append(
                (
                    source.source_file_id,
                    sync_source(source.source_file_id, repository_root),
                )
            )
    return results


def verify_source_storage(source_file_id: int) -> StorageResult:
    """Verify one registered S3 object by HEAD metadata and size."""
    storage = build_storage()
    if not isinstance(storage, S3LandingStorage):
        raise ValueError("storage verification requires LANDING_BACKEND=s3")  # noqa: TRY004
    engine = get_engine()
    try:
        with Session(engine) as session:
            source = session.get(SourceFile, source_file_id)
            if source is None:
                raise ValueError(f"Unknown source file ID: {source_file_id}")
            if source.storage_backend != "s3":
                raise ValueError(f"Source file {source_file_id} is not S3-backed")
            result = storage.inspect(_metadata_from_record(source))
            if source.storage_uri != result.uri:
                raise ValueError(
                    f"Source file {source_file_id} storage URI does not match its immutable key"
                )
            if (
                source.storage_version_id is not None
                and result.version_id is not None
                and source.storage_version_id != result.version_id
            ):
                raise ValueError(
                    f"Source file {source_file_id} storage version does not match S3"
                )
            return result
    finally:
        engine.dispose()


def materialize_source(source_file_id: int, repository_root: Path) -> Path:
    """Restore one registered S3 source to its deterministic local path."""
    storage = build_storage()
    if not isinstance(storage, S3LandingStorage):
        raise ValueError("materialization requires LANDING_BACKEND=s3")  # noqa: TRY004
    engine = get_engine()
    try:
        with Session(engine) as session:
            source = session.get(SourceFile, source_file_id)
            if source is None:
                raise ValueError(f"Unknown source file ID: {source_file_id}")
            values = {
                "storage_uri": source.storage_uri,
                "destination": _destination(repository_root, source.landing_path),
                "checksum_sha256": source.checksum_sha256,
                "file_size_bytes": source.file_size_bytes,
            }
        return storage.materialize(**values)
    finally:
        engine.dispose()


def _recover_partition_if_known(
    storage: S3LandingStorage,
    partition_key: str,
    repository_root: Path,
) -> None:
    if not os.getenv("DATABASE_URL"):
        return
    engine = get_engine()
    try:
        with Session(engine) as session:
            source = session.scalar(
                select(SourceFile)
                .where(
                    SourceFile.partition_key == partition_key,
                    SourceFile.storage_backend == "s3",
                    SourceFile.storage_uri.is_not(None),
                )
                .order_by(SourceFile.source_file_id.desc())
                .limit(1)
            )
            if source is None:
                return
            values = {
                "storage_uri": source.storage_uri,
                "destination": _destination(repository_root, source.landing_path),
                "checksum_sha256": source.checksum_sha256,
                "file_size_bytes": source.file_size_bytes,
            }
        storage.materialize(**values)
    finally:
        engine.dispose()


def _metadata_from_record(source: SourceFile) -> SourceFileMetadata:
    suffix = Path(source.landing_path).suffix.lower()
    return SourceFileMetadata(
        dataset_name=source.dataset_name,
        service_type=source.service_type,
        year=source.source_year,
        month=source.source_month,
        partition_key=source.partition_key,
        source_url=source.source_url,
        landing_path=source.landing_path,
        source_format="csv" if suffix == ".csv" else "parquet",
        checksum_sha256=source.checksum_sha256,
        file_size_bytes=source.file_size_bytes,
        row_count=source.row_count,
        schema_fingerprint=source.schema_fingerprint,
        schema_version=None,
    )


def _destination(repository_root: Path, landing_path: str) -> Path:
    landing_root = (repository_root / "data" / "landing").resolve()
    destination = (repository_root / landing_path).resolve()
    if not destination.is_relative_to(landing_root):
        raise ValueError("Landing materialization must stay under data/landing")
    return destination
