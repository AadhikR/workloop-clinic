from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.schemas.insurance import (
    CoverageReplaceRequest,
    EmployeeCoverageResponse,
    InsuranceDependantCreateRequest,
    InsuranceDependantResponse,
    InsuranceDependantUpdateRequest,
    InsurancePolicyCreateRequest,
    InsurancePolicyResponse,
    InsurancePolicyUpdateRequest,
    SelfInsuranceResponse,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError

POLICY_COLUMNS = """
id,insurer_name,policy_number,tier_name,annual_premium,renewal_date,
broker_name,broker_contact,notes,created_at,updated_at
"""


@dataclass(frozen=True, slots=True)
class InsurancePolicyListQuery:
    renewal_from: date | None
    renewal_to: date | None
    search: str | None
    limit: int
    cursor: str | None


@dataclass(frozen=True, slots=True)
class InsuranceDependantListQuery:
    employee_id: uuid.UUID
    limit: int
    cursor: str | None


class InsuranceService:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def list_policies(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: InsurancePolicyListQuery,
        cursor_codec: EmployeeCursorCodec,
    ) -> tuple[list[InsurancePolicyResponse], str | None]:
        try:
            cursor_id = cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_insurance_policies",
                query=query,
                cursor=query.cursor,
            )
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None
        parameters: dict[str, object] = {
            "company_id": principal.company_id,
            "branch_id": branch_id,
            "renewal_from": query.renewal_from,
            "renewal_to": query.renewal_to,
            "search": query.search,
            "limit": query.limit + 1,
        }
        cursor_clause = ""
        if cursor_id is not None:
            anchor = (
                await self.connection.execute(
                    text(
                        "SELECT renewal_date,insurer_name FROM public.insurance_policies "
                        "WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id "
                        "AND (CAST(:renewal_from AS date) IS NULL OR renewal_date>=:renewal_from) "
                        "AND (CAST(:renewal_to AS date) IS NULL OR renewal_date<=:renewal_to) "
                        "AND (CAST(:search AS text) IS NULL "
                        "OR insurer_name ILIKE '%'||:search||'%' "
                        "OR policy_number ILIKE '%'||:search||'%')"
                    ),
                    {**parameters, "id": cursor_id},
                )
            ).one_or_none()
            if anchor is None:
                raise ServiceExecutionError("invalid_cursor")
            parameters.update(
                {
                    "cursor_renewal_date": anchor.renewal_date,
                    "cursor_insurer_name": anchor.insurer_name,
                    "cursor_id": cursor_id,
                }
            )
            cursor_clause = """
 AND (COALESCE(renewal_date,'infinity'::date),insurer_name,id) >
     (COALESCE(:cursor_renewal_date,'infinity'::date),:cursor_insurer_name,:cursor_id)
"""
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT {POLICY_COLUMNS} FROM public.insurance_policies
WHERE company_id=:company_id AND branch_id=:branch_id
 AND (CAST(:renewal_from AS date) IS NULL OR renewal_date>=:renewal_from)
 AND (CAST(:renewal_to AS date) IS NULL OR renewal_date<=:renewal_to)
 AND (CAST(:search AS text) IS NULL OR insurer_name ILIKE '%'||:search||'%'
      OR policy_number ILIKE '%'||:search||'%')
{cursor_clause}
ORDER BY renewal_date ASC NULLS LAST,insurer_name ASC,id ASC LIMIT :limit
"""
                    ),
                    parameters,
                )
            )
            .mappings()
            .all()
        )
        visible = rows[: query.limit]
        items = [InsurancePolicyResponse.model_validate(row) for row in visible]
        next_cursor = (
            cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_insurance_policies",
                query=query,
                last_id=visible[-1]["id"],
            )
            if len(rows) > query.limit
            else None
        )
        return items, next_cursor

    async def get_policy(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, policy_id: uuid.UUID
    ) -> InsurancePolicyResponse:
        row = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT {POLICY_COLUMNS} FROM public.insurance_policies "
                        "WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id"
                    ),
                    {"id": policy_id, "company_id": principal.company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return InsurancePolicyResponse.model_validate(row)

    async def create_policy(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: InsurancePolicyCreateRequest,
    ) -> InsurancePolicyResponse:
        policy_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.insurance_policies(
 company_id,branch_id,insurer_name,policy_number,tier_name,annual_premium,
 renewal_date,broker_name,broker_contact,notes)
VALUES(:company_id,:branch_id,:insurer_name,:policy_number,:tier_name,:annual_premium,
 :renewal_date,:broker_name,:broker_contact,:notes) RETURNING id
"""
                ),
                {
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    **request.model_dump(by_alias=False),
                },
            )
        ).scalar_one()
        await self._audit(
            "insurance_policy_created",
            "insurance_policy",
            policy_id,
            ["id"],
            "Insurance policy created",
        )
        return await self.get_policy(principal, branch_id, policy_id)

    async def update_policy(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        policy_id: uuid.UUID,
        request: InsurancePolicyUpdateRequest,
    ) -> InsurancePolicyResponse:
        current = await self._lock_policy(principal, branch_id, policy_id)
        if current.updated_at != request.expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        values = request.model_dump(exclude={"expected_updated_at"}, by_alias=False)
        await self.connection.execute(
            text(
                """
UPDATE public.insurance_policies SET insurer_name=:insurer_name,
 policy_number=:policy_number,tier_name=:tier_name,annual_premium=:annual_premium,
 renewal_date=:renewal_date,broker_name=:broker_name,broker_contact=:broker_contact,notes=:notes
WHERE id=:id
"""
            ),
            {"id": policy_id, **values},
        )
        await self._audit(
            "insurance_policy_updated",
            "insurance_policy",
            policy_id,
            list(values),
            "Insurance policy updated",
        )
        return await self.get_policy(principal, branch_id, policy_id)

    async def delete_policy(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        policy_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> None:
        current = await self._lock_policy(principal, branch_id, policy_id)
        if current.updated_at != expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        linked = (
            await self.connection.execute(
                text(
                    "SELECT 1 FROM public.employee_insurance WHERE policy_id=:id LIMIT 1 FOR SHARE"
                ),
                {"id": policy_id},
            )
        ).scalar_one_or_none()
        if linked is not None:
            raise ServiceExecutionError("state_conflict")
        await self._audit(
            "insurance_policy_deleted",
            "insurance_policy",
            policy_id,
            ["id"],
            "Insurance policy deleted",
        )
        await self.connection.execute(
            text("DELETE FROM public.insurance_policies WHERE id=:id"), {"id": policy_id}
        )

    async def _lock_policy(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, policy_id: uuid.UUID
    ):
        row = (
            await self.connection.execute(
                text(
                    f"SELECT {POLICY_COLUMNS} FROM public.insurance_policies "
                    "WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id FOR UPDATE"
                ),
                {"id": policy_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return row

    async def replace_coverage(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: CoverageReplaceRequest,
    ) -> EmployeeCoverageResponse:
        employee = (
            await self.connection.execute(
                text(
                    "SELECT id FROM public.employees WHERE id=:id AND company_id=:company_id "
                    "AND branch_id=:branch_id AND active FOR UPDATE"
                ),
                {"id": employee_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).scalar_one_or_none()
        if employee is None:
            raise ServiceExecutionError("resource_not_found")
        await self._lock_policy(principal, branch_id, request.policy_id)
        current = (
            await self.connection.execute(
                text(
                    "SELECT id,updated_at FROM public.employee_insurance "
                    "WHERE employee_id=:employee_id FOR UPDATE"
                ),
                {"employee_id": employee_id},
            )
        ).one_or_none()
        if (current is None and request.expected_updated_at is not None) or (
            current is not None and current.updated_at != request.expected_updated_at
        ):
            raise ServiceExecutionError("state_conflict")
        if current is None:
            coverage_id = (
                await self.connection.execute(
                    text(
                        """
INSERT INTO public.employee_insurance(
 company_id,branch_id,employee_id,policy_id,member_id,card_number,
 effective_date,expiry_date,tier_name)
VALUES(:company_id,:branch_id,:employee_id,:policy_id,:member_id,:card_number,
 :effective_date,:expiry_date,:tier_name) RETURNING id
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                        **request.model_dump(exclude={"expected_updated_at"}, by_alias=False),
                    },
                )
            ).scalar_one()
        else:
            coverage_id = current.id
            await self.connection.execute(
                text(
                    """
UPDATE public.employee_insurance SET policy_id=:policy_id,member_id=:member_id,
 card_number=:card_number,effective_date=:effective_date,expiry_date=:expiry_date,
 tier_name=:tier_name WHERE id=:id
"""
                ),
                {
                    "id": coverage_id,
                    **request.model_dump(exclude={"expected_updated_at"}, by_alias=False),
                },
            )
        await self._audit(
            "insurance_coverage_replaced",
            "employee_insurance",
            coverage_id,
            ["policy_id", "member_id", "card_number", "effective_date", "expiry_date", "tier_name"],
            "Employee insurance coverage replaced",
        )
        return await self.get_coverage(principal, branch_id, employee_id)

    async def get_coverage(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> EmployeeCoverageResponse:
        row = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT coverage.id,coverage.employee_id,coverage.policy_id,coverage.member_id,
 coverage.card_number,coverage.effective_date,coverage.expiry_date,coverage.tier_name,
 policy.insurer_name,coverage.created_at,coverage.updated_at
FROM public.employee_insurance coverage
JOIN public.insurance_policies policy ON policy.id=coverage.policy_id
WHERE coverage.company_id=:company_id AND coverage.branch_id=:branch_id
 AND coverage.employee_id=:employee_id
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return EmployeeCoverageResponse.model_validate(row)

    async def self_coverage(self, principal: AuthorizationPrincipal) -> SelfInsuranceResponse:
        if principal.employee_id is None or principal.branch_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        row = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT coverage.policy_id,policy.insurer_name,coverage.tier_name,
 coverage.effective_date,coverage.expiry_date
FROM public.employee_insurance coverage
JOIN public.insurance_policies policy ON policy.id=coverage.policy_id
WHERE coverage.company_id=:company_id AND coverage.branch_id=:branch_id
 AND coverage.employee_id=:employee_id
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": principal.branch_id,
                        "employee_id": principal.employee_id,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return SelfInsuranceResponse.model_validate(row)

    async def list_dependants(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: InsuranceDependantListQuery,
        cursor_codec: EmployeeCursorCodec,
    ) -> tuple[list[InsuranceDependantResponse], str | None]:
        employee_id = query.employee_id
        await self._employee_exists(principal, branch_id, employee_id)
        try:
            cursor_id = cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_insurance_dependants",
                query=query,
                cursor=query.cursor,
            )
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None
        parameters: dict[str, object] = {
            "company_id": principal.company_id,
            "branch_id": branch_id,
            "employee_id": employee_id,
            "limit": query.limit + 1,
        }
        cursor_clause = ""
        if cursor_id is not None:
            anchor = (
                await self.connection.execute(
                    text(
                        "SELECT name FROM public.insurance_dependants "
                        "WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id "
                        "AND employee_id=:employee_id"
                    ),
                    {**parameters, "id": cursor_id},
                )
            ).scalar_one_or_none()
            if anchor is None:
                raise ServiceExecutionError("invalid_cursor")
            parameters.update({"cursor_name": anchor, "cursor_id": cursor_id})
            cursor_clause = " AND (name,id) > (:cursor_name,:cursor_id)"
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT id,employee_id,name,relationship,date_of_birth,card_number,created_at,updated_at
FROM public.insurance_dependants
WHERE company_id=:company_id AND branch_id=:branch_id AND employee_id=:employee_id
{cursor_clause}
ORDER BY name,id LIMIT :limit
"""
                    ),
                    parameters,
                )
            )
            .mappings()
            .all()
        )
        visible = rows[: query.limit]
        items = [InsuranceDependantResponse.model_validate(row) for row in visible]
        next_cursor = (
            cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_insurance_dependants",
                query=query,
                last_id=visible[-1]["id"],
            )
            if len(rows) > query.limit
            else None
        )
        return items, next_cursor

    async def create_dependant(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: InsuranceDependantCreateRequest,
    ) -> InsuranceDependantResponse:
        await self._employee_exists(principal, branch_id, employee_id, lock=True)
        dependant_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.insurance_dependants(
 company_id,branch_id,employee_id,name,relationship,date_of_birth,card_number)
VALUES(:company_id,:branch_id,:employee_id,:name,:relationship,:date_of_birth,:card_number)
RETURNING id
"""
                ),
                {
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    "employee_id": employee_id,
                    **request.model_dump(by_alias=False),
                },
            )
        ).scalar_one()
        await self._audit(
            "insurance_dependant_created",
            "insurance_dependant",
            dependant_id,
            ["id"],
            "Insurance dependant created",
        )
        return await self.get_dependant(principal, branch_id, dependant_id)

    async def get_dependant(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, dependant_id: uuid.UUID
    ) -> InsuranceDependantResponse:
        row = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT id,employee_id,name,relationship,date_of_birth,card_number,created_at,updated_at
FROM public.insurance_dependants
WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id
"""
                    ),
                    {
                        "id": dependant_id,
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return InsuranceDependantResponse.model_validate(row)

    async def update_dependant(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        dependant_id: uuid.UUID,
        request: InsuranceDependantUpdateRequest,
    ) -> InsuranceDependantResponse:
        row = await self._lock_dependant(principal, branch_id, dependant_id)
        if row.updated_at != request.expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        values = request.model_dump(exclude={"expected_updated_at"}, by_alias=False)
        await self.connection.execute(
            text(
                """
UPDATE public.insurance_dependants SET name=:name,relationship=:relationship,
 date_of_birth=:date_of_birth,card_number=:card_number WHERE id=:id
"""
            ),
            {"id": dependant_id, **values},
        )
        await self._audit(
            "insurance_dependant_updated",
            "insurance_dependant",
            dependant_id,
            list(values),
            "Insurance dependant updated",
        )
        return await self.get_dependant(principal, branch_id, dependant_id)

    async def delete_dependant(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        dependant_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> None:
        row = await self._lock_dependant(principal, branch_id, dependant_id)
        if row.updated_at != expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        await self._audit(
            "insurance_dependant_deleted",
            "insurance_dependant",
            dependant_id,
            ["id"],
            "Insurance dependant deleted",
        )
        await self.connection.execute(
            text("DELETE FROM public.insurance_dependants WHERE id=:id"), {"id": dependant_id}
        )

    async def _lock_dependant(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, dependant_id: uuid.UUID
    ):
        row = (
            await self.connection.execute(
                text(
                    "SELECT id,updated_at FROM public.insurance_dependants WHERE id=:id "
                    "AND company_id=:company_id AND branch_id=:branch_id FOR UPDATE"
                ),
                {"id": dependant_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return row

    async def _employee_exists(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> None:
        suffix = " FOR UPDATE" if lock else ""
        exists = (
            await self.connection.execute(
                text(
                    "SELECT 1 FROM public.employees WHERE id=:id AND company_id=:company_id "
                    f"AND branch_id=:branch_id{suffix}"
                ),
                {"id": employee_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).scalar_one_or_none()
        if exists is None:
            raise ServiceExecutionError("resource_not_found")

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        tables = {
            "insurance_policy": "insurance_policies",
            "employee_insurance": "employee_insurance",
            "insurance_dependant": "insurance_dependants",
        }
        table = tables.get(kind)
        if table is None or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        exists = (
            await self.connection.execute(
                text(
                    f"SELECT 1 FROM public.{table} WHERE id=:id AND company_id=:company_id "
                    "AND branch_id=:branch_id"
                ),
                {"id": resource_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).scalar_one_or_none()
        if exists is None:
            raise ServiceExecutionError("resource_not_found")

    async def _audit(
        self,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        changed_fields: list[str],
        reason: str,
    ) -> None:
        await append_audit_event(
            self.connection,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changed_fields=changed_fields,
            reason=reason,
            metadata={},
        )
