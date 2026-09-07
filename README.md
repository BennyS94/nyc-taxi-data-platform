# NYC TLC Data Pipeline & Quality Platform

The project includes source profiling and management, PostgreSQL-backed transactional raw
ingestion, SQL-first quality checks, a dbt dimensional warehouse, and Apache Airflow 3
orchestration for the monthly Yellow and Green pipeline. A read-only FastAPI interface
exposes operational metadata and aggregated warehouse analytics.
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

## dbt staging

Phase 07 adds a dbt Core/PostgreSQL transformation project under `dbt/taxi_analytics`.
The dbt-owned `staging` schema contains views for loaded Yellow Taxi rows and the single
active loaded Taxi Zone version. Raw TLC names are mapped to stable canonical names while
source, row, run, and ingestion lineage remain available.

The Yellow staging contract supplies `service_type = 'yellow'`, a typed null `trip_type`,
and `cbd_congestion_fee_amount` for both supported schemas. Historical v1 values remain
null and v2 values pass through unchanged. Staging performs no business-anomaly filtering,
aggregation, or zone enrichment.

From `dbt/taxi_analytics`, with the PostgreSQL variables from `.env` exported, run:

```bash
dbt debug
dbt parse
dbt build --select staging
dbt docs generate
```

The committed dbt tests enforce lineage integrity, per-source Yellow grain, active Taxi
Zone version cardinality, and active reference uniqueness. Generated dbt artifacts remain
ignored.

## Dimensional warehouse

Phase 08 extends dbt with canonical and enriched intermediate views, then builds a small
analytics-ready warehouse in `marts`. The warehouse contains date, zone, and vendor
dimensions plus `fct_trips`; the same zone dimension serves the pickup and dropoff roles.
Every dimension has an explicit key-zero `Unknown` member, so unresolved references keep
their fact row instead of being filtered.

Small version-controlled seeds provide TLC vendor, rate-code, and payment-type names. The
fact preserves the original numeric codes and source-file, source-row, and pipeline-run
lineage. Normal dbt builds process only loaded `source_file_id` values not already present
in the incremental fact, while `dbt build --full-refresh` remains available for model
changes. No business anomalies are removed by these transformations.

From `dbt/taxi_analytics`, build the complete warehouse with:

```bash
dbt seed
dbt build
```

## Green Taxi integration

Phase 09 adds Green Taxi January 2025 through the same landing, source registry,
transactional batch/COPY ingestion, and service-aware quality framework used by Yellow.
The targeted source profile is recorded in
[`reports/data_profiling/GREEN_2025_01_REPORT.md`](reports/data_profiling/GREEN_2025_01_REPORT.md).

`stg_tlc__green_trips` maps Green source names into the shared canonical contract. The
canonical model combines Yellow and Green with `UNION ALL`, preserving `service_type`,
technical lineage, Green `trip_type`, and source anomalies. The incremental fact loads
new Green source-file IDs without replacing Yellow history. Run the Green path with:

```bash
python -m taxi_pipeline ingest --service green --year 2025 --month 1
python -m taxi_pipeline quality run --service green --year 2025 --month 1
```

## Airflow orchestration

The `tlc_monthly_pipeline` DAG runs one small, sequential local workflow: resolve the
month, ensure Taxi Zones, ingest and check Yellow, ingest and check Green, then run
`dbt build`. Manual runs accept `year` and `month`; scheduled runs use the logical month
minus two months. `catchup` is disabled and only one DAG run is active at a time.

Airflow uses LocalExecutor and a separate `airflow` database on the existing PostgreSQL
server. The DAG passes only identifiers and counts through XCom. Application services
remain directly runnable without Airflow and continue to own downloads, contracts,
registration, ingestion, quality, and idempotency. This Compose deployment is intended
for local development and portfolio demonstrations, not production.

After copying `.env.example` to `.env`, replace the PostgreSQL password and all Airflow
secret/password placeholders. Initialize and start Airflow with:

```bash
docker compose up airflow-init
docker compose up -d airflow-api-server airflow-scheduler airflow-dag-processor
docker compose exec airflow-api-server airflow dags unpause tlc_monthly_pipeline
```

The UI is available at `http://localhost:8080` using `AIRFLOW_ADMIN_USERNAME` and
`AIRFLOW_ADMIN_PASSWORD`. Trigger February 2025 from the UI by supplying `year=2025` and
`month=2`, or from a shell with:

