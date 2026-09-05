from datetime import UTC, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from taxi_pipeline.ingestion.taxi_zones import iter_taxi_zone_batches
from taxi_pipeline.ingestion.yellow import iter_yellow_batches
from taxi_pipeline.sources.contracts import (
    YELLOW_ADDITIVE_FIELD,
    YELLOW_BASELINE_FIELDS,
    YELLOW_FIELD_TYPES,
)


def write_yellow(path, *, include_cbd: bool, rows: int = 3):
    names = list(YELLOW_BASELINE_FIELDS)
    if include_cbd:
        names.append(YELLOW_ADDITIVE_FIELD)
    arrays = []
    for name in names:
        data_type = YELLOW_FIELD_TYPES[name]
        if pa.types.is_timestamp(data_type):
            values = [datetime.fromisoformat(f"2025-01-{index + 1:02d}") for index in range(rows)]
        elif pa.types.is_string(data_type) or pa.types.is_large_string(data_type):
            values = ["N"] * rows
        elif pa.types.is_integer(data_type):
            values = list(range(1, rows + 1))
        else:
            values = [float(index) for index in range(rows)]
        arrays.append(pa.array(values, type=data_type))
    schema = pa.schema([pa.field(name, YELLOW_FIELD_TYPES[name]) for name in names])
    pq.write_table(pa.Table.from_arrays(arrays, schema=schema), path)


@pytest.mark.parametrize("include_cbd", [False, True])
def test_yellow_batches_keep_continuous_lineage_and_schema_values(tmp_path, include_cbd):
    path = tmp_path / "yellow.parquet"
    write_yellow(path, include_cbd=include_cbd)
    ingested_at = datetime.now(UTC)

    batches = list(
        iter_yellow_batches(
            path,
            source_file_id=7,
            pipeline_run_id=11,
            ingested_at=ingested_at,
            batch_size=2,
        )
    )

    assert [batch.start_row_number for batch in batches] == [1, 3]
    assert [batch.row_count for batch in batches] == [2, 1]
    rows = [row for batch in batches for row in batch.rows]
    assert [row[21] for row in rows] == [1, 2, 3]
    assert all(row[20] == 7 and row[22] == 11 and row[23] == ingested_at for row in rows)
    assert [row[19] for row in rows] == ([0.0, 1.0, 2.0] if include_cbd else [None] * 3)


def test_yellow_batch_size_must_be_positive(tmp_path):
    path = tmp_path / "yellow.parquet"
    write_yellow(path, include_cbd=False)

    with pytest.raises(ValueError, match="positive"):
        next(
            iter_yellow_batches(
                path,
                source_file_id=1,
                pipeline_run_id=1,
                ingested_at=datetime.now(UTC),
                batch_size=0,
            )
        )


def test_taxi_zone_batches_follow_csv_order(tmp_path):
    path = tmp_path / "zones.csv"
    path.write_text(
        "LocationID,Borough,Zone,service_zone\n1,A,One,Yellow\n2,B,Two,Boro\n3,C,Three,Boro\n",
        encoding="utf-8",
    )

    batches = list(
        iter_taxi_zone_batches(
            path,
            source_file_id=5,
            pipeline_run_id=8,
            ingested_at=datetime.now(UTC),
            batch_size=2,
        )
    )

    assert [batch.start_row_number for batch in batches] == [1, 3]
    rows = [row for batch in batches for row in batch.rows]
    assert [row[0] for row in rows] == [1, 2, 3]
    assert [row[5] for row in rows] == [1, 2, 3]
