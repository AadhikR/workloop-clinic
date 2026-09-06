import asyncio
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any, cast

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine

from app.auth.application_user import (
    ApplicationUserResolver,
    ApplicationUserUnavailableError,
    AuthorizationPrincipal,
)
from app.auth.scopes import (
    branch_authorization_scope,
    direct_report_authorization_scope,
    employee_self_authorization_scope,
    expiry_processing_authorization_scope,
    tenant_authorization_scope,
)
from app.db.seed import constants as c
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.models.identity import AccountStatus, AppRole

RLS_TABLES = (
    "companies",
    "branches",
    "app_users",
    "user_profiles",
    "employees",
    "employee_job_history",
    "departments",
    "department_staffing_rules",
)

POLICIES = {
    ("companies", "phase5e_companies_select_runtime", "SELECT", "workloop_runtime"),
    ("companies", "phase5e_companies_update_runtime", "UPDATE", "workloop_runtime"),
    (
        "companies",
        "phase5e_companies_select_expiry",
        "SELECT",
        "workloop_expiry_processing",
    ),
    ("branches", "phase5e_branches_select_runtime", "SELECT", "workloop_runtime"),
    ("branches", "phase5e_branches_insert_runtime", "INSERT", "workloop_runtime"),
    ("branches", "phase5e_branches_update_runtime", "UPDATE", "workloop_runtime"),
    ("branches", "phase5e_branches_delete_runtime", "DELETE", "workloop_runtime"),
    (
        "branches",
        "phase5e_branches_select_expiry",
        "SELECT",
        "workloop_expiry_processing",
    ),
    ("app_users", "phase5e_app_users_select_runtime", "SELECT", "workloop_runtime"),
    (
        "app_users",
        "phase5e_app_users_select_expiry",
        "SELECT",
        "workloop_expiry_processing",
    ),
    (
        "user_profiles",
        "phase5e_user_profiles_select_runtime",
        "SELECT",
        "workloop_runtime",
    ),
    (
        "user_profiles",
        "phase5e_user_profiles_update_runtime",
        "UPDATE",
        "workloop_runtime",
    ),
    (
        "user_profiles",
        "phase5e_user_profiles_select_expiry",
        "SELECT",
        "workloop_expiry_processing",
    ),
    ("employees", "phase5e_employees_select_runtime", "SELECT", "workloop_runtime"),
    ("employees", "phase5e_employees_insert_runtime", "INSERT", "workloop_runtime"),
    ("employees", "phase5e_employees_update_runtime", "UPDATE", "workloop_runtime"),
    (
        "employees",
        "phase5e_employees_select_expiry",
        "SELECT",
        "workloop_expiry_processing",
    ),
    (
        "employee_job_history",
        "phase5e_employee_job_history_select_runtime",
        "SELECT",
        "workloop_runtime",
    ),
    (
        "employee_job_history",
        "phase5e_employee_job_history_insert_runtime",
        "INSERT",
        "workloop_runtime",
    ),
    ("departments", "phase5e_departments_select_runtime", "SELECT", "workloop_runtime"),
    ("departments", "phase5e_departments_insert_runtime", "INSERT", "workloop_runtime"),
    ("departments", "phase5e_departments_update_runtime", "UPDATE", "workloop_runtime"),
    ("departments", "phase5e_departments_delete_runtime", "DELETE", "workloop_runtime"),
    (
        "department_staffing_rules",
        "phase5e_department_staffing_rules_select_runtime",
        "SELECT",
        "workloop_runtime",
    ),
    (
        "department_staffing_rules",
        "phase5e_department_staffing_rules_insert_runtime",
        "INSERT",
        "workloop_runtime",
    ),
    (
        "department_staffing_rules",
        "phase5e_department_staffing_rules_update_runtime",
        "UPDATE",
        "workloop_runtime",
    ),
    (
        "department_staffing_rules",
        "phase5e_department_staffing_rules_delete_runtime",
        "DELETE",
        "workloop_runtime",
    ),
}

RUNTIME_GRANTS = {
    "companies": {"SELECT", "UPDATE"},
    "branches": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "app_users": {"SELECT"},
    "user_profiles": {"SELECT"},
    "employees": {"SELECT", "INSERT", "UPDATE"},
    "employee_job_history": {"SELECT", "INSERT"},
    "departments": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "department_staffing_rules": {"SELECT", "INSERT", "UPDATE", "DELETE"},
}

