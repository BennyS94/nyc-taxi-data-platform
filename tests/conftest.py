import os
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from taxi_pipeline.database.engine import get_engine


@contextmanager
def _database_url(database_url: str) -> Iterator[None]:
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        yield
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url


@pytest.fixture(scope="session")
def postgres_engine():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL to run PostgreSQL integration tests")

    with _database_url(database_url):
        command.upgrade(Config("alembic.ini"), "head")
        engine = get_engine(database_url)
        yield engine
        engine.dispose()


@pytest.fixture
def migration_database_url() -> Iterator[str]:
    """Create a database owned exclusively by one destructive migration test."""
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("set TEST_DATABASE_URL to run PostgreSQL migration tests")

    parsed_url = make_url(test_url)
    database_name = f"nyc_tlc_migration_{uuid4().hex}"
    maintenance_database = "postgres"
    if parsed_url.database == maintenance_database:
        maintenance_database = "template1"
    maintenance_url = parsed_url.set(database=maintenance_database)
    disposable_url = parsed_url.set(database=database_name)
    maintenance_engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    quoted_name = maintenance_engine.dialect.identifier_preparer.quote(database_name)

    with maintenance_engine.connect() as connection:
        connection.execute(text(f"CREATE DATABASE {quoted_name}"))
    try:
        yield disposable_url.render_as_string(hide_password=False)
    finally:
        with maintenance_engine.connect() as connection:
            connection.execute(text(f"DROP DATABASE {quoted_name}"))
        maintenance_engine.dispose()


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
