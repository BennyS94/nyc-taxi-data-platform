import io

import pytest

from taxi_pipeline.landing.downloader import ensure_local
from taxi_pipeline.landing.metadata import file_sha256
from taxi_pipeline.sources.tlc import taxi_zone_source


class InspectingResponse(io.BytesIO):
    def __init__(self, content, destination):
        super().__init__(content)
        self.headers = {"Content-Length": str(len(content))}
        self.destination = destination
        self.saw_partial = False

    def read(self, size=-1):
        self.saw_partial = self.saw_partial or bool(
            list(self.destination.parent.glob(f"{self.destination.name}.*.part"))
        )
        assert not self.destination.exists()
        return super().read(size)


def test_download_uses_partial_then_atomically_creates_final_file(tmp_path):
    source = taxi_zone_source()
    destination = tmp_path / source.landing_path
    response = InspectingResponse(b"complete source", destination)

    result = ensure_local(source, tmp_path, opener=lambda *args, **kwargs: response)

    assert result == destination.resolve()
    assert result.read_bytes() == b"complete source"
    assert response.saw_partial
    assert not list(destination.parent.glob("*.part"))


def test_failed_download_removes_partial_and_propagates_error(tmp_path):
    source = taxi_zone_source()
    response = io.BytesIO(b"short")
    response.headers = {"Content-Length": "100"}

    with pytest.raises(OSError, match="Incomplete source download"):
        ensure_local(source, tmp_path, opener=lambda *args, **kwargs: response)

    destination = tmp_path / source.landing_path
    assert not destination.exists()
    assert not list(destination.parent.glob("*.part"))


def test_existing_file_is_reused_without_remote_access(tmp_path):
    source = taxi_zone_source()
    destination = tmp_path / source.landing_path
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"existing")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("remote access should not occur")

    assert ensure_local(source, tmp_path, opener=fail_if_called) == destination.resolve()
    assert destination.read_bytes() == b"existing"


def test_file_sha256_is_stable_and_streamed(tmp_path):
    path = tmp_path / "source.bin"
    content = b"source content" * 100
    path.write_bytes(content)

    first = file_sha256(path)
    second = file_sha256(path)

    assert first == second
    assert len(first) == 64
