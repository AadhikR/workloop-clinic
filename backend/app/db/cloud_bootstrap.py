from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict


@dataclass(frozen=True, slots=True)
class DatabaseBootstrap:
    environment_name: str
    database: str
    owner: str
    runtime_role: str | None = None


BOOTSTRAPS = (
    DatabaseBootstrap(
        environment_name="CLOUD_ADMIN_WORKLOOP_DATABASE_URL",
        database="workloop",
        owner="workloop_migration",
        runtime_role="workloop_runtime",
    ),
    DatabaseBootstrap(
        environment_name="CLOUD_ADMIN_KEYCLOAK_DATABASE_URL",
        database="keycloak",
        owner="keycloak",
    ),
)


def validate_admin_connection_url(value: str, expected_database: str) -> str:
    settings = conninfo_to_dict(value)
    host = settings.get("host")
    if (
        settings.get("dbname") != expected_database
        or settings.get("user") != "doadmin"
        or settings.get("sslmode") != "require"
        or not isinstance(host, str)
        or not host.startswith("private-")
        or not host.endswith(".db.ondigitalocean.com")
    ):
        raise RuntimeError("cloud database bootstrap connection is outside the approved boundary")
    return value


def apply_bootstrap(specification: DatabaseBootstrap, connection_url: str) -> None:
    validated_url = validate_admin_connection_url(connection_url, specification.database)
    with psycopg.connect(validated_url, autocommit=True) as connection:
        row = connection.execute("SELECT current_database(), current_user").fetchone()
        if row != (specification.database, "doadmin"):
            raise RuntimeError("cloud database bootstrap identity does not match its target")
        connection.execute(
            sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                sql.Identifier(specification.database)
            )
        )
        connection.execute(
            sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                sql.Identifier(specification.database),
                sql.Identifier(specification.owner),
            )
        )
        connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        connection.execute(
            sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(specification.owner))
        )
        if specification.runtime_role is not None:
            connection.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(specification.database),
                    sql.Identifier(specification.runtime_role),
                )
            )


def main() -> int:
    for specification in BOOTSTRAPS:
        connection_url = os.environ.get(specification.environment_name)
        if not connection_url:
            raise RuntimeError(f"{specification.environment_name} is required")
        apply_bootstrap(specification, connection_url)
    print("Phase 6G database ownership is ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
