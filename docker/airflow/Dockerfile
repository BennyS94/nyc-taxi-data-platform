FROM apache/airflow:3.3.1-python3.13

COPY --chown=airflow:root pyproject.toml /opt/taxi_pipeline/pyproject.toml
COPY --chown=airflow:root src /opt/taxi_pipeline/src

RUN pip install --no-cache-dir "apache-airflow==3.3.1" "/opt/taxi_pipeline[dev]"
