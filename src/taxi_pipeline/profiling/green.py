"""Targeted profiling for a Green Taxi Parquet source."""

from pathlib import Path

import pyarrow.parquet as pq

from taxi_pipeline.profiling.schema import schema_fingerprint
from taxi_pipeline.profiling.statistics import (
    datetime_profile,
    domain_profile,
    duration_profile,
    exact_duplicate_profile,
    null_summary,
    numeric_profile,
    zone_reference_profile,
)
from taxi_pipeline.sources.models import SourcePartition
from taxi_pipeline.sources.tlc import file_identity

GREEN_DOCUMENTED_COLUMNS = (
    "VendorID",
    "lpep_pickup_datetime",
    "lpep_dropoff_datetime",
    "store_and_fwd_flag",
    "RatecodeID",
    "PULocationID",
    "DOLocationID",
    "passenger_count",
    "trip_distance",
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "ehail_fee",
    "improvement_surcharge",
    "total_amount",
    "payment_type",
    "trip_type",
    "congestion_surcharge",
    "cbd_congestion_fee",
)
GREEN_DOMAIN_COLUMNS = (
    "VendorID",
    "RatecodeID",
    "store_and_fwd_flag",
    "payment_type",
    "trip_type",
)
GREEN_NUMERIC_COLUMNS = (
    "passenger_count",
    "trip_distance",
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "ehail_fee",
    "improvement_surcharge",
    "total_amount",
    "congestion_surcharge",
    "cbd_congestion_fee",
)


def profile_green(source: SourcePartition, root: Path, zone_ids: set[int]) -> dict:
    """Profile the Green fields relevant to contract and quality decisions."""
    path = root / source.landing_path
    parquet = pq.ParquetFile(path)
    arrow_schema = parquet.schema_arrow
    normalized, fingerprint = schema_fingerprint(arrow_schema)

    def read(name: str):
        return pq.read_table(path, columns=[name]).column(0)

    pickup = read("lpep_pickup_datetime")
    dropoff = read("lpep_dropoff_datetime")
    assert source.year is not None and source.month is not None
    return {
        "file": {
            **file_identity(source, root),
            "row_count": parquet.metadata.num_rows,
            "column_count": parquet.metadata.num_columns,
            "row_group_count": parquet.metadata.num_row_groups,
            "created_by": parquet.metadata.created_by,
        },
        "schema": {
            "normalized": normalized,
            "schema_sha256": fingerprint,
            "arrow_schema": arrow_schema.to_string(),
            "documented_field_presence": {
                name: name in arrow_schema.names for name in GREEN_DOCUMENTED_COLUMNS
            },
        },
        "columns": [
            {**field, **null_summary(read(field["name"]))} for field in normalized
        ],
        "observed_domains": {
            name: domain_profile(read(name))
            for name in GREEN_DOMAIN_COLUMNS
            if name in arrow_schema.names
        },
        "numeric_distributions": {
            name: numeric_profile(read(name))
            for name in GREEN_NUMERIC_COLUMNS
            if name in arrow_schema.names
        },
        "datetimes": {
            "lpep_pickup_datetime": datetime_profile(pickup),
            "lpep_dropoff_datetime": datetime_profile(dropoff),
            "trip_duration_seconds": duration_profile(
                pickup, dropoff, source.year, source.month
            ),
        },
        "taxi_zone_references": {
            name: zone_reference_profile(read(name), zone_ids)
            for name in ("PULocationID", "DOLocationID")
        },
        "exact_duplicate_source_rows": exact_duplicate_profile(path),
    }
