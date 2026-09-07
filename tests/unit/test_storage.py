from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from taxi_pipeline.database.models import SourceFile
from taxi_pipeline.landing.metadata import file_sha256
from taxi_pipeline.sources.models import SourceFileMetadata
from taxi_pipeline.storage import (
    LocalLandingStorage,
    S3LandingStorage,
    StorageIntegrityError,
    StorageResult,
    build_storage,
    s3_key,
)
from taxi_pipeline.storage.service import _merge_storage_metadata


class FakeS3Client:
    def __init__(self):
        self.objects = {}
        self.put_calls = 0

    def head_object(self, *, Bucket, Key):
        try:
            value = self.objects[(Bucket, Key)]
        except KeyError as error:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject") from error
        return {
            "ContentLength": len(value["body"]),
            "Metadata": value["metadata"],
            "VersionId": value["version_id"],
        }

    def put_object(self, *, Bucket, Key, Body, Metadata):
        self.put_calls += 1
        self.objects[(Bucket, Key)] = {
            "body": Body.read(),
            "metadata": Metadata,
            "version_id": "version-1",
        }
        return {"VersionId": "version-1"}

    def get_object(self, *, Bucket, Key):
        return {"Body": BytesIO(self.objects[(Bucket, Key)]["body"])}

    def get_bucket_versioning(self, *, Bucket):
        return {"Status": "Enabled"}

    def get_public_access_block(self, *, Bucket):
        return {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        }

    def get_bucket_encryption(self, *, Bucket):
        return {
            "ServerSideEncryptionConfiguration": {
                "Rules": [
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                ]
            }
        }


def metadata(path: Path, *, service="yellow", year=2025, month=1, checksum=None):
    is_zones = service is None
    return SourceFileMetadata(
        dataset_name="taxi_zone_lookup" if is_zones else f"{service}_tripdata",
        service_type=service,
        year=None if is_zones else year,
        month=None if is_zones else month,
        partition_key="reference/taxi_zones" if is_zones else f"{service}/{year}/{month:02d}",
        source_url="https://example.test/source",
        landing_path=f"data/landing/{path.name}",
        source_format="csv" if is_zones else "parquet",
        checksum_sha256=checksum or file_sha256(path),
        file_size_bytes=path.stat().st_size,
        row_count=1,
        schema_fingerprint=None,
        schema_version=None,
    )


def test_checksum_addressed_keys_are_portable(tmp_path):
    path = tmp_path / "source"
    path.write_bytes(b"fixture")
    digest = "a" * 64
    assert s3_key(metadata(path, checksum=digest)) == f"landing/yellow/2025/01/{digest}.parquet"
    assert s3_key(metadata(path, service="green", checksum=digest)) == (
        f"landing/green/2025/01/{digest}.parquet"
    )
    assert s3_key(metadata(path, service=None, checksum=digest)) == (
        f"landing/reference/taxi_zones/{digest}.csv"
    )


