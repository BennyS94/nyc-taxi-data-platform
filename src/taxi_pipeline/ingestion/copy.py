"""Small psycopg COPY helpers used by raw loaders."""

from collections.abc import Iterable

from psycopg import sql
from sqlalchemy.orm import Session


def copy_rows(
    session: Session,
    *,
    schema: str,
    table: str,
    columns: tuple[str, ...],
    rows: Iterable[tuple],
) -> int:
    """Write rows with psycopg COPY inside the SQLAlchemy session transaction."""
    driver_connection = session.connection().connection.driver_connection
    statement = sql.SQL("COPY {}.{} ({}) FROM STDIN").format(
        sql.Identifier(schema),
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
    )
    copied = 0
    with driver_connection.cursor().copy(statement) as copy:
        for row in rows:
            copy.write_row(row)
            copied += 1
    return copied