EXPIRY_COLUMNS = {
    "companies": {"id"},
    "branches": {"id", "company_id"},
    "app_users": {"id", "status"},
    "user_profiles": {"app_user_id", "company_id", "employee_id", "role"},
    "employees": {
        "id",
        "company_id",
        "branch_id",
        "name",
        "active",
        "employment_status",
        "probation_end_date",
        "contract_type",
        "contract_end_date",
        "visa_expiry",
        "passport_expiry",
        "emirates_id_expiry",
        "labour_card_expiry",
        "licence_authority",
        "licence_expiry",
    },
}


def row_values(table: str, **matches: object) -> dict[str, object]:
    candidates = [
        row.values
        for row in build_rows()
        if row.table == table
        and all(row.values.get(key) == value for key, value in matches.items())
    ]
    if len(candidates) != 1:
        raise AssertionError(f"expected one synthetic {table} row")
    return candidates[0]


def principal_for(subject: str) -> AuthorizationPrincipal:
    app_user = row_values("app_users", identity_subject=subject)
    profile = row_values("user_profiles", app_user_id=app_user["id"])
    employee_id = cast(uuid.UUID | None, profile["employee_id"])
    employee = None if employee_id is None else row_values("employees", id=employee_id)
    return AuthorizationPrincipal(
        app_user_id=cast(uuid.UUID, app_user["id"]),
        account_status=AccountStatus.ACTIVE,
        role=AppRole(cast(str, profile["role"])),
        company_id=cast(uuid.UUID, profile["company_id"]),
        employee_id=employee_id,
        branch_id=None if employee is None else cast(uuid.UUID, employee["branch_id"]),
    )


def connect_as(role: str) -> psycopg.Connection[Any]:
    password_key = {
        "workloop_runtime": "WORKLOOP_RUNTIME_PASSWORD",
        "workloop_expiry_processing": "WORKLOOP_EXPIRY_PROCESSING_PASSWORD",
    }[role]
    return psycopg.connect(
        host="postgres",
        dbname="workloop",
        user=role,
        password=os.environ[password_key],
        autocommit=True,
    )


async def verify_application_resolution() -> None:
    engine = create_async_engine(
        URL.create(
            "postgresql+psycopg",
            username="workloop_runtime",
            password=os.environ["WORKLOOP_RUNTIME_PASSWORD"],
            host="postgres",
            database="workloop",
        )
    )
    resolver = ApplicationUserResolver(
        engine=engine,
        issuer=c.SEED_ISSUER,
        timeout_seconds=2,
    )
    try:
        for subject in (
            "hr.admin@horizon.test",
            "aisha.manager@horizon.test",
            "ravi.employee@horizon.test",
        ):
            assert await resolver.resolve(issuer=c.SEED_ISSUER, subject=subject) == principal_for(
                subject
            )
        try:
            await resolver.resolve(issuer=c.SEED_ISSUER, subject="guessed-subject")
        except ApplicationUserUnavailableError:
            pass
        else:
            raise AssertionError("the application resolved a guessed subject")
    finally:
        await engine.dispose()


def set_value(cursor: psycopg.Cursor[Any], key: str, value: object | None) -> None:
    cursor.execute(
        "SELECT pg_catalog.set_config(%s, %s, true)",
        (key, "" if value is None else str(value)),
    )


@contextmanager
def human_context(
    connection: psycopg.Connection[Any],
    subject: str,
    *,
    branch_id: uuid.UUID | None = None,
    overrides: dict[str, object | None] | None = None,
) -> Iterator[psycopg.Cursor[Any]]:
    principal = principal_for(subject)
    selected_branch = principal.branch_id if principal.role is not AppRole.ADMIN else branch_id
    values: dict[str, object | None] = {
        "workloop.identity_issuer": c.SEED_ISSUER,
        "workloop.identity_subject": subject,
        "workloop.app_user_id": principal.app_user_id,
        "workloop.role": principal.role.value,
        "workloop.company_id": principal.company_id,
        "workloop.employee_id": principal.employee_id,
        "workloop.branch_id": selected_branch,
        "workloop.actor_kind": "human",
        "workloop.actor_key": None,
        "workloop.business_date": date(2026, 9, 6),
    }
    values.update(overrides or {})
    with connection.transaction(), connection.cursor() as cursor:
        for key, value in values.items():
            set_value(cursor, key, value)
        yield cursor


@contextmanager
def job_context(
    connection: psycopg.Connection[Any],
    *,
    company_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    actor_kind: str = "scheduled_job",
    actor_key: str = "expiry_processing",
) -> Iterator[psycopg.Cursor[Any]]:
    with connection.transaction(), connection.cursor() as cursor:
        for key, value in {
            "workloop.company_id": company_id,
            "workloop.branch_id": branch_id,
            "workloop.actor_kind": actor_kind,
            "workloop.actor_key": actor_key,
            "workloop.business_date": date(2026, 9, 6),
        }.items():
            set_value(cursor, key, value)
        yield cursor


