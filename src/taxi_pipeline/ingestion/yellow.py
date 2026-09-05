"""Bounded Yellow Taxi Parquet reading and raw COPY loading."""

from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
from sqlalchemy.orm import Session

from taxi_pipeline.ingestion.copy import copy_rows
from taxi_pipeline.ingestion.models import LoadCounts, RawBatch
from taxi_pipeline.sources.contracts import (
    YELLOW_ADDITIVE_FIELD,
    YELLOW_BASELINE_FIELDS,
    validate_yellow_schema,
)

YELLOW_SOURCE_COLUMNS = (*YELLOW_BASELINE_FIELDS, YELLOW_ADDITIVE_FIELD)
YELLOW_COPY_COLUMNS = (
    *YELLOW_SOURCE_COLUMNS,
    "_source_file_id",
    "_source_row_number",
    "_pipeline_run_id",
    "_ingested_at",
)


def iter_yellow_batches(
    path: Path,
    *,
    source_file_id: int,
    pipeline_run_id: int,
    ingested_at: datetime,
    batch_size: int,
):
    """Yield bounded raw rows with continuous, deterministic 1-based positions."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    parquet = pq.ParquetFile(path)
    validate_yellow_schema(parquet.schema_arrow)
    available_columns = tuple(parquet.schema_arrow.names)
    source_row_number = 1

    for record_batch in parquet.iter_batches(batch_size=batch_size, columns=available_columns):
        values_by_name = {
            name: record_batch.column(index).to_pylist()
            for index, name in enumerate(record_batch.schema.names)
        }
        row_count = record_batch.num_rows
        source_values = [
            values_by_name.get(name, [None] * row_count) for name in YELLOW_SOURCE_COLUMNS
        ]
        rows = tuple(
            (*values, source_file_id, source_row_number + offset, pipeline_run_id, ingested_at)
            for offset, values in enumerate(zip(*source_values, strict=True))
        )
        yield RawBatch(start_row_number=source_row_number, rows=rows)
        source_row_number += row_count


def load_yellow(
    session: Session,
    path: Path,
    *,
    source_file_id: int,
    pipeline_run_id: int,
    ingested_at: datetime,
    batch_size: int,
) -> LoadCounts:
    """COPY one Yellow source into raw.yellow_trips without business cleaning."""
    rows_read = 0
    rows_loaded = 0
    for batch in iter_yellow_batches(
        path,
        source_file_id=source_file_id,
        pipeline_run_id=pipeline_run_id,
        ingested_at=ingested_at,
        batch_size=batch_size,
    ):
        rows_read += batch.row_count
        rows_loaded += copy_rows(
            session,
            schema="raw",
            table="yellow_trips",
            columns=YELLOW_COPY_COLUMNS,
            rows=batch.rows,
        )
    return LoadCounts(rows_read=rows_read, rows_loaded=rows_loaded)
