"""Operational pipeline-run metadata model."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    Text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from taxi_pipeline.database.base import Base


class PipelineRun(Base):
    """An execution attempt for a source dataset or partition."""

    __tablename__ = "pipeline_runs"
    __table_args__ = (
        CheckConstraint(
            "source_month IS NULL OR source_month BETWEEN 1 AND 12",
            name="source_month_valid",
        ),
        CheckConstraint("rows_read IS NULL OR rows_read >= 0", name="rows_read_nonnegative"),
        CheckConstraint("rows_loaded IS NULL OR rows_loaded >= 0", name="rows_loaded_nonnegative"),
        CheckConstraint(
            "warning_count IS NULL OR warning_count >= 0",
            name="warning_count_nonnegative",
        ),
        CheckConstraint(
            "error_count IS NULL OR error_count >= 0",
            name="error_count_nonnegative",
        ),
        {"schema": "ops"},
    )

    run_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_name: Mapped[str] = mapped_column(Text, nullable=False)
    service_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source_month: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source_file_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ops.source_files.source_file_id"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    rows_read: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rows_loaded: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    warning_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
