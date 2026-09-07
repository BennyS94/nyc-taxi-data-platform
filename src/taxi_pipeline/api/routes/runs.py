"""Pipeline-run and quality operational routes."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from taxi_pipeline.api.dependencies import DatabaseSession
from taxi_pipeline.api.routes.sources import ServiceType
from taxi_pipeline.api.schemas.operational import (
    PipelineRunDetailResponse,
    PipelineRunPage,
    QualityResultResponse,
)
from taxi_pipeline.database.models import DataQualityResult, PipelineRun

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=PipelineRunPage, summary="List pipeline runs")
def list_runs(
    session: DatabaseSession,
    service_type: ServiceType | None = None,
    run_status: str | None = Query(default=None, alias="status"),
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    source_file_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PipelineRunPage:
    statement = select(PipelineRun)
    if service_type is not None:
        statement = statement.where(PipelineRun.service_type == service_type.value)
    if run_status is not None:
        statement = statement.where(PipelineRun.status == run_status)
    if year is not None:
        statement = statement.where(PipelineRun.source_year == year)
    if month is not None:
        statement = statement.where(PipelineRun.source_month == month)
    if source_file_id is not None:
        statement = statement.where(PipelineRun.source_file_id == source_file_id)
    statement = statement.order_by(PipelineRun.started_at.desc(), PipelineRun.run_id.desc())
    statement = statement.limit(limit).offset(offset)
    return PipelineRunPage(items=list(session.scalars(statement)), limit=limit, offset=offset)


def _get_run_or_404(session: DatabaseSession, run_id: int) -> PipelineRun:
    run = session.get(PipelineRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="pipeline run not found")
    return run


@router.get("/{run_id}", response_model=PipelineRunDetailResponse, summary="Get one pipeline run")
def get_run(run_id: int, session: DatabaseSession) -> PipelineRun:
    return _get_run_or_404(session, run_id)


@router.get(
    "/{run_id}/quality",
    response_model=list[QualityResultResponse],
    summary="List persisted quality results for a run",
)
def list_run_quality(
    run_id: int,
    session: DatabaseSession,
    severity: str | None = None,
    quality_status: str | None = Query(default=None, alias="status"),
) -> list[DataQualityResult]:
    _get_run_or_404(session, run_id)
    statement = select(DataQualityResult).where(DataQualityResult.run_id == run_id)
    if severity is not None:
        statement = statement.where(DataQualityResult.severity == severity)
    if quality_status is not None:
        statement = statement.where(DataQualityResult.status == quality_status)
    statement = statement.order_by(DataQualityResult.quality_result_id)
    return list(session.scalars(statement))
