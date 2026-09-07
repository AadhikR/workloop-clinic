import uuid
from collections.abc import Mapping
from typing import Any, cast

import pytest
from sqlalchemy import Update
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.elements import ClauseElement

from app.auth.application_user import AuthorizationPrincipal
from app.auth.scopes import (
    branch_authorization_scope,
    branch_scope_predicate,
    direct_report_authorization_scope,
    direct_report_scope_predicate,
)
from app.db.seed import constants as fixture_ids
from app.models.identity import AccountStatus, AppRole, Employee
from app.models.payroll import ExpenseClaim
from app.models.records import Appraisal, AppraisalSection
from app.repositories.scoped import (
    InvalidBatchError,
    MutationConflictError,
    RelationshipLockMode,
    ResourceNotFoundError,
    ScopedRepository,
    build_scoped_delete,
    build_scoped_lookup,
    build_scoped_update,
)
from app.schemas.mutations import GuardedMutationValues, MutationFieldGuard

VISIBLE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
INACCESSIBLE_ID = uuid.UUID("31000000-0000-4000-8000-000000000002")


def admin_scope_predicate() -> Any:
    principal = AuthorizationPrincipal(
        app_user_id=fixture_ids.ADMIN_APP_USER[fixture_ids.HORIZON],
        account_status=AccountStatus.ACTIVE,
        role=AppRole.ADMIN,
        company_id=fixture_ids.COMPANY_ID[fixture_ids.HORIZON],
        employee_id=None,
        branch_id=None,
    )
    scope = branch_authorization_scope(
        principal,
        verified_admin_branch_id=fixture_ids.BRANCH_DXB,
    )
    return branch_scope_predicate(
        Employee.__table__.c.company_id,
        Employee.__table__.c.branch_id,
        scope,
    )


def compile_statement(statement: ClauseElement) -> tuple[str, Mapping[str, object]]:
    compiled = statement.compile(dialect=postgresql.dialect())
    return str(compiled), cast(dict[str, object], compiled.params)


def guarded_values(**values: object) -> Any:
    guard = MutationFieldGuard(allowed_input_fields=frozenset(values))
    return guard.prepare(values)


def test_scoped_lookup_combines_object_identity_and_authorization() -> None:
    injection = "' OR TRUE --"
    statement = build_scoped_lookup(
        Employee.__table__,
        Employee.__table__.c.id,
        injection,
        admin_scope_predicate(),
    )

    sql, parameters = compile_statement(statement)
    assert "employees.id =" in sql
    assert "employees.company_id =" in sql
    assert "employees.branch_id =" in sql
    assert injection not in sql
    assert injection in parameters.values()


def test_scoped_update_repeats_identity_and_scope_predicates() -> None:
    statement = build_scoped_update(
        Employee.__table__,
        Employee.__table__.c.id,
        (VISIBLE_ID,),
        admin_scope_predicate(),
        guarded_values(phone="+971500000099"),
    )

    sql, parameters = compile_statement(statement)
    assert sql.startswith("UPDATE employees SET")
    assert "employees.id IN" in sql
    assert "employees.company_id =" in sql
    assert "employees.branch_id =" in sql
    assert fixture_ids.COMPANY_ID[fixture_ids.HORIZON] in parameters.values()
    assert fixture_ids.BRANCH_DXB in parameters.values()


def test_scoped_update_rejects_raw_request_values_at_runtime() -> None:
    with pytest.raises(TypeError):
        build_scoped_update(
            Employee.__table__,
            Employee.__table__.c.id,
            (VISIBLE_ID,),
            admin_scope_predicate(),
            cast(GuardedMutationValues, {"status": "Terminated"}),
        )


def test_scoped_delete_repeats_identity_and_scope_predicates() -> None:
    statement = build_scoped_delete(
        Employee.__table__,
        Employee.__table__.c.id,
        (VISIBLE_ID,),
        admin_scope_predicate(),
    )

    sql, _ = compile_statement(statement)
    assert sql.startswith("DELETE FROM employees")
    assert "employees.id IN" in sql
    assert "employees.company_id =" in sql
    assert "employees.branch_id =" in sql


@pytest.mark.parametrize("object_ids", [(), (VISIBLE_ID, VISIBLE_ID)])
def test_batch_builders_reject_empty_and_duplicate_identifiers(
    object_ids: tuple[uuid.UUID, ...],
) -> None:
    with pytest.raises(InvalidBatchError):
        build_scoped_delete(
            Employee.__table__,
            Employee.__table__.c.id,
            object_ids,
            admin_scope_predicate(),
        )


