"""Small HTTP client for the read-only FastAPI interface."""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class APIClientError(RuntimeError):
    """A dashboard-safe API request failure."""


class APIUnavailableError(APIClientError):
    """The configured API could not be reached."""


class APIResponseError(APIClientError):
    """The API returned an unsuccessful or invalid response."""


class APIClient:
    """Centralized client for dashboard GET requests."""

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, **params: Any) -> Any:
        query = urlencode(
            {
                key: value.isoformat() if isinstance(value, date) else value
                for key, value in params.items()
                if value is not None
            }
        )
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except HTTPError as error:
            detail = _error_detail(error)
            raise APIResponseError(f"API request failed ({error.code}): {detail}") from error
        except (TimeoutError, URLError) as error:
            raise APIUnavailableError("API unavailable. Start FastAPI and try again.") from error

        try:
            return json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise APIResponseError("API returned an invalid JSON response.") from error

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def list_sources(self, **params: Any) -> dict[str, Any]:
        return self._get("/sources/files", **params)

    def list_all_sources(self, **params: Any) -> list[dict[str, Any]]:
        return self._all_pages("/sources/files", **params)

    def get_source(self, source_file_id: int) -> dict[str, Any]:
        return self._get(f"/sources/files/{source_file_id}")

    def list_runs(self, **params: Any) -> dict[str, Any]:
        return self._get("/runs", **params)

    def list_all_runs(self, **params: Any) -> list[dict[str, Any]]:
        return self._all_pages("/runs", **params)

    def get_run(self, run_id: int) -> dict[str, Any]:
        return self._get(f"/runs/{run_id}")

    def get_run_quality(self, run_id: int, **params: Any) -> list[dict[str, Any]]:
        return self._get(f"/runs/{run_id}/quality", **params)

    def analytics_summary(self, **params: Any) -> dict[str, Any]:
        return self._get("/analytics/summary", **params)

    def analytics_monthly(self, **params: Any) -> list[dict[str, Any]]:
        return self._get("/analytics/monthly", **params)

    def analytics_zones(self, **params: Any) -> list[dict[str, Any]]:
        return self._get("/analytics/zones", **params)

    def _all_pages(self, path: str, **params: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._get(path, **params, limit=100, offset=offset)
            page_items = page["items"]
            items.extend(page_items)
            if len(page_items) < 100:
                return items
            offset += 100


def _error_detail(error: HTTPError) -> str:
    try:
        payload = json.loads(error.read())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return error.reason or "request failed"
    detail = payload.get("detail") if isinstance(payload, dict) else None
    return str(detail or error.reason or "request failed")
