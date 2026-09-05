from dataclasses import replace
from datetime import datetime
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from taxi_pipeline.database.models import PipelineRun, SourceFile, TaxiZone, YellowTrip
from taxi_pipeline.ingestion import IngestionError, ingest_source
from taxi_pipeline.ingestion import yellow as yellow_loader
from taxi_pipeline.landing.metadata import inspect_source
from taxi_pipeline.metadata.statuses import RunStatus, SkipReason, SourceStatus
from taxi_pipeline.sources.contracts import (
    YELLOW_ADDITIVE_FIELD,
    YELLOW_BASELINE_FIELDS,
    YELLOW_FIELD_TYPES,
)
from taxi_pipeline.sources.models import SourcePartition

pytestmark = pytest.mark.integration


@pytest.fixture
def source_factory(postgres_engine, tmp_path):
    partitions = []

    def create(source_format: str, path, *, service_type="yellow"):
        token = uuid4().hex
        if source_format == "parquet":
            partition_key = f"yellow/test/{token}"
            dataset_name = "yellow_tripdata"
        else:
            partition_key = f"reference/taxi_zones/{token}"
            dataset_name = "taxi_zone_lookup"
            service_type = None
        partitions.append(partition_key)
        source = SourcePartition(
            dataset_name=dataset_name,
            service_type=service_type,
            year=2025 if service_type else None,
            month=1 if service_type else None,
            partition_key=partition_key,
            source_url=f"https://example.test/{path.name}",
            landing_path=path.name,
            source_format=source_format,
        )
        return inspect_source(source, tmp_path)

    yield create

    with Session(postgres_engine) as session, session.begin():
        source_ids = session.scalars(
            select(SourceFile.source_file_id).where(SourceFile.partition_key.in_(partitions))
        ).all()
        if source_ids:
            session.execute(delete(YellowTrip).where(YellowTrip.source_file_id.in_(source_ids)))
            session.execute(delete(TaxiZone).where(TaxiZone.source_file_id.in_(source_ids)))
            session.execute(delete(PipelineRun).where(PipelineRun.source_file_id.in_(source_ids)))
            session.execute(delete(SourceFile).where(SourceFile.source_file_id.in_(source_ids)))


def write_yellow(path, *, include_cbd: bool, anomaly: bool = False):
    names = list(YELLOW_BASELINE_FIELDS)
    if include_cbd:
        names.append(YELLOW_ADDITIVE_FIELD)
    row_count = 3
    values = {}
    for name in names:
        data_type = YELLOW_FIELD_TYPES[name]
        if pa.types.is_timestamp(data_type):
            values[name] = [
                datetime.fromisoformat("2025-01-02"),
                datetime.fromisoformat("2025-01-03"),
                datetime.fromisoformat("2025-01-04"),
            ]
        elif pa.types.is_string(data_type) or pa.types.is_large_string(data_type):
            values[name] = ["N", "Y", None]
        elif pa.types.is_integer(data_type):
            values[name] = [1, 2, 3]
        else:
            values[name] = [1.0, 2.0, 3.0]
    if anomaly:
        values["fare_amount"] = [-5.0, 2.0, 3.0]
        values["trip_distance"] = [0.0, 2.0, 3.0]
        values["passenger_count"] = [None, 2, 3]
        values["tpep_dropoff_datetime"][0] = datetime.fromisoformat("2025-01-01")

    schema = pa.schema([pa.field(name, YELLOW_FIELD_TYPES[name]) for name in names])
    arrays = [pa.array(values[name], type=YELLOW_FIELD_TYPES[name]) for name in names]
    pq.write_table(pa.Table.from_arrays(arrays, schema=schema), path, row_group_size=2)
    return row_count


def raw_count(session, model, source_file_id):
    return session.scalar(
        select(func.count()).select_from(model).where(model.source_file_id == source_file_id)
    )


@pytest.mark.parametrize("include_cbd", [False, True])
def test_yellow_v1_and_v2_ingestion_persist_values_and_lineage(
    postgres_engine, tmp_path, source_factory, include_cbd
):
    path = tmp_path / f"yellow-{uuid4().hex}.parquet"
    write_yellow(path, include_cbd=include_cbd, anomaly=True)
    metadata = source_factory("parquet", path)

    result = ingest_source(postgres_engine, metadata, tmp_path, batch_size=2)

    with Session(postgres_engine) as session:
        rows = session.scalars(
            select(YellowTrip)
            .where(YellowTrip.source_file_id == result.source_file_id)
            .order_by(YellowTrip.source_row_number)
        ).all()
        run = session.get(PipelineRun, result.run_id)
        source = session.get(SourceFile, result.source_file_id)

    assert result.status is RunStatus.SUCCEEDED
    assert result.rows_read == result.rows_loaded == 3
    assert [row.source_row_number for row in rows] == [1, 2, 3]
    assert all(row.pipeline_run_id == result.run_id for row in rows)
    assert all(row.ingested_at is not None for row in rows)
    assert [row.cbd_congestion_fee for row in rows] == (
        [1.0, 2.0, 3.0] if include_cbd else [None, None, None]
    )
    assert rows[0].fare_amount == -5.0
    assert rows[0].trip_distance == 0.0
    assert rows[0].passenger_count is None
    assert rows[0].dropoff_datetime < rows[0].pickup_datetime
    assert run.status == RunStatus.SUCCEEDED.value
    assert run.rows_read == run.rows_loaded == 3
    assert source.status == SourceStatus.LOADED.value


