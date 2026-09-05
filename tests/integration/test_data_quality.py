from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select, update

from taxi_pipeline.database.models import (
    DataQualityResult,
    PipelineRun,
    SourceFile,
    TaxiZone,
    YellowTrip,
)
from taxi_pipeline.metadata.statuses import RunStatus, SourceStatus
from taxi_pipeline.quality import (
    QualityEvaluationError,
    QualitySeverity,
    QualityStatus,
    run_quality_checks,
)

pytestmark = pytest.mark.integration


def _source(db_session, *, dataset_name, partition_key, service_type=None, year=None, month=None):
    source = SourceFile(
        dataset_name=dataset_name,
        service_type=service_type,
        source_year=year,
        source_month=month,
        partition_key=partition_key,
        source_url=f"https://example.test/{partition_key}",
        landing_path=f"data/landing/test/{uuid4().hex}",
        checksum_sha256=uuid4().hex * 2,
        file_size_bytes=100,
        row_count=4 if service_type else 1,
        schema_fingerprint="f" * 64 if service_type else None,
        status=SourceStatus.LOADED.value,
        loaded_at=datetime.now(UTC),
    )
    db_session.add(source)
    db_session.flush()
    return source


def _run(db_session, source, *, status=RunStatus.SUCCEEDED):
    run = PipelineRun(
        dataset_name=source.dataset_name,
        service_type=source.service_type,
        source_year=source.source_year,
        source_month=source.source_month,
        source_file_id=source.source_file_id,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        status=status.value,
        rows_read=source.row_count,
        rows_loaded=source.row_count,
        warning_count=0,
        error_count=0,
    )
    db_session.add(run)
    db_session.flush()
    return run


@pytest.fixture
def quality_fixture(db_session):
    token = uuid4().hex
    zone_source = _source(
        db_session,
        dataset_name="taxi_zone_lookup",
        partition_key=f"reference/taxi_zones/{token}",
    )
    zone_run = _run(db_session, zone_source)
    db_session.add(
        TaxiZone(
            source_file_id=zone_source.source_file_id,
            source_row_number=1,
            pipeline_run_id=zone_run.run_id,
            ingested_at=datetime.now(UTC),
            location_id=1,
            borough="Test",
            zone="Known",
            service_zone="Test Zone",
        )
    )

    yellow_source = _source(
        db_session,
        dataset_name="yellow_tripdata",
        partition_key=f"yellow/2025/01/{token}",
        service_type="yellow",
        year=2025,
        month=1,
    )
    yellow_run = _run(db_session, yellow_source)
    common = {
        "vendor_id": 1,
        "pickup_datetime": datetime.fromisoformat("2025-01-10T10:00:00"),
        "dropoff_datetime": datetime.fromisoformat("2025-01-10T10:10:00"),
        "passenger_count": 1,
        "trip_distance": 1.0,
        "rate_code_id": 1,
        "store_and_fwd_flag": "N",
        "pickup_location_id": 1,
        "dropoff_location_id": 1,
        "payment_type": 1,
        "fare_amount": 10.0,
        "extra": 0.0,
        "mta_tax": 0.5,
        "tip_amount": 2.0,
        "tolls_amount": 0.0,
        "improvement_surcharge": 1.0,
        "total_amount": 13.5,
        "congestion_surcharge": 0.0,
        "airport_fee": 0.0,
        "cbd_congestion_fee": 0.75,
    }
    rows = [
        common,
        common,
        {
            **common,
            "vendor_id": 99,
            "pickup_datetime": datetime.fromisoformat("2024-12-31T23:59:00"),
            "dropoff_datetime": datetime.fromisoformat("2024-12-30T23:59:00"),
            "passenger_count": 0,
            "trip_distance": 0.0,
            "rate_code_id": 88,
            "store_and_fwd_flag": "X",
            "pickup_location_id": 999,
            "dropoff_location_id": 888,
            "payment_type": 9,
            "fare_amount": -5.0,
        },
        {
            **common,
            "passenger_count": None,
            "rate_code_id": None,
            "store_and_fwd_flag": None,
            "congestion_surcharge": None,
            "airport_fee": None,
        },
    ]
    for row_number, values in enumerate(rows, start=1):
        db_session.add(
            YellowTrip(
                source_file_id=yellow_source.source_file_id,
                source_row_number=row_number,
                pipeline_run_id=yellow_run.run_id,
                ingested_at=datetime.now(UTC),
                **values,
            )
        )
    db_session.flush()
    return yellow_run, yellow_source


