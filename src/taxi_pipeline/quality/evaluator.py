"""Quality target validation, SQL evaluation, persistence, and run aggregation."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from taxi_pipeline.database.models import (
    DataQualityResult,
    PipelineRun,
    SourceFile,
    TaxiZone,
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
from taxi_pipeline.quality.rules import RULES_BY_NAME, YELLOW_RULES


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
            PipelineRun.dataset_name == "yellow_tripdata",
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
    """Evaluate and upsert all raw Yellow quality checks for one successful run."""
    run, source = _validated_target(session, run_id)
    zone_source_file_id = _loaded_zone_source_id(session)
    rows_checked, measurements = scalar_measurements(
        session,
        source.source_file_id,
        source.source_year,
        source.source_month,
    )
    measurements.update(domain_measurements(session, source.source_file_id, rows_checked))
    measurements.update(
        zone_measurements(session, source.source_file_id, zone_source_file_id, rows_checked)
    )
    measurements["exact_duplicate_source_rows"] = duplicate_measurement(
        session,
        source.source_file_id,
        rows_checked,
    )
    if set(measurements) != set(RULES_BY_NAME):
        raise QualityEvaluationError("Quality rule catalog and measurements are inconsistent")

    executed_at = datetime.now(UTC)
    for rule in YELLOW_RULES:
        _upsert_result(session, run_id, rule.name, measurements[rule.name], executed_at)
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
        check_count=len(YELLOW_RULES),
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
    if run.dataset_name != "yellow_tripdata" or run.source_file_id is None:
        raise QualityEvaluationError(f"Run {run_id} is not a loaded Yellow ingestion run")
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
    check_name: str,
    measurement: QualityMeasurement,
    executed_at: datetime,
) -> None:
    rule = RULES_BY_NAME[check_name]
    status = (
        QualityStatus.PASSED if measurement.rows_failed == 0 else QualityStatus.VIOLATED
    )
    failure_rate = (
        measurement.rows_failed / measurement.rows_checked if measurement.rows_checked else 0.0
    )
    values = {
        "run_id": run_id,
        "check_name": check_name,
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
