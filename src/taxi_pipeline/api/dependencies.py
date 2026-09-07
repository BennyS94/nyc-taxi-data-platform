"""FastAPI dependencies shared by API routes."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from taxi_pipeline.database.engine import get_engine


@lru_cache(maxsize=1)
def get_api_engine() -> Engine:
    """Create the application's existing synchronous engine on first use."""
    return get_engine()


def get_db_session():
    """Yield one read-only-by-behavior session per request."""
    with Session(get_api_engine()) as session:
        yield session


DatabaseSession = Annotated[Session, Depends(get_db_session)]
