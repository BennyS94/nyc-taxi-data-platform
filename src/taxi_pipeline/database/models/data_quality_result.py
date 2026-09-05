"""Persisted operational data-quality result model."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Float, ForeignKey, Identity, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from taxi_pipeline.database.base import Base


class DataQualityResult(Base):
    """One deterministic quality check result for an ingestion run."""

    __tablename__ = "data_quality_results"
    __table_args__ = (
        UniqueConstraint("run_id", "check_name", name="uq_quality_results_run_check"),
        {"schema": "ops"},
    )

    quality_result_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ops.pipeline_runs.run_id"),
        nullable=False,
    )
    check_name: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    rows_checked: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rows_failed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    failure_rate: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
