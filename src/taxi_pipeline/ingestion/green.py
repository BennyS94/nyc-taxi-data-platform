"""Bounded Green Taxi Parquet reading and raw COPY loading."""

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from taxi_pipeline.ingestion.copy import copy_rows
from taxi_pipeline.ingestion.models import LoadCounts
from taxi_pipeline.ingestion.parquet import iter_parquet_batches
from taxi_pipeline.sources.contracts import GREEN_BASELINE_FIELDS, validate_green_schema

GREEN_SOURCE_COLUMNS = GREEN_BASELINE_FIELDS
GREEN_COPY_COLUMNS = (
    *GREEN_SOURCE_COLUMNS,
    "_source_file_id",
    "_source_row_number",
    "_pipeline_run_id",
    "_ingested_at",
)


def iter_green_batches(
    path: Path,
    *,
    source_file_id: int,
    pipeline_run_id: int,
    ingested_at: datetime,
    batch_size: int,
):
    """Yield Green raw rows through the shared Parquet batching path."""
    yield from iter_parquet_batches(
        path,
        source_columns=GREEN_SOURCE_COLUMNS,
        validate_schema=validate_green_schema,
        source_file_id=source_file_id,
        pipeline_run_id=pipeline_run_id,
        ingested_at=ingested_at,
        batch_size=batch_size,
    )


def load_green(
    session: Session,
    path: Path,
    *,
    source_file_id: int,
    pipeline_run_id: int,
    ingested_at: datetime,
    batch_size: int,
) -> LoadCounts:
    """COPY one Green source into raw.green_trips without business cleaning."""
    rows_read = 0
    rows_loaded = 0
    for batch in iter_green_batches(
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
            table="green_trips",
            columns=GREEN_COPY_COLUMNS,
            rows=batch.rows,
        )
    return LoadCounts(rows_read=rows_read, rows_loaded=rows_loaded)
