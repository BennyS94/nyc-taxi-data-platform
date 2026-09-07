from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from taxi_pipeline.api.app import create_app
from taxi_pipeline.api.dependencies import get_db_session
from taxi_pipeline.database.models import DataQualityResult, PipelineRun, SourceFile

pytestmark = pytest.mark.integration


@pytest.fixture
def api_client(db_session):
    source = SourceFile(
        dataset_name="yellow_trips",
        service_type="yellow",
        source_year=2025,
        source_month=1,
        partition_key="yellow/2025/01-api",
        source_url="https://example.test/yellow.parquet",
        landing_path="data/landing/yellow/2025/01.parquet",
        checksum_sha256="a" * 64,
        file_size_bytes=100,
        row_count=2,
        schema_fingerprint="b" * 64,
        status="loaded",
        discovered_at=datetime(2025, 2, 1, tzinfo=UTC),
    )
    db_session.add(source)
    db_session.flush()
    run = PipelineRun(
        dataset_name="yellow_trips",
        service_type="yellow",
        source_year=2025,
        source_month=1,
        source_file_id=source.source_file_id,
        started_at=datetime(2025, 2, 1, tzinfo=UTC),
        finished_at=datetime(2025, 2, 1, 0, 1, tzinfo=UTC),
        status="succeeded",
        rows_read=2,
        rows_loaded=2,
        warning_count=1,
        error_count=0,
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(
        DataQualityResult(
            run_id=run.run_id,
            check_name="pickup_outside_month",
            severity="WARNING",
            status="WARN",
            rows_checked=2,
            rows_failed=1,
            failure_rate=0.5,
            details={"partition": "2025-01"},
            executed_at=datetime(2025, 2, 1, 0, 1, tzinfo=UTC),
        )
    )
    db_session.execute(text("DROP SCHEMA IF EXISTS marts CASCADE"))
    db_session.execute(text("CREATE SCHEMA marts"))
    db_session.execute(
        text(
            """
            CREATE TABLE marts.dim_date (date_key integer PRIMARY KEY, full_date date);
            CREATE TABLE marts.dim_zone (
                zone_key integer PRIMARY KEY,
                location_id integer,
                borough text NOT NULL,
                zone_name text NOT NULL
            );
            CREATE TABLE marts.fct_trips (
                service_type text NOT NULL,
                pickup_date_key integer NOT NULL,
                pickup_zone_key integer NOT NULL,
                trip_distance_miles double precision,
                fare_amount double precision,
                tip_amount double precision,
                total_amount double precision
            );
            INSERT INTO marts.dim_date VALUES
                (20250115, '2025-01-15'), (20250210, '2025-02-10');
            INSERT INTO marts.dim_zone VALUES
                (1, 1, 'Manhattan', 'Alpha'), (2, 2, 'Queens', 'Beta');
            INSERT INTO marts.fct_trips VALUES
                ('yellow', 20250115, 1, 2.0, 10.0, 2.0, 15.0),
                ('yellow', 20250210, 2, 4.0, 20.0, 4.0, 30.0),
                ('green', 20250115, 1, 3.0, 12.0, 1.0, 18.0);
            """
        )
    )
    app = create_app()

    def override_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_session
    yield TestClient(app), source.source_file_id, run.run_id


def test_operational_endpoints_filter_paginate_and_do_not_write(api_client, db_session):
    client, source_file_id, run_id = api_client
    source_count = db_session.scalar(text("SELECT count(*) FROM ops.source_files"))
    run_count = db_session.scalar(text("SELECT count(*) FROM ops.pipeline_runs"))

    sources = client.get("/sources/files?service_type=yellow&year=2025&limit=1").json()
    assert sources["limit"] == 1
    assert sources["items"][0]["source_file_id"] == source_file_id
    assert client.get(f"/sources/files/{source_file_id}").status_code == 200

    runs = client.get(f"/runs?source_file_id={source_file_id}&status=succeeded").json()
    assert runs["items"][0]["run_id"] == run_id
    assert client.get(f"/runs/{run_id}").json()["rows_loaded"] == 2
    quality = client.get(f"/runs/{run_id}/quality?severity=WARNING").json()
    assert quality[0]["rows_failed"] == 1
    assert db_session.scalar(text("SELECT count(*) FROM ops.source_files")) == source_count
    assert db_session.scalar(text("SELECT count(*) FROM ops.pipeline_runs")) == run_count


def test_analytics_endpoints_return_exact_warehouse_aggregates(api_client):
    client, _, _ = api_client
    summary = client.get("/analytics/summary?service_type=yellow").json()
    assert summary == {
        "trip_count": 2,
        "total_amount": 45.0,
        "average_trip_distance_miles": 3.0,
        "average_fare_amount": 15.0,
        "average_tip_amount": 3.0,
    }

    monthly = client.get("/analytics/monthly?end_date=2025-01-31").json()
    assert [(row["month"], row["service_type"], row["trip_count"]) for row in monthly] == [
        ("2025-01-01", "green", 1),
        ("2025-01-01", "yellow", 1),
    ]

    zones = client.get("/analytics/zones?limit=1").json()
    assert zones == [
        {
            "location_id": 1,
            "borough": "Manhattan",
            "zone_name": "Alpha",
            "trip_count": 2,
            "total_amount": 33.0,
        }
    ]