def scalar(cursor: psycopg.Cursor[Any], sql: str, values: tuple[object, ...] = ()) -> Any:
    cursor.execute(sql, values)
    row = cursor.fetchone()
    if row is None:
        raise AssertionError("query returned no scalar row")
    return row[0]


def owner_scalar(engine: Any, sql: str, values: dict[str, object] | None = None) -> Any:
    from sqlalchemy import text

    with engine.connect() as connection:
        return connection.execute(text(sql), values or {}).scalar_one()


def assert_denied_mutation(
    runtime: psycopg.Connection[Any],
    engine: Any,
    *,
    subject: str,
    branch_id: uuid.UUID | None,
    sql: str,
    values: tuple[object, ...],
    state_sql: str,
    state_values: dict[str, object],
) -> None:
    before = owner_scalar(engine, state_sql, state_values)
    try:
        with human_context(runtime, subject, branch_id=branch_id) as cursor:
            cursor.execute(sql, values)
            assert cursor.rowcount == 0
    except psycopg.errors.InsufficientPrivilege:
        pass
    after = owner_scalar(engine, state_sql, state_values)
    assert after == before


def verify_catalog(engine: Any) -> None:
    from sqlalchemy import text

    with engine.connect() as connection:
        actual_policies = {
            (row.tablename, row.policyname, row.cmd, row.roles[0])
            for row in connection.execute(
                text(
                    """
SELECT tablename, policyname, cmd, roles
FROM pg_catalog.pg_policies
WHERE schemaname = 'public'
"""
                )
            )
        }
        assert actual_policies == POLICIES

        rows = connection.execute(
            text(
                """
SELECT tablename, policyname, cmd, qual, with_check
FROM pg_catalog.pg_policies
WHERE schemaname = 'public'
"""
            )
        ).mappings()
        seen_commands: set[tuple[str, str, str]] = set()
        for row in rows:
            command = cast(str, row["cmd"])
            role = next(item[3] for item in POLICIES if item[1] == row["policyname"])
            key = (cast(str, row["tablename"]), role, command)
            assert key not in seen_commands
            seen_commands.add(key)
            assert (row["qual"] is not None) == (command in {"SELECT", "UPDATE", "DELETE"})
            assert (row["with_check"] is not None) == (command in {"INSERT", "UPDATE"})
            expression = f"{row['qual']} {row['with_check']}".lower()
            assert not any(
                term in expression
                for term in ("auth.", "storage.", "authenticated", "service_role")
            )
            if role == "workloop_expiry_processing":
                assert "workloop_expiry_processing" in expression
                assert "expiry_processing" in expression
                assert "workloop_company_id" in expression
                assert "workloop_branch_id" in expression
            elif row["policyname"] == "phase5e_app_users_select_runtime":
                assert "workloop_identity_issuer" in expression
                assert "workloop_identity_subject" in expression
                assert "resolve_workloop_principal" not in expression
            else:
                assert "resolve_workloop_principal" in expression
                assert "workloop_business_date" in expression

        flags = connection.execute(
            text(
                """
SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
"""
            )
        ).all()
        enabled = {name for name, rls, force in flags if rls and not force}
        assert enabled == set(RLS_TABLES)
        assert not any(force for _, _, force in flags)

        runtime_grants = connection.execute(
            text(
                """
SELECT table_name, privilege_type
FROM information_schema.role_table_grants
WHERE table_schema = 'public' AND grantee = 'workloop_runtime'
  AND table_name = ANY(:tables)
"""
            ),
            {"tables": list(RLS_TABLES)},
        ).all()
        grouped_runtime = {table: set() for table in RLS_TABLES}
        for table, privilege in runtime_grants:
            grouped_runtime[table].add(privilege)
        assert grouped_runtime == RUNTIME_GRANTS

        profile_updates = connection.execute(
            text(
                """
SELECT column_name
FROM information_schema.column_privileges
WHERE table_schema = 'public' AND table_name = 'user_profiles'
  AND grantee = 'workloop_runtime' AND privilege_type = 'UPDATE'
"""
            )
        ).scalars()
        assert set(profile_updates) == {"role"}

        expiry_grants = connection.execute(
            text(
                """
SELECT table_name, column_name
FROM information_schema.column_privileges
WHERE table_schema = 'public' AND grantee = 'workloop_expiry_processing'
  AND privilege_type = 'SELECT'
"""
            )
        ).all()
        grouped_expiry: dict[str, set[str]] = {}
        for table, column in expiry_grants:
            grouped_expiry.setdefault(table, set()).add(column)
        assert grouped_expiry == EXPIRY_COLUMNS

        functions = connection.execute(
            text(
                """
SELECT p.proname, pg_catalog.pg_get_userbyid(p.proowner), p.prosecdef,
       p.provolatile, p.proconfig,
       pg_catalog.pg_get_function_identity_arguments(p.oid),
       pg_catalog.pg_get_function_result(p.oid), p.proretset, p.prorows,
       pg_catalog.has_function_privilege('workloop_runtime', p.oid, 'EXECUTE'),
       pg_catalog.has_function_privilege('workloop_expiry_processing', p.oid, 'EXECUTE'),
       pg_catalog.has_function_privilege('public', p.oid, 'EXECUTE')
FROM pg_catalog.pg_proc AS p
JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND p.proname IN ('resolve_workloop_principal', 'is_scoped_active_app_user')
"""
            )
        ).all()
        assert len(functions) == 2
        function_shapes = {
            name: (arguments, result, returns_set, rows)
            for (
                name,
                _,
                _,
                _,
                _,
                arguments,
                result,
                returns_set,
                rows,
                _,
                _,
                _,
            ) in functions
        }
        assert function_shapes == {
            "is_scoped_active_app_user": (
                "p_app_user_id uuid",
                "boolean",
                False,
                0.0,
            ),
            "resolve_workloop_principal": (
                "",
                "TABLE(app_user_id uuid, account_status text, profile_app_user_id uuid, "
                "profile_company_id uuid, role text, profile_employee_id uuid, "
                "company_id uuid, employee_id uuid, employee_company_id uuid, "
                "employee_branch_id uuid, employee_active boolean, employment_status text, "
                "branch_id uuid, branch_company_id uuid)",
                True,
                1.0,
            ),
        }
        for (
            _,
            owner,
            definer,
            volatility,
            config,
            _,
            _,
            _,
            _,
            runtime,
            expiry,
            public,
        ) in functions:
            assert owner == "workloop_migration"
            assert definer and volatility == "s"
            assert config == ["search_path=pg_catalog, public, pg_temp"]
            assert runtime and not expiry and not public

        helper_acls = set(
            connection.execute(
                text(
                    """
SELECT p.proname, pg_catalog.pg_get_userbyid(acl.grantee),
       acl.privilege_type, acl.is_grantable
FROM pg_catalog.pg_proc AS p
JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
CROSS JOIN LATERAL pg_catalog.aclexplode(p.proacl) AS acl
WHERE n.nspname = 'public'
  AND p.proname IN ('resolve_workloop_principal', 'is_scoped_active_app_user')
"""
                )
            ).all()
        )
        assert helper_acls == {
            (name, role, "EXECUTE", False)
            for name in ("resolve_workloop_principal", "is_scoped_active_app_user")
            for role in ("workloop_migration", "workloop_runtime")
        }

        expiry_functions = set(
            connection.execute(
                text(
                    """
SELECT p.proname
FROM pg_catalog.pg_proc AS p
JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND pg_catalog.has_function_privilege(
    'workloop_expiry_processing', p.oid, 'EXECUTE'
  )
"""
                )
            ).scalars()
        )
        assert expiry_functions == {
            "workloop_company_id",
            "workloop_branch_id",
            "workloop_actor_kind",
            "workloop_actor_key",
            "workloop_business_date",
        }

        roles = connection.execute(
            text(
                """
SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb,
       rolcanlogin, rolreplication, rolbypassrls
FROM pg_catalog.pg_roles
WHERE rolname IN ('workloop_runtime', 'workloop_expiry_processing')
ORDER BY rolname
"""
            )
        ).all()
        assert roles == [
            ("workloop_expiry_processing", False, False, False, False, True, False, False),
            ("workloop_runtime", False, True, False, False, True, False, False),
        ]
        memberships = connection.execute(
            text(
                """
SELECT count(*)
FROM pg_catalog.pg_auth_members AS membership
JOIN pg_catalog.pg_roles AS member ON member.oid = membership.member
JOIN pg_catalog.pg_roles AS granted ON granted.oid = membership.roleid
WHERE member.rolname IN ('workloop_runtime', 'workloop_expiry_processing')
   OR granted.rolname IN ('workloop_runtime', 'workloop_expiry_processing')
"""
            )
        ).scalar_one()
        assert memberships == 0
        for role in ("workloop_runtime", "workloop_expiry_processing"):
            assert not connection.execute(
                text("SELECT pg_catalog.has_schema_privilege(:role, 'public', 'CREATE')"),
                {"role": role},
            ).scalar_one()
        assert connection.execute(
            text(
                "SELECT pg_catalog.has_database_privilege("
                "'workloop_expiry_processing', current_database(), 'CONNECT')"
            )
        ).scalar_one()
        assert not connection.execute(
            text(
                "SELECT pg_catalog.has_database_privilege("
                "'workloop_expiry_processing', current_database(), 'TEMPORARY')"
            )
        ).scalar_one()

        non_migration_owners = connection.execute(
            text(
                """
SELECT count(*)
FROM pg_catalog.pg_class AS object
JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = object.relnamespace
WHERE namespace.nspname = 'public'
  AND object.relkind IN ('r', 'p', 'S', 'v', 'm')
  AND pg_catalog.pg_get_userbyid(object.relowner) <> 'workloop_migration'
"""
            )
        ).scalar_one()
        assert non_migration_owners == 0


