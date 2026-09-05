import pyarrow as pa

from taxi_pipeline.profiling.schema import compare_schemas, schema_fingerprint


def test_schema_capture_and_fingerprint_is_deterministic():
    schema = pa.schema([pa.field("id", pa.int64(), nullable=False), pa.field("amount", pa.float64())])
    normalized, digest = schema_fingerprint(schema)
    assert normalized[0] == {
        "ordinal_position": 0, "name": "id", "arrow_type": "int64", "nullable": False,
    }
    assert schema_fingerprint(schema) == (normalized, digest)
    assert len(digest) == 64


def test_compare_detects_added_field_and_type_change():
    old = pa.schema([pa.field("id", pa.int32()), pa.field("amount", pa.float64())])
    new = pa.schema([
        pa.field("id", pa.int64()), pa.field("amount", pa.float64()),
        pa.field("cbd_congestion_fee", pa.float64()),
    ])
    comparison = compare_schemas(old, new, "old", "new")
    assert comparison["columns_only_in_yellow_2025_01"] == ["cbd_congestion_fee"]
    assert comparison["type_differences"] == [
        {"name": "id", "yellow_2024_12": "int32", "yellow_2025_01": "int64"}
    ]
    assert comparison["column_order_difference"] is False
    assert comparison["cbd_congestion_fee"] == {
        "yellow_2024_12": False, "yellow_2025_01": True,
    }
