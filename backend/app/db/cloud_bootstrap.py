from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict


@dataclass(frozen=True, slots=True)
class DatabaseRole:
    name: str
    inherit: bool = False


@dataclass(frozen=True, slots=True)
class DatabaseBootstrap:
    environment_name: str
    database: str
    owner: DatabaseRole
    connect_roles: tuple[DatabaseRole, ...] = ()

    @property
    def roles(self) -> tuple[DatabaseRole, ...]:
        return (self.owner, *self.connect_roles)


BOOTSTRAPS = (
    DatabaseBootstrap(
        environment_name="CLOUD_ADMIN_WORKLOOP_DATABASE_URL",
        database="workloop",
        owner=DatabaseRole("workloop_migration", inherit=False),
        connect_roles=(
            DatabaseRole("workloop_runtime", inherit=False),
            DatabaseRole("workloop_expiry_processing", inherit=False),
            DatabaseRole("workloop_file_scanner", inherit=False),
            DatabaseRole("workloop_storage_reconciler", inherit=False),
        ),
    ),
    DatabaseBootstrap(
        environment_name="CLOUD_ADMIN_KEYCLOAK_DATABASE_URL",
        database="keycloak",
        owner=DatabaseRole("keycloak", inherit=False),
    ),
)


def harden_btree_gist_functions(
    connection: psycopg.Connection[tuple[object, ...]],
    roles: tuple[DatabaseRole, ...],
) -> None:
    role_names = sql.SQL(", ").join(sql.Literal(role.name) for role in roles)
    connection.execute(
        sql.SQL(
            """
DO $$
DECLARE
  signature pg_catalog.regprocedure;
  role_name text;
  function_count integer := 0;
BEGIN
  FOR signature IN
    SELECT procedure.oid::pg_catalog.regprocedure
    FROM pg_catalog.pg_depend dependency
    JOIN pg_catalog.pg_extension extension ON extension.oid = dependency.refobjid
    JOIN pg_catalog.pg_proc procedure ON procedure.oid = dependency.objid
    WHERE dependency.classid = 'pg_catalog.pg_proc'::pg_catalog.regclass
      AND dependency.refclassid = 'pg_catalog.pg_extension'::pg_catalog.regclass
      AND dependency.deptype = 'e'
      AND extension.extname = 'btree_gist'
  LOOP
    function_count := function_count + 1;
    EXECUTE pg_catalog.format('ALTER FUNCTION %s OWNER TO workloop_migration', signature);
    EXECUTE pg_catalog.format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', signature);
    FOREACH role_name IN ARRAY ARRAY[{}]::text[]
    LOOP
      EXECUTE pg_catalog.format(
        'GRANT EXECUTE ON FUNCTION %s TO %I',
        signature,
        role_name
      );
    END LOOP;
  END LOOP;
  IF function_count = 0 THEN
    RAISE EXCEPTION 'btree_gist has no functions to secure';
  END IF;
END
$$
"""
        ).format(role_names)
    )


def harden_migrated_schema(admin_connection_url: str) -> None:
    validated_url = validate_admin_connection_url(admin_connection_url, "workloop")
    with psycopg.connect(validated_url, autocommit=True) as connection:
        row = connection.execute("SELECT current_database(), current_user").fetchone()
        if row != ("workloop", "doadmin"):
            raise RuntimeError("schema hardening must use the workloop administrator identity")
        extension_owner = connection.execute(
            """
SELECT pg_catalog.pg_get_userbyid(extowner)
FROM pg_catalog.pg_extension
WHERE extname = 'btree_gist'
"""
        ).fetchone()
        if extension_owner != ("workloop_migration",):
            raise RuntimeError("btree_gist must be owned by the migration identity")
        harden_btree_gist_functions(connection, BOOTSTRAPS[0].roles)


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
        for role in specification.roles:
            connection.execute(sql.SQL("ALTER ROLE {} NOINHERIT").format(sql.Identifier(role.name)))
            role_attributes = connection.execute(
                """
SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole,
       rolreplication, rolbypassrls
FROM pg_catalog.pg_roles
WHERE rolname = %s
""",
                (role.name,),
            ).fetchone()
            expected_attributes = (
                True,
                role.inherit,
                False,
                False,
                False,
                False,
                False,
            )
            if role_attributes != expected_attributes:
                raise RuntimeError(f"cloud database role {role.name} is not restricted")
        connection.execute(
            sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                sql.Identifier(specification.database)
            )
        )
        connection.execute(
            sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                sql.Identifier(specification.database),
                sql.Identifier(specification.owner.name),
            )
        )
        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(specification.database),
                sql.Identifier(specification.owner.name),
            )
        )
        connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        connection.execute(
            sql.SQL("ALTER SCHEMA public OWNER TO {}").format(
                sql.Identifier(specification.owner.name)
            )
        )
        for connect_role in specification.connect_roles:
            connection.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(specification.database),
                    sql.Identifier(connect_role.name),
                )
            )
        for statement in (
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
            "REVOKE ALL ON TABLES FROM PUBLIC",
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
            "REVOKE ALL ON SEQUENCES FROM PUBLIC",
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
            "REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC",
        ):
            connection.execute(sql.SQL(statement).format(sql.Identifier(specification.owner.name)))


def main() -> int:
    for specification in BOOTSTRAPS:
        connection_url = os.environ.get(specification.environment_name)
        if not connection_url:
            raise RuntimeError(f"{specification.environment_name} is required")
        apply_bootstrap(specification, connection_url)
    print("Shared-development database ownership is ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
