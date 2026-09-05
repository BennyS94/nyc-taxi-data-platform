"""Explicit structural contracts for currently supported TLC sources."""

from pathlib import Path

import pandas as pd
import pyarrow as pa

YELLOW_BASELINE_FIELDS = (
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "RatecodeID",
    "store_and_fwd_flag",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "improvement_surcharge",
    "total_amount",
    "congestion_surcharge",
    "Airport_fee",
)
YELLOW_ADDITIVE_FIELD = "cbd_congestion_fee"
YELLOW_FIELD_TYPES = {
    "VendorID": pa.int32(),
    "tpep_pickup_datetime": pa.timestamp("us"),
    "tpep_dropoff_datetime": pa.timestamp("us"),
    "passenger_count": pa.int64(),
    "trip_distance": pa.float64(),
    "RatecodeID": pa.int64(),
    "store_and_fwd_flag": pa.large_string(),
    "PULocationID": pa.int32(),
    "DOLocationID": pa.int32(),
    "payment_type": pa.int64(),
    "fare_amount": pa.float64(),
    "extra": pa.float64(),
    "mta_tax": pa.float64(),
    "tip_amount": pa.float64(),
    "tolls_amount": pa.float64(),
    "improvement_surcharge": pa.float64(),
    "total_amount": pa.float64(),
    "congestion_surcharge": pa.float64(),
    "Airport_fee": pa.float64(),
    "cbd_congestion_fee": pa.float64(),
}
TAXI_ZONE_REQUIRED_FIELDS = ("LocationID", "Borough", "Zone", "service_zone")


class SourceContractError(ValueError):
    """A source file does not match a supported structural contract."""


def validate_yellow_schema(schema: pa.Schema) -> str:
    """Validate and identify one of the two frozen Yellow schema versions."""
    missing = [name for name in YELLOW_BASELINE_FIELDS if name not in schema.names]
    if missing:
        raise SourceContractError(f"Missing baseline Yellow fields: {', '.join(missing)}")

    allowed = {*YELLOW_BASELINE_FIELDS, YELLOW_ADDITIVE_FIELD}
    unknown = [name for name in schema.names if name not in allowed]
    if unknown:
        raise SourceContractError(f"Unsupported Yellow fields: {', '.join(unknown)}")

    expected_names = list(YELLOW_BASELINE_FIELDS)
    schema_version = "yellow_v1"
    if YELLOW_ADDITIVE_FIELD in schema.names:
        expected_names.append(YELLOW_ADDITIVE_FIELD)
        schema_version = "yellow_v2"
    if schema.names != expected_names:
        raise SourceContractError("Unsupported Yellow source column order")

    for field in schema:
        expected_type = YELLOW_FIELD_TYPES[field.name]
        if field.type != expected_type:
            raise SourceContractError(
                f"Unsupported type for {field.name}: expected {expected_type}, got {field.type}"
            )
        if not field.nullable:
            raise SourceContractError(f"Unsupported nullability for {field.name}: expected nullable")
    return schema_version


def validate_taxi_zones(path: Path) -> int:
    """Validate required Taxi Zone columns and per-file LocationID identity."""
    frame = pd.read_csv(path)
    missing = [name for name in TAXI_ZONE_REQUIRED_FIELDS if name not in frame.columns]
    if missing:
        raise SourceContractError(f"Missing Taxi Zone fields: {', '.join(missing)}")
    if frame.empty:
        raise SourceContractError("Taxi Zone source is empty")
    if frame["LocationID"].isna().any():
        raise SourceContractError("Taxi Zone LocationID contains null values")
    if frame["LocationID"].duplicated().any():
        raise SourceContractError("Taxi Zone LocationID contains duplicate values")
    return len(frame)