def verify_role_boundaries(
    runtime: psycopg.Connection[Any], expiry: psycopg.Connection[Any]
) -> None:
    for connection in (runtime, expiry):
        for sql in (
            "SET ROLE workloop_migration",
            "CREATE TABLE public.phase5e_forbidden_create (id integer)",
        ):
            try:
                with connection.transaction(), connection.cursor() as cursor:
                    cursor.execute(sql)
            except psycopg.errors.InsufficientPrivilege:
                pass
            else:
                raise AssertionError("a protected login gained a privileged capability")


def verify_bootstrap(runtime: psycopg.Connection[Any]) -> None:
    with runtime.transaction(), runtime.cursor() as cursor:
        set_value(cursor, "workloop.identity_issuer", c.SEED_ISSUER)
        set_value(cursor, "workloop.identity_subject", "hr.admin@horizon.test")
        assert scalar(cursor, "SELECT count(*) FROM app_users") == 1
        cursor.execute("SELECT * FROM public.resolve_workloop_principal()")
        resolved = cursor.fetchone()
        assert resolved is not None
        assert resolved[0] == c.ADMIN_APP_USER[c.HORIZON]
        assert resolved[4] == "admin"
        for table in ("companies", "branches", "user_profiles", "employees"):
            assert scalar(cursor, f"SELECT count(*) FROM {table}") == 0

    for issuer, subject in (
        ("https://wrong.test", "hr.admin@horizon.test"),
        (c.SEED_ISSUER, "wrong-subject"),
        ("", "hr.admin@horizon.test"),
        (c.SEED_ISSUER, "x" * 256),
    ):
        with runtime.transaction(), runtime.cursor() as cursor:
            set_value(cursor, "workloop.identity_issuer", issuer)
            set_value(cursor, "workloop.identity_subject", subject)
            assert scalar(cursor, "SELECT count(*) FROM app_users") == 0
            assert scalar(cursor, "SELECT count(*) FROM resolve_workloop_principal()") == 0


