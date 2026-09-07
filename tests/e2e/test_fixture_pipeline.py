"""Small cross-layer smoke path over deterministic local source fixtures."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from taxi_pipeline.api.app import create_app
from taxi_pipeline.database.models import DataQualityResult, GreenTrip, SourceFile, YellowTrip
from taxi_pipeline.ingestion import ingest_source
from taxi_pipeline.landing.metadata import inspect_source
from taxi_pipeline.metadata.statuses import RunStatus, SkipReason
from taxi_pipeline.quality import run_quality_checks
from taxi_pipeline.sources.models import SourcePartition

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"


def _metadata(filename: str, dataset: str, service: str | None):
    partition = f"{service}/2025/01" if service else "reference/taxi_zones"
    source = SourcePartition(
        dataset_name=dataset,
        service_type=service,
        year=2025 if service else None,
        month=1 if service else None,
        partition_key=partition,
        source_url=f"https://fixtures.invalid/{filename}",
        landing_path=filename,
        source_format="parquet" if filename.endswith(".parquet") else "csv",
    )
    return inspect_source(source, FIXTURES)


def test_fixture_pipeline_from_source_to_api(postgres_engine):
    zones = ingest_source(
        postgres_engine,
        _metadata("taxi_zones.csv", "taxi_zone_lookup", None),
        FIXTURES,
        batch_size=2,
    )
    yellow_metadata = _metadata("yellow_v2.parquet", "yellow_tripdata", "yellow")
    yellow = ingest_source(postgres_engine, yellow_metadata, FIXTURES, batch_size=2)
    green = ingest_source(
        postgres_engine,
        _metadata("green.parquet", "green_tripdata", "green"),
        FIXTURES,
        batch_size=2,
    )
    repeated = ingest_source(postgres_engine, yellow_metadata, FIXTURES, batch_size=2)

    assert zones.status is yellow.status is green.status is RunStatus.SUCCEEDED
    assert repeated.status is RunStatus.SKIPPED
    assert repeated.status_reason is SkipReason.ALREADY_LOADED

    with Session(postgres_engine) as session, session.begin():
        yellow_quality = run_quality_checks(session, yellow.run_id)
        green_quality = run_quality_checks(session, green.run_id)
    assert yellow_quality.check_count > 0
    assert green_quality.check_count > 0

    subprocess.run(
        [sys.executable, "-m", "dbt.cli.main", "build", "--profiles-dir", "."],
        cwd=ROOT / "dbt" / "taxi_analytics",
        env=os.environ.copy(),
        check=True,
    )

    with Session(postgres_engine) as session:
        assert session.scalar(select(func.count()).select_from(YellowTrip)) == 3
        assert session.scalar(select(func.count()).select_from(GreenTrip)) == 3
        assert session.scalar(select(func.count()).select_from(DataQualityResult)) > 0
        assert session.scalar(select(func.count()).select_from(SourceFile)) == 3
        fact_count = session.scalar(select(func.count()).select_from(_fact_table(session)))
        unique_lineage = session.execute(
            _lineage_count_statement()
        ).one()
    assert fact_count == 6
    assert unique_lineage == (6, 6)

    response = TestClient(create_app()).get("/analytics/summary")
    assert response.status_code == 200
    assert response.json()["trip_count"] == 6


def _fact_table(session: Session):
    from sqlalchemy import MetaData, Table

    return Table("fct_trips", MetaData(), schema="marts", autoload_with=session.connection())


def _lineage_count_statement():
    from sqlalchemy import text

    return text(
        """
        SELECT count(*)::integer,
               count(DISTINCT (source_file_id, source_row_number))::integer
        FROM marts.fct_trips
        """
    )
