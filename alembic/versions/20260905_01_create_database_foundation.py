"""Create database foundation.

Revision ID: 20260905_01
Revises:
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260905_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create application-owned schemas and foundational tables."""
    op.execute(sa.schema.CreateSchema("ops"))
    op.execute(sa.schema.CreateSchema("raw"))

    op.create_table(
        "source_files",
        sa.Column("source_file_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("dataset_name", sa.Text(), nullable=False),
        sa.Column("service_type", sa.Text(), nullable=True),
        sa.Column("source_year", sa.SmallInteger(), nullable=True),
        sa.Column("source_month", sa.SmallInteger(), nullable=True),
        sa.Column("partition_key", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("landing_path", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("schema_fingerprint", sa.CHAR(length=64), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("discovered_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("downloaded_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("validated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("loaded_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("file_size_bytes > 0", name="file_size_positive"),
        sa.CheckConstraint(
            "row_count IS NULL OR row_count >= 0",
            name="row_count_nonnegative",
        ),
        sa.CheckConstraint(
            "source_month IS NULL OR source_month BETWEEN 1 AND 12",
            name="source_month_valid",
        ),
        sa.PrimaryKeyConstraint("source_file_id", name="pk_source_files"),
        sa.UniqueConstraint(
            "partition_key",
            "checksum_sha256",
            name="uq_source_files_partition_checksum",
        ),
        schema="ops",
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("run_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("dataset_name", sa.Text(), nullable=False),
        sa.Column("service_type", sa.Text(), nullable=True),
        sa.Column("source_year", sa.SmallInteger(), nullable=True),
        sa.Column("source_month", sa.SmallInteger(), nullable=True),
        sa.Column("source_file_id", sa.BigInteger(), nullable=True),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("rows_read", sa.BigInteger(), nullable=True),
        sa.Column("rows_loaded", sa.BigInteger(), nullable=True),
        sa.Column("warning_count", sa.Integer(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "error_count IS NULL OR error_count >= 0",
            name="error_count_nonnegative",
        ),
        sa.CheckConstraint(
            "rows_loaded IS NULL OR rows_loaded >= 0",
            name="rows_loaded_nonnegative",
        ),
        sa.CheckConstraint(
            "rows_read IS NULL OR rows_read >= 0",
            name="rows_read_nonnegative",
        ),
        sa.CheckConstraint(
            "source_month IS NULL OR source_month BETWEEN 1 AND 12",
            name="source_month_valid",
        ),
        sa.CheckConstraint(
            "warning_count IS NULL OR warning_count >= 0",
            name="warning_count_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["source_file_id"],
            ["ops.source_files.source_file_id"],
            name="fk_pipeline_runs_source_file_id_source_files",
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_pipeline_runs"),
        schema="ops",
    )

    op.create_table(
        "yellow_trips",
        sa.Column("_source_file_id", sa.BigInteger(), nullable=False),
        sa.Column("_source_row_number", sa.BigInteger(), nullable=False),
        sa.Column("_pipeline_run_id", sa.BigInteger(), nullable=False),
        sa.Column("_ingested_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("VendorID", sa.Integer(), nullable=True),
        sa.Column("tpep_pickup_datetime", postgresql.TIMESTAMP(timezone=False), nullable=True),
        sa.Column("tpep_dropoff_datetime", postgresql.TIMESTAMP(timezone=False), nullable=True),
        sa.Column("passenger_count", sa.BigInteger(), nullable=True),
        sa.Column("trip_distance", sa.Float(), nullable=True),
        sa.Column("RatecodeID", sa.BigInteger(), nullable=True),
        sa.Column("store_and_fwd_flag", sa.Text(), nullable=True),
        sa.Column("PULocationID", sa.Integer(), nullable=True),
        sa.Column("DOLocationID", sa.Integer(), nullable=True),
        sa.Column("payment_type", sa.BigInteger(), nullable=True),
        sa.Column("fare_amount", sa.Float(), nullable=True),
        sa.Column("extra", sa.Float(), nullable=True),
        sa.Column("mta_tax", sa.Float(), nullable=True),
        sa.Column("tip_amount", sa.Float(), nullable=True),
        sa.Column("tolls_amount", sa.Float(), nullable=True),
        sa.Column("improvement_surcharge", sa.Float(), nullable=True),
        sa.Column("total_amount", sa.Float(), nullable=True),
        sa.Column("congestion_surcharge", sa.Float(), nullable=True),
        sa.Column("Airport_fee", sa.Float(), nullable=True),
        sa.Column("cbd_congestion_fee", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "_source_row_number > 0",
            name="source_row_number_positive",
        ),
        sa.ForeignKeyConstraint(
            ["_pipeline_run_id"],
            ["ops.pipeline_runs.run_id"],
            name="fk_yellow_trips__pipeline_run_id_pipeline_runs",
        ),
        sa.ForeignKeyConstraint(
            ["_source_file_id"],
            ["ops.source_files.source_file_id"],
            name="fk_yellow_trips__source_file_id_source_files",
        ),
        sa.PrimaryKeyConstraint(
            "_source_file_id",
            "_source_row_number",
            name="pk_yellow_trips",
        ),
        schema="raw",
    )
    op.create_index(
        "ix_yellow_trips_pipeline_run_id",
        "yellow_trips",
        ["_pipeline_run_id"],
        schema="raw",
    )

    op.create_table(
        "taxi_zones",
        sa.Column("_source_file_id", sa.BigInteger(), nullable=False),
        sa.Column("_source_row_number", sa.BigInteger(), nullable=False),
        sa.Column("_pipeline_run_id", sa.BigInteger(), nullable=False),
        sa.Column("_ingested_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("LocationID", sa.Integer(), nullable=False),
        sa.Column("Borough", sa.Text(), nullable=True),
        sa.Column("Zone", sa.Text(), nullable=True),
        sa.Column("service_zone", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "_source_row_number > 0",
            name="source_row_number_positive",
        ),
        sa.ForeignKeyConstraint(
            ["_pipeline_run_id"],
            ["ops.pipeline_runs.run_id"],
            name="fk_taxi_zones__pipeline_run_id_pipeline_runs",
        ),
        sa.ForeignKeyConstraint(
            ["_source_file_id"],
            ["ops.source_files.source_file_id"],
            name="fk_taxi_zones__source_file_id_source_files",
        ),
        sa.PrimaryKeyConstraint(
            "_source_file_id",
            "_source_row_number",
            name="pk_taxi_zones",
        ),
        sa.UniqueConstraint(
            "_source_file_id",
            "LocationID",
            name="uq_taxi_zones_source_file_location",
        ),
        schema="raw",
    )
    op.create_index(
        "ix_taxi_zones_pipeline_run_id",
        "taxi_zones",
        ["_pipeline_run_id"],
        schema="raw",
    )


def downgrade() -> None:
    """Remove foundational tables and application-owned schemas."""
    op.drop_index("ix_taxi_zones_pipeline_run_id", table_name="taxi_zones", schema="raw")
    op.drop_table("taxi_zones", schema="raw")
    op.drop_index("ix_yellow_trips_pipeline_run_id", table_name="yellow_trips", schema="raw")
    op.drop_table("yellow_trips", schema="raw")
    op.drop_table("pipeline_runs", schema="ops")
    op.drop_table("source_files", schema="ops")
    op.execute(sa.schema.DropSchema("raw"))
    op.execute(sa.schema.DropSchema("ops"))
