"""Phase 01 sources and immutable local downloads."""

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen


@dataclass(frozen=True)
class Source:
    service_type: str
    year: int | None
    month: int | None
    url: str
    landing_path: str


def yellow_source(year: int, month: int) -> Source:
    if not 1 <= month <= 12 or not 1 <= year <= 9999:
        raise ValueError("Invalid source month/year")
    return Source(
        "yellow", year, month,
        f"https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{year:04}-{month:02}.parquet",
        f"data/landing/yellow/{year:04}/{month:02}.parquet",
    )


ZONES = Source(
    "taxi_zones", None, None,
    "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv",
    "data/landing/reference/taxi_zone_lookup.csv",
)
SOURCES = (yellow_source(2024, 12), yellow_source(2025, 1), ZONES)


def ensure_local(source: Source, root: Path) -> Path:
    destination = (root / source.landing_path).resolve()
    if not destination.is_relative_to((root / "data/landing").resolve()):
        raise ValueError("Download must stay under data/landing")
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, suffix=".partial", delete=False
        ) as output:
            partial = Path(output.name)
            with urlopen(source.url, timeout=120) as response:
                expected = response.headers.get("Content-Length")
                size = 0
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    size += len(chunk)
                if size == 0 or (expected is not None and size != int(expected)):
                    raise OSError("Incomplete source download")
        partial.rename(destination)
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)
    return destination


def file_identity(source: Source, root: Path) -> dict:
    path = root / source.landing_path
    with path.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "service_type": source.service_type, "year": source.year, "month": source.month,
        "source_url": source.url, "local_path": source.landing_path,
        "file_size_bytes": path.stat().st_size, "checksum_sha256": checksum,
    }
