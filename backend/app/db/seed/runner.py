"""Apply, validate, and clean the synthetic fixture seed.

The seed is idempotent: every row upserts on its primary key, so a repeat run
produces the same ids and counts. It runs as the migration or a dedicated seed
identity and refuses to run as ``workloop_runtime``. It never touches a row
outside the two fixture tenants. It is not part of the Alembic upgrade path.
"""

import argparse
import hashlib
import importlib
import json
import os
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import Connection, Date, DateTime, Time, create_engine, func, insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.seed import constants as c
from app.db.seed.fixtures import TENANT_COMPANY_IDS, Row, build_rows

# Register every model table on Base.metadata.
importlib.import_module("app.models")


def _sync_url(url: str) -> str:
    # A standalone seed uses a sync engine; the async driver marker is optional.
    return url


def _coerce(table_name: str, values: Mapping[str, object]) -> dict[str, object]:
    columns = Base.metadata.tables[table_name].columns
    enriched = dict(values)
    for column in columns:
        if (
            column.name not in enriched
            and isinstance(column.type, DateTime)
            and not column.nullable
            and column.server_default is not None
        ):
            enriched[column.name] = c.CLOCK_TIMESTAMP
    coerced: dict[str, object] = {}
    for key, value in enriched.items():
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
    # Every manifest row exists by primary key and retains every fixed value.
    for row in rows:
        table = Base.metadata.tables[row.table]
        pk = {col.name: row.values[col.name] for col in table.primary_key.columns}
        clauses = [table.c[name] == value for name, value in pk.items()]
        for name, value in _coerce(row.table, row.values).items():
            clauses.append(table.c[name] == value)
        found = connection.execute(select(func.count()).select_from(table).where(*clauses))
        if found.scalar_one() != 1:
            raise RuntimeError(f"missing or changed fixture row {row.table} {pk}")

    # Per-table scoped count equals the manifest count, so there are no extra or
    # missing rows in the fixture tenants.
    expected = Counter(row.table for row in rows)
    for table_name, want in expected.items():
        got = _scoped_count(connection, table_name)
        if got != want:
            raise RuntimeError(f"{table_name}: expected {want} fixture rows, found {got}")

    _validate_scope_controls(connection)
    _validate_notification_dedup(connection, rows)


def _validate_scope_controls(connection: Connection) -> None:
    employees = Base.metadata.tables["employees"]
    incidents = Base.metadata.tables["incident_reports"]
    rosters = Base.metadata.tables["roster_assignments"]

    horizon_cedar = connection.execute(
        select(func.count())
        .select_from(employees)
        .where(
            employees.c.company_id == c.COMPANY_ID[c.HORIZON],
            employees.c.id == uuid.UUID("31000000-0000-4000-8000-000000000002"),
        )
    ).scalar_one()
    if horizon_cedar != 0:
        raise RuntimeError("tenant-scoped employee query returned the Cedar control")

    dxb_auh = connection.execute(
        select(func.count())
        .select_from(rosters)
        .where(
            rosters.c.branch_id == c.BRANCH_DXB,
            rosters.c.employee_id == uuid.UUID("22000000-0000-4000-8000-000000000001"),
        )
    ).scalar_one()
    if dxb_auh != 0:
        raise RuntimeError("branch-scoped roster query returned the Abu Dhabi control")

    branch_count = connection.execute(
        select(func.count(func.distinct(incidents.c.branch_id))).where(
            incidents.c.company_id.in_(TENANT_COMPANY_IDS)
        )
    ).scalar_one()
    if branch_count != 4:
        raise RuntimeError("incident controls do not cover all four branches")

    probes: list[dict[str, object]] = [
        {
            "id": c.derive(
                "letter_requests", c.HORIZON, "dubai", "C-SHJ-002", "cross-tenant-rejected"
            ),
            "company_id": c.COMPANY_ID[c.HORIZON],
            "branch_id": c.BRANCH_DXB,
            "employee_id": uuid.UUID("31000000-0000-4000-8000-000000000002"),
            "request_kind": "letter",
            "letter_type": "scope_probe",
        },
        {
            "id": c.derive(
                "letter_requests", c.HORIZON, "dubai", "H-AUH-002", "cross-branch-rejected"
            ),
            "company_id": c.COMPANY_ID[c.HORIZON],
            "branch_id": c.BRANCH_DXB,
            "employee_id": uuid.UUID("22000000-0000-4000-8000-000000000002"),
            "request_kind": "letter",
            "letter_type": "scope_probe",
        },
    ]
    table = Base.metadata.tables["letter_requests"]
    for values in probes:
        try:
            with connection.begin_nested():
                connection.execute(insert(table).values(**_coerce("letter_requests", values)))
        except IntegrityError:
            continue
        raise RuntimeError("a cross-scope fixture row bypassed the composite employee constraint")


def _validate_notification_dedup(connection: Connection, rows: Sequence[Row]) -> None:
    source = next(row for row in rows if row.table == "notifications")
    values = _coerce("notifications", source.values)
    values["id"] = c.derive("notifications", c.HORIZON, "dubai", "H-DXB-002", "dedup-replay")
    table = Base.metadata.tables["notifications"]
    statement = (
        pg_insert(table)
        .values(**values)
        .on_conflict_do_nothing(constraint="uq_notifications_dedup")
    )
    connection.execute(statement)
    dedup_count = connection.execute(
        select(func.count())
        .select_from(table)
        .where(
            table.c.company_id == values["company_id"],
            table.c.recipient_app_user_id == values["recipient_app_user_id"],
            table.c.type == values["type"],
            table.c.related_entity_type == values["related_entity_type"],
            table.c.related_entity_id == values["related_entity_id"],
        )
    ).scalar_one()
    if dedup_count != 1:
        raise RuntimeError("notification deduplication did not leave exactly one row")


def _json_value(value: Any) -> Any:
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        return {str(key): _json_value(item) for key, item in sorted(mapping.items(), key=str)}
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        return [_json_value(item) for item in sequence]
    return value


def fingerprint(connection: Connection, rows: Sequence[Row]) -> str:
    payload: list[dict[str, object]] = []
    for row in rows:
        table = Base.metadata.tables[row.table]
        pk = {col.name: row.values[col.name] for col in table.primary_key.columns}
        clauses = [table.c[name] == value for name, value in pk.items()]
        stored = connection.execute(select(table).where(*clauses)).mappings().one()
        payload.append({"table": row.table, "values": _json_value(dict(stored))})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def clean(connection: Connection, rows: Sequence[Row]) -> None:
    # Delete only fixture rows, child before parent (reverse insert order).
    for row in reversed(rows):
        table = Base.metadata.tables[row.table]
        pk = {col.name: row.values[col.name] for col in table.primary_key.columns}
        clauses = [table.c[name] == value for name, value in pk.items()]
        connection.execute(table.delete().where(*clauses))
    for table_name in Counter(row.table for row in rows):
        remaining = _scoped_count(connection, table_name)
        if remaining != 0:
            raise RuntimeError(f"{table_name}: cleanup left {remaining} fixture rows")


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
    parser.add_argument("--fingerprint", action="store_true")
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
            digest = fingerprint(connection, rows)
        counts = Counter(row.table for row in rows)
        if args.fingerprint:
            print(digest)
            return 0
        print(f"seeded {len(rows)} rows across {len(counts)} tables; validation passed")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
