"""Shared bounded Parquet-to-raw batch conversion."""

from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from taxi_pipeline.ingestion.models import RawBatch


def iter_parquet_batches(
    path: Path,
    *,
    source_columns: tuple[str, ...],
    validate_schema: Callable[[pa.Schema], str],
    source_file_id: int,
    pipeline_run_id: int,
    ingested_at: datetime,
    batch_size: int,
) -> Iterator[RawBatch]:
    """Yield source-ordered rows with deterministic 1-based technical lineage."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    parquet = pq.ParquetFile(path)
    validate_schema(parquet.schema_arrow)
    available_columns = tuple(parquet.schema_arrow.names)
    source_row_number = 1

    for record_batch in parquet.iter_batches(batch_size=batch_size, columns=available_columns):
        values_by_name = {
            name: record_batch.column(index).to_pylist()
            for index, name in enumerate(record_batch.schema.names)
        }
        row_count = record_batch.num_rows
        source_values = [
            values_by_name.get(name, [None] * row_count) for name in source_columns
        ]
        rows = tuple(
            (*values, source_file_id, source_row_number + offset, pipeline_run_id, ingested_at)
            for offset, values in enumerate(zip(*source_values, strict=True))
        )
        yield RawBatch(start_row_number=source_row_number, rows=rows)
        source_row_number += row_count
