# NYC TLC Data Pipeline & Quality Platform

The project currently includes source profiling, reusable source management, a
PostgreSQL-backed source registry, and pipeline-run lifecycle tracking.
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
`source_revision_detected` are stored separately from genuine error messages. Phase 04
does not load any source rows into the raw tables.

## PostgreSQL setup

Phase 02 provides PostgreSQL 17 through Docker Compose. Alembic manages the `ops` and
`raw` schemas, including operational source/run metadata and empty source-conformed
Yellow Taxi and Taxi Zone tables. It does not load production TLC rows.

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
