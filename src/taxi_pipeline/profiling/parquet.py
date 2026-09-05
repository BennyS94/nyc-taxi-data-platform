"""Profiling orchestration for Yellow Taxi Parquet files."""

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
from taxi_pipeline.sources.tlc import Source, file_identity

DOCUMENTED_COLUMNS = [
    "VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime", "passenger_count",
    "trip_distance", "RatecodeID", "store_and_fwd_flag", "PULocationID", "DOLocationID",
    "payment_type", "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
    "improvement_surcharge", "total_amount", "congestion_surcharge", "Airport_fee",
    "cbd_congestion_fee",
]
DOMAIN_COLUMNS = ["VendorID", "RatecodeID", "store_and_fwd_flag", "payment_type"]
NUMERIC_COLUMNS = [
    "passenger_count", "trip_distance", "fare_amount", "total_amount", "extra", "mta_tax",
    "tip_amount", "tolls_amount", "improvement_surcharge", "congestion_surcharge",
    "Airport_fee", "cbd_congestion_fee",
]


def profile_yellow(source: Source, root: Path, zone_ids: set) -> dict:
    path = root / source.landing_path
    parquet = pq.ParquetFile(path)
    arrow_schema = parquet.schema_arrow
    normalized, fingerprint = schema_fingerprint(arrow_schema)
    metadata = parquet.metadata
    physical_schema = [
        {
            "ordinal_position": index,
            "path": parquet.schema.column(index).path,
            "physical_type": parquet.schema.column(index).physical_type,
            "logical_type": str(parquet.schema.column(index).logical_type),
            "max_definition_level": parquet.schema.column(index).max_definition_level,
            "max_repetition_level": parquet.schema.column(index).max_repetition_level,
        }
        for index in range(len(parquet.schema))
    ]
    columns = []
    for field in normalized:
        array = pq.read_table(path, columns=[field["name"]]).column(0)
        columns.append({**field, **null_summary(array)})
    def read(name):
        return pq.read_table(path, columns=[name]).column(0)
    domains = {name: domain_profile(read(name)) for name in DOMAIN_COLUMNS if name in arrow_schema.names}
    numerics = {name: numeric_profile(read(name)) for name in NUMERIC_COLUMNS if name in arrow_schema.names}
    pickup, dropoff = read("tpep_pickup_datetime"), read("tpep_dropoff_datetime")
    return {
        "file": {
            **file_identity(source, root), "row_count": metadata.num_rows,
            "column_count": metadata.num_columns, "row_group_count": metadata.num_row_groups,
            "created_by": metadata.created_by,
        },
        "schema": {
            "normalized": normalized, "schema_sha256": fingerprint,
            "arrow_schema": arrow_schema.to_string(), "parquet_schema": physical_schema,
            "documented_field_presence": {name: name in arrow_schema.names for name in DOCUMENTED_COLUMNS},
        },
        "columns": columns, "observed_domains": domains, "numeric_distributions": numerics,
        "datetimes": {
            "tpep_pickup_datetime": datetime_profile(pickup),
            "tpep_dropoff_datetime": datetime_profile(dropoff),
            "trip_duration_seconds": duration_profile(pickup, dropoff, source.year, source.month),
        },
        "taxi_zone_references": {
            name: zone_reference_profile(read(name), zone_ids)
            for name in ("PULocationID", "DOLocationID")
        },
        "exact_duplicate_source_rows": exact_duplicate_profile(path),
    }
