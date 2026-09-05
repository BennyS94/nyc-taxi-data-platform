"""Synchronous database engine creation."""

import os

from sqlalchemy import Engine, create_engine


def get_engine(database_url: str | None = None) -> Engine:
    """Create an engine from an explicit URL or the DATABASE_URL environment variable."""
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return create_engine(url)