class _FakeMutationResult:
    def __init__(self, rowcount: int, scalar_values: tuple[uuid.UUID, ...] = ()) -> None:
        self.rowcount = rowcount
        self._scalar_values = scalar_values

    def scalars(self) -> "_FakeMutationResult":
        return self

    def all(self) -> tuple[uuid.UUID, ...]:
        return self._scalar_values


class _FakeNestedTransaction:
    def __init__(self, connection: "_FakeMutationConnection") -> None:
        self._connection = connection
        self._snapshot: dict[uuid.UUID, str] = {}

    async def __aenter__(self) -> "_FakeNestedTransaction":
        self._snapshot = dict(self._connection.state)
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object,
    ) -> None:
        if exception_type is not None:
            self._connection.state = self._snapshot
            self._connection.rolled_back = True


class _FakeMutationConnection:
    def __init__(
        self,
        *,
        visible_ids: tuple[uuid.UUID, ...] = (VISIBLE_ID,),
        update_rowcount: int = 1,
    ) -> None:
        self.state = {VISIBLE_ID: "old", INACCESSIBLE_ID: "other-tenant"}
        self.rolled_back = False
        self.statements: list[object] = []
        self.visible_ids = visible_ids
        self.update_rowcount = update_rowcount

    def begin_nested(self) -> _FakeNestedTransaction:
        return _FakeNestedTransaction(self)

    async def execute(self, statement: object) -> _FakeMutationResult:
        self.statements.append(statement)
        if isinstance(statement, Update):
            self.state[VISIBLE_ID] = "new"
            return _FakeMutationResult(rowcount=self.update_rowcount)
        return _FakeMutationResult(rowcount=len(self.visible_ids), scalar_values=self.visible_ids)


@pytest.mark.asyncio
async def test_mixed_scope_batch_update_rolls_back_every_change() -> None:
    connection = _FakeMutationConnection()
    repository = ScopedRepository(
        connection=cast(AsyncConnection, connection),
        table=Employee.__table__,
        id_column=Employee.__table__.c.id,
        scope_predicate=admin_scope_predicate(),
        relationship_lock=RelationshipLockMode.STABLE,
    )

    with pytest.raises(ResourceNotFoundError):
        await repository.update_batch(
            (VISIBLE_ID, INACCESSIBLE_ID),
            guarded_values(phone="+971500000099"),
        )

    assert connection.state == {VISIBLE_ID: "old", INACCESSIBLE_ID: "other-tenant"}
    assert connection.rolled_back is True
    assert len(connection.statements) == 1


@pytest.mark.asyncio
async def test_affected_row_mismatch_rolls_back_after_batch_validation() -> None:
    connection = _FakeMutationConnection(update_rowcount=0)
    repository = ScopedRepository(
        connection=cast(AsyncConnection, connection),
        table=Employee.__table__,
        id_column=Employee.__table__.c.id,
        scope_predicate=admin_scope_predicate(),
        relationship_lock=RelationshipLockMode.STABLE,
    )

    with pytest.raises(MutationConflictError):
        await repository.update_one(
            VISIBLE_ID,
            guarded_values(phone="+971500000099"),
        )

    assert connection.state[VISIBLE_ID] == "old"
    assert connection.rolled_back is True
    assert len(connection.statements) == 2


@pytest.mark.asyncio
async def test_report_mutation_locks_relationship_before_business_row() -> None:
    employee_id = uuid.uuid4()

    class RelationshipResult:
        def __init__(self, *, rows: tuple[tuple[uuid.UUID, uuid.UUID], ...] = ()) -> None:
            self.rows = rows
            self.rowcount = 1

        def all(self) -> tuple[tuple[uuid.UUID, uuid.UUID], ...]:
            return self.rows

        def scalars(self) -> "RelationshipResult":
            return self

    class RelationshipConnection(_FakeMutationConnection):
        async def execute(
            self,
            statement: object,
            parameters: Mapping[str, object] | None = None,
        ) -> Any:
            self.statements.append(statement)
            call = len(self.statements)
            if call == 1:
                return RelationshipResult(rows=((VISIBLE_ID, employee_id),))
            if call == 2:
                assert "lock_authorized_employee_relationships" in str(statement)
                assert parameters == {"employee_ids": [employee_id]}
                return RelationshipResult()
            if call == 3:
                return _FakeMutationResult(rowcount=1, scalar_values=(VISIBLE_ID,))
            if isinstance(statement, Update):
                self.state[VISIBLE_ID] = "new"
                return _FakeMutationResult(rowcount=1)
            raise AssertionError("unexpected relationship-lock statement")

    connection = RelationshipConnection()
    scope = branch_scope_predicate(
        ExpenseClaim.__table__.c.company_id,
        ExpenseClaim.__table__.c.branch_id,
        branch_authorization_scope(
            AuthorizationPrincipal(
                app_user_id=fixture_ids.ADMIN_APP_USER[fixture_ids.HORIZON],
                account_status=AccountStatus.ACTIVE,
                role=AppRole.ADMIN,
                company_id=fixture_ids.COMPANY_ID[fixture_ids.HORIZON],
                employee_id=None,
                branch_id=None,
            ),
            verified_admin_branch_id=fixture_ids.BRANCH_DXB,
        ),
    )
    repository = ScopedRepository(
        connection=cast(AsyncConnection, connection),
        table=ExpenseClaim.__table__,
        id_column=ExpenseClaim.__table__.c.id,
        scope_predicate=scope,
        relationship_lock=RelationshipLockMode.DIRECT_REPORT,
        authorization_employee_column=ExpenseClaim.__table__.c.employee_id,
        authorization_from=ExpenseClaim.__table__,
    )

    await repository.update_one(
        VISIBLE_ID,
        guarded_values(description="Updated description"),
    )

    assert len(connection.statements) == 4
    assert "lock_authorized_employee_relationships" in str(connection.statements[1])


