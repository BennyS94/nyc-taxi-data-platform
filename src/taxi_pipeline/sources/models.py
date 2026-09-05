"""Lightweight source and source-metadata value objects."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePartition:
    """A deterministic official source partition and its landing location."""

    dataset_name: str
    service_type: str | None
    year: int | None
    month: int | None
    partition_key: str
    source_url: str
    landing_path: str
    source_format: str

    @property
    def url(self) -> str:
        """Retain the Phase 01 attribute name used by the profiler."""
        return self.source_url


@dataclass(frozen=True)
class SourceFileMetadata:
    """Portable structural metadata for one local source file."""

    dataset_name: str
    service_type: str | None
    year: int | None
    month: int | None
    partition_key: str
    source_url: str
    landing_path: str
    source_format: str
    checksum_sha256: str
    file_size_bytes: int
    row_count: int | None
    schema_fingerprint: str | None
    schema_version: str | None
