"""Add source-conformed Green Taxi raw storage.

Revision ID: 20260906_04
Revises: 20260905_03
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260906_04"
down_revision: str | None = "20260905_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create raw Green Taxi storage from the profiled physical contract."""
    op.create_table(
        "green_trips",
        sa.Column("_source_file_id", sa.BigInteger(), nullable=False),
        sa.Column("_source_row_number", sa.BigInteger(), nullable=False),
        sa.Column("_pipeline_run_id", sa.BigInteger(), nullable=False),
        sa.Column("_ingested_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("VendorID", sa.Integer(), nullable=True),
        sa.Column("lpep_pickup_datetime", postgresql.TIMESTAMP(timezone=False), nullable=True),
        sa.Column("lpep_dropoff_datetime", postgresql.TIMESTAMP(timezone=False), nullable=True),
        sa.Column("store_and_fwd_flag", sa.Text(), nullable=True),
        sa.Column("RatecodeID", sa.BigInteger(), nullable=True),
        sa.Column("PULocationID", sa.Integer(), nullable=True),
        sa.Column("DOLocationID", sa.Integer(), nullable=True),
        sa.Column("passenger_count", sa.BigInteger(), nullable=True),
        sa.Column("trip_distance", sa.Float(), nullable=True),
        sa.Column("fare_amount", sa.Float(), nullable=True),
        sa.Column("extra", sa.Float(), nullable=True),
        sa.Column("mta_tax", sa.Float(), nullable=True),
        sa.Column("tip_amount", sa.Float(), nullable=True),
        sa.Column("tolls_amount", sa.Float(), nullable=True),
        sa.Column("ehail_fee", sa.Float(), nullable=True),
        sa.Column("improvement_surcharge", sa.Float(), nullable=True),
        sa.Column("total_amount", sa.Float(), nullable=True),
        sa.Column("payment_type", sa.BigInteger(), nullable=True),
        sa.Column("trip_type", sa.BigInteger(), nullable=True),
        sa.Column("congestion_surcharge", sa.Float(), nullable=True),
        sa.Column("cbd_congestion_fee", sa.Float(), nullable=True),
        sa.CheckConstraint("_source_row_number > 0", name="source_row_number_positive"),
        sa.ForeignKeyConstraint(
            ["_pipeline_run_id"],
            ["ops.pipeline_runs.run_id"],
            name="fk_green_trips__pipeline_run_id_pipeline_runs",
        ),
        sa.ForeignKeyConstraint(
            ["_source_file_id"],
            ["ops.source_files.source_file_id"],
            name="fk_green_trips__source_file_id_source_files",
        ),
        sa.PrimaryKeyConstraint(
            "_source_file_id", "_source_row_number", name="pk_green_trips"
        ),
        schema="raw",
    )
    op.create_index(
        "ix_green_trips_pipeline_run_id",
        "green_trips",
        ["_pipeline_run_id"],
        schema="raw",
    )


def downgrade() -> None:
    """Remove raw Green Taxi storage."""
    op.drop_index("ix_green_trips_pipeline_run_id", table_name="green_trips", schema="raw")
    op.drop_table("green_trips", schema="raw")
