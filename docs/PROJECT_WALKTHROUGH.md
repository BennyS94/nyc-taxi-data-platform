# Project walkthrough and engineering decisions

## Why NYC TLC?

TLC publishes real monthly Parquet files with millions of rows, imperfect values,
reference data, and observable schema evolution. That makes the dataset large enough to
exercise practical ingestion and analytics decisions while remaining understandable on
one machine.

## Why Parquet and PyArrow?

Parquet preserves the published physical schema and supports bounded record batches.
PyArrow reads those batches without forcing multi-million-row files through pandas. The
loader converts batches to PostgreSQL `COPY` input while keeping deterministic 1-based
source row numbers.

## Why PostgreSQL COPY and transactions?

Row-by-row ORM insertion is inappropriate for the source volume. `COPY` provides the
bulk path, while one transaction couples raw rows, count verification, source status,
and run completion. Failure rolls back raw changes and records a separate failed attempt.

## Why file-level idempotency?

TLC provides no public business trip ID, so a heuristic trip key would make unsupported
deduplication claims. A source version is instead identified by logical partition plus
SHA-256. The exact version is skipped after load; a different checksum for the same
partition is preserved and blocked for review.

## Why separate raw, staging, and marts?

Raw retains TLC names, nullable values, anomalies, and technical lineage. dbt staging
maps source names to the canonical contract. Intermediate models share Yellow/Green
normalization and enrichment. Marts expose a small star schema. Alembic owns `raw`/`ops`;
dbt owns analytical schemas, preventing competing migrations.

## Why SQL-first data quality?

The checks evaluate already-loaded data with set-based PostgreSQL queries and persist one
result per run/check. Structural errors stop unsafe ingestion. Record-level anomalies
remain as warnings or information rather than silently deleting real source evidence.

## Why dbt and an incremental fact?

dbt makes SQL lineage, testing, seeds, schema ownership, and rebuild behavior explicit.
The fact loads only source-file IDs not already present, matching application source
identity without replacing historical facts. Full refresh remains available for model
changes.

## Why Airflow?

Airflow schedules and orders a real monthly dependency graph. The DAG stays thin and
passes only identifiers/counts because source management, ingestion, quality, and dbt
execution are already callable services. This keeps the CLI useful and unit tests fast.

## Why FastAPI and Streamlit?

FastAPI creates one typed, read-only boundary over operational metadata and aggregate
warehouse queries. Streamlit consumes that API rather than receiving database credentials
or duplicating metric SQL. It adds an explainable portfolio view without becoming a
second backend or control plane.

## Why S3?

S3 separates durable source-object storage from local execution. Checksum-addressed keys
preserve immutable source versions and align with registry identity. Recovery verifies
full SHA-256 before exposing the final local file, so the proven local loader remains
unchanged. ETag is not treated as a content identity.

## Why no Spark or Kafka?

The source is monthly batch files and measured PostgreSQL/PyArrow throughput is adequate
for the documented local scale. Spark would add distributed execution complexity; Kafka
would add a streaming system to a non-streaming source. Neither fixes a demonstrated
problem here.

## What Phase 13 concluded about partitioning

The benchmark warehouse contained 7.19 million facts. Selective queries benefited from a
single pickup-date/service B-tree and fresh statistics. A measured BRIN trial did not
improve those queries, while full-history aggregations still appropriately scanned most
rows. Table partitioning would add routing, migration, pruning, and uniqueness complexity
without measured benefit, so ordinary tables remain the explicit decision until scale or
retention requirements materially change.

## Practical lessons

- Detection and acceptance are separate parts of schema evolution.
- Required column presence does not imply non-null source values.
- Warning severity does not imply deleting or rejecting a row.
- Application run history and Airflow orchestration history have different identities.
- Benchmark evidence is more useful than adding infrastructure for résumé keywords.
- A presentation layer is safest when it stays read-only and depends on one typed API.
