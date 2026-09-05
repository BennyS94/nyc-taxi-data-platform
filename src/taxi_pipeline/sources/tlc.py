"""Official NYC TLC source definitions and Phase 01 compatibility helpers."""

from pathlib import Path
from urllib.request import urlopen

from taxi_pipeline.sources.models import SourcePartition

TLC_BASE_URL = "https://d37ci6vzurychx.cloudfront.net"
Source = SourcePartition


def yellow_trip_source(year: int, month: int) -> SourcePartition:
    """Resolve one monthly Yellow Taxi source without performing network access."""
    if not 1000 <= year <= 9999:
        raise ValueError("year must be a four-digit positive integer")
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    return SourcePartition(
        dataset_name="yellow_tripdata",
        service_type="yellow",
        year=year,
        month=month,
        partition_key=f"yellow/{year:04}/{month:02}",
        source_url=(
            f"{TLC_BASE_URL}/trip-data/yellow_tripdata_{year:04}-{month:02}.parquet"
        ),
        landing_path=f"data/landing/yellow/{year:04}/{month:02}.parquet",
        source_format="parquet",
    )


yellow_source = yellow_trip_source


def taxi_zone_source() -> SourcePartition:
    """Resolve the non-partitioned Taxi Zone Lookup source."""
    return SourcePartition(
        dataset_name="taxi_zone_lookup",
        service_type=None,
        year=None,
        month=None,
        partition_key="reference/taxi_zones",
        source_url=f"{TLC_BASE_URL}/misc/taxi_zone_lookup.csv",
        landing_path="data/landing/reference/taxi_zone_lookup.csv",
        source_format="csv",
    )


ZONES = taxi_zone_source()
SOURCES = (yellow_trip_source(2024, 12), yellow_trip_source(2025, 1), ZONES)


def ensure_local(source: Source, root: Path) -> Path:
    """Compatibility wrapper for the Phase 01 profiling command."""
    from taxi_pipeline.landing.downloader import ensure_local as download

    return download(source, root, opener=urlopen)


def file_identity(source: Source, root: Path) -> dict:
    """Compatibility wrapper retaining the Phase 01 report shape."""
    from taxi_pipeline.landing.metadata import file_identity as identify

    identity = identify(source, root)
    if source.dataset_name == "taxi_zone_lookup":
        identity["service_type"] = "taxi_zones"
    return identity
