"""Quality target validation, SQL evaluation, persistence, and run aggregation."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from taxi_pipeline.database.models import (
    DataQualityResult,
    GreenTrip,
    PipelineRun,
    SourceFile,
    TaxiZone,
    YellowTrip,
)
from taxi_pipeline.metadata.statuses import RunStatus, SourceStatus
from taxi_pipeline.quality.models import (
    QualityMeasurement,
    QualityRunSummary,
    QualitySeverity,
    QualityStatus,
)
from taxi_pipeline.quality.queries import (
    domain_measurements,
    duplicate_measurement,
    scalar_measurements,
    zone_measurements,
)
from taxi_pipeline.quality.rules import (
    DOMAIN_VALUES,
    GREEN_DOMAIN_VALUES,
    RULES_BY_DATASET,
)

QUALITY_CONFIG = {
    "yellow_tripdata": (YellowTrip, DOMAIN_VALUES),
    "green_tripdata": (GreenTrip, GREEN_DOMAIN_VALUES),
}


class QualityEvaluationError(ValueError):
    """A run cannot be evaluated safely under the quality contract."""


def find_latest_successful_run(
    session: Session,
    *,
    service_type: str,
    year: int,
    month: int,
) -> int:
    """Resolve the latest successful ingestion run for one exact monthly partition."""
    run_id = session.scalar(
        select(PipelineRun.run_id)
        .join(SourceFile, SourceFile.source_file_id == PipelineRun.source_file_id)
        .where(
            PipelineRun.dataset_name == f"{service_type}_tripdata",
            PipelineRun.service_type == service_type,
            PipelineRun.source_year == year,
            PipelineRun.source_month == month,
            PipelineRun.status == RunStatus.SUCCEEDED.value,
            SourceFile.status == SourceStatus.LOADED.value,
        )
        .order_by(PipelineRun.run_id.desc())
        .limit(1)
    )
    if run_id is None:
        raise QualityEvaluationError(
            f"No successful loaded run for {service_type}/{year}/{month:02d}"
        )
    return run_id


def run_quality_checks(session: Session, run_id: int) -> QualityRunSummary:
    """Evaluate and upsert service-aware raw trip quality checks."""
    run, source = _validated_target(session, run_id)
    trip_model, domain_values = QUALITY_CONFIG[source.dataset_name]
    rules = RULES_BY_DATASET[source.dataset_name]
    rules_by_name = {rule.name: rule for rule in rules}
    zone_source_file_id = _loaded_zone_source_id(session)
    rows_checked, measurements = scalar_measurements(
        session,
        trip_model,
        source.source_file_id,
        source.source_year,
        source.source_month,
    )
    measurements.update(
        domain_measurements(
            session, trip_model, domain_values, source.source_file_id, rows_checked
        )
    )
    measurements.update(
        zone_measurements(
            session,
            trip_model,
            source.source_file_id,
            zone_source_file_id,
            rows_checked,
        )
    )
    measurements["exact_duplicate_source_rows"] = duplicate_measurement(
        session,
        trip_model,
        source.source_file_id,
        rows_checked,
    )
    if set(measurements) != set(rules_by_name):
        raise QualityEvaluationError("Quality rule catalog and measurements are inconsistent")

    executed_at = datetime.now(UTC)
    for rule in rules:
        _upsert_result(session, run_id, rule, measurements[rule.name], executed_at)
    session.flush()

    warning_count = _violated_count(session, run_id, QualitySeverity.WARNING)
    error_count = _violated_count(session, run_id, QualitySeverity.ERROR)
    run.warning_count = warning_count
    run.error_count = error_count
    session.flush()
    return QualityRunSummary(
        partition_key=source.partition_key,
        run_id=run_id,
        rows_checked=rows_checked,
        check_count=len(rules),
        warnings_violated=warning_count,
        errors_violated=error_count,
    )


def _validated_target(session: Session, run_id: int) -> tuple[PipelineRun, SourceFile]:
    run = session.get(PipelineRun, run_id)
    if run is None:
        raise QualityEvaluationError(f"Unknown pipeline run ID: {run_id}")
    if run.status != RunStatus.SUCCEEDED.value:
        raise QualityEvaluationError(
            f"Run {run_id} has status {run.status}; quality requires succeeded"
        )
    if run.dataset_name not in QUALITY_CONFIG or run.source_file_id is None:
        raise QualityEvaluationError(f"Run {run_id} is not a supported loaded trip ingestion run")
    source = session.get(SourceFile, run.source_file_id)
    if source is None or source.status != SourceStatus.LOADED.value:
        raise QualityEvaluationError(f"Run {run_id} does not reference a loaded source")
    if source.source_year is None or source.source_month is None:
        raise QualityEvaluationError(f"Run {run_id} has no monthly source dimensions")
    return run, source


def _loaded_zone_source_id(session: Session) -> int:
    source_file_id = session.scalar(
        select(SourceFile.source_file_id)
        .where(
            SourceFile.dataset_name == "taxi_zone_lookup",
            SourceFile.status == SourceStatus.LOADED.value,
        )
        .order_by(SourceFile.loaded_at.desc().nullslast(), SourceFile.source_file_id.desc())
        .limit(1)
    )
    if source_file_id is None:
        raise QualityEvaluationError("No loaded Taxi Zone source is available")
    zone_count = session.scalar(
        select(func.count())
        .select_from(TaxiZone)
        .where(TaxiZone.source_file_id == source_file_id)
    )
    if not zone_count:
        raise QualityEvaluationError("Loaded Taxi Zone source contains no raw rows")
    return source_file_id


def _upsert_result(
    session: Session,
    run_id: int,
    rule,
    measurement: QualityMeasurement,
    executed_at: datetime,
) -> None:
    status = (
        QualityStatus.PASSED if measurement.rows_failed == 0 else QualityStatus.VIOLATED
    )
    failure_rate = (
        measurement.rows_failed / measurement.rows_checked if measurement.rows_checked else 0.0
    )
    values = {
        "run_id": run_id,
        "check_name": rule.name,
        "severity": rule.severity.value,
        "status": status.value,
        "rows_checked": measurement.rows_checked,
        "rows_failed": measurement.rows_failed,
        "failure_rate": failure_rate,
        "details": measurement.details,
        "executed_at": executed_at,
    }
    statement = insert(DataQualityResult).values(**values)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["run_id", "check_name"],
            set_={key: value for key, value in values.items() if key not in {"run_id", "check_name"}},
        )
    )


def _violated_count(
    session: Session,
    run_id: int,
    severity: QualitySeverity,
) -> int:
    return session.scalar(
        select(func.count())
        .select_from(DataQualityResult)
        .where(
            DataQualityResult.run_id == run_id,
            DataQualityResult.severity == severity.value,
            DataQualityResult.status == QualityStatus.VIOLATED.value,
        )
    ) or 0
