# Performance baseline

## Scope and environment

Measurements were taken on 2026-09-07 against an isolated local benchmark database. The
database was loaded from the repository's unchanged real TLC landing files; the normal
development registry was not modified. Results describe this machine only and are not an
SLA or production-capacity claim.

| Component | Value |
|---|---|
| OS | Windows 11 |
| CPU | Intel Core i5-12500H, 12 cores / 16 logical processors |
| RAM | 15.7 GiB |
| Storage | GIGABYTE AG4512G-SI B10; Windows reported only fixed-disk media |
| PostgreSQL | 18.6, local isolated cluster |
| Python | 3.13.2 |
| dbt Core / PostgreSQL adapter | 1.12.3 / 1.11.0 |
| Airflow | 3.3.1 (not part of timed workloads) |

The benchmark warehouse contains Yellow December 2024 and January 2025, Green January
2025, and the Taxi Zone Lookup.

## Relation baseline

| Relation | Rows | Heap | Indexes | Total |
|---|---:|---:|---:|---:|
| `raw.yellow_trips` | 7,143,597 | 1,439 MB | 259 MB | 1,698 MB |
| `raw.green_trips` | 48,326 | 10 MB | 1,824 kB | 12 MB |
| `raw.taxi_zones` | 265 | 32 kB | 48 kB | 120 kB |
| `ops.source_files` | 4 | 8 kB | 32 kB | 48 kB |
| `ops.pipeline_runs` | 5 | 8 kB | 16 kB | 32 kB |
| `ops.data_quality_results` | 82 | 16 kB | 32 kB | 80 kB |
| `marts.fct_trips` | 7,191,923 | 1,749 MB | 0 before optimization | 1,749 MB |
| `marts.dim_zone` | 266 | 32 kB | 0 | 40 kB |
| `marts.dim_vendor` | 5 | 8 kB | 0 | 16 kB |
| `marts.dim_date` | 74 | 8 kB | 0 | 16 kB |

Sizes came from `pg_relation_size`, `pg_indexes_size`, and `pg_total_relation_size` after
the measured full refresh.

## Ingestion throughput

Each trial loaded all 3,475,226 Yellow January 2025 rows through the production PyArrow
and PostgreSQL COPY path after resetting only the isolated benchmark database.

| Batch rows | Elapsed seconds | Rows/second |
|---:|---:|---:|
| 25,000 | 104.653 | 33,207 |
| 50,000 | 113.735 | 30,556 |
| 100,000 | 101.147 | 34,358 |
| 250,000 | 104.433 | 33,277 |

The single-pass results differ by about 12%, are not monotonic, and do not establish a
stable better default. The production default remains 50,000 rows.

## Query baseline

Five warm requests were timed for each representative query. Analytics summary and zones
used Yellow trips for 2025-01-15; monthly analytics covered the complete warehouse.

| Workload | Median | p95 | Plan observation |
|---|---:|---:|---|
| Analytics summary | 711.337 ms | 717.750 ms | Parallel sequential fact scan |
| Monthly analytics | 2,683.454 ms | 2,686.623 ms | Required full fact scan and aggregate |
| Top pickup zones | 818.283 ms | 837.251 ms | Parallel sequential fact scan plus grouping |
| Latest runs | 0.500 ms | 0.743 ms | Tiny operational table |
| Quality rows for run | 0.762 ms | 0.914 ms | Existing unique index begins with `run_id` |
| Exact duplicate quality check | 4,538.723 ms | 4,558.113 ms | Per-file scan and exact external merge sort |

The exact-duplicate check spilled about 556 MB of temporary sort data across the leader
and two workers. It already scopes by `_source_file_id`, whose primary-key prefix is
indexed. No extra index can cover the exact grouping without a very large write-heavy
index, so its exact semantics were retained unchanged.

Raw plans are in `query_plans/before/`.

## dbt build timings

| Build | Rows in scope | Elapsed |
|---|---:|---:|
| Initial January full refresh | 3,523,552 | 115.589 s |
| No-op incremental | no new source | 26.307 s |
| Incremental after adding Yellow December | 3,668,371 new | 92.923 s |
| Full refresh of all data | 7,191,923 | 111.590 s |

Warm filesystem/database caches affect the comparison, but the no-op path clearly avoids
rebuilding the fact. The new-source incremental path preserves the existing January fact
and remains faster than the all-data full refresh.
