"""Apply, validate, and clean the synthetic fixture seed.

The seed is idempotent: every row upserts on its primary key, so a repeat run
produces the same ids and counts. It runs as the migration or a dedicated seed
identity and refuses to run as ``workloop_runtime``. It never touches a row
outside the two fixture tenants. It is not part of the Alembic upgrade path.
"""

import argparse
import importlib
import os
from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime, time

from sqlalchemy import Connection, Date, DateTime, Time, create_engine, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.base import Base
from app.db.seed import constants as c
from app.db.seed.fixtures import TENANT_COMPANY_IDS, Row, build_rows

# Register every model table on Base.metadata.
importlib.import_module("app.models")


def _sync_url(url: str) -> str:
    # A standalone seed uses a sync engine; the async driver marker is optional.
    return url


def _coerce(table_name: str, values: dict[str, object]) -> dict[str, object]:
    columns = Base.metadata.tables[table_name].columns
    coerced: dict[str, object] = {}
    for key, value in values.items():
        column_type = columns[key].type
        if (
            isinstance(value, str)
            and isinstance(column_type, Date)
            and not isinstance(column_type, DateTime)
        ):
            coerced[key] = date.fromisoformat(value)
        elif isinstance(value, str) and isinstance(column_type, DateTime):
            coerced[key] = datetime.fromisoformat(value)
        elif isinstance(value, str) and isinstance(column_type, Time):
            coerced[key] = time.fromisoformat(value)
        else:
            coerced[key] = value
    return coerced


def _guard_identity(connection: Connection) -> None:
    current = connection.execute(text("SELECT current_user")).scalar_one()
    if current == "workloop_runtime":
        raise RuntimeError("the seed must not run as the runtime role workloop_runtime")


def apply_rows(connection: Connection, rows: Sequence[Row]) -> None:
    for row in rows:
        table = Base.metadata.tables[row.table]
        values = _coerce(row.table, row.values)
        statement = pg_insert(table).values(**values)
        update = {k: statement.excluded[k] for k in values if k not in row.conflict}
        if update:
            statement = statement.on_conflict_do_update(
                index_elements=list(row.conflict), set_=update
            )
        else:
            statement = statement.on_conflict_do_nothing(index_elements=list(row.conflict))
        connection.execute(statement)


def _scoped_count(connection: Connection, table_name: str) -> int:
    table = Base.metadata.tables[table_name]
    query = select(func.count()).select_from(table)
    if table_name == "companies":
        query = query.where(table.c.id.in_(TENANT_COMPANY_IDS))
    elif table_name == "app_users":
        query = query.where(table.c.identity_issuer == c.SEED_ISSUER)
    else:
        query = query.where(table.c.company_id.in_(TENANT_COMPANY_IDS))
    return connection.execute(query).scalar_one()


def validate(connection: Connection, rows: Sequence[Row]) -> None:
    # Every manifest row exists by primary key.
    for row in rows:
        table = Base.metadata.tables[row.table]
        pk = {col.name: row.values[col.name] for col in table.primary_key.columns}
        clauses = [table.c[name] == value for name, value in pk.items()]
        found = connection.execute(select(func.count()).select_from(table).where(*clauses))
        if found.scalar_one() != 1:
            raise RuntimeError(f"missing fixture row {row.table} {pk}")

    # Per-table scoped count equals the manifest count, so there are no extra or
    # missing rows in the fixture tenants.
    expected = Counter(row.table for row in rows)
    for table_name, want in expected.items():
        got = _scoped_count(connection, table_name)
        if got != want:
            raise RuntimeError(f"{table_name}: expected {want} fixture rows, found {got}")


def clean(connection: Connection, rows: Sequence[Row]) -> None:
    # Delete only fixture rows, child before parent (reverse insert order).
    for row in reversed(rows):
        table = Base.metadata.tables[row.table]
        pk = {col.name: row.values[col.name] for col in table.primary_key.columns}
        clauses = [table.c[name] == value for name, value in pk.items()]
        connection.execute(table.delete().where(*clauses))


def _database_url(explicit: str | None) -> str:
    url = explicit or os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("set MIGRATION_DATABASE_URL or pass --database-url")
    return _sync_url(url)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed synthetic development fixtures.")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args(argv)

    rows = build_rows()
    engine = create_engine(_database_url(args.database_url))
    try:
        with engine.begin() as connection:
            _guard_identity(connection)
            if args.clean:
                clean(connection, rows)
                print(f"removed {len(rows)} fixture rows")
                return 0
            if not args.validate_only:
                apply_rows(connection, rows)
            validate(connection, rows)
        counts = Counter(row.table for row in rows)
        print(f"seeded {len(rows)} rows across {len(counts)} tables; validation passed")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
