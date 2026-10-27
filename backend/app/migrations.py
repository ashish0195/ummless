"""Additive schema migration at startup: add missing nullable columns to existing tables.

`create_all` creates new tables but never alters existing ones, so a development database from an older version
would miss new columns. This adds them (SQLite and Postgres) and logs each change. Columns that are NOT NULL
without a server default are skipped with a warning. A real migration tool (Alembic) is still the plan before the
first production schema change; see docs/LAUNCH.md.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .db import Base

log = logging.getLogger("comlogue.migrations")


def add_missing_columns(engine: Engine) -> list[str]:
    """Return the "table.column" names that were added."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    preparer = engine.dialect.identifier_preparer
    added: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        present = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            if not column.nullable and column.server_default is None:
                log.warning("Not adding %s.%s: it is NOT NULL without a server default", table.name, column.name)
                continue
            column_type = column.type.compile(dialect=engine.dialect)
            statement = (f"ALTER TABLE {preparer.quote(table.name)} "
                         f"ADD COLUMN {preparer.quote(column.name)} {column_type}")
            with engine.begin() as connection:
                connection.execute(text(statement))
            log.info("Migrated: added column %s.%s (%s)", table.name, column.name, column_type)
            added.append(f"{table.name}.{column.name}")
    return added