def _results_by_name(db_session, run_id):
    return {
        result.check_name: result
        for result in db_session.scalars(
            select(DataQualityResult).where(DataQualityResult.run_id == run_id)
        )
    }


def test_quality_table_exists(postgres_engine):
    assert "data_quality_results" in inspect(postgres_engine).get_table_names(schema="ops")


def test_quality_evaluation_persists_rules_details_and_run_counters(
    db_session, quality_fixture
):
    run, _ = quality_fixture

    summary = run_quality_checks(db_session, run.run_id)
    results = _results_by_name(db_session, run.run_id)

    assert summary.rows_checked == 4
    assert summary.check_count == 27
    assert len(results) == 27
    assert results["negative_tip_amount"].status == QualityStatus.PASSED.value
    assert results["negative_tip_amount"].rows_failed == 0
    assert results["negative_fare_amount"].severity == QualitySeverity.WARNING.value
    assert results["negative_fare_amount"].status == QualityStatus.VIOLATED.value
    assert results["negative_fare_amount"].rows_failed == 1
    assert results["zero_trip_distance"].severity == QualitySeverity.INFO.value
    assert results["zero_trip_distance"].rows_failed == 1
    assert results["passenger_count_null_rate"].rows_failed == 1
    assert results["unexpected_vendor_id"].details == {
        "unexpected_values": [{"value": 99, "count": 1}]
    }
    assert results["unknown_pickup_zone"].rows_failed == 1
    assert results["unknown_dropoff_zone"].rows_failed == 1
    duplicate = results["exact_duplicate_source_rows"]
    assert duplicate.rows_failed == 2
    assert duplicate.details == {"duplicate_excess_rows": 1, "duplicate_groups": 1}
    assert run.status == RunStatus.SUCCEEDED.value
    assert run.warning_count == summary.warnings_violated == 10
    assert run.error_count == summary.errors_violated == 0


def test_quality_rerun_upserts_same_check_rows(db_session, quality_fixture):
    run, _ = quality_fixture
    first = run_quality_checks(db_session, run.run_id)
    original_ids = {
        result.check_name: result.quality_result_id
        for result in db_session.scalars(
            select(DataQualityResult).where(DataQualityResult.run_id == run.run_id)
        )
    }

    second = run_quality_checks(db_session, run.run_id)
    repeated_ids = {
        result.check_name: result.quality_result_id
        for result in db_session.scalars(
            select(DataQualityResult).where(DataQualityResult.run_id == run.run_id)
        )
    }

    assert second == first
    assert repeated_ids == original_ids
    assert db_session.scalar(
        select(func.count())
        .select_from(DataQualityResult)
        .where(DataQualityResult.run_id == run.run_id)
    ) == 27


def test_invalid_target_run_is_rejected(db_session, quality_fixture):
    run, _ = quality_fixture
    run.status = RunStatus.FAILED.value
    db_session.flush()

    with pytest.raises(QualityEvaluationError, match="quality requires succeeded"):
        run_quality_checks(db_session, run.run_id)


def test_missing_loaded_taxi_zones_is_rejected(db_session, quality_fixture):
    run, _ = quality_fixture
    db_session.execute(
        update(SourceFile)
        .where(SourceFile.dataset_name == "taxi_zone_lookup")
        .values(status=SourceStatus.READY.value)
    )

    with pytest.raises(QualityEvaluationError, match="No loaded Taxi Zone"):
        run_quality_checks(db_session, run.run_id)
