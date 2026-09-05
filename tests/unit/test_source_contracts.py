from dataclasses import replace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from taxi_pipeline.landing.metadata import inspect_source
from taxi_pipeline.profiling.schema import schema_fingerprint
from taxi_pipeline.sources.contracts import (
    TAXI_ZONE_REQUIRED_FIELDS,
    YELLOW_ADDITIVE_FIELD,
    YELLOW_BASELINE_FIELDS,
    YELLOW_FIELD_TYPES,
    SourceContractError,
    validate_taxi_zones,
    validate_yellow_schema,
)
from taxi_pipeline.sources.tlc import taxi_zone_source, yellow_trip_source


def yellow_schema(*, version: int = 1, missing: str | None = None) -> pa.Schema:
    names = [name for name in YELLOW_BASELINE_FIELDS if name != missing]
    if version == 2:
        names.append(YELLOW_ADDITIVE_FIELD)
    return pa.schema([pa.field(name, YELLOW_FIELD_TYPES[name]) for name in names])


def write_yellow(path, schema: pa.Schema, rows: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = [pa.array([None] * rows, type=field.type) for field in schema]
    pq.write_table(pa.Table.from_arrays(arrays, schema=schema), path)


@pytest.mark.parametrize(("version", "expected"), [(1, "yellow_v1"), (2, "yellow_v2")])
def test_supported_yellow_schema_versions(version, expected):
    assert validate_yellow_schema(yellow_schema(version=version)) == expected


def test_missing_yellow_baseline_field_is_rejected():
    with pytest.raises(SourceContractError, match="fare_amount"):
        validate_yellow_schema(yellow_schema(missing="fare_amount"))


def test_unknown_yellow_field_is_rejected():
    schema = yellow_schema().append(pa.field("unexpected_new_field", pa.int64()))
    with pytest.raises(SourceContractError, match="unexpected_new_field"):
        validate_yellow_schema(schema)


def test_yellow_type_change_is_rejected():
    fields = [
        pa.field(field.name, pa.string() if field.name == "fare_amount" else field.type)
        for field in yellow_schema()
    ]
    with pytest.raises(SourceContractError, match="Unsupported type for fare_amount"):
        validate_yellow_schema(pa.schema(fields))


def test_yellow_metadata_is_stable_and_portable(tmp_path):
    source = yellow_trip_source(2025, 1)
    path = tmp_path / source.landing_path
    schema = yellow_schema(version=2)
    write_yellow(path, schema, rows=3)

    first = inspect_source(source, tmp_path)
    second = inspect_source(source, tmp_path)
    _, expected_fingerprint = schema_fingerprint(pq.ParquetFile(path).schema_arrow)

    assert first == second
    assert first.row_count == 3
    assert first.file_size_bytes == path.stat().st_size
    assert len(first.checksum_sha256) == 64
    assert first.schema_fingerprint == expected_fingerprint
    assert first.schema_version == "yellow_v2"
    assert first.landing_path == "data/landing/yellow/2025/01.parquet"
    assert str(tmp_path) not in first.landing_path


def write_zones(tmp_path, content: str):
    path = tmp_path / taxi_zone_source().landing_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_valid_taxi_zones_allow_null_descriptions(tmp_path):
    path = write_zones(
        tmp_path,
        "LocationID,Borough,Zone,service_zone\n1,,First,\n2,Queens,Second,Boro Zone\n",
    )
    assert validate_taxi_zones(path) == 2

    metadata = inspect_source(taxi_zone_source(), tmp_path)
    assert metadata.row_count == 2
    assert metadata.schema_fingerprint is None
    assert metadata.schema_version is None


@pytest.mark.parametrize("missing", TAXI_ZONE_REQUIRED_FIELDS)
def test_missing_taxi_zone_field_is_rejected(tmp_path, missing):
    fields = [field for field in TAXI_ZONE_REQUIRED_FIELDS if field != missing]
    path = write_zones(tmp_path, ",".join(fields) + "\n" + ",".join("x" for _ in fields))
    with pytest.raises(SourceContractError, match="Missing Taxi Zone fields"):
        validate_taxi_zones(path)


@pytest.mark.parametrize(
    ("rows", "message"),
    [(",Borough,Zone,Service\n", "null"), ("1,Borough,Zone,Service\n1,B,Z,S\n", "duplicate")],
)
def test_invalid_taxi_zone_location_ids_are_rejected(tmp_path, rows, message):
    path = write_zones(tmp_path, "LocationID,Borough,Zone,service_zone\n" + rows)
    with pytest.raises(SourceContractError, match=message):
        validate_taxi_zones(path)


def test_inspection_rejects_unknown_source_format(tmp_path):
    source = replace(taxi_zone_source(), source_format="json")
    path = tmp_path / source.landing_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported source format"):
        inspect_source(source, tmp_path)
