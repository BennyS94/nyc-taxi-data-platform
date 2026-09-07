from unittest.mock import Mock

from fastapi.testclient import TestClient

from taxi_pipeline.api.app import create_app
from taxi_pipeline.api.dependencies import get_db_session


def client_with_session(session: Mock) -> TestClient:
    app = create_app()

    def override_session():
        yield session

    app.dependency_overrides[get_db_session] = override_session
    return TestClient(app)


def test_health_reports_database_connection():
    client = client_with_session(Mock())
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_invalid_operational_pagination_returns_422():
    client = client_with_session(Mock())
    assert client.get("/sources/files?limit=101").status_code == 422
    assert client.get("/runs?offset=-1").status_code == 422


def test_invalid_service_type_returns_422():
    client = client_with_session(Mock())
    assert client.get("/analytics/summary?service_type=blue").status_code == 422


def test_invalid_date_range_returns_422():
    client = client_with_session(Mock())
    response = client.get("/analytics/monthly?start_date=2025-02-01&end_date=2025-01-01")
    assert response.status_code == 422
    assert response.json()["detail"] == "start_date must be on or before end_date"


def test_missing_operational_resources_return_404():
    session = Mock()
    session.get.return_value = None
    client = client_with_session(session)
    assert client.get("/sources/files/999").status_code == 404
    assert client.get("/runs/999").status_code == 404
    assert client.get("/runs/999/quality").status_code == 404


def test_openapi_documents_typed_routes():
    schema = client_with_session(Mock()).get("/openapi.json").json()
    expected_paths = {
        "/health",
        "/sources/files",
        "/sources/files/{source_file_id}",
        "/runs",
        "/runs/{run_id}",
        "/runs/{run_id}/quality",
        "/analytics/summary",
        "/analytics/monthly",
        "/analytics/zones",
    }
    assert expected_paths.issubset(schema["paths"])
