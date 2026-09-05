"""Add run status reason.

Revision ID: 20260905_02
Revises: 20260905_01
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260905_02"
down_revision: str | None = "20260905_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a non-error explanation for terminal skipped runs."""
    op.add_column(
        "pipeline_runs",
        sa.Column("status_reason", sa.Text(), nullable=True),
        schema="ops",
    )


def downgrade() -> None:
    """Remove the run status reason."""
    op.drop_column("pipeline_runs", "status_reason", schema="ops")
