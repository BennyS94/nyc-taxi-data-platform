# Measured optimizations

## Accepted fact index and statistics refresh

The selective API queries joined the small date dimension to `fct_trips`, but without an
index PostgreSQL scanned all 7.19 million fact rows. A candidate B-tree on
`(pickup_date_key, service_type)` changed the plans to a date-driven nested loop with a
bitmap index and heap scan. It reads only the 125,359 Yellow rows for the measured day.

The index is configured on `fct_trips` through dbt, which owns `marts`. A dbt post-hook
runs `ANALYZE` after the fact build because the baseline plan substantially
underestimated filtered rows before statistics were collected. Alembic remains limited to
`raw` and `ops`.

| Workload | Before median | After median | Result |
|---|---:|---:|---:|
| Analytics summary, one day | 711.337 ms | 23.563 ms | 96.7% lower |
| Top pickup zones, one day | 818.283 ms | 111.040 ms | 86.4% lower |
| Monthly analytics, all data | 2,683.454 ms | 2,580.996 ms | effectively unchanged |

The index occupied 48 MB, about 2.7% of the 1,749 MB fact heap. An optimized full refresh
including index creation and `ANALYZE` took 113.365 seconds versus 111.590 seconds before,
an observed 1.775-second build cost on this run. This is an acceptable local write/storage
trade-off for the large selective-read improvement.

The monthly endpoint still scans the fact because it intentionally aggregates all stored
warehouse rows. No materialized view or cache was added for a roughly 2.6-second local
query.

## API timings after optimization

Five in-process FastAPI requests were measured through `TestClient`, including response
validation and serialization. The historical upper-sample column is the fourth sorted
observation recorded by the old benchmark implementation, not p95. Future runs use the
empirical nearest-rank p95 (`ceil(0.95 * n)`).

| Endpoint | Median | Legacy upper sample |
|---|---:|---:|
| `/analytics/summary` (Yellow, one day) | 28.462 ms | 29.036 ms |
| `/analytics/monthly` | 2,575.305 ms | 2,587.031 ms |
| `/analytics/zones` (Yellow, one day) | 69.347 ms | 74.580 ms |
| `/runs?limit=50` | 4.393 ms | 4.656 ms |

These are local observations, not service-level guarantees.

## Rejected changes

A BRIN index on `pickup_date_key` occupied only 64 kB, but it did not improve the
selective queries: summary measured 683.422 ms and zones 731.220 ms. The source-file load
layout and page ranges were not selective enough for this workload, so the BRIN index was
removed.

No new operational index was added. Operational queries were already sub-millisecond at
the SQL layer, and `data_quality_results(run_id, check_name)` already supplies the useful
`run_id` B-tree prefix.

No quality-query index or approximation was added. The expensive duplicate check groups
every source field exactly; weakening that contract or adding a huge covering index was
not justified for a quality task that runs once per ingested file.

## Reproduction

Use a disposable database whose name includes `benchmark`, run migrations, and point
`BENCHMARK_DATABASE_URL` at it. The scripts deliberately reject other database names.

```bash
python scripts/benchmark/benchmark_ingestion.py
python scripts/benchmark/load_partition.py green --year 2025 --month 1
python scripts/benchmark/benchmark_queries.py --plans-dir docs/performance/query_plans/run
DATABASE_URL="$BENCHMARK_DATABASE_URL" python scripts/benchmark/benchmark_api.py
```

The scripts use existing local landing files and never download data. dbt build timings
were recorded with `time.perf_counter`-equivalent wall-clock timing around the documented
dbt commands.
