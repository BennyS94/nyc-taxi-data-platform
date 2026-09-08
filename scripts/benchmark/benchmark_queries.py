"""Time representative application SQL and optionally save PostgreSQL query plans."""

import argparse
import json
import os
import statistics
import time
from pathlib import Path

from sqlalchemy import create_engine, text

from taxi_pipeline.benchmarking import nearest_rank_percentile

QUERIES = {
    "analytics_summary": """
        SELECT count(*), sum(f.total_amount), avg(f.trip_distance_miles),
               avg(f.fare_amount), avg(f.tip_amount)
        FROM marts.fct_trips f
        JOIN marts.dim_date d ON d.date_key = f.pickup_date_key
        WHERE f.service_type = 'yellow'
          AND d.full_date BETWEEN DATE '2025-01-15' AND DATE '2025-01-15'
    """,
    "monthly_analytics": """
        SELECT date_trunc('month', d.full_date)::date, f.service_type,
               count(*), sum(f.total_amount), avg(f.trip_distance_miles),
               avg(f.fare_amount), avg(f.tip_amount)
        FROM marts.fct_trips f
        JOIN marts.dim_date d ON d.date_key = f.pickup_date_key
        GROUP BY 1, f.service_type ORDER BY 1, f.service_type
    """,
    "top_pickup_zones": """
        SELECT z.location_id, z.borough, z.zone_name, count(*) AS trip_count,
               sum(f.total_amount)
        FROM marts.fct_trips f
        JOIN marts.dim_date d ON d.date_key = f.pickup_date_key
        JOIN marts.dim_zone z ON z.zone_key = f.pickup_zone_key
        WHERE f.service_type = 'yellow'
          AND d.full_date BETWEEN DATE '2025-01-15' AND DATE '2025-01-15'
        GROUP BY z.zone_key, z.location_id, z.borough, z.zone_name
        ORDER BY trip_count DESC, z.zone_key LIMIT 10
    """,
    "latest_runs": """
        SELECT * FROM ops.pipeline_runs ORDER BY started_at DESC, run_id DESC LIMIT 50
    """,
    "run_quality": """
        SELECT * FROM ops.data_quality_results
        WHERE run_id = (SELECT max(run_id) FROM ops.data_quality_results)
        ORDER BY quality_result_id
    """,
    "exact_duplicate_quality": """
        SELECT count(*) FROM (
          SELECT 1 FROM raw.yellow_trips
          WHERE _source_file_id = (SELECT max(_source_file_id) FROM raw.yellow_trips)
          GROUP BY "VendorID", tpep_pickup_datetime, tpep_dropoff_datetime,
                   passenger_count, trip_distance, "RatecodeID", store_and_fwd_flag,
                   "PULocationID", "DOLocationID", payment_type, fare_amount, extra,
                   mta_tax, tip_amount, tolls_amount, improvement_surcharge, total_amount,
                   congestion_surcharge, "Airport_fee", cbd_congestion_fee
          HAVING count(*) > 1
        ) duplicates
    """,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--plans-dir", type=Path)
    args = parser.parse_args()
    engine = create_engine(os.environ["BENCHMARK_DATABASE_URL"])
    results = {}
    with engine.connect() as connection:
        for name, sql in QUERIES.items():
            timings = []
            for _ in range(args.runs):
                started = time.perf_counter()
                connection.execute(text(sql)).all()
                timings.append((time.perf_counter() - started) * 1_000)
            results[name] = {
                "median_ms": round(statistics.median(timings), 3),
                "p95_ms": round(nearest_rank_percentile(timings, 0.95), 3),
            }
            if args.plans_dir:
                args.plans_dir.mkdir(parents=True, exist_ok=True)
                plan = connection.execute(text(f"EXPLAIN (ANALYZE, BUFFERS) {sql}")).scalars()
                (args.plans_dir / f"{name}.txt").write_text(
                    "\n".join(plan) + "\n", encoding="utf-8"
                )
    print(json.dumps(results, indent=2))
    engine.dispose()


if __name__ == "__main__":
    main()
