#!/usr/bin/env python3
"""Verify Phase 7G employee lifecycle workflows with synthetic data."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as c
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.employees import (
    EmployeeArchiveRequest,
    EmployeeCreateRequest,
    EmployeeDepartmentChangeRequest,
    EmployeeManagerChangeRequest,
    EmployeePortalRoleUpdateRequest,
    EmployeeProbationConfirmationRequest,
    EmployeeProbationExtensionRequest,
    EmployeeProbationTerminationRequest,
    EmployeeSalaryChangeRequest,
    EmployeeSelfContactRequest,
    EmployeeStatusChangeRequest,
    EmployeeTitleChangeRequest,
)
from app.services.employees import EmployeeCursorCodec, EmployeeService
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

EXPECTED_HEAD = "8f6b2d1a4c70"
FIXTURE_PATH = Path("/workspace-fixtures/phase-7g/employee-lifecycle.json")
CURSOR_CODEC = EmployeeCursorCodec(b"phase-7g-verifier-cursor-key-000")
ADMIN_SUBJECT = "hr.admin@horizon.test"
PORTAL_SUBJECT = "phase7g.portal@horizon.test"


def claims(subject: str) -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer=c.SEED_ISSUER,
        subject=subject,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


async def expect_code(code: str, operation: Awaitable[object]) -> None:
    try:
        await operation
    except ServiceExecutionError as error:
        assert error.code == code
        return
    raise AssertionError(f"expected {code}")


def request(model: type[Any], values: dict[str, object]) -> Any:
    return model.model_validate(values)


async def verify(engine: Engine, fixture: dict[str, Any]) -> dict[str, object]:
    runtime_engine = create_async_engine(
        URL.create(
            "postgresql+psycopg",
            username="workloop_runtime",
            password=os.environ["WORKLOOP_RUNTIME_PASSWORD"],
            host="postgres",
            database="workloop",
        )
    )
    resolver = ApplicationUserResolver(
        engine=runtime_engine, issuer=c.SEED_ISSUER, timeout_seconds=2
    )
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=2),
        deadline_seconds=15,
    )
    admin = await resolver.resolve(issuer=c.SEED_ISSUER, subject=ADMIN_SUBJECT)
    employee_ids = {
        name: uuid.UUID(value)
        for name, value in fixture.items()
        if name.endswith("EmployeeId") or name.endswith("ManagerId")
    }
    app_user_ids = {
        name: uuid.UUID(value) for name, value in fixture.items() if name.endswith("AppUserId")
    }
    idempotency_keys = [uuid.UUID(value) for value in fixture["workflowIdempotencyKeys"]]

    def state_snapshot() -> str:
        with engine.connect() as connection:
            state = {
                "employees": [
                    tuple(row)
                    for row in connection.execute(
                        text(
                            "SELECT id,active,employment_status,reporting_manager_id,"
                            "probation_end_date,probation_extended,termination_date,"
                            "termination_reason,updated_at FROM employees "
                            "WHERE id=ANY(:ids) ORDER BY id"
                        ),
                        {"ids": list(employee_ids.values())},
                    ).all()
                ],
                "profiles": [
                    tuple(row)
                    for row in connection.execute(
                        text(
                            "SELECT app_user_id,employee_id,role FROM user_profiles "
                            "WHERE app_user_id=ANY(:ids) ORDER BY app_user_id"
                        ),
                        {"ids": list(app_user_ids.values())},
                    ).all()
                ],
                "history": [
                    tuple(row)
                    for row in connection.execute(
                        text(
                            "SELECT id,employee_id,change_type,old_value,new_value,reason "
                            "FROM employee_job_history WHERE employee_id=ANY(:ids) ORDER BY id"
                        ),
                        {"ids": list(employee_ids.values())},
                    ).all()
                ],
                "audit": [
                    tuple(row)
                    for row in connection.execute(
                        text(
                            "SELECT id,action,entity_type,entity_id,changed_fields,reason,metadata "
                            "FROM audit_events WHERE entity_id=ANY(:ids) ORDER BY id"
                        ),
                        {"ids": [*employee_ids.values(), *app_user_ids.values()]},
                    ).all()
                ],
            }
        return hashlib.sha256(
            json.dumps(state, default=str, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()

    async def run(
        principal: AuthorizationPrincipal,
        subject: str,
        operation: Callable[[EmployeeService, AsyncConnection], Awaitable[Any]],
        *,
        selected_branch_id: uuid.UUID | None,
        generated_id: uuid.UUID | None = None,
    ) -> Any:
        async def execute(connection: AsyncConnection) -> Any:
            factory = (lambda: generated_id) if generated_id is not None else uuid.uuid4
            service = EmployeeService(connection, CURSOR_CODEC, id_factory=factory)
            return await operation(service, connection)

        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            operation=execute,
            selected_admin_branch_id=selected_branch_id,
        )

    async def run_admin(
        operation: Callable[[EmployeeService, AsyncConnection], Awaitable[Any]],
        *,
        generated_id: uuid.UUID | None = None,
        branch_id: uuid.UUID = c.BRANCH_DXB,
    ) -> Any:
        return await run(
            admin,
            ADMIN_SUBJECT,
            operation,
            selected_branch_id=branch_id,
            generated_id=generated_id,
        )

    async def direct_audit(
        *,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        changed_fields: list[str] | None,
        reason: str,
        metadata: object,
        principal: AuthorizationPrincipal = admin,
        subject: str = ADMIN_SUBJECT,
        selected_branch_id: uuid.UUID | None = c.BRANCH_DXB,
        context_overrides: dict[str, str] | None = None,
    ) -> object:
        async def operation(_service: EmployeeService, connection: AsyncConnection) -> object:
            for key, value in (context_overrides or {}).items():
                await connection.execute(
                    text("SELECT pg_catalog.set_config(:key,:value,true)"),
                    {"key": key, "value": value},
                )
            return await connection.execute(
                text(
                    "SELECT public.append_audit_event(:action,:entity_type,:entity_id,"
                    ":changed_fields,:reason,CAST(:metadata AS jsonb))"
                ),
                {
                    "action": action,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "changed_fields": changed_fields,
                    "reason": reason,
                    "metadata": json.dumps(metadata, separators=(",", ":")),
                },
            )

        return await run(
            principal,
            subject,
            operation,
            selected_branch_id=selected_branch_id,
        )

    denial_count = 0

    async def expect_database_denial(operation: Awaitable[object]) -> None:
        nonlocal denial_count
        before = state_snapshot()
        try:
            await operation
        except Exception:
            pass
        else:
            raise AssertionError("protected audit call was accepted")
        assert state_snapshot() == before
        denial_count += 1

    async def create_employee(
        fixture_name: str,
        *,
        status: str = "active",
        manager_id: uuid.UUID | None = None,
        probation_end: str | None = None,
    ) -> Any:
        employee_id = employee_ids[fixture_name]
        body: dict[str, object] = {
            "empNo": f"7G-{employee_id.int % 1000:03d}",
            "name": f"Phase 7G {fixture_name}",
            "molId": f"9900000000{employee_id.int % 100000:05d}",
            "department": "Nursing",
            "employmentStatus": status,
            "reportingManagerId": None if manager_id is None else str(manager_id),
            "basicSalary": "7000.00",
        }
        if probation_end is not None:
            body["probationEndDate"] = probation_end
        return await run_admin(
            lambda service, _connection: service.create_employee(
                admin, c.BRANCH_DXB, EmployeeCreateRequest.model_validate(body)
            ),
            generated_id=employee_id,
        )

    created: dict[str, Any] = {}
    try:
        created["replacement"] = await create_employee("replacementManagerId")
        created["manager"] = await create_employee("managerEmployeeId")
        created["report"] = await create_employee(
            "reportEmployeeId", manager_id=employee_ids["managerEmployeeId"]
        )
        created["title"] = await create_employee("titleEmployeeId")
        created["probation"] = await create_employee(
            "probationEmployeeId", status="probation", probation_end="2026-09-20"
        )
        created["probation_termination"] = await create_employee(
            "probationTerminationEmployeeId",
            status="probation",
            probation_end="2026-09-20",
        )
        created["portal"] = await create_employee("portalEmployeeId")

        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO app_users(id,identity_issuer,identity_subject,status) VALUES"
                    "(:portal_id,:issuer,:portal_subject,'active'),"
                    "(:inactive_id,:issuer,:inactive_subject,'disabled'),"
                    "(:ineligible_id,:issuer,:ineligible_subject,'active')"
                ),
                {
                    "portal_id": app_user_ids["portalAppUserId"],
                    "inactive_id": app_user_ids["inactivePortalAppUserId"],
                    "ineligible_id": app_user_ids["ineligiblePortalAppUserId"],
                    "issuer": c.SEED_ISSUER,
                    "portal_subject": PORTAL_SUBJECT,
                    "inactive_subject": "phase7g.inactive-admin@horizon.test",
                    "ineligible_subject": "phase7g.ineligible@horizon.test",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO user_profiles(app_user_id,company_id,employee_id,role) VALUES"
                    "(:portal_id,:company_id,:portal_employee,'employee'),"
                    "(:inactive_id,:company_id,:inactive_employee,'employee'),"
                    "(:ineligible_id,:company_id,:ineligible_employee,'employee')"
                ),
                {
                    "portal_id": app_user_ids["portalAppUserId"],
                    "inactive_id": app_user_ids["inactivePortalAppUserId"],
                    "ineligible_id": app_user_ids["ineligiblePortalAppUserId"],
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "portal_employee": employee_ids["portalEmployeeId"],
                    "inactive_employee": employee_ids["replacementManagerId"],
                    "ineligible_employee": employee_ids["probationTerminationEmployeeId"],
                },
            )

        title_calls = 0
        title_body = EmployeeTitleChangeRequest.model_validate(
            {
                "expectedUpdatedAt": created["title"].updated_at,
                "jobTitle": "Senior Nurse",
                "reason": "Approved Phase 7G promotion",
            }
        )

        async def title_operation(
            service: EmployeeService, connection: AsyncConnection
        ) -> IdempotentResponse:
            command = IdempotencyCommand(
                key=idempotency_keys[0],
                operation_id="change_employee_title",
                method="POST",
                route_parameters={"employeeId": str(employee_ids["titleEmployeeId"])},
                fingerprint="7" * 64,
                branch_id=c.BRANCH_DXB,
            )

            async def mutate() -> IdempotentResponse:
                nonlocal title_calls
                title_calls += 1
                result = await service.change_title(
                    admin, c.BRANCH_DXB, employee_ids["titleEmployeeId"], title_body
                )
                return IdempotentResponse(
                    status=200,
                    body={"data": result.model_dump(mode="json", by_alias=True)},
                    location=None,
                    resource_kind="employee",
                    resource_id=result.id,
                )

            return await IdempotencyCoordinator(IdempotencyRepository(connection)).execute(
                principal=admin,
                command=command,
                authorize_replay=lambda kind, resource_id: service.authorize_employee_replay(
                    admin, c.BRANCH_DXB, kind, resource_id
                ),
                mutation=mutate,
            )

        title_first = await run_admin(title_operation)
        title_replay = await run_admin(title_operation)
        assert title_replay.replayed and title_replay.body == title_first.body and title_calls == 1

        current = await run_admin(
            lambda service, _connection: service.get_employee(
                admin, c.BRANCH_DXB, employee_ids["titleEmployeeId"]
            )
        )
        current = await run_admin(
            lambda service, _connection: service.change_department(
                admin,
                c.BRANCH_DXB,
                current.id,
                request(
                    EmployeeDepartmentChangeRequest,
                    {
                        "expectedUpdatedAt": current.updated_at,
                        "department": "Clinical",
                        "reason": "Approved department move",
                    },
                ),
            )
        )
        current = await run_admin(
            lambda service, _connection: service.change_salary(
                admin,
                c.BRANCH_DXB,
                current.id,
                request(
                    EmployeeSalaryChangeRequest,
                    {
                        "expectedUpdatedAt": current.updated_at,
                        "basicSalary": "8000.00",
                        "allowance": "250.00",
                        "housingAllowance": "1000.00",
                        "transportAllowance": "500.00",
                        "otherAllowances": "100.00",
                        "otherAllowancesLabel": "Synthetic allowance",
                        "reason": "Approved salary adjustment",
                    },
                ),
            )
        )
        current = await run_admin(
            lambda service, _connection: service.change_manager(
                admin,
                c.BRANCH_DXB,
                current.id,
                request(
                    EmployeeManagerChangeRequest,
                    {
                        "expectedUpdatedAt": current.updated_at,
                        "reportingManagerId": str(employee_ids["replacementManagerId"]),
                        "reason": "Approved reporting change",
                    },
                ),
            )
        )
        current = await run_admin(
            lambda service, _connection: service.change_status(
                admin,
                c.BRANCH_DXB,
                current.id,
                request(
                    EmployeeStatusChangeRequest,
                    {
                        "expectedUpdatedAt": current.updated_at,
                        "employmentStatus": "on_leave",
                        "reason": "Approved leave",
                    },
                ),
            )
        )
        assert current.employment_status == "on_leave"

        await expect_code(
            "state_conflict",
            run_admin(
                lambda service, _connection: service.change_title(
                    admin, c.BRANCH_DXB, current.id, title_body
                )
            ),
        )

        probation = await run_admin(
            lambda service, _connection: service.extend_probation(
                admin,
                c.BRANCH_DXB,
                employee_ids["probationEmployeeId"],
                request(
                    EmployeeProbationExtensionRequest,
                    {
                        "expectedUpdatedAt": created["probation"].updated_at,
                        "probationEndDate": "2026-10-20",
                        "reason": "Approved probation extension",
                    },
                ),
            )
        )
        await expect_database_denial(
            direct_audit(
                action="employee_probation_extended",
                entity_type="employee",
                entity_id=employee_ids["probationEmployeeId"],
                changed_fields=["probation_end_date", "probation_extended"],
                reason="Noncanonical date must fail",
                metadata={
                    "previous_probation_end_date": "2026-9-20",
                    "new_probation_end_date": "2026-10-20",
                },
            )
        )
        probation = await run_admin(
            lambda service, _connection: service.confirm_probation(
                admin,
                c.BRANCH_DXB,
                probation.id,
                request(
                    EmployeeProbationConfirmationRequest,
                    {
                        "expectedUpdatedAt": probation.updated_at,
                        "reason": "Probation requirements completed",
                    },
                ),
            )
        )
        assert probation.employment_status == "active" and probation.probation_end_date is None

        terminated = await run_admin(
            lambda service, _connection: service.terminate_probation(
                admin,
                c.BRANCH_DXB,
                employee_ids["probationTerminationEmployeeId"],
                request(
                    EmployeeProbationTerminationRequest,
                    {
                        "expectedUpdatedAt": created["probation_termination"].updated_at,
                        "reason": "Probation requirements not met",
                    },
                ),
            )
        )
        assert terminated.employment_status == "terminated" and not terminated.active

        before_denial = created["manager"].updated_at
        await expect_code(
            "manager_reassignment_conflict",
            run_admin(
                lambda service, _connection: service.archive_employee(
                    admin,
                    c.BRANCH_DXB,
                    employee_ids["managerEmployeeId"],
                    request(
                        EmployeeArchiveRequest,
                        {
                            "expectedUpdatedAt": before_denial,
                            "reason": "Incomplete reassignment must fail",
                        },
                    ),
                )
            ),
        )
        await expect_code(
            "manager_reassignment_conflict",
            run_admin(
                lambda service, _connection: service.change_manager(
                    admin,
                    c.BRANCH_DXB,
                    employee_ids["managerEmployeeId"],
                    request(
                        EmployeeManagerChangeRequest,
                        {
                            "expectedUpdatedAt": before_denial,
                            "reportingManagerId": str(employee_ids["reportEmployeeId"]),
                            "reason": "Cycle must fail",
                        },
                    ),
                )
            ),
        )
        archived = await run_admin(
            lambda service, _connection: service.archive_employee(
                admin,
                c.BRANCH_DXB,
                employee_ids["managerEmployeeId"],
                request(
                    EmployeeArchiveRequest,
                    {
                        "expectedUpdatedAt": before_denial,
                        "reason": "Approved synthetic archive",
                        "reportReassignments": [
                            {
                                "employeeId": str(employee_ids["reportEmployeeId"]),
                                "newManagerId": str(employee_ids["replacementManagerId"]),
                                "expectedUpdatedAt": created["report"].updated_at,
                            }
                        ],
                    },
                ),
            )
        )
        assert archived.employment_status == "terminated" and not archived.active

        portal = await run_admin(
            lambda service, _connection: service.get_portal_role(
                admin, c.BRANCH_DXB, employee_ids["portalEmployeeId"]
            )
        )
        assert portal.activated and portal.role == "employee"
        promoted = await run_admin(
            lambda service, _connection: service.set_portal_role(
                admin,
                c.BRANCH_DXB,
                employee_ids["portalEmployeeId"],
                EmployeePortalRoleUpdateRequest(role="manager", expectedRole="employee"),
            )
        )
        assert promoted.role == "manager"
        demoted = await run_admin(
            lambda service, _connection: service.set_portal_role(
                admin,
                c.BRANCH_DXB,
                employee_ids["portalEmployeeId"],
                EmployeePortalRoleUpdateRequest(
                    role="employee", expectedRole="manager", reportReassignments=[]
                ),
            )
        )
        assert demoted.role == "employee"
        await expect_code(
            "portal_role_conflict",
            run_admin(
                lambda service, _connection: service.set_portal_role(
                    admin,
                    c.BRANCH_DXB,
                    employee_ids["portalEmployeeId"],
                    EmployeePortalRoleUpdateRequest(role="manager", expectedRole="manager"),
                )
            ),
        )
        await expect_code(
            "resource_not_found",
            run_admin(
                lambda service, _connection: service.get_portal_role(
                    admin, c.BRANCH_AUH, employee_ids["portalEmployeeId"]
                ),
                branch_id=c.BRANCH_AUH,
            ),
        )
        unlinked = await run_admin(
            lambda service, _connection: service.get_portal_role(
                admin, c.BRANCH_DXB, employee_ids["titleEmployeeId"]
            )
        )
        inactive = await run_admin(
            lambda service, _connection: service.get_portal_role(
                admin, c.BRANCH_DXB, employee_ids["replacementManagerId"]
            )
        )
        ineligible = await run_admin(
            lambda service, _connection: service.get_portal_role(
                admin, c.BRANCH_DXB, employee_ids["probationTerminationEmployeeId"]
            )
        )
        assert not unlinked.activated and unlinked.role is None
        assert not inactive.activated and inactive.role is None
        assert not ineligible.activated and ineligible.role is None
        for target in (
            employee_ids["replacementManagerId"],
            employee_ids["probationTerminationEmployeeId"],
        ):
            await expect_code(
                "portal_role_conflict",
                run_admin(
                    lambda service, _connection, target=target: service.set_portal_role(
                        admin,
                        c.BRANCH_DXB,
                        target,
                        EmployeePortalRoleUpdateRequest(role="manager", expectedRole="employee"),
                    )
                ),
            )

        before_self_role = state_snapshot()
        self_role_result = await run_admin(
            lambda _service, connection: connection.execute(
                text("UPDATE user_profiles SET role='employee' WHERE app_user_id=:app_user_id"),
                {"app_user_id": admin.app_user_id},
            )
        )
        assert self_role_result.rowcount == 0 and state_snapshot() == before_self_role

        portal_principal = await resolver.resolve(issuer=c.SEED_ISSUER, subject=PORTAL_SUBJECT)
        self_before = await run(
            portal_principal,
            PORTAL_SUBJECT,
            lambda service, _connection: service.get_self(portal_principal),
            selected_branch_id=None,
        )
        self_after = await run(
            portal_principal,
            PORTAL_SUBJECT,
            lambda service, _connection: service.update_self_contact(
                portal_principal,
                EmployeeSelfContactRequest(
                    expectedUpdatedAt=self_before.updated_at,
                    phone="+971500007007",
                ),
            ),
            selected_branch_id=None,
        )
        assert self_after.phone == "+971500007007"
        await expect_code(
            "state_conflict",
            run(
                portal_principal,
                PORTAL_SUBJECT,
                lambda service, _connection: service.update_self_contact(
                    portal_principal,
                    EmployeeSelfContactRequest(
                        expectedUpdatedAt=self_before.updated_at,
                        phone="+971500007008",
                    ),
                ),
                selected_branch_id=None,
            ),
        )

        manager_audit = {
            "action": "employee_manager_changed",
            "entity_type": "employee",
            "entity_id": employee_ids["reportEmployeeId"],
            "changed_fields": ["reporting_manager_id"],
            "reason": "Reporting manager reassigned",
            "metadata": {
                "previous_manager_id": str(employee_ids["managerEmployeeId"]),
                "new_manager_id": str(employee_ids["replacementManagerId"]),
            },
        }
        archive_audit = {
            "action": "employee_archived",
            "entity_type": "employee",
            "entity_id": employee_ids["managerEmployeeId"],
            "changed_fields": [
                "active",
                "employment_status",
                "termination_date",
                "termination_reason",
            ],
            "reason": "Approved synthetic archive",
            "metadata": {"transition": "active_to_terminated"},
        }
        portal_audit = {
            "action": "employee_portal_role_changed",
            "entity_type": "user_profile",
            "entity_id": app_user_ids["portalAppUserId"],
            "changed_fields": ["role"],
            "reason": "Portal role changed",
            "metadata": {"transition": "manager_to_employee"},
        }

        payload_denials = [
            {**manager_audit, "entity_type": "user_profile"},
            {**manager_audit, "entity_id": c.BRANCH_AUH},
            {**manager_audit, "changed_fields": None},
            {**manager_audit, "changed_fields": []},
            {**manager_audit, "changed_fields": ["reporting_manager_id", "reporting_manager_id"]},
            {**manager_audit, "changed_fields": ["reporting_manager_id", "active"]},
            {**manager_audit, "reason": ""},
            {**manager_audit, "reason": " untrimmed "},
            {**manager_audit, "reason": "x" * 1001},
            {**manager_audit, "metadata": None},
            {**manager_audit, "metadata": []},
            {
                **manager_audit,
                "metadata": {"new_manager_id": str(employee_ids["replacementManagerId"])},
            },
            {**manager_audit, "metadata": {**manager_audit["metadata"], "extra": True}},
            {
                **manager_audit,
                "metadata": {
                    "previous_manager_id": "not-a-uuid",
                    "new_manager_id": str(employee_ids["replacementManagerId"]),
                },
            },
            {
                **manager_audit,
                "metadata": {
                    "previous_manager_id": str(employee_ids["managerEmployeeId"]),
                    "new_manager_id": str(employee_ids["managerEmployeeId"]),
                },
            },
            {**archive_audit, "changed_fields": list(reversed(archive_audit["changed_fields"]))},
            {**archive_audit, "metadata": {"transition": "probation_to_terminated"}},
            {**archive_audit, "reason": "Wrong stored reason"},
            {**portal_audit, "entity_type": "employee"},
            {**portal_audit, "entity_id": admin.app_user_id},
            {**portal_audit, "entity_id": app_user_ids["inactivePortalAppUserId"]},
            {**portal_audit, "entity_id": app_user_ids["ineligiblePortalAppUserId"]},
            {**portal_audit, "entity_id": uuid.UUID("12000000-0000-4000-8000-000000000001")},
            {**portal_audit, "metadata": {"transition": "employee_to_manager"}},
            {**portal_audit, "metadata": {"transition": "manager_to_employee", "extra": True}},
            {**portal_audit, "changed_fields": ["role", "employee_id"]},
            {**manager_audit, "action": "role_changed", "changed_fields": ["role"], "metadata": {}},
            {
                **manager_audit,
                "action": "employment_access_changed",
                "changed_fields": ["active"],
                "metadata": {},
            },
            {**manager_audit, "action": "unknown_employee_action", "metadata": {}},
        ]
        for payload in payload_denials:
            await expect_database_denial(direct_audit(**payload))

        manager_principal = await resolver.resolve(
            issuer=c.SEED_ISSUER, subject="aisha.manager@horizon.test"
        )
        employee_principal = await resolver.resolve(
            issuer=c.SEED_ISSUER, subject="ravi.employee@horizon.test"
        )
        await expect_database_denial(
            direct_audit(
                **manager_audit,
                principal=manager_principal,
                subject="aisha.manager@horizon.test",
                selected_branch_id=None,
            )
        )
        await expect_database_denial(
            direct_audit(
                **manager_audit,
                principal=employee_principal,
                subject="ravi.employee@horizon.test",
                selected_branch_id=None,
            )
        )
        await expect_database_denial(direct_audit(**manager_audit, selected_branch_id=None))
        for context_name, context_overrides in (
            (
                "scheduled job",
                {
                "workloop.actor_kind": "scheduled_job",
                "workloop.actor_key": "expiry_processing",
                },
            ),
            ("human actor key", {"workloop.actor_key": "expiry_processing"}),
            ("missing business date", {"workloop.business_date": ""}),
            ("foreign branch", {"workloop.branch_id": str(c.BRANCH_SHJ)}),
            (
                "inactive principal",
                {
                    "workloop.identity_subject": "phase7g.inactive-admin@horizon.test",
                    "workloop.app_user_id": str(app_user_ids["inactivePortalAppUserId"]),
                },
            ),
        ):
            try:
                await expect_database_denial(
                    direct_audit(**manager_audit, context_overrides=context_overrides)
                )
            except AssertionError as error:
                raise AssertionError(f"{context_name} audit context was accepted") from error

        before_non_runtime = state_snapshot()
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "SELECT public.append_audit_event(:action,:entity_type,:entity_id,"
                        ":changed_fields,:reason,CAST(:metadata AS jsonb))"
                    ),
                    {
                        **manager_audit,
                        "metadata": json.dumps(manager_audit["metadata"]),
                    },
                )
        except Exception:
            pass
        else:
            raise AssertionError("non-runtime protected audit call was accepted")
        assert state_snapshot() == before_non_runtime
        denial_count += 1

        with engine.connect() as connection:
            actions = dict(
                connection.execute(
                    text(
                        "SELECT action,count(*) FROM audit_events "
                        "WHERE entity_id=ANY(:ids) GROUP BY action"
                    ),
                    {"ids": [*employee_ids.values(), uuid.UUID(fixture["portalAppUserId"])]},
                ).all()
            )
            history = dict(
                connection.execute(
                    text(
                        "SELECT change_type,count(*) FROM employee_job_history "
                        "WHERE employee_id=ANY(:ids) GROUP BY change_type"
                    ),
                    {"ids": list(employee_ids.values())},
                ).all()
            )
            report_manager = connection.execute(
                text("SELECT reporting_manager_id FROM employees WHERE id=:id"),
                {"id": employee_ids["reportEmployeeId"]},
            ).scalar_one()
        assert actions == {
            "employee_archived": 1,
            "employee_manager_changed": 2,
            "employee_portal_role_changed": 2,
            "employee_probation_confirmed": 1,
            "employee_probation_extended": 1,
            "employee_probation_terminated": 1,
        }
        assert history == {
            "department_change": 1,
            "salary_change": 1,
            "status_change": 4,
            "title_change": 1,
        }
        assert report_manager == employee_ids["replacementManagerId"]
        return {
            "actions": actions,
            "history": history,
            "managerReassignmentAtomic": True,
            "portalRoleRoundTrip": True,
            "protectedAuditDenials": denial_count,
            "selfContactStaleWriteRejected": True,
            "titleReplay": title_replay.replayed,
        }
    finally:
        await runtime_engine.dispose()
        with engine.begin() as connection:
            ids = list(employee_ids.values())
            connection.execute(
                text("DELETE FROM idempotency_records WHERE idempotency_key=ANY(:keys)"),
                {"keys": idempotency_keys},
            )
            connection.execute(
                text("DELETE FROM audit_events WHERE entity_id=ANY(:ids)"),
                {"ids": [*ids, *app_user_ids.values()]},
            )
            connection.execute(
                text("DELETE FROM employee_job_history WHERE employee_id=ANY(:ids)"),
                {"ids": ids},
            )
            connection.execute(
                text("DELETE FROM user_profiles WHERE app_user_id=ANY(:ids)"),
                {"ids": list(app_user_ids.values())},
            )
            connection.execute(text("DELETE FROM employees WHERE id=ANY(:ids)"), {"ids": ids})
            connection.execute(
                text("DELETE FROM app_users WHERE id=ANY(:ids)"),
                {"ids": list(app_user_ids.values())},
            )


def main() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    rows = build_rows()
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == EXPECTED_HEAD
            )
        evidence = asyncio.run(verify(engine, fixture))
        evidence["alembicHead"] = EXPECTED_HEAD
        evidence["syntheticState"] = hashlib.sha256(
            json.dumps(evidence, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        print(json.dumps(evidence, separators=(",", ":"), sort_keys=True))
    finally:
        with engine.begin() as connection:
            clean(connection, rows)
        engine.dispose()


if __name__ == "__main__":
    main()
