"""Structural metadata collection for immutable landing files."""

import hashlib
from pathlib import Path

import pyarrow.parquet as pq

from taxi_pipeline.profiling.schema import schema_fingerprint
from taxi_pipeline.sources.contracts import (
    SourceContractError,
    validate_taxi_zones,
    validate_yellow_schema,
)
from taxi_pipeline.sources.models import SourceFileMetadata, SourcePartition

HASH_CHUNK_SIZE = 1024 * 1024


def file_sha256(path: Path) -> str:
    """Hash a file incrementally using SHA-256."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(source: SourcePartition, root: Path) -> dict:
    """Return the stable Phase 01 file-identity report fields."""
    path = root / source.landing_path
    return {
        "service_type": source.service_type,
        "year": source.year,
        "month": source.month,
        "source_url": source.source_url,
        "local_path": source.landing_path,
        "file_size_bytes": path.stat().st_size,
        "checksum_sha256": file_sha256(path),
    }


def inspect_source(source: SourcePartition, root: Path) -> SourceFileMetadata:
    """Collect deterministic identity and validated structural metadata."""
    path = root / source.landing_path
    file_size = path.stat().st_size
    if file_size == 0:
        raise SourceContractError("Source file is empty")

    row_count: int | None
    fingerprint: str | None
    schema_version: str | None
    if source.source_format == "parquet":
        parquet = pq.ParquetFile(path)
        schema = parquet.schema_arrow
        schema_version = validate_yellow_schema(schema)
        _, fingerprint = schema_fingerprint(schema)
        row_count = parquet.metadata.num_rows
    elif source.source_format == "csv":
        row_count = validate_taxi_zones(path)
        fingerprint = None
        schema_version = None
    else:
        raise ValueError(f"Unsupported source format: {source.source_format}")

    return SourceFileMetadata(
        dataset_name=source.dataset_name,
        service_type=source.service_type,
        year=source.year,
        month=source.month,
        partition_key=source.partition_key,
        source_url=source.source_url,
        landing_path=source.landing_path,
        source_format=source.source_format,
        checksum_sha256=file_sha256(path),
        file_size_bytes=file_size,
        row_count=row_count,
        schema_fingerprint=fingerprint,
        schema_version=schema_version,
    )
