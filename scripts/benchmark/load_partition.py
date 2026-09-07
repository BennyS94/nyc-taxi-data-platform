"""Load and quality-check one real partition in an isolated benchmark database."""

import argparse
import json
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from taxi_pipeline.ingestion import ingest_source
from taxi_pipeline.landing.metadata import inspect_source
from taxi_pipeline.metadata.statuses import RunStatus
from taxi_pipeline.quality import find_latest_successful_run, run_quality_checks
from taxi_pipeline.sources import green_trip_source, taxi_zone_source, yellow_trip_source

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("service", choices=["yellow", "green", "zones"])
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--month", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=50_000)
    args = parser.parse_args()
    database_url = os.environ["BENCHMARK_DATABASE_URL"]
    engine = create_engine(database_url)
    if "benchmark" not in (engine.url.database or "").lower():
        raise ValueError("benchmark database name must contain 'benchmark'")
    source = {
        "yellow": lambda: yellow_trip_source(args.year, args.month),
        "green": lambda: green_trip_source(args.year, args.month),
        "zones": taxi_zone_source,
    }[args.service]()
    result = ingest_source(
        engine,
        inspect_source(source, ROOT),
        ROOT,
        batch_size=args.batch_size,
    )
    payload = {"status": result.status.value, "rows_loaded": result.rows_loaded}
    if args.service != "zones":
        run_id = result.run_id
        if result.status is RunStatus.SKIPPED:
            with Session(engine) as session:
                run_id = find_latest_successful_run(
                    session,
                    service_type=args.service,
                    year=args.year,
                    month=args.month,
                )
        with Session(engine) as session, session.begin():
            quality = run_quality_checks(session, run_id)
        payload["quality_checks"] = quality.check_count
    print(json.dumps(payload))
    engine.dispose()


if __name__ == "__main__":
    main()