```bash
docker compose exec airflow-api-server airflow dags trigger \
  --conf '{"year": 2025, "month": 2}' tlc_monthly_pipeline
```

Inspect individual task logs in the UI. Component startup logs are also available with
`docker compose logs airflow-api-server airflow-scheduler airflow-dag-processor`.
Rerunning the same month records application-level `already_loaded` attempts, reruns
quality and dbt, and does not duplicate raw or fact rows.

See [`docs/architecture.md`](docs/architecture.md) for component ownership and runtime
flow.

## Operational and analytics API

The synchronous FastAPI application reads pipeline metadata from `ops` and analytics from
dbt-owned `marts`; it does not trigger ingestion, Airflow, or dbt and does not expose
individual trip rows. Typed endpoints cover health, source files, pipeline runs, quality
results, summary metrics, monthly metrics, and top pickup zones. Interactive OpenAPI
documentation is available at `/docs`.

With `DATABASE_URL` configured and the application warehouse available, start it locally:

```bash
uvicorn taxi_pipeline.api.app:app --reload --port 8000
```

Operational list endpoints use newest-first ordering with `limit`/`offset` pagination.
Analytics accept optional `service_type`, `start_date`, and `end_date` filters and retain
the warehouse's source-faithful anomaly semantics.

## PostgreSQL setup

Phase 02 provides PostgreSQL 17 through Docker Compose. Alembic manages the `ops` and
`raw` schemas, including operational source/run metadata and source-conformed Yellow,
Green, and Taxi Zone tables. Airflow metadata lives in the separate `airflow` database.

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

## Testing and CI

Tests are separated by responsibility: fast unit tests avoid network and database access;
integration tests exercise real PostgreSQL migrations, constraints, COPY ingestion,
rollback, quality SQL, and FastAPI queries; DAG tests validate Airflow structure without a
scheduler. The end-to-end smoke ingests tiny committed Yellow, Green, and Taxi Zone
fixtures, runs quality and dbt, verifies fact lineage, and queries the analytics API.

Regenerate the deterministic offline fixtures when their explicit contract changes:

```bash
python scripts/bootstrap_test_data.py
```

Run the main local checks with a clean PostgreSQL test database configured through
`TEST_DATABASE_URL` and the matching dbt `POSTGRES_*` variables:

```bash
ruff check .
alembic upgrade head
alembic check
python -m pytest
dbt build --project-dir dbt/taxi_analytics --profiles-dir dbt/taxi_analytics
docker compose config --quiet
```

GitHub Actions runs isolated lint, Python/PostgreSQL, dbt/end-to-end, and Airflow jobs on
pushes and pull requests. CI uses PostgreSQL 17 and only the committed tiny fixtures; it
does not contact NYC TLC or download production trip files.

## Performance

Real-data benchmarks use an isolated database and the existing local landing files. At
7.19 million fact rows, measured plans justified one dbt-owned B-tree on pickup date and
service type plus a post-build statistics refresh; selective daily summary and zone
queries improved substantially while full-history monthly aggregation remained a simple
scan. COPY batch comparisons did not provide stable evidence to change the 50,000-row
default. PostgreSQL partitioning and BRIN were measured and rejected at the current scale.

Environment details, reproducible scripts, timings, query plans, storage cost, and the
partitioning decision are documented in [`docs/performance/`](docs/performance/BASELINE.md).

## Optional AWS S3 landing storage

`LANDING_BACKEND=local` preserves the default local workflow. With
`LANDING_BACKEND=s3`, `AWS_REGION`, and `TLC_S3_BUCKET` configured, boto3 stores validated
source artifacts in one private, versioned, encrypted bucket using checksum-addressed
immutable keys. Uploads verify object size and SHA-256 metadata; recovery downloads to a
partial local file, verifies its full SHA-256, and atomically restores the normal landing
path used by ingestion.

Alembic records storage backend, S3 URI, Version ID, and storage time on each source-file
version without changing checksum identity or source-revision blocking. Airflow continues
to call the application layer and contains no direct AWS logic. Normal tests and CI use
mocked S3 behavior and require no AWS account or credentials.

Bucket safeguards, least-privilege IAM guidance, sync/verification commands, recovery,
and version-aware cleanup are documented in [`docs/aws_s3.md`](docs/aws_s3.md).