def test_direct_report_repository_requires_explicit_employee_column() -> None:
    connection = _FakeMutationConnection()
    with pytest.raises(
        ValueError,
        match="direct-report mutations require an authorization employee column and source",
    ):
        ScopedRepository(
            connection=cast(AsyncConnection, connection),
            table=ExpenseClaim.__table__,
            id_column=ExpenseClaim.__table__.c.id,
            scope_predicate=admin_scope_predicate(),
            relationship_lock=RelationshipLockMode.DIRECT_REPORT,
        )


def test_repository_rejects_untyped_relationship_lock_mode() -> None:
    connection = _FakeMutationConnection()
    with pytest.raises(TypeError, match="relationship lock mode must be explicit"):
        ScopedRepository(
            connection=cast(AsyncConnection, connection),
            table=ExpenseClaim.__table__,
            id_column=ExpenseClaim.__table__.c.id,
            scope_predicate=admin_scope_predicate(),
            relationship_lock=cast(Any, "direct_report"),
        )


@pytest.mark.asyncio
async def test_nested_report_mutation_resolves_employee_before_locking() -> None:
    employee_id = uuid.uuid4()

    class NestedResult:
        def __init__(self, rows: tuple[tuple[uuid.UUID, uuid.UUID], ...] = ()) -> None:
            self.rows = rows
            self.rowcount = 1

        def all(self) -> tuple[tuple[uuid.UUID, uuid.UUID], ...]:
            return self.rows

        def scalars(self) -> "NestedResult":
            return self

    class NestedConnection(_FakeMutationConnection):
        async def execute(
            self,
            statement: object,
            parameters: Mapping[str, object] | None = None,
        ) -> Any:
            self.statements.append(statement)
            call = len(self.statements)
            if call == 1:
                assert "JOIN appraisals" in str(statement)
                return NestedResult(((VISIBLE_ID, employee_id),))
            if call == 2:
                assert parameters == {"employee_ids": [employee_id]}
                return NestedResult()
            if call == 3:
                return _FakeMutationResult(rowcount=1, scalar_values=(VISIBLE_ID,))
            if isinstance(statement, Update):
                return _FakeMutationResult(rowcount=1)
            raise AssertionError("unexpected nested relationship-lock statement")

    manager = AuthorizationPrincipal(
        app_user_id=uuid.UUID("11000000-0000-4000-8000-000000000001"),
        account_status=AccountStatus.ACTIVE,
        role=AppRole.MANAGER,
        company_id=fixture_ids.COMPANY_ID[fixture_ids.HORIZON],
        employee_id=uuid.UUID("21000000-0000-4000-8000-000000000001"),
        branch_id=fixture_ids.BRANCH_DXB,
    )
    source = AppraisalSection.__table__.join(
        Appraisal.__table__,
        Appraisal.__table__.c.id == AppraisalSection.__table__.c.appraisal_id,
    )
    connection = NestedConnection()
    repository = ScopedRepository(
        connection=cast(AsyncConnection, connection),
        table=AppraisalSection.__table__,
        id_column=AppraisalSection.__table__.c.id,
        scope_predicate=direct_report_scope_predicate(
            Appraisal.__table__.c.employee_id,
            direct_report_authorization_scope(manager),
        ),
        relationship_lock=RelationshipLockMode.DIRECT_REPORT,
        authorization_employee_column=Appraisal.__table__.c.employee_id,
        authorization_from=source,
    )

    await repository.update_one(VISIBLE_ID, guarded_values(section_name="Reviewed"))
    assert len(connection.statements) == 4
