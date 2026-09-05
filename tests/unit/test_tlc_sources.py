import io
from dataclasses import replace

import pytest

from taxi_pipeline.sources import tlc


def test_sources():
    for source, period, path in zip(tlc.SOURCES[:2], ["2024-12", "2025-01"],
                                    ["2024/12", "2025/01"]):
        assert source.url == (
            f"https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{period}.parquet"
        )
        assert source.landing_path == f"data/landing/yellow/{path}.parquet"
    assert tlc.ZONES.url == "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
    assert tlc.ZONES.landing_path == "data/landing/reference/taxi_zone_lookup.csv"


def test_source_partition_metadata():
    yellow = tlc.yellow_trip_source(2025, 1)
    assert yellow.dataset_name == "yellow_tripdata"
    assert yellow.service_type == "yellow"
    assert yellow.partition_key == "yellow/2025/01"
    assert yellow.source_format == "parquet"

    zones = tlc.taxi_zone_source()
    assert zones.dataset_name == "taxi_zone_lookup"
    assert zones.service_type is None
    assert zones.year is None
    assert zones.month is None
    assert zones.partition_key == "reference/taxi_zones"
    assert zones.source_format == "csv"


@pytest.mark.parametrize(("year", "month"), [(2025, 0), (2025, 13), (999, 1)])
def test_invalid_yellow_partition_is_rejected(year, month):
    with pytest.raises(ValueError):
        tlc.yellow_trip_source(year, month)


def test_download_reuse_and_identity(tmp_path, monkeypatch):
    response = io.BytesIO(b"source")
    response.headers = {"Content-Length": "6"}
    monkeypatch.setattr(tlc, "urlopen", lambda *a, **k: response)
    path = tlc.ensure_local(tlc.ZONES, tmp_path)
    assert path.read_bytes() == b"source"
    assert tlc.ensure_local(tlc.ZONES, tmp_path) == path
    identity = tlc.file_identity(tlc.ZONES, tmp_path)
    assert identity["file_size_bytes"] == 6
    assert len(identity["checksum_sha256"]) == 64


def test_failed_download_cleanup(tmp_path, monkeypatch):
    response = io.BytesIO(b"short")
    response.headers = {"Content-Length": "100"}
    monkeypatch.setattr(tlc, "urlopen", lambda *a, **k: response)
    with pytest.raises(OSError, match="Incomplete"):
        tlc.ensure_local(tlc.ZONES, tmp_path)
    assert not list((tmp_path / "data/landing").rglob("*.partial"))
    assert not (tmp_path / tlc.ZONES.landing_path).exists()


def test_download_path_guard(tmp_path):
    with pytest.raises(ValueError, match="data/landing"):
        tlc.ensure_local(replace(tlc.ZONES, landing_path="outside.csv"), tmp_path)
