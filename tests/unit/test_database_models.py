import pytest
from sqlalchemy import BigInteger, Float, Integer, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP

from taxi_pipeline.database.base import Base
from taxi_pipeline.database.engine import get_engine
from taxi_pipeline.database.models import (
    DataQualityResult,
    PipelineRun,
    SourceFile,
    TaxiZone,
    YellowTrip,
)


def test_database_metadata_contains_application_owned_tables():
    assert set(Base.metadata.tables) == {
        "ops.source_files",
        "ops.pipeline_runs",
        "raw.yellow_trips",
        "raw.taxi_zones",
        "ops.data_quality_results",
    }
    assert SourceFile.__table__.schema == "ops"
    assert PipelineRun.__table__.schema == "ops"
    assert YellowTrip.__table__.schema == "raw"
    assert TaxiZone.__table__.schema == "raw"
    assert DataQualityResult.__table__.schema == "ops"


def test_quality_result_has_per_run_check_uniqueness():
    uniques = {
        tuple(column.name for column in constraint.columns)
        for constraint in DataQualityResult.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("run_id", "check_name") in uniques


def test_yellow_trip_preserves_source_names_types_and_nullability():
    table = YellowTrip.__table__
    expected_types = {
        "VendorID": Integer,
        "tpep_pickup_datetime": TIMESTAMP,
        "tpep_dropoff_datetime": TIMESTAMP,
        "passenger_count": BigInteger,
        "trip_distance": Float,
        "RatecodeID": BigInteger,
        "store_and_fwd_flag": Text,
        "PULocationID": Integer,
        "DOLocationID": Integer,
        "payment_type": BigInteger,
        "fare_amount": Float,
        "extra": Float,
        "mta_tax": Float,
        "tip_amount": Float,
        "tolls_amount": Float,
        "improvement_surcharge": Float,
        "total_amount": Float,
        "congestion_surcharge": Float,
        "Airport_fee": Float,
        "cbd_congestion_fee": Float,
    }

    for name, type_ in expected_types.items():
        assert name in table.c
        assert isinstance(table.c[name].type, type_)
        assert table.c[name].nullable

    assert not table.c.tpep_pickup_datetime.type.timezone
    assert not table.c.tpep_dropoff_datetime.type.timezone


@pytest.mark.parametrize("model", [YellowTrip, TaxiZone])
def test_raw_lineage_contract(model):
    table = model.__table__
    assert {column.name for column in table.primary_key.columns} == {
        "_source_file_id",
        "_source_row_number",
    }
    for name in (
        "_source_file_id",
        "_source_row_number",
        "_pipeline_run_id",
        "_ingested_at",
    ):
        assert not table.c[name].nullable
    assert table.c._ingested_at.type.timezone


def test_source_file_version_and_taxi_zone_uniqueness_contracts():
    source_uniques = {
        tuple(column.name for column in constraint.columns)
        for constraint in SourceFile.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    zone_uniques = {
        tuple(column.name for column in constraint.columns)
        for constraint in TaxiZone.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("partition_key", "checksum_sha256") in source_uniques
    assert ("_source_file_id", "LocationID") in zone_uniques
    assert ("LocationID",) not in zone_uniques


def test_get_engine_requires_or_accepts_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        get_engine()

    engine = get_engine("postgresql+psycopg://user:password@localhost/example")
    assert engine.url.database == "example"
    engine.dispose()
