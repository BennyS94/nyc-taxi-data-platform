"""Structural metadata collection for immutable landing files."""

import hashlib
from pathlib import Path

from taxi_pipeline.sources.models import SourcePartition

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
