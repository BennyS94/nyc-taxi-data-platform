"""Taxi Zone CSV raw COPY loading."""

import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from taxi_pipeline.ingestion.copy import copy_rows
from taxi_pipeline.ingestion.models import LoadCounts, RawBatch
from taxi_pipeline.sources.contracts import TAXI_ZONE_REQUIRED_FIELDS

TAXI_ZONE_COPY_COLUMNS = (
    *TAXI_ZONE_REQUIRED_FIELDS,
    "_source_file_id",
    "_source_row_number",
    "_pipeline_run_id",
    "_ingested_at",
)


def iter_taxi_zone_batches(
    path: Path,
    *,
    source_file_id: int,
    pipeline_run_id: int,
    ingested_at: datetime,
    batch_size: int,
):
    """Yield Taxi Zone rows in source order with deterministic lineage."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    source_row_number = 1
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        batch_rows: list[tuple] = []
        for source_row in reader:
            batch_rows.append(
                (
                    int(source_row["LocationID"]),
                    source_row["Borough"],
                    source_row["Zone"],
                    source_row["service_zone"],
                    source_file_id,
                    source_row_number,
                    pipeline_run_id,
                    ingested_at,
                )
            )
            source_row_number += 1
            if len(batch_rows) == batch_size:
                start = source_row_number - len(batch_rows)
                yield RawBatch(start_row_number=start, rows=tuple(batch_rows))
                batch_rows = []

        if batch_rows:
            start = source_row_number - len(batch_rows)
            yield RawBatch(start_row_number=start, rows=tuple(batch_rows))


def load_taxi_zones(
    session: Session,
    path: Path,
    *,
    source_file_id: int,
    pipeline_run_id: int,
    ingested_at: datetime,
    batch_size: int,
) -> LoadCounts:
    """COPY one validated Taxi Zone source into raw.taxi_zones."""
    rows_read = 0
    rows_loaded = 0
    for batch in iter_taxi_zone_batches(
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
            table="taxi_zones",
            columns=TAXI_ZONE_COPY_COLUMNS,
            rows=batch.rows,
        )
    return LoadCounts(rows_read=rows_read, rows_loaded=rows_loaded)