def test_partial_copy_failure_rolls_back_and_retry_uses_new_run(
    postgres_engine, tmp_path, source_factory, monkeypatch
):
    path = tmp_path / f"yellow-{uuid4().hex}.parquet"
    write_yellow(path, include_cbd=True)
    metadata = source_factory("parquet", path)
    original_copy_rows = yellow_loader.copy_rows
    calls = 0

    def fail_after_first_batch(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("controlled failure after partial COPY")
        return original_copy_rows(*args, **kwargs)

    monkeypatch.setattr(yellow_loader, "copy_rows", fail_after_first_batch)
    with pytest.raises(IngestionError, match="controlled failure"):
        ingest_source(postgres_engine, metadata, tmp_path, batch_size=2)

    with Session(postgres_engine) as session:
        source = session.scalar(
            select(SourceFile).where(SourceFile.partition_key == metadata.partition_key)
        )
        failed_run = session.scalar(
            select(PipelineRun).where(PipelineRun.source_file_id == source.source_file_id)
        )
        assert raw_count(session, YellowTrip, source.source_file_id) == 0
        assert failed_run.status == RunStatus.FAILED.value
        assert source.status == SourceStatus.READY.value

    monkeypatch.setattr(yellow_loader, "copy_rows", original_copy_rows)
    retry = ingest_source(postgres_engine, metadata, tmp_path, batch_size=2)

    with Session(postgres_engine) as session:
        runs = session.scalars(
            select(PipelineRun)
            .where(PipelineRun.source_file_id == retry.source_file_id)
            .order_by(PipelineRun.run_id)
        ).all()
        assert raw_count(session, YellowTrip, retry.source_file_id) == 3
    assert retry.run_id != failed_run.run_id
    assert [run.status for run in runs] == [RunStatus.FAILED.value, RunStatus.SUCCEEDED.value]


def test_already_loaded_yellow_is_skipped_without_duplicate_rows(
    postgres_engine, tmp_path, source_factory
):
    path = tmp_path / f"yellow-{uuid4().hex}.parquet"
    write_yellow(path, include_cbd=False)
    metadata = source_factory("parquet", path)
    first = ingest_source(postgres_engine, metadata, tmp_path, batch_size=2)

    repeated = ingest_source(postgres_engine, metadata, tmp_path, batch_size=2)

    with Session(postgres_engine) as session:
        assert raw_count(session, YellowTrip, first.source_file_id) == 3
        skipped = session.get(PipelineRun, repeated.run_id)
    assert repeated.status is RunStatus.SKIPPED
    assert repeated.status_reason is SkipReason.ALREADY_LOADED
    assert repeated.rows_loaded == 0
    assert skipped.status_reason == SkipReason.ALREADY_LOADED.value


def test_taxi_zones_ingest_with_lineage_and_skip_duplicate_rerun(
    postgres_engine, tmp_path, source_factory
):
    path = tmp_path / f"zones-{uuid4().hex}.csv"
    path.write_text(
        "LocationID,Borough,Zone,service_zone\n1,A,One,Yellow\n2,B,Two,Boro\n",
        encoding="utf-8",
    )
    metadata = source_factory("csv", path)

    first = ingest_source(postgres_engine, metadata, tmp_path, batch_size=1)
    repeated = ingest_source(postgres_engine, metadata, tmp_path, batch_size=1)

    with Session(postgres_engine) as session:
        zones = session.scalars(
            select(TaxiZone)
            .where(TaxiZone.source_file_id == first.source_file_id)
            .order_by(TaxiZone.source_row_number)
        ).all()
        source = session.get(SourceFile, first.source_file_id)
    assert [zone.location_id for zone in zones] == [1, 2]
    assert [zone.source_row_number for zone in zones] == [1, 2]
    assert all(zone.pipeline_run_id == first.run_id for zone in zones)
    assert source.status == SourceStatus.LOADED.value
    assert repeated.status is RunStatus.SKIPPED
    assert repeated.status_reason is SkipReason.ALREADY_LOADED


def test_source_revision_is_skipped_without_touching_raw(
    postgres_engine, tmp_path, source_factory
):
    path = tmp_path / f"yellow-{uuid4().hex}.parquet"
    write_yellow(path, include_cbd=False)
    metadata = source_factory("parquet", path)
    loaded = ingest_source(postgres_engine, metadata, tmp_path, batch_size=2)
    revision = replace(metadata, checksum_sha256="f" * 64)

    blocked = ingest_source(postgres_engine, revision, tmp_path, batch_size=2)

    with Session(postgres_engine) as session:
        assert raw_count(session, YellowTrip, loaded.source_file_id) == 3
        assert raw_count(session, YellowTrip, blocked.source_file_id) == 0
        source = session.get(SourceFile, blocked.source_file_id)
    assert blocked.status is RunStatus.SKIPPED
    assert blocked.status_reason is SkipReason.SOURCE_REVISION_DETECTED
    assert blocked.rows_loaded == 0
    assert source.status == SourceStatus.REVISION_DETECTED.value


def test_row_count_mismatch_rolls_back_raw_and_fails_run(
    postgres_engine, tmp_path, source_factory
):
    path = tmp_path / f"yellow-{uuid4().hex}.parquet"
    write_yellow(path, include_cbd=False)
    metadata = replace(source_factory("parquet", path), row_count=4)

    with pytest.raises(IngestionError, match="Row-count mismatch"):
        ingest_source(postgres_engine, metadata, tmp_path, batch_size=2)

    with Session(postgres_engine) as session:
        source = session.scalar(
            select(SourceFile).where(SourceFile.partition_key == metadata.partition_key)
        )
        run = session.scalar(
            select(PipelineRun).where(PipelineRun.source_file_id == source.source_file_id)
        )
        assert raw_count(session, YellowTrip, source.source_file_id) == 0
    assert source.status == SourceStatus.READY.value
    assert run.status == RunStatus.FAILED.value
