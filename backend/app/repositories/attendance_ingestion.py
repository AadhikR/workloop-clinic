from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, insert, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.attendance import (
    AttendanceImportBatch,
    AttendanceImportRowOutcome,
    BiometricMapping,
    ClockEvent,
)
from app.models.identity import Employee
from app.repositories.scoped import ResourceNotFoundError

EVENT_COLUMNS = (
    ClockEvent.id,
    ClockEvent.employee_id,
    ClockEvent.event_type,
    ClockEvent.event_time,
    ClockEvent.method,
    ClockEvent.notes,
    ClockEvent.created_at,
)
MAPPING_COLUMNS = (
    BiometricMapping.id,
    BiometricMapping.badge_no,
    BiometricMapping.employee_id,
    BiometricMapping.device_name,
    BiometricMapping.created_at,
)


class AttendanceIngestionRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def business_date(self):
        return (
            await self.connection.exec_driver_sql("SELECT public.workloop_business_date()")
        ).scalar_one()

    async def employee(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> RowMapping:
        statement = select(Employee.id, Employee.active, Employee.employment_status).where(
            Employee.company_id == company_id,
            Employee.branch_id == branch_id,
            Employee.id == employee_id,
        )
        if lock:
            statement = statement.with_for_update()
        row = (await self.connection.execute(statement)).mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def events(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID | None,
        start: datetime | None,
        end: datetime | None,
        after: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> Sequence[RowMapping]:
        statement = select(*EVENT_COLUMNS).where(
            ClockEvent.company_id == company_id, ClockEvent.branch_id == branch_id
        )
        if employee_id is not None:
            statement = statement.where(ClockEvent.employee_id == employee_id)
        if start is not None:
            statement = statement.where(ClockEvent.event_time >= start)
        if end is not None:
            statement = statement.where(ClockEvent.event_time < end)
        if after is not None:
            event_time, event_id = after
            statement = statement.where(
                or_(
                    ClockEvent.event_time < event_time,
                    and_(ClockEvent.event_time == event_time, ClockEvent.id > event_id),
                )
            )
        return (
            (
                await self.connection.execute(
                    statement.order_by(ClockEvent.event_time.desc(), ClockEvent.id).limit(limit)
                )
            )
            .mappings()
            .all()
        )

    async def event_position(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, event_id: uuid.UUID
    ) -> tuple[datetime, uuid.UUID]:
        row = (
            await self.connection.execute(
                select(ClockEvent.event_time, ClockEvent.id).where(
                    ClockEvent.company_id == company_id,
                    ClockEvent.branch_id == branch_id,
                    ClockEvent.id == event_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row.event_time, row.id

    async def create_manual(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        values: dict[str, object],
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    postgresql_insert(ClockEvent)
                    .values(
                        company_id=company_id,
                        branch_id=branch_id,
                        entered_by_app_user_id=actor_id,
                        method="MANUAL",
                        **values,
                    )
                    .on_conflict_do_nothing()
                    .returning(*EVENT_COLUMNS)
                )
            )
            .mappings()
            .one_or_none()
        )

    async def minute_duplicate(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        event_type: str,
        method: str,
        event_time: datetime,
    ) -> bool:
        statement = (
            select(ClockEvent.id)
            .where(
                ClockEvent.company_id == company_id,
                ClockEvent.branch_id == branch_id,
                ClockEvent.employee_id == employee_id,
                ClockEvent.event_type == event_type,
                ClockEvent.method == method,
                text(
                    "date_trunc('minute', clock_events.event_time AT TIME ZONE 'UTC') "
                    "= date_trunc('minute', :event_time AT TIME ZONE 'UTC')"
                ),
            )
            .limit(1)
        )
        return (
            await self.connection.execute(statement, {"event_time": event_time})
        ).scalar_one_or_none() is not None

    async def mappings(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        after: tuple[str, uuid.UUID] | None,
        limit: int,
    ) -> Sequence[RowMapping]:
        statement = select(*MAPPING_COLUMNS).where(
            BiometricMapping.company_id == company_id,
            BiometricMapping.branch_id == branch_id,
        )
        if after is not None:
            badge_no, mapping_id = after
            statement = statement.where(
                or_(
                    BiometricMapping.badge_no > badge_no,
                    and_(
                        BiometricMapping.badge_no == badge_no,
                        BiometricMapping.id > mapping_id,
                    ),
                )
            )
        return (
            (
                await self.connection.execute(
                    statement.order_by(BiometricMapping.badge_no, BiometricMapping.id).limit(limit)
                )
            )
            .mappings()
            .all()
        )

    async def mapping_position(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, mapping_id: uuid.UUID
    ) -> tuple[str, uuid.UUID]:
        row = (
            await self.connection.execute(
                select(BiometricMapping.badge_no, BiometricMapping.id).where(
                    BiometricMapping.company_id == company_id,
                    BiometricMapping.branch_id == branch_id,
                    BiometricMapping.id == mapping_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row.badge_no, row.id

    async def mapping(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, badge_no: str, *, lock: bool = False
    ) -> RowMapping | None:
        statement = select(*MAPPING_COLUMNS).where(
            BiometricMapping.company_id == company_id,
            BiometricMapping.branch_id == branch_id,
            BiometricMapping.badge_no == badge_no,
        )
        if lock:
            statement = statement.with_for_update()
        return (await self.connection.execute(statement)).mappings().one_or_none()

    async def replace_mapping(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        badge_no: str,
        employee_id: uuid.UUID,
        device_name: str,
    ) -> RowMapping:
        existing = await self.mapping(company_id, branch_id, badge_no, lock=True)
        if existing is None:
            statement = (
                insert(BiometricMapping)
                .values(
                    company_id=company_id,
                    branch_id=branch_id,
                    badge_no=badge_no,
                    employee_id=employee_id,
                    device_name=device_name,
                )
                .returning(*MAPPING_COLUMNS)
            )
        else:
            statement = (
                update(BiometricMapping)
                .where(BiometricMapping.id == existing["id"])
                .values(employee_id=employee_id, device_name=device_name)
                .returning(*MAPPING_COLUMNS)
            )
        return (await self.connection.execute(statement)).mappings().one()

    async def delete_mapping(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, badge_no: str
    ) -> None:
        row = await self.mapping(company_id, branch_id, badge_no, lock=True)
        if row is None:
            raise ResourceNotFoundError
        await self.connection.execute(
            text("DELETE FROM public.biometric_mappings WHERE id=:id"), {"id": row["id"]}
        )

    async def create_batch(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        fingerprint: str,
        row_count: int,
        byte_count: int,
    ) -> RowMapping:
        return (
            (
                await self.connection.execute(
                    insert(AttendanceImportBatch)
                    .values(
                        company_id=company_id,
                        branch_id=branch_id,
                        submitted_by_app_user_id=actor_id,
                        batch_fingerprint=fingerprint,
                        row_count=row_count,
                        byte_count=byte_count,
                    )
                    .returning(AttendanceImportBatch.id)
                )
            )
            .mappings()
            .one()
        )

    async def lock_batch_fingerprint(self, fingerprint: str) -> None:
        await self.connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:fingerprint, 0))"),
            {"fingerprint": fingerprint},
        )

    async def batch_by_fingerprint(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, fingerprint: str
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(AttendanceImportBatch.id).where(
                        AttendanceImportBatch.company_id == company_id,
                        AttendanceImportBatch.branch_id == branch_id,
                        AttendanceImportBatch.batch_fingerprint == fingerprint,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )

    async def batch_outcomes(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, batch_id: uuid.UUID
    ) -> Sequence[RowMapping]:
        return (
            (
                await self.connection.execute(
                    select(
                        AttendanceImportRowOutcome.row_number,
                        AttendanceImportRowOutcome.outcome,
                        AttendanceImportRowOutcome.reason_code,
                        AttendanceImportRowOutcome.clock_event_id,
                    )
                    .where(
                        AttendanceImportRowOutcome.company_id == company_id,
                        AttendanceImportRowOutcome.branch_id == branch_id,
                        AttendanceImportRowOutcome.batch_id == batch_id,
                    )
                    .order_by(AttendanceImportRowOutcome.row_number)
                )
            )
            .mappings()
            .all()
        )

    async def badge_employee(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, badge_no: str
    ) -> uuid.UUID | None:
        return (
            await self.connection.execute(
                select(BiometricMapping.employee_id)
                .join(Employee, Employee.id == BiometricMapping.employee_id)
                .where(
                    BiometricMapping.company_id == company_id,
                    BiometricMapping.branch_id == branch_id,
                    BiometricMapping.badge_no == badge_no,
                    Employee.active.is_(True),
                    Employee.employment_status.in_(("Active", "Probation", "On Leave")),
                )
            )
        ).scalar_one_or_none()

    async def duplicate(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        fingerprint: str,
        employee_id: uuid.UUID,
        event_type: str,
        event_time: datetime,
    ) -> bool:
        statement = (
            select(ClockEvent.id)
            .where(
                ClockEvent.company_id == company_id,
                ClockEvent.branch_id == branch_id,
                or_(
                    ClockEvent.event_fingerprint == fingerprint,
                    and_(
                        ClockEvent.employee_id == employee_id,
                        ClockEvent.event_type == event_type,
                        ClockEvent.method == "BIOMETRIC",
                        text(
                            "date_trunc('minute', clock_events.event_time AT TIME ZONE 'UTC') "
                            "= date_trunc('minute', :event_time AT TIME ZONE 'UTC')"
                        ),
                    ),
                ),
            )
            .limit(1)
        )
        return (
            await self.connection.execute(statement, {"event_time": event_time})
        ).scalar_one_or_none() is not None

    async def biometric_event(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        batch_id: uuid.UUID,
        row_number: int,
        employee_id: uuid.UUID,
        event_type: str,
        event_time: datetime,
        badge_no: str,
        device_name: str,
        fingerprint: str,
    ) -> uuid.UUID | None:
        return (
            await self.connection.execute(
                postgresql_insert(ClockEvent)
                .values(
                    company_id=company_id,
                    branch_id=branch_id,
                    employee_id=employee_id,
                    event_type=event_type,
                    event_time=event_time,
                    method="BIOMETRIC",
                    notes="",
                    import_batch_id=batch_id,
                    import_row_number=row_number,
                    source_badge_no=badge_no,
                    source_device_name=device_name,
                    event_fingerprint=fingerprint,
                )
                .on_conflict_do_nothing()
                .returning(ClockEvent.id)
            )
        ).scalar_one_or_none()

    async def outcome(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        batch_id: uuid.UUID,
        row_number: int,
        outcome: str,
        reason: str | None,
        event_id: uuid.UUID | None,
    ) -> None:
        await self.connection.execute(
            insert(AttendanceImportRowOutcome).values(
                batch_id=batch_id,
                company_id=company_id,
                branch_id=branch_id,
                row_number=row_number,
                outcome=outcome,
                reason_code=reason,
                clock_event_id=event_id,
            )
        )

    async def resource_exists(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID,
    ) -> bool:
        table = {
            "clock_event": ClockEvent,
            "biometric_mapping": BiometricMapping,
            "attendance_import_batch": AttendanceImportBatch,
        }.get(kind)
        if table is None:
            return False
        statement = select(table.id).where(
            table.id == resource_id,
            table.company_id == company_id,
            table.branch_id == branch_id,
        )
        return (await self.connection.execute(statement.limit(1))).scalar_one_or_none() is not None
