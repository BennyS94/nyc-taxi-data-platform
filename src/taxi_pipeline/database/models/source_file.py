"""Operational source-file metadata model."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Identity,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from taxi_pipeline.database.base import Base


class SourceFile(Base):
    """An immutable source-file version known to the platform."""

    __tablename__ = "source_files"
    __table_args__ = (
        UniqueConstraint(
            "partition_key",
            "checksum_sha256",
            name="uq_source_files_partition_checksum",
        ),
        CheckConstraint("file_size_bytes > 0", name="file_size_positive"),
        CheckConstraint("row_count IS NULL OR row_count >= 0", name="row_count_nonnegative"),
        CheckConstraint(
            "source_month IS NULL OR source_month BETWEEN 1 AND 12",
            name="source_month_valid",
        ),
        {"schema": "ops"},
    )

    source_file_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_name: Mapped[str] = mapped_column(Text, nullable=False)
    service_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source_month: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    partition_key: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    landing_path: Mapped[str] = mapped_column(Text, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    row_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    schema_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    discovered_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    loaded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
