"""Source-conformed Taxi Zone lookup raw model."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from taxi_pipeline.database.base import Base


class TaxiZone(Base):
    """A Taxi Zone source row with per-file location uniqueness."""

    __tablename__ = "taxi_zones"
    __table_args__ = (
        UniqueConstraint(
            "_source_file_id",
            "LocationID",
            name="uq_taxi_zones_source_file_location",
        ),
        CheckConstraint("_source_row_number > 0", name="source_row_number_positive"),
        Index("ix_taxi_zones_pipeline_run_id", "_pipeline_run_id"),
        {"schema": "raw"},
    )

    source_file_id: Mapped[int] = mapped_column(
        "_source_file_id",
        BigInteger,
        ForeignKey("ops.source_files.source_file_id"),
        primary_key=True,
    )
    source_row_number: Mapped[int] = mapped_column(
        "_source_row_number", BigInteger, primary_key=True
    )
    pipeline_run_id: Mapped[int] = mapped_column(
        "_pipeline_run_id",
        BigInteger,
        ForeignKey("ops.pipeline_runs.run_id"),
        nullable=False,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        "_ingested_at", TIMESTAMP(timezone=True), nullable=False
    )

    location_id: Mapped[int] = mapped_column("LocationID", Integer, nullable=False)
    borough: Mapped[str | None] = mapped_column("Borough", Text, nullable=True)
    zone: Mapped[str | None] = mapped_column("Zone", Text, nullable=True)
    service_zone: Mapped[str | None] = mapped_column(Text, nullable=True)
