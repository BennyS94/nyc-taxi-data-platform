"""Add source storage metadata.

Revision ID: 20260907_05
Revises: 20260906_04
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260907_05"
down_revision: str | None = "20260906_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Record local or durable S3 storage for each immutable source version."""
    op.add_column(
        "source_files",
        sa.Column("storage_backend", sa.Text(), server_default="local", nullable=False),
        schema="ops",
    )
    op.add_column("source_files", sa.Column("storage_uri", sa.Text()), schema="ops")
    op.add_column("source_files", sa.Column("storage_version_id", sa.Text()), schema="ops")
    op.add_column(
        "source_files",
        sa.Column("stored_at", postgresql.TIMESTAMP(timezone=True)),
        schema="ops",
    )


def downgrade() -> None:
    """Remove optional durable-storage metadata."""
    op.drop_column("source_files", "stored_at", schema="ops")
    op.drop_column("source_files", "storage_version_id", schema="ops")
    op.drop_column("source_files", "storage_uri", schema="ops")
    op.drop_column("source_files", "storage_backend", schema="ops")
