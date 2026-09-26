#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    target = ROOT / path
    assert target.is_file(), f"missing Part 12B artifact: {path}"
    return target.read_text(encoding="utf-8")


def main() -> None:
    assert not any((ROOT / "backend" / "alembic" / "versions").glob("*phase12b*"))

    api = source("backend/app/notification_api.py")
    for route in (
        'prefix="/api/v1/notifications"',
        '"/unread-count"',
        '"/{notification_id}/read"',
        '"/read-all"',
    ):
        assert route in api, route
    assert "recipient_app_user_id" not in api

    repository = source("backend/app/repositories/notifications.py")
    for clause in (
        "recipient_app_user_id=:recipient_id",
        "created_at DESC,id DESC",
        "read_at=COALESCE(read_at,statement_timestamp())",
    ):
        assert clause in repository, clause

    command = source("backend/app/expiry_command.py")
    for control in (
        "workloop_expiry_processing",
        "pg_advisory_xact_lock",
        "expiry_notification_created",
        "EXPIRY_DATABASE_URL",
        "expiry_processing_failed",
    ):
        assert control in command, control
    assert "scheduler" not in command.lower()
    assert "print(json.dumps" in command

    migration_client = source("src/notificationApi.js")
    migration_bell = source("src/NotificationBell.jsx")
    migration_shell = source("src/OrganizationPanel.jsx")
    assert "supabase" not in (migration_client + migration_bell).lower()
    assert "<NotificationBell" in migration_shell

    leave = source("backend/app/services/leave_approval.py")
    assert 'if new_status in {"Approved", "Rejected", "ManagerRejected"}' in leave
    assert '"leave_approved" if new_status == "Approved" else "leave_rejected"' in leave
    assert leave.index("await self.repository.update_request") < leave.index(
        "await self.repository.create_workflow_notification"
    )

    payroll_service = source("backend/app/services/payroll.py")
    payroll_repository = source("backend/app/repositories/payroll.py")
    assert payroll_service.index("await self.repository.insert_payslip") < payroll_service.index(
        "await self.repository.create_payslip_notification"
    )
    assert "'payslip_available',CAST(:source_id AS text)" in payroll_repository
    assert "employee.employment_status IN ('Active','Probation','On Leave')" in payroll_repository
    assert "account.status='active'" in payroll_repository

    roster = source("backend/app/repositories/roster_publication.py")
    assert roster.index("phase10h_publish_assignments") < roster.index(
        "'roster_published',CAST(:source_id AS text)"
    )
    assert "employee.employment_status IN ('Active','Probation','On Leave')" in roster
    assert "account.status='active'" in roster

    print("Phase 12B boundary verification passed")


if __name__ == "__main__":
    main()
