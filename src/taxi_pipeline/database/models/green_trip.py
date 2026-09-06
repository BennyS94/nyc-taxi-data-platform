"""Source-conformed Green Taxi raw model."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from taxi_pipeline.database.base import Base


class GreenTrip(Base):
    """A Green Taxi source row with deterministic technical lineage."""

    __tablename__ = "green_trips"
    __table_args__ = (
        CheckConstraint("_source_row_number > 0", name="source_row_number_positive"),
        Index("ix_green_trips_pipeline_run_id", "_pipeline_run_id"),
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

    vendor_id: Mapped[int | None] = mapped_column("VendorID", Integer, nullable=True)
    pickup_datetime: Mapped[datetime | None] = mapped_column(
        "lpep_pickup_datetime", TIMESTAMP(timezone=False), nullable=True
    )
    dropoff_datetime: Mapped[datetime | None] = mapped_column(
        "lpep_dropoff_datetime", TIMESTAMP(timezone=False), nullable=True
    )
    store_and_fwd_flag: Mapped[str | None] = mapped_column(Text, nullable=True)
    rate_code_id: Mapped[int | None] = mapped_column("RatecodeID", BigInteger, nullable=True)
    pickup_location_id: Mapped[int | None] = mapped_column("PULocationID", Integer, nullable=True)
    dropoff_location_id: Mapped[int | None] = mapped_column("DOLocationID", Integer, nullable=True)
    passenger_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trip_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    fare_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra: Mapped[float | None] = mapped_column(Float, nullable=True)
    mta_tax: Mapped[float | None] = mapped_column(Float, nullable=True)
    tip_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    tolls_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    ehail_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    improvement_surcharge: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_type: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trip_type: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    congestion_surcharge: Mapped[float | None] = mapped_column(Float, nullable=True)
    cbd_congestion_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
