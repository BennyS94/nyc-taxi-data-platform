# NYC TLC Data Pipeline & Quality Platform

The project currently includes source profiling, reusable source management, a
PostgreSQL-backed source registry, pipeline-run lifecycle tracking, and transactional raw
ingestion.
Phase 01 profiles official NYC TLC Yellow Taxi trip records for December 2024 and January
2025, plus the Taxi Zone Lookup. The generated reports capture source identity, physical
schemas, nulls, observed domains, numeric and datetime distributions, zone reference
coverage, and exact duplicate source-row counts.

The observed January schema adds `cbd_congestion_fee`; the remaining common columns have
the same Arrow types as December. The source files contain 3,668,371 December rows and
3,475,226 January rows. Full findings and unresolved design questions are in
[`reports/data_profiling/PROFILING_REPORT.md`](reports/data_profiling/PROFILING_REPORT.md).

Install the profiling dependencies and run the complete profile with:

```bash
python -m pip install -e ".[dev]"
python scripts/profile_tlc_data.py
```

The command downloads source files into the Git-ignored `data/landing/` directory and
reuses them on subsequent runs. It regenerates deterministic JSON and Markdown reports.

## Source management

Phase 03 provides deterministic official URLs, portable landing paths, safe partial-file
downloads, SHA-256 identity, and structural validation. It recognizes the profiled Yellow
schemas as `yellow_v1` (19 baseline fields) and `yellow_v2` (plus
`cbd_congestion_fee`), and validates required Taxi Zone fields and `LocationID` identity.

Fetch or reuse and inspect a source with:

```bash
python -m taxi_pipeline source fetch --service yellow --year 2025 --month 1
python -m taxi_pipeline source fetch-zones
```

These commands only manage files under the Git-ignored `data/landing/` directory. They do
not persist source metadata to PostgreSQL or load raw tables.

## Source registry and run tracking

Phase 04 persists validated source metadata using `(partition_key, checksum_sha256)` as
the immutable version identity. Exact versions are registered idempotently, loaded
versions are skipped, and a new checksum for an existing partition is preserved as a
blocked revision rather than replacing prior data.

Register sources with:

```bash
python -m taxi_pipeline source register --service yellow --year 2025 --month 1
python -m taxi_pipeline source register-zones
```

The application services also track `running`, `succeeded`, `failed`, and `skipped`
attempts. Retries create new run records, while skip reasons such as `already_loaded` and
`source_revision_detected` are stored separately from genuine error messages. PostgreSQL
uniqueness plus transaction recovery handles concurrent registration of the same exact
version; simultaneous registration of different new revisions for one partition remains
outside the initial portfolio concurrency scope.

## Raw ingestion

Phase 05 reads Yellow Parquet in bounded 50,000-row PyArrow batches and bulk loads raw
rows through psycopg `COPY`. It assigns deterministic 1-based source row numbers and
persists source-file, pipeline-run, and UTC ingestion lineage. Historical `yellow_v1`
files receive `NULL` for the absent `cbd_congestion_fee`; `yellow_v2` values are preserved.

Each file load is transactional. Counts are checked against registered source metadata
before the raw rows, successful run, and loaded source status commit together. A failed
load rolls back all raw rows, records the run failure separately, and leaves the source
ready for a new-run retry. Exact loaded versions and blocked revisions create skipped run
records without touching raw data. Taxi Zone CSV loading follows the same lifecycle and
lineage rules.

Run ingestion directly with:

```bash
python -m taxi_pipeline ingest --service yellow --year 2025 --month 1
python -m taxi_pipeline ingest-zones
```

## Data quality

Phase 06 evaluates each successful Yellow ingestion run with set-based PostgreSQL queries
and persists one idempotent result per run and check in `ops.data_quality_results`.
Results use `INFO`, `WARNING`, or `ERROR` severity and `passed`/`violated` status. Run
warning and error counters represent violated checks, while warning-only quality findings
leave the ingestion run `succeeded` and never mutate raw rows.

The checks cover source-month timestamps, reversed trip times, negative numeric values,
zero-value and null-rate metrics, documented code domains, loaded Taxi Zone references,
and collision-safe exact duplicate grouping across all source fields. Run them with:

```bash
python -m taxi_pipeline quality run --service yellow --year 2025 --month 1
```

Rerunning quality updates the same `(run_id, check_name)` results instead of creating
duplicates.

## PostgreSQL setup

Phase 02 provides PostgreSQL 17 through Docker Compose. Alembic manages the `ops` and
`raw` schemas, including operational source/run metadata and source-conformed Yellow Taxi
and Taxi Zone tables.

Create local configuration, replace the example password in both password locations,
and export `DATABASE_URL` from that file into the current shell. Then run:

```bash
cp .env.example .env
set -a
source .env
set +a
docker compose up -d
alembic upgrade head
```

Docker Compose should report the `postgres` service as healthy. Validate the project with:

```bash
export TEST_DATABASE_URL="$DATABASE_URL"
python -m pytest
ruff check .
alembic check
```

On PowerShell, create the file with `Copy-Item .env.example .env` and set the test URL with
`$env:TEST_DATABASE_URL = $env:DATABASE_URL`. The integration tests require an explicit
`TEST_DATABASE_URL` and use transactions so test-controlled rows are rolled back.
