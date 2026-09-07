"""Operational API response contracts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str
    database: str


class SourceFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_file_id: int
    dataset_name: str
    service_type: str | None
    source_year: int | None
    source_month: int | None
    partition_key: str
    source_url: str
    landing_path: str
    checksum_sha256: str
    file_size_bytes: int
    row_count: int | None
    schema_fingerprint: str | None
    status: str
    discovered_at: datetime | None
    downloaded_at: datetime | None
    validated_at: datetime | None
    loaded_at: datetime | None


class SourceFilePage(BaseModel):
    items: list[SourceFileResponse]
    limit: int
    offset: int


class PipelineRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: int
    dataset_name: str
    service_type: str | None
    source_year: int | None
    source_month: int | None
    source_file_id: int | None
    started_at: datetime
    finished_at: datetime | None
    status: str
    status_reason: str | None
    rows_read: int | None
    rows_loaded: int | None
    warning_count: int | None
    error_count: int | None


class PipelineRunDetailResponse(PipelineRunResponse):
    error_message: str | None


class PipelineRunPage(BaseModel):
    items: list[PipelineRunResponse]
    limit: int
    offset: int


class QualityResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    quality_result_id: int
    check_name: str
    severity: str
    status: str
    rows_checked: int
    rows_failed: int
    failure_rate: float
    details: dict[str, Any] | None
    executed_at: datetime
