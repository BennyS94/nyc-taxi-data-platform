# Five-minute project demo

## Before the demo

Copy `.env.example` to `.env`, replace all local placeholders, install the project, and
make sure migrations and the warehouse are current:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres
alembic upgrade head
dbt build --project-dir dbt/taxi_analytics --profiles-dir dbt/taxi_analytics
```

Initialize and start Airflow when needed:

```bash
docker compose up airflow-init
docker compose up -d airflow-api-server airflow-scheduler airflow-dag-processor
docker compose exec airflow-api-server airflow dags unpause tlc_monthly_pipeline
```

Start the presentation services in separate shells:

```bash
uvicorn taxi_pipeline.api.app:app --port 8000
streamlit run src/taxi_pipeline/dashboard/app.py
```

## Walkthrough

1. Open Airflow at `http://localhost:8080` and show `tlc_monthly_pipeline`: Taxi Zones,
   Yellow ingestion/quality, Green ingestion/quality, and dbt execute in order.
2. Show one successful run. Rerun an already-loaded month and point out the application
   run with `status=skipped` and `status_reason=already_loaded`; raw/fact rows do not
   duplicate.
3. Open FastAPI `/docs` at `http://localhost:8000/docs`. Call `/sources/files`, `/runs`,
   and `/runs/{run_id}/quality` to show source identity, lineage, skip reasons, and
   persisted checks.
4. Open Streamlit at `http://localhost:8501`. On **Overview**, show service totals and
   month/zone charts. On **Trip Analytics**, filter service, dates, and Top N.
5. On **Pipeline Monitoring**, select a run and source. Point out rows read/loaded,
   checksum, storage backend, and explicit source-revision messaging.
6. On **Data Quality**, select a successful run and filter severity/status. Explain that
   warning counts are violated checks, while the table separately shows rows failed and
   failure rates.
7. Briefly show `dbt/taxi_analytics/models`: source-conformed staging, shared canonical
   intermediate models, dimensions, and incremental `fct_trips`.
8. If S3 is configured, show a checksum-addressed source object and its metadata. Use the
   documented storage verify/materialize command from `docs/aws_s3.md` to explain tested
   recovery; do not delete an object during the demo.

## Closing summary

The platform solves a monthly batch problem with explicit source contracts, transactional
loading, durable lineage, persisted quality, incremental analytics, thin orchestration,
and read-only presentation. Its technology choices follow the measured workload; Spark,
Kafka, and table partitioning were intentionally not added.
