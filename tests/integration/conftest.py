import os

import pytest
from alembic.config import Config
from sqlalchemy.orm import Session

from alembic import command
from taxi_pipeline.database.engine import get_engine


@pytest.fixture(scope="session")
def postgres_engine():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL to run PostgreSQL integration tests")

    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(Config("alembic.ini"), "head")
        engine = get_engine(database_url)
        yield engine
        engine.dispose()
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url


@pytest.fixture
def connection(postgres_engine):
    with postgres_engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()


@pytest.fixture
def db_session(postgres_engine):
    with Session(postgres_engine) as session:
        transaction = session.begin()
        try:
            yield session
        finally:
            transaction.rollback()