def verify_human_scope(runtime: psycopg.Connection[Any], engine: Any) -> None:
    admin = principal_for("hr.admin@horizon.test")
    cedar_admin = principal_for("hr.admin@cedar.test")
    manager = principal_for("aisha.manager@horizon.test")
    employee = principal_for("ravi.employee@horizon.test")
    other_branch_employee = principal_for("leila.employee@horizon.test")

    assert tenant_authorization_scope(admin).company_id == admin.company_id
    assert (
        branch_authorization_scope(admin, verified_admin_branch_id=c.BRANCH_DXB).branch_id
        == c.BRANCH_DXB
    )
    assert employee_self_authorization_scope(employee).employee_id == employee.employee_id
    assert direct_report_authorization_scope(manager).manager_employee_id == manager.employee_id

    with human_context(runtime, "hr.admin@horizon.test") as cursor:
        assert scalar(cursor, "SELECT count(*) FROM companies") == 1
        assert scalar(cursor, "SELECT count(*) FROM branches") == 2
        assert scalar(cursor, "SELECT count(*) FROM employees") == 0
        assert scalar(cursor, "SELECT count(*) FROM user_profiles") > 1
        cursor.execute("UPDATE companies SET name = name WHERE id = %s", (admin.company_id,))
        assert cursor.rowcount == 1
        assert scalar(
            cursor,
            "SELECT public.is_scoped_active_app_user(%s)",
            (employee.app_user_id,),
        )
        assert not scalar(
            cursor,
            "SELECT public.is_scoped_active_app_user(%s)",
            (cedar_admin.app_user_id,),
        )
        cursor.execute(
            "UPDATE user_profiles SET role = 'manager' WHERE app_user_id = %s",
            (employee.app_user_id,),
        )
        assert cursor.rowcount == 1
        cursor.execute(
            "UPDATE user_profiles SET role = 'employee' WHERE app_user_id = %s",
            (employee.app_user_id,),
        )
        assert cursor.rowcount == 1
        new_branch = uuid.uuid4()
        cursor.execute(
            "INSERT INTO branches (id, company_id, name) VALUES (%s, %s, %s)",
            (new_branch, admin.company_id, "Phase 5E synthetic branch"),
        )
        set_value(cursor, "workloop.branch_id", new_branch)
        cursor.execute("UPDATE branches SET address = 'synthetic' WHERE id = %s", (new_branch,))
        assert cursor.rowcount == 1
        cursor.execute("DELETE FROM branches WHERE id = %s", (new_branch,))
        assert cursor.rowcount == 1

    inserted_employee = uuid.uuid4()
    inserted_history = uuid.uuid4()
    try:
        with human_context(runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB) as cursor:
            assert scalar(cursor, "SELECT count(*) FROM branches") == 1
            assert scalar(cursor, "SELECT count(*) FROM employees") == 6
            assert scalar(cursor, "SELECT count(*) FROM departments") > 0
            assert scalar(cursor, "SELECT count(*) FROM department_staffing_rules") > 0
            cursor.execute(
                "UPDATE employees SET phone = phone WHERE id = %s",
                (employee.employee_id,),
            )
            assert cursor.rowcount == 1
            cursor.execute(
                "INSERT INTO employees (id, company_id, branch_id, name, mol_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    inserted_employee,
                    admin.company_id,
                    c.BRANCH_DXB,
                    "Phase 5E synthetic employee",
                    "90000000009999",
                ),
            )
            assert cursor.rowcount == 1
            cursor.execute(
                "INSERT INTO employee_job_history ("
                "id, company_id, branch_id, employee_id, changed_by_app_user_id, "
                "change_type, old_value, new_value, reason"
                ") VALUES (%s, %s, %s, %s, %s, 'title_change', 'old', 'new', 'test')",
                (
                    inserted_history,
                    admin.company_id,
                    c.BRANCH_DXB,
                    employee.employee_id,
                    admin.app_user_id,
                ),
            )
            assert cursor.rowcount == 1

            department_id = uuid.uuid4()
            cursor.execute(
                "INSERT INTO departments (id, company_id, branch_id, name) VALUES (%s, %s, %s, %s)",
                (department_id, admin.company_id, c.BRANCH_DXB, "Phase 5E department"),
            )
            assert cursor.rowcount == 1
            cursor.execute(
                "UPDATE departments SET description = 'synthetic' WHERE id = %s",
                (department_id,),
            )
            assert cursor.rowcount == 1

            staffing_id = uuid.uuid4()
            cursor.execute(
                "INSERT INTO department_staffing_rules ("
                "id, company_id, branch_id, department, shift_category, min_staff"
                ") VALUES (%s, %s, %s, %s, 'morning', 1)",
                (staffing_id, admin.company_id, c.BRANCH_DXB, "Phase 5E department"),
            )
            assert cursor.rowcount == 1
            cursor.execute(
                "UPDATE department_staffing_rules SET min_staff = 2 WHERE id = %s",
                (staffing_id,),
            )
            assert cursor.rowcount == 1
            cursor.execute("DELETE FROM department_staffing_rules WHERE id = %s", (staffing_id,))
            assert cursor.rowcount == 1
            cursor.execute("DELETE FROM departments WHERE id = %s", (department_id,))
            assert cursor.rowcount == 1

            cursor.execute(
                "UPDATE user_profiles SET role = 'manager' WHERE app_user_id = %s",
                (employee.app_user_id,),
            )
            assert cursor.rowcount == 0
    finally:
        from sqlalchemy import text

        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM employee_job_history WHERE id = :id"),
                {"id": inserted_history},
            )
            connection.execute(
                text("DELETE FROM employees WHERE id = :id"), {"id": inserted_employee}
            )

    with human_context(runtime, "aisha.manager@horizon.test") as cursor:
        visible = set(row[0] for row in cursor.execute("SELECT id FROM employees").fetchall())
        assert manager.employee_id in visible
        assert employee.employee_id in visible
        assert other_branch_employee.employee_id not in visible
        assert scalar(cursor, "SELECT count(*) FROM departments") == 0
        assert scalar(cursor, "SELECT count(*) FROM employee_job_history") == 0
        assert scalar(cursor, "SELECT count(*) FROM user_profiles") == 1

    with human_context(runtime, "ravi.employee@horizon.test") as cursor:
        assert cursor.execute("SELECT id FROM employees").fetchall() == [(employee.employee_id,)]
        assert scalar(cursor, "SELECT count(*) FROM departments") == 0
        assert scalar(cursor, "SELECT count(*) FROM employee_job_history") == 0
        cursor.execute("UPDATE employees SET phone = phone WHERE id = %s", (employee.employee_id,))
        assert cursor.rowcount == 1

    assert_denied_mutation(
        runtime,
        engine,
        subject="hr.admin@horizon.test",
        branch_id=c.BRANCH_DXB,
        sql="UPDATE employees SET phone = 'denied' WHERE id = %s",
        values=(other_branch_employee.employee_id,),
        state_sql="SELECT phone FROM employees WHERE id = :id",
        state_values={"id": other_branch_employee.employee_id},
    )
    assert_denied_mutation(
        runtime,
        engine,
        subject="ravi.employee@horizon.test",
        branch_id=None,
        sql="UPDATE employees SET phone = 'denied' WHERE id = %s",
        values=(manager.employee_id,),
        state_sql="SELECT phone FROM employees WHERE id = :id",
        state_values={"id": manager.employee_id},
    )
    assert_denied_mutation(
        runtime,
        engine,
        subject="aisha.manager@horizon.test",
        branch_id=None,
        sql="UPDATE user_profiles SET role = 'manager' WHERE app_user_id = %s",
        values=(employee.app_user_id,),
        state_sql="SELECT role::text FROM user_profiles WHERE app_user_id = :id",
        state_values={"id": employee.app_user_id},
    )
    assert_denied_mutation(
        runtime,
        engine,
        subject="hr.admin@horizon.test",
        branch_id=None,
        sql="UPDATE companies SET name = 'denied' WHERE id = %s",
        values=(cedar_admin.company_id,),
        state_sql="SELECT name FROM companies WHERE id = :id",
        state_values={"id": cedar_admin.company_id},
    )
    assert_denied_mutation(
        runtime,
        engine,
        subject="hr.admin@horizon.test",
        branch_id=c.BRANCH_DXB,
        sql="UPDATE app_users SET status = 'disabled' WHERE id = %s",
        values=(admin.app_user_id,),
        state_sql="SELECT status::text FROM app_users WHERE id = :id",
        state_values={"id": admin.app_user_id},
    )

    with human_context(
        runtime,
        "ravi.employee@horizon.test",
        overrides={"workloop.company_id": uuid.uuid4()},
    ) as cursor:
        assert scalar(cursor, "SELECT count(*) FROM employees") == 0
    with human_context(
        runtime,
        "ravi.employee@horizon.test",
        overrides={"workloop.app_user_id": uuid.uuid4()},
    ) as cursor:
        assert scalar(cursor, "SELECT count(*) FROM employees") == 0
    with human_context(
        runtime,
        "ravi.employee@horizon.test",
        overrides={"workloop.company_id": "malformed"},
    ) as cursor:
        assert scalar(cursor, "SELECT count(*) FROM employees") == 0
    with runtime.transaction(), runtime.cursor() as cursor:
        assert scalar(cursor, "SELECT count(*) FROM employees") == 0


