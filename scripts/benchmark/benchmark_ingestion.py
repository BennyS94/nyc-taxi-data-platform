"""Compare COPY batch sizes in an explicitly isolated benchmark database."""

import argparse
import json
import os
import time
from pathlib import Path

from sqlalchemy import create_engine, text

from taxi_pipeline.ingestion import ingest_source
from taxi_pipeline.landing.metadata import inspect_source
from taxi_pipeline.sources import taxi_zone_source, yellow_trip_source

ROOT = Path(__file__).resolve().parents[2]


def _require_benchmark_database(database_url: str) -> None:
    database = create_engine(database_url).url.database or ""
    if "benchmark" not in database.lower():
        raise ValueError("benchmark database name must contain 'benchmark'")


def _reset(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE raw.yellow_trips, raw.green_trips, raw.taxi_zones,
                         ops.data_quality_results, ops.pipeline_runs, ops.source_files
                RESTART IDENTITY CASCADE
                """
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--month", type=int, default=1)
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=[25_000, 50_000, 100_000, 250_000])
    args = parser.parse_args()
    database_url = os.environ["BENCHMARK_DATABASE_URL"]
    _require_benchmark_database(database_url)
    engine = create_engine(database_url)
    zones = inspect_source(taxi_zone_source(), ROOT)
    yellow = inspect_source(yellow_trip_source(args.year, args.month), ROOT)
    results = []
    for batch_size in args.batch_sizes:
        _reset(engine)
        ingest_source(engine, zones, ROOT, batch_size=1_000)
        started = time.perf_counter()
        loaded = ingest_source(engine, yellow, ROOT, batch_size=batch_size)
        elapsed = time.perf_counter() - started
        results.append(
            {
                "batch_size": batch_size,
                "rows": loaded.rows_loaded,
                "elapsed_seconds": round(elapsed, 3),
                "rows_per_second": round(loaded.rows_loaded / elapsed),
            }
        )
    print(json.dumps(results, indent=2))
    engine.dispose()


if __name__ == "__main__":
    main()
