"""Source-file operational routes."""

from enum import StrEnum

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from taxi_pipeline.api.dependencies import DatabaseSession
from taxi_pipeline.api.schemas.operational import SourceFilePage, SourceFileResponse
from taxi_pipeline.database.models import SourceFile


class ServiceType(StrEnum):
    yellow = "yellow"
    green = "green"


router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/files", response_model=SourceFilePage, summary="List registered source files")
def list_source_files(
    session: DatabaseSession,
    service_type: ServiceType | None = None,
    source_status: str | None = Query(default=None, alias="status"),
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SourceFilePage:
    statement = select(SourceFile)
    if service_type is not None:
        statement = statement.where(SourceFile.service_type == service_type.value)
    if source_status is not None:
        statement = statement.where(SourceFile.status == source_status)
    if year is not None:
        statement = statement.where(SourceFile.source_year == year)
    if month is not None:
        statement = statement.where(SourceFile.source_month == month)
    statement = statement.order_by(SourceFile.source_file_id.desc()).limit(limit).offset(offset)
    return SourceFilePage(items=list(session.scalars(statement)), limit=limit, offset=offset)


@router.get(
    "/files/{source_file_id}",
    response_model=SourceFileResponse,
    summary="Get one registered source file",
)
def get_source_file(source_file_id: int, session: DatabaseSession) -> SourceFile:
    source_file = session.get(SourceFile, source_file_id)
    if source_file is None:
        raise HTTPException(status_code=404, detail="source file not found")
    return source_file
