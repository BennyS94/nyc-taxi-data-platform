# Local platform architecture

Airflow orchestrates. The application and dbt components implement the work.

```text
Airflow 3 (LocalExecutor, monthly schedule/manual parameters)
   |
   v
taxi_pipeline source handling and source contracts
   |
   v
taxi_pipeline registry and transactional raw ingestion
   |
   v
taxi_pipeline PostgreSQL quality evaluation
   |
   v
dbt staging, intermediate, dimensions, and incremental fact
   |
   v
PostgreSQL analytics warehouse
   |
   v
FastAPI read-only operational and aggregate analytics interface
```

The DAG calls the same application services used by the CLI. It does not generate source
URLs, inspect schemas, load batches, define quality SQL, or transform warehouse data.
Task communication is limited to small serializable metadata such as partition labels,
source-file IDs, run IDs, decisions, statuses, and row counts.

Yellow and Green execute sequentially to keep local database and memory demand modest.
Application source registration and ingestion remain authoritative for idempotency, while
dbt owns warehouse incrementality. A source revision is recorded as a skipped application
attempt but raised as a failed Airflow task so downstream transformations cannot continue.

Airflow DAG runs and task instances are orchestration history stored in the separate
`airflow` database. `ops.pipeline_runs` is application ingestion history stored in
`nyc_tlc`; the two run identities have different ownership and must not be conflated.

The local Docker topology contains PostgreSQL, a one-shot Airflow database initializer,
an Airflow API/UI server, scheduler, and the DAG processor required by Airflow 3. It uses
LocalExecutor and deliberately has no Redis, Celery workers, or Kubernetes components.

FastAPI is separate from orchestration. It uses request-scoped synchronous SQLAlchemy
sessions to read `ops.source_files`, `ops.pipeline_runs`, and `ops.data_quality_results`,
and queries dbt-owned `marts` for aggregate analytics. It has no pipeline-control or data
mutation endpoints.
