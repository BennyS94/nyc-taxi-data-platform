"""Add operational data-quality results.

Revision ID: 20260905_03
Revises: 20260905_02
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260905_03"
down_revision: str | None = "20260905_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create per-run, per-check quality-result storage."""
    op.create_table(
        "data_quality_results",
        sa.Column("quality_result_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("check_name", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("rows_checked", sa.BigInteger(), nullable=False),
        sa.Column("rows_failed", sa.BigInteger(), nullable=False),
        sa.Column("failure_rate", sa.Float(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("executed_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["ops.pipeline_runs.run_id"],
            name="fk_data_quality_results_run_id_pipeline_runs",
        ),
        sa.PrimaryKeyConstraint("quality_result_id", name="pk_data_quality_results"),
        sa.UniqueConstraint("run_id", "check_name", name="uq_quality_results_run_check"),
        schema="ops",
    )


def downgrade() -> None:
    """Remove operational quality-result storage."""
    op.drop_table("data_quality_results", schema="ops")
