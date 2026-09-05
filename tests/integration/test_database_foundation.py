from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from taxi_pipeline.database.models import PipelineRun, SourceFile, TaxiZone, YellowTrip

pytestmark = pytest.mark.integration


def insert_source_file(connection, partition_key: str, checksum: str) -> int:
    result = connection.execute(
        SourceFile.__table__.insert()
        .values(
            dataset_name="yellow_trips",
            service_type="yellow",
            source_year=2025,
            source_month=1,
            partition_key=partition_key,
            source_url=f"https://example.test/{checksum}.parquet",
            landing_path=f"data/landing/{checksum}.parquet",
            checksum_sha256=checksum,
            file_size_bytes=100,
            status="validated",
        )
        .returning(SourceFile.source_file_id)
    )
    return result.scalar_one()


def insert_run(connection, source_file_id: int) -> int:
    result = connection.execute(
        PipelineRun.__table__.insert()
        .values(
            dataset_name="yellow_trips",
            service_type="yellow",
            source_year=2025,
            source_month=1,
            source_file_id=source_file_id,
            started_at=datetime.now(UTC),
            status="running",
        )
        .returning(PipelineRun.run_id)
    )
    return result.scalar_one()


def lineage_values(source_file_id: int, run_id: int, row_number: int = 1) -> dict:
    return {
        "_source_file_id": source_file_id,
        "_source_row_number": row_number,
        "_pipeline_run_id": run_id,
        "_ingested_at": datetime.now(UTC),
    }


def test_schemas_and_tables_exist(postgres_engine):
    database = inspect(postgres_engine)
    assert {"ops", "raw"}.issubset(database.get_schema_names())
    assert {"source_files", "pipeline_runs"}.issubset(database.get_table_names(schema="ops"))
    assert {"yellow_trips", "taxi_zones"}.issubset(database.get_table_names(schema="raw"))


def test_source_file_version_uniqueness(connection):
    checksum_a = "a" * 64
    insert_source_file(connection, "yellow/2025/01", checksum_a)

    with pytest.raises(IntegrityError), connection.begin_nested():
        insert_source_file(connection, "yellow/2025/01", checksum_a)

    insert_source_file(connection, "yellow/2025/01", "b" * 64)


def test_raw_row_identity_is_scoped_to_source_file(connection):
    source_a = insert_source_file(connection, "yellow/2025/01", "c" * 64)
    source_b = insert_source_file(connection, "yellow/2025/02", "d" * 64)
    run_a = insert_run(connection, source_a)
    run_b = insert_run(connection, source_b)
    connection.execute(YellowTrip.__table__.insert().values(**lineage_values(source_a, run_a)))

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(YellowTrip.__table__.insert().values(**lineage_values(source_a, run_a)))

    connection.execute(YellowTrip.__table__.insert().values(**lineage_values(source_b, run_b)))


def test_raw_yellow_row_preserves_known_anomalies(connection):
    source_file_id = insert_source_file(connection, "yellow/2025/03", "e" * 64)
    run_id = insert_run(connection, source_file_id)

    connection.execute(
        YellowTrip.__table__.insert().values(
            **lineage_values(source_file_id, run_id),
            fare_amount=-5.0,
            trip_distance=0.0,
            passenger_count=None,
        )
    )


def test_taxi_zone_location_uniqueness_is_scoped_to_source_file(connection):
    source_a = insert_source_file(connection, "reference/taxi_zones", "f" * 64)
    source_b = insert_source_file(connection, "reference/taxi_zones", "0" * 64)
    run_a = insert_run(connection, source_a)
    run_b = insert_run(connection, source_b)
    first_zone = {**lineage_values(source_a, run_a), "LocationID": 1}
    connection.execute(TaxiZone.__table__.insert().values(**first_zone))

    duplicate_zone = {**lineage_values(source_a, run_a, row_number=2), "LocationID": 1}
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(TaxiZone.__table__.insert().values(**duplicate_zone))

    revised_zone = {**lineage_values(source_b, run_b), "LocationID": 1}
    connection.execute(TaxiZone.__table__.insert().values(**revised_zone))


def test_raw_foreign_keys_reject_unknown_lineage(connection):
    source_file_id = insert_source_file(connection, "yellow/2025/04", "1" * 64)
    run_id = insert_run(connection, source_file_id)

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            YellowTrip.__table__.insert().values(
                **lineage_values(999_999, run_id),
            )
        )

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            YellowTrip.__table__.insert().values(
                **lineage_values(source_file_id, 999_999),
            )
        )