def verify_stale_state(runtime: psycopg.Connection[Any], engine: Any) -> None:
    from sqlalchemy import text

    manager = principal_for("aisha.manager@horizon.test")
    employee = principal_for("ravi.employee@horizon.test")
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE app_users SET status = 'disabled' WHERE id = :id"),
                {"id": employee.app_user_id},
            )
        with human_context(runtime, "ravi.employee@horizon.test") as cursor:
            assert scalar(cursor, "SELECT count(*) FROM employees") == 0
            assert scalar(cursor, "SELECT count(*) FROM app_users") == 0
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE app_users SET status = 'active' WHERE id = :id"),
                {"id": employee.app_user_id},
            )

    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE employees SET active = false WHERE id = :id"),
                {"id": manager.employee_id},
            )
        with human_context(runtime, "aisha.manager@horizon.test") as cursor:
            assert scalar(cursor, "SELECT count(*) FROM employees") == 0
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE employees SET active = true WHERE id = :id"),
                {"id": manager.employee_id},
            )

    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE employees SET reporting_manager_id = NULL WHERE id = :id"),
                {"id": employee.employee_id},
            )
        with human_context(runtime, "aisha.manager@horizon.test") as cursor:
            assert (
                scalar(
                    cursor,
                    "SELECT count(*) FROM employees WHERE id = %s",
                    (employee.employee_id,),
                )
                == 0
            )
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE employees SET reporting_manager_id = :manager WHERE id = :id"),
                {"manager": manager.employee_id, "id": employee.employee_id},
            )


