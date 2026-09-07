"""Generate the tiny deterministic source fixtures used by CI and integration tests."""

from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from taxi_pipeline.sources.contracts import (
    GREEN_BASELINE_FIELDS,
    GREEN_FIELD_TYPES,
    YELLOW_ADDITIVE_FIELD,
    YELLOW_BASELINE_FIELDS,
    YELLOW_FIELD_TYPES,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def _source_datetime(value: str) -> datetime:
    """Create a naive timestamp because TLC source timestamps have no timezone."""
    return datetime.fromisoformat(value)


def _yellow_values(include_cbd: bool) -> dict[str, list]:
    values = {
        "VendorID": [1, 2, 99],
        "tpep_pickup_datetime": [
            _source_datetime("2025-01-05T10:00:00"),
            _source_datetime("2025-01-06T11:00:00"),
            _source_datetime("2024-12-31T23:59:00"),
        ],
        "tpep_dropoff_datetime": [
            _source_datetime("2025-01-05T10:15:00"),
            _source_datetime("2025-01-06T10:59:00"),
            _source_datetime("2025-01-01T00:10:00"),
        ],
        "passenger_count": [1, None, 0],
        "trip_distance": [2.0, 0.0, 4.0],
        "RatecodeID": [1, None, 88],
        "store_and_fwd_flag": ["N", None, "X"],
        "PULocationID": [1, 2, 999],
        "DOLocationID": [2, 1, 998],
        "payment_type": [1, 2, 9],
        "fare_amount": [10.0, -2.0, 20.0],
        "extra": [1.0, 0.0, 1.0],
        "mta_tax": [0.5, 0.5, 0.5],
        "tip_amount": [2.0, 0.0, 3.0],
        "tolls_amount": [0.0, 0.0, 0.0],
        "improvement_surcharge": [1.0, 1.0, 1.0],
        "total_amount": [14.5, -0.5, 25.5],
        "congestion_surcharge": [0.0, None, 0.0],
        "Airport_fee": [0.0, None, 0.0],
    }
    if include_cbd:
        values[YELLOW_ADDITIVE_FIELD] = [0.75, None, 0.75]
    return values


def _write_yellow(path: Path, *, include_cbd: bool) -> None:
    fields = list(YELLOW_BASELINE_FIELDS)
    if include_cbd:
        fields.append(YELLOW_ADDITIVE_FIELD)
    values = _yellow_values(include_cbd)
    schema = pa.schema([pa.field(name, YELLOW_FIELD_TYPES[name]) for name in fields])
    arrays = [pa.array(values[name], type=YELLOW_FIELD_TYPES[name]) for name in fields]
    pq.write_table(pa.Table.from_arrays(arrays, schema=schema), path, row_group_size=2)


def _write_green(path: Path) -> None:
    values = {
        "VendorID": [1, 2, 2],
        "lpep_pickup_datetime": [_source_datetime("2025-01-07T09:00:00")] * 3,
        "lpep_dropoff_datetime": [_source_datetime("2025-01-07T09:10:00")] * 3,
        "store_and_fwd_flag": ["N", "Y", "N"],
        "RatecodeID": [1, 1, 1],
        "PULocationID": [1, 2, 999],
        "DOLocationID": [2, 1, 1],
        "passenger_count": [1, 2, 1],
        "trip_distance": [1.0, 0.0, 3.0],
        "fare_amount": [8.0, 9.0, -1.0],
        "extra": [0.0, 0.0, 0.0],
        "mta_tax": [0.5, 0.5, 0.5],
        "tip_amount": [1.0, 2.0, 0.0],
        "tolls_amount": [0.0, 0.0, 0.0],
        "ehail_fee": [None, None, None],
        "improvement_surcharge": [1.0, 1.0, 1.0],
        "total_amount": [10.5, 12.5, 0.5],
        "payment_type": [1, 1, 9],
        "trip_type": [1, 2, 3],
        "congestion_surcharge": [0.0, 0.0, 0.0],
        "cbd_congestion_fee": [0.75, 0.75, 0.75],
    }
    schema = pa.schema(
        [pa.field(name, GREEN_FIELD_TYPES[name]) for name in GREEN_BASELINE_FIELDS]
    )
    arrays = [
        pa.array(values[name], type=GREEN_FIELD_TYPES[name]) for name in GREEN_BASELINE_FIELDS
    ]
    pq.write_table(pa.Table.from_arrays(arrays, schema=schema), path, row_group_size=2)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    _write_yellow(FIXTURES / "yellow_v1.parquet", include_cbd=False)
    _write_yellow(FIXTURES / "yellow_v2.parquet", include_cbd=True)
    _write_green(FIXTURES / "green.parquet")
    (FIXTURES / "taxi_zones.csv").write_text(
        "LocationID,Borough,Zone,service_zone\n"
        "1,Manhattan,Alpha,Yellow Zone\n"
        "2,Queens,Beta,Boro Zone\n",
        encoding="utf-8",
        newline="",
    )


if __name__ == "__main__":
    main()
