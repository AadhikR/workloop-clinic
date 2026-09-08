from __future__ import annotations

import os
import uuid
from urllib.parse import urlsplit

import psycopg

COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000060")
APP_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000061")
IDENTITY_SUBJECT = str(APP_USER_ID)


def issuer_from_public_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".ondigitalocean.app")
        or parsed.username
        or parsed.password
        or parsed.port is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("WORKLOOP_PUBLIC_URL must be one exact App Platform HTTPS origin")
    return f"{value.rstrip('/')}/auth/realms/workloop-dev"


def apply_seed(connection_url: str, issuer: str) -> None:
    with psycopg.connect(connection_url) as connection:
        row = connection.execute("SELECT current_database(), current_user").fetchone()
        if row != ("workloop", "workloop_migration"):
            raise RuntimeError("Phase 6G seed must use the migration identity")
        connection.execute(
            """
            INSERT INTO companies (id, name, sector)
            VALUES (%s, 'Phase 6G synthetic company', 'Architecture proof')
            ON CONFLICT (id) DO NOTHING
            """,
            (COMPANY_ID,),
        )
        connection.execute(
            """
            INSERT INTO app_users (id, identity_issuer, identity_subject, status)
            VALUES (%s, %s, %s, 'active')
            ON CONFLICT (id) DO NOTHING
            """,
            (APP_USER_ID, issuer, IDENTITY_SUBJECT),
        )
        connection.execute(
            """
            INSERT INTO user_profiles (app_user_id, company_id, employee_id, role)
            VALUES (%s, %s, NULL, 'admin')
            ON CONFLICT (app_user_id) DO NOTHING
            """,
            (APP_USER_ID, COMPANY_ID),
        )
        stored = connection.execute(
            """
            SELECT a.identity_issuer, a.identity_subject, a.status, p.company_id, p.role
            FROM app_users AS a
            JOIN user_profiles AS p ON p.app_user_id = a.id
            WHERE a.id = %s
            """,
            (APP_USER_ID,),
        ).fetchone()
        if stored != (issuer, IDENTITY_SUBJECT, "active", COMPANY_ID, "admin"):
            raise RuntimeError("Phase 6G synthetic identity is missing or changed")


def main() -> int:
    connection_url = os.environ.get("MIGRATION_DATABASE_URL")
    public_url = os.environ.get("WORKLOOP_PUBLIC_URL")
    if not connection_url or not public_url:
        raise RuntimeError("Phase 6G seed environment is incomplete")
    apply_seed(connection_url, issuer_from_public_url(public_url))
    print("Phase 6G synthetic identity is ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
