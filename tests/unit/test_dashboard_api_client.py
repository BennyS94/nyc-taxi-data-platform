from datetime import date
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from taxi_pipeline.dashboard import api_client
from taxi_pipeline.dashboard.api_client import (
    APIClient,
    APIResponseError,
    APIUnavailableError,
)


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return self.payload


def test_analytics_request_uses_configured_url_filters_and_timeout(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _Response(b'{"trip_count": 4}')

    monkeypatch.setattr(api_client, "urlopen", fake_urlopen)

    result = APIClient("http://api.example/", timeout=2.5).analytics_summary(
        service_type="yellow", start_date=date(2025, 1, 1), end_date=None
    )

    assert result == {"trip_count": 4}
    assert captured == {
        "url": "http://api.example/analytics/summary?service_type=yellow&start_date=2025-01-01",
        "timeout": 2.5,
    }


def test_paginated_source_request_reads_every_page(monkeypatch):
    offsets = []

    def fake_get(self, path, **params):
        offsets.append(params["offset"])
        count = 100 if params["offset"] == 0 else 2
        return {"items": [{"source_file_id": index} for index in range(count)]}

    monkeypatch.setattr(APIClient, "_get", fake_get)

    items = APIClient("http://api.example").list_all_sources(service_type="green")

    assert len(items) == 102
    assert offsets == [0, 100]


def test_unavailable_api_has_concise_dashboard_message(monkeypatch):
    def unavailable(*args, **kwargs):
        raise URLError("refused")

    monkeypatch.setattr(api_client, "urlopen", unavailable)

    with pytest.raises(APIUnavailableError, match="Start FastAPI"):
        APIClient("http://api.example").health()


def test_api_error_uses_fastapi_detail(monkeypatch):
    def invalid(*args, **kwargs):
        raise HTTPError(
            "http://api.example/runs/1",
            422,
            "Unprocessable Entity",
            {},
            BytesIO(b'{"detail":"invalid selection"}'),
        )

    monkeypatch.setattr(api_client, "urlopen", invalid)

    with pytest.raises(APIResponseError, match="invalid selection"):
        APIClient("http://api.example").get_run(1)