def verify_job_scope(expiry: psycopg.Connection[Any], engine: Any) -> None:
    horizon = principal_for("hr.admin@horizon.test")
    cedar = principal_for("hr.admin@cedar.test")
    scope = expiry_processing_authorization_scope(
        database_actor="workloop_expiry_processing",
        company_id=horizon.company_id,
        branch_id=c.BRANCH_DXB,
        business_date=date(2026, 9, 6),
    )
    assert scope.company_id == horizon.company_id and scope.branch_id == c.BRANCH_DXB

    with job_context(expiry, company_id=horizon.company_id, branch_id=c.BRANCH_DXB) as cursor:
        assert cursor.execute("SELECT id FROM companies").fetchall() == [(horizon.company_id,)]
        assert cursor.execute("SELECT id FROM branches").fetchall() == [(c.BRANCH_DXB,)]
        assert cursor.execute("SELECT id FROM app_users").fetchall() == [(horizon.app_user_id,)]
        assert cursor.execute("SELECT app_user_id FROM user_profiles").fetchall() == [
            (horizon.app_user_id,)
        ]
        assert scalar(cursor, "SELECT count(*) FROM employees") == 6
        try:
            cursor.execute("SELECT mol_id FROM employees")
        except psycopg.errors.InsufficientPrivilege:
            pass
        else:
            raise AssertionError("expiry login read an excluded employee identity column")

    with job_context(expiry, company_id=horizon.company_id, branch_id=None) as cursor:
        assert cursor.execute("SELECT id FROM companies").fetchall() == [(horizon.company_id,)]
        assert cursor.execute("SELECT app_user_id FROM user_profiles").fetchall() == [
            (horizon.app_user_id,)
        ]
        assert scalar(cursor, "SELECT count(*) FROM employees") == 0

    with job_context(expiry, company_id=horizon.company_id, branch_id=c.BRANCH_SHJ) as cursor:
        assert scalar(cursor, "SELECT count(*) FROM companies") == 0
        assert scalar(cursor, "SELECT count(*) FROM branches") == 0
        assert scalar(cursor, "SELECT count(*) FROM employees") == 0

    for actor_kind, actor_key in (("human", "expiry_processing"), ("scheduled_job", "bad")):
        with job_context(
            expiry,
            company_id=cedar.company_id,
            branch_id=c.BRANCH_SHJ,
            actor_kind=actor_kind,
            actor_key=actor_key,
        ) as cursor:
            assert scalar(cursor, "SELECT count(*) FROM companies") == 0
            assert scalar(cursor, "SELECT count(*) FROM employees") == 0

    before = owner_scalar(
        engine,
        "SELECT phone FROM employees WHERE id = :id",
        {"id": principal_for("ravi.employee@horizon.test").employee_id},
    )
    try:
        with job_context(expiry, company_id=horizon.company_id, branch_id=c.BRANCH_DXB) as cursor:
            cursor.execute("UPDATE employees SET phone = 'denied'")
    except psycopg.errors.InsufficientPrivilege:
        pass
    else:
        raise AssertionError("expiry login received an employee mutation grant")
    after = owner_scalar(
        engine,
        "SELECT phone FROM employees WHERE id = :id",
        {"id": principal_for("ravi.employee@horizon.test").employee_id},
    )
    assert after == before


def main() -> None:
    migration_url = os.environ["MIGRATION_DATABASE_URL"]
    rows = build_rows()
    engine = create_engine(migration_url)
    runtime = connect_as("workloop_runtime")
    expiry = connect_as("workloop_expiry_processing")
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
        verify_catalog(engine)
        verify_role_boundaries(runtime, expiry)
        asyncio.run(verify_application_resolution())
        verify_bootstrap(runtime)
        verify_human_scope(runtime, engine)
        verify_stale_state(runtime, engine)
        verify_job_scope(expiry, engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT count(*) FROM companies").scalar_one() == 2
    finally:
        runtime.close()
        expiry.close()
        with engine.begin() as connection:
            clean(connection, rows)
        engine.dispose()

    print("Phase 5E identity, organization, workforce RLS, and grant checks passed.")


if __name__ == "__main__":
    main()
