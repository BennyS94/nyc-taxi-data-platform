"""Narrow landing-storage implementations for local files and AWS S3."""

import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

from taxi_pipeline.landing.metadata import file_sha256
from taxi_pipeline.sources.models import SourceFileMetadata

CHUNK_SIZE = 1024 * 1024


class StorageIntegrityError(RuntimeError):
    """Stored or materialized bytes conflict with immutable source identity."""


@dataclass(frozen=True)
class StorageResult:
    backend: str
    uri: str | None
    version_id: str | None
    stored_at: datetime


def s3_key(metadata: SourceFileMetadata) -> str:
    """Return the checksum-addressed key for one supported source version."""
    checksum = metadata.checksum_sha256
    if metadata.dataset_name == "taxi_zone_lookup":
        return f"landing/reference/taxi_zones/{checksum}.csv"
    if metadata.service_type not in {"yellow", "green"}:
        raise ValueError(f"Unsupported S3 dataset: {metadata.dataset_name}")
    if metadata.year is None or metadata.month is None:
        raise ValueError("Monthly S3 sources require year and month")
    return (
        f"landing/{metadata.service_type}/{metadata.year:04d}/{metadata.month:02d}/"
        f"{checksum}.parquet"
    )


class LocalLandingStorage:
    backend = "local"

    def store(self, metadata: SourceFileMetadata, path: Path) -> StorageResult:
        _verify_local(path, metadata.checksum_sha256)
        return StorageResult("local", None, None, datetime.now(UTC))

    def materialize(
        self,
        *,
        storage_uri: str | None,
        destination: Path,
        checksum_sha256: str,
        file_size_bytes: int,
    ) -> Path:
        del storage_uri, file_size_bytes
        _verify_local(destination, checksum_sha256)
        return destination


class S3LandingStorage:
    backend = "s3"

    def __init__(self, bucket: str, region: str, *, client: Any | None = None):
        if not bucket:
            raise ValueError("TLC_S3_BUCKET is required for the S3 landing backend")
        if not region:
            raise ValueError("AWS_REGION is required for the S3 landing backend")
        self.bucket = bucket
        self.client = client or boto3.client("s3", region_name=region)

    def store(self, metadata: SourceFileMetadata, path: Path) -> StorageResult:
        _verify_local(path, metadata.checksum_sha256)
        key = s3_key(metadata)
        existing = self._head(key)
        if existing is None:
            with path.open("rb") as body:
                response = self.client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=body,
                    Metadata=_object_metadata(metadata),
                )
            version_id = response.get("VersionId")
            existing = self.client.head_object(Bucket=self.bucket, Key=key)
        else:
            version_id = existing.get("VersionId")
        self._verify_head(existing, metadata)
        return StorageResult(
            backend="s3",
            uri=f"s3://{self.bucket}/{key}",
            version_id=version_id,
            stored_at=datetime.now(UTC),
        )

    def inspect(self, metadata: SourceFileMetadata) -> StorageResult:
        key = s3_key(metadata)
        head = self._head(key)
        if head is None:
            raise StorageIntegrityError("S3 object does not exist")
        self._verify_head(head, metadata)
        return StorageResult(
            "s3",
            f"s3://{self.bucket}/{key}",
            head.get("VersionId"),
            datetime.now(UTC),
        )

    def materialize(
        self,
        *,
        storage_uri: str | None,
        destination: Path,
        checksum_sha256: str,
        file_size_bytes: int,
    ) -> Path:
        if destination.exists():
            _verify_local(destination, checksum_sha256)
            return destination
        bucket, key = _parse_s3_uri(storage_uri)
        if bucket != self.bucket:
            raise StorageIntegrityError("storage URI bucket does not match configuration")
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial: Path | None = None
        try:
            response = self.client.get_object(Bucket=bucket, Key=key)
            with tempfile.NamedTemporaryFile(
                dir=destination.parent,
                prefix=f"{destination.name}.",
                suffix=".part",
                delete=False,
            ) as output:
                partial = Path(output.name)
                size = 0
                while chunk := response["Body"].read(CHUNK_SIZE):
                    output.write(chunk)
                    size += len(chunk)
            if size != file_size_bytes or file_sha256(partial) != checksum_sha256:
                raise StorageIntegrityError("materialized S3 object failed SHA-256 or size check")
            partial.replace(destination)
            return destination
        finally:
            if partial is not None:
                partial.unlink(missing_ok=True)

    def verify_bucket(self) -> dict[str, str]:
        versioning = self.client.get_bucket_versioning(Bucket=self.bucket).get("Status")
        public = self.client.get_public_access_block(Bucket=self.bucket)[
            "PublicAccessBlockConfiguration"
        ]
        encryption = self.client.get_bucket_encryption(Bucket=self.bucket)
        if versioning != "Enabled" or not all(public.values()):
            raise StorageIntegrityError("bucket versioning or Block Public Access is not enabled")
        algorithm = encryption["ServerSideEncryptionConfiguration"]["Rules"][0][
            "ApplyServerSideEncryptionByDefault"
        ]["SSEAlgorithm"]
        return {"versioning": versioning, "public_access": "blocked", "encryption": algorithm}

    def _head(self, key: str) -> dict[str, Any] | None:
        try:
            return self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    @staticmethod
    def _verify_head(head: dict[str, Any], metadata: SourceFileMetadata) -> None:
        object_metadata = head.get("Metadata", {})
        if (
            head.get("ContentLength") != metadata.file_size_bytes
            or object_metadata.get("sha256") != metadata.checksum_sha256
            or object_metadata.get("partition-key") != metadata.partition_key
            or object_metadata.get("dataset-name") != metadata.dataset_name
        ):
            raise StorageIntegrityError("S3 object metadata or size conflicts with source")


def build_storage(*, client: Any | None = None):
    backend = os.getenv("LANDING_BACKEND", "local").lower()
    if backend == "local":
        return LocalLandingStorage()
    if backend == "s3":
        return S3LandingStorage(
            os.getenv("TLC_S3_BUCKET", ""),
            os.getenv("AWS_REGION", ""),
            client=client,
        )
    raise ValueError(f"Unsupported LANDING_BACKEND: {backend}")


def _object_metadata(metadata: SourceFileMetadata) -> dict[str, str]:
    values = {
        "sha256": metadata.checksum_sha256,
        "partition-key": metadata.partition_key,
        "dataset-name": metadata.dataset_name,
    }
    if metadata.service_type:
        values["service-type"] = metadata.service_type
    return values


def _verify_local(path: Path, checksum_sha256: str) -> None:
    if not path.is_file() or file_sha256(path) != checksum_sha256:
        raise StorageIntegrityError("local landing file does not match registered SHA-256")


def _parse_s3_uri(uri: str | None) -> tuple[str, str]:
    parsed = urlparse(uri or "")
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.lstrip("/"):
        raise StorageIntegrityError("invalid S3 storage URI")
    return parsed.netloc, parsed.path.lstrip("/")
