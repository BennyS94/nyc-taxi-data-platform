# Five-minute project demo

## Before the demo

Run from the repository root. Copy `.env.example` to `.env` using your shell:

```bash
cp .env.example .env
```

```powershell
Copy-Item .env.example .env
```

Edit `.env` to configure the project and replace every local secret placeholder. Keep
the example's unquoted `KEY=value` format. Ensure `DATABASE_URL` matches your PostgreSQL
settings, URL-encoding password characters where needed in that URL.

Load the values into the **current shell before running Alembic or application commands**.
These loaders preserve values literally; Alembic does not load `.env` automatically.

Bash-compatible shells:

```bash
while IFS= read -r entry || [ -n "$entry" ]; do
  entry=${entry%$'\r'}
  if [[ "$entry" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
    export "$entry"
  fi
done < .env
```

PowerShell:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
    }
}
```

Then, in that configured shell (either Bash or PowerShell), install the project and
run migrations:

```bash
python -m pip install -e ".[dev]"
docker compose up -d --wait postgres
alembic upgrade head
```

For a fresh database, follow the [README ingestion commands](../README.md#local-setup)
to load sources before building the warehouse:

```bash
dbt build --project-dir dbt/taxi_analytics --profiles-dir dbt/taxi_analytics
```

Initialize and start Airflow when needed:

```bash
docker compose up airflow-init
docker compose up -d airflow-api-server airflow-scheduler airflow-dag-processor
docker compose exec airflow-api-server airflow dags unpause tlc_monthly_pipeline
```

Start the presentation services in separate shells. Load `.env` using the corresponding
loader above in the FastAPI shell before starting it:

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
