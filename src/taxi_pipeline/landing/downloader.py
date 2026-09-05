"""Safe immutable landing-file downloads."""

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO
from urllib.request import urlopen

from taxi_pipeline.sources.models import SourcePartition

CHUNK_SIZE = 1024 * 1024


def ensure_local(
    source: SourcePartition,
    root: Path,
    *,
    opener: Callable[..., BinaryIO] = urlopen,
) -> Path:
    """Reuse a final landing file or download it through a temporary partial path."""
    landing_root = (root / "data" / "landing").resolve()
    destination = (root / source.landing_path).resolve()
    if not destination.is_relative_to(landing_root):
        raise ValueError("Download must stay under data/landing")
    if destination.exists():
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f"{destination.name}.",
            suffix=".part",
            delete=False,
        ) as output:
            partial = Path(output.name)
            with opener(source.source_url, timeout=120) as response:
                expected_size = response.headers.get("Content-Length")
                downloaded_size = _copy_response(response, output)
            if downloaded_size == 0 or (
                expected_size is not None and downloaded_size != int(expected_size)
            ):
                raise OSError("Incomplete source download")
        partial.replace(destination)
        return destination
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)


def _copy_response(response: BinaryIO, output: BinaryIO) -> int:
    downloaded_size = 0
    while chunk := response.read(CHUNK_SIZE):
        output.write(chunk)
        downloaded_size += len(chunk)
    return downloaded_size