def test_backend_selection_is_explicit(monkeypatch):
    monkeypatch.setenv("LANDING_BACKEND", "local")
    assert isinstance(build_storage(), LocalLandingStorage)
    monkeypatch.setenv("LANDING_BACKEND", "s3")
    monkeypatch.setenv("TLC_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    assert isinstance(build_storage(client=FakeS3Client()), S3LandingStorage)
    monkeypatch.setenv("LANDING_BACKEND", "unknown")
    with pytest.raises(ValueError, match="Unsupported LANDING_BACKEND"):
        build_storage()


def test_s3_upload_is_verified_and_idempotent(tmp_path):
    path = tmp_path / "yellow.parquet"
    path.write_bytes(b"immutable source")
    source = metadata(path)
    client = FakeS3Client()
    storage = S3LandingStorage("test-bucket", "us-east-1", client=client)

    first = storage.store(source, path)
    second = storage.store(source, path)

    assert first.uri == second.uri == f"s3://test-bucket/{s3_key(source)}"
    assert first.version_id == "version-1"
    assert client.put_calls == 1
    head = client.head_object(Bucket="test-bucket", Key=s3_key(source))
    assert head["Metadata"] == {
        "sha256": source.checksum_sha256,
        "partition-key": source.partition_key,
        "dataset-name": source.dataset_name,
        "service-type": "yellow",
    }


def test_existing_object_conflict_is_not_overwritten(tmp_path):
    path = tmp_path / "yellow.parquet"
    path.write_bytes(b"expected")
    source = metadata(path)
    client = FakeS3Client()
    client.objects[("test-bucket", s3_key(source))] = {
        "body": b"wrong",
        "metadata": {"sha256": "wrong"},
        "version_id": "old",
    }
    storage = S3LandingStorage("test-bucket", "us-east-1", client=client)

    with pytest.raises(StorageIntegrityError, match="conflicts"):
        storage.store(source, path)
    assert client.put_calls == 0


@pytest.mark.parametrize("stored_bytes, succeeds", [(b"restore me", True), (b"corrupt", False)])
def test_materialization_verifies_sha256_and_hides_corruption(tmp_path, stored_bytes, succeeds):
    original = tmp_path / "original.parquet"
    original.write_bytes(b"restore me")
    source = metadata(original)
    key = s3_key(source)
    client = FakeS3Client()
    client.objects[("test-bucket", key)] = {
        "body": stored_bytes,
        "metadata": {
            "sha256": source.checksum_sha256,
            "partition-key": source.partition_key,
            "dataset-name": source.dataset_name,
        },
        "version_id": "version-1",
    }
    destination = tmp_path / "landing" / "restored.parquet"
    storage = S3LandingStorage("test-bucket", "us-east-1", client=client)
    if succeeds:
        assert storage.materialize(
            storage_uri=f"s3://test-bucket/{key}",
            destination=destination,
            checksum_sha256=source.checksum_sha256,
            file_size_bytes=source.file_size_bytes,
        ) == destination
        assert destination.read_bytes() == b"restore me"
    else:
        with pytest.raises(StorageIntegrityError, match="SHA-256"):
            storage.materialize(
                storage_uri=f"s3://test-bucket/{key}",
                destination=destination,
                checksum_sha256=source.checksum_sha256,
                file_size_bytes=source.file_size_bytes,
            )
        assert not destination.exists()
        assert list(destination.parent.glob("*.part")) == []


def test_source_revisions_produce_distinct_keys(tmp_path):
    path = tmp_path / "yellow.parquet"
    path.write_bytes(b"version")
    first = metadata(path, checksum="a" * 64)
    revision = metadata(path, checksum="b" * 64)
    assert first.partition_key == revision.partition_key
    assert s3_key(first) != s3_key(revision)


def test_bucket_safeguards_are_checked():
    storage = S3LandingStorage("test-bucket", "us-east-1", client=FakeS3Client())
    assert storage.verify_bucket() == {
        "versioning": "Enabled",
        "public_access": "blocked",
        "encryption": "AES256",
    }


def test_local_s3_local_transitions_preserve_durable_metadata(tmp_path):
    path = tmp_path / "yellow.parquet"
    path.write_bytes(b"recoverable source")
    source_metadata = metadata(path)
    source = SourceFile(storage_backend="local")
    local_time = datetime.now(UTC)
    local_result = StorageResult("local", None, None, local_time)

    _merge_storage_metadata(source, local_result)
    assert source.storage_backend == "local"
    assert source.storage_uri is None

    client = FakeS3Client()
    s3_storage = S3LandingStorage("test-bucket", "us-east-1", client=client)
    s3_result = s3_storage.store(source_metadata, path)
    _merge_storage_metadata(source, s3_result)
    durable_values = (
        source.storage_backend,
        source.storage_uri,
        source.storage_version_id,
        source.stored_at,
    )
    assert durable_values[:3] == ("s3", s3_result.uri, "version-1")

    rerun_local_result = StorageResult(
        "local", None, None, s3_result.stored_at + timedelta(seconds=1)
    )
    _merge_storage_metadata(source, rerun_local_result)
    assert (
        source.storage_backend,
        source.storage_uri,
        source.storage_version_id,
        source.stored_at,
    ) == durable_values

    path.unlink()
    restored = s3_storage.materialize(
        storage_uri=source.storage_uri,
        destination=path,
        checksum_sha256=source_metadata.checksum_sha256,
        file_size_bytes=source_metadata.file_size_bytes,
    )
    assert restored.read_bytes() == b"recoverable source"
