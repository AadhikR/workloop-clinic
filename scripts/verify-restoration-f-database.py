"""Verify retained portal commands and safe projections on a disposable database."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import uuid
from pathlib import Path
from decimal import Decimal

from app.auth.application_user import ApplicationUserResolver
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.main import create_app
from app.portal_retained_api import archive_portal_record, restore_portal_record
from app.portal_retained_api import cancel_pending_admin_advance
from app.portal_retained_api import save_admin_appraisal_review
from app.schemas.appraisals import AppraisalAdminReviewRequest
from app.schemas.appraisals import AppraisalManagerReviewRequest, AppraisalSectionRatingRequest
from app.appraisal_api import submit_manager_appraisal_review
from app.employment_contract_api import download_employment_contract_pdf
from app.services.appraisals import AppraisalService
from alembic import command as alembic_command
from alembic.config import Config
from sqlalchemy.exc import DBAPIError
from app.schemas.development import VersionRequest
from app.services.development import DevelopmentService, TrainingListQuery
from app.services.development import CertificationListQuery
from app.services.incidents import IncidentService, IncidentListQuery
from app.services.organization import OrganizationService, BranchCursorCodec
from app.schemas.organization import BranchUpdateRequest
from app.services.execution import AuthorizedServiceExecutor
from app.services.portal_projections import PortalProjectionService
from app.services.insurance import InsuranceService
from app.services.employment_contracts import EmploymentContractService
from app.services.execution import ServiceExecutionError
from app.schemas.insurance import InsurancePolicyUpdateRequest, CoverageReplaceRequest
from app.schemas.employment_contract import ContractCommandRequest
from app.services.retained_records import RetainedRecordService
from app.services.employees import EmployeeCursorCodec, EmployeeService
from app.schemas.employees import EmployeeProfileSaveRequest
from app.employee_api import save_employee_profile
from app.services.leave_approval import LeaveApprovalService, ApprovalQueueQuery
from app.schemas.leave_approval import LeaveDecisionRequest
from app.repositories.dashboards import SqlDashboardRepository
from app.expiry_command import CLINICAL_DOCUMENT_TYPES
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request

spec = importlib.util.spec_from_file_location(
    "restoration_e", Path(__file__).with_name("verify-restoration-e-database.py")
)
assert spec and spec.loader
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
COMPANY = seed.COMPANY_ID[seed.HORIZON]
BRANCH = seed.BRANCH_DXB


async def main() -> None:
    if os.environ.get("RESTORATION_F_DISPOSABLE") != "true":
        raise RuntimeError("explicit disposable database confirmation required")
    migration = create_engine(previous.url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD"))
    runtime = create_async_engine(previous.url("workloop_runtime", "WORKLOOP_RUNTIME_PASSWORD"))
    rows = build_rows()
    with migration.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "f3a5c7e9b1d4"
        for table in ("idempotency_records", "audit_events", "leave_audit_log", "notifications"):
            connection.execute(text(f"DELETE FROM {table} WHERE company_id=:company"), {"company": COMPANY})
        connection.execute(text("DELETE FROM leave_balances WHERE id='f3000000-0000-4000-8000-000000000101'"))
        connection.execute(text("DELETE FROM salary_advances WHERE id='f3000000-0000-4000-8000-000000000102'"))
        connection.execute(text("DELETE FROM employee_job_history WHERE company_id=:company AND reason='Part F synthetic profile'"), {"company": COMPANY})
        connection.execute(text("DELETE FROM leave_approval_delegates WHERE id='f3000000-0000-4000-8000-000000000103'"))
        connection.execute(text("DELETE FROM training_records WHERE id::text LIKE 'f3100000-%'"))
        connection.execute(text("DELETE FROM certifications WHERE id::text LIKE 'f3110000-%'"))
        connection.execute(text("DELETE FROM incident_reports WHERE id::text LIKE 'f3120000-%'"))
        clean(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        protected = connection.execute(text("""
SELECT p.proname,r.rolname,p.prosecdef,p.proconfig,
 has_function_privilege('workloop_runtime',p.oid,'EXECUTE'),
 EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) acl
  WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE')
FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner
WHERE p.proname IN ('set_portal_record_archival','set_admin_appraisal_section_rating',
 'cancel_pending_advance','read_recent_manager_leave_actions','read_own_advance_progress',
 'set_manager_appraisal_section_rating','submit_manager_appraisal_review')
""")).all()
        assert len(protected) == 7
        for name, owner, definer, config, granted, public in protected:
            assert owner == "workloop_migration" and definer and granted and not public, name
            assert "search_path=pg_catalog, public, pg_temp" in config
        appraisal = connection.execute(text("""
SELECT a.id,a.updated_at,s.id section_id FROM appraisals a
JOIN appraisal_cycles c ON c.id=a.cycle_id JOIN appraisal_sections s ON s.appraisal_id=a.id
WHERE a.branch_id=:branch AND a.status='pending' AND c.status='active'
ORDER BY a.id,s.id LIMIT 1
"""), {"branch": BRANCH}).mappings().one()
        incident = connection.execute(text("SELECT id,updated_at FROM incident_reports WHERE branch_id=:branch AND status='open' LIMIT 1"), {"branch": BRANCH}).mappings().one()
        expense = connection.execute(text("SELECT id,updated_at FROM expense_claims WHERE branch_id=:branch AND status='pending' LIMIT 1"), {"branch": BRANCH}).mappings().one()
        advance = connection.scalar(text("SELECT id FROM salary_advances WHERE employee_id=(SELECT id FROM employees WHERE emp_no='H-DXB-002') AND status='active'"))
    resolver = ApplicationUserResolver(engine=runtime, issuer=seed.SEED_ISSUER, timeout_seconds=5)
    principals = [await resolver.resolve(issuer=seed.SEED_ISSUER, subject=subject) for subject in previous.SUBJECTS]
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime, setup_timeout_seconds=5, clock=lambda: seed.CLOCK_TIMESTAMP), deadline_seconds=15
    )
    app = create_app()
    app.state.authorized_service_executor = executor

    async def run(index, operation, branch=BRANCH):
        return await executor.execute(
            claims=previous.claims(previous.SUBJECTS[index]), principal=principals[index],
            selected_admin_branch_id=branch if index == 2 else None, operation=operation
        )

    async def raw(index, statement, values=None, branch=BRANCH):
        async def operation(connection):
            return (await connection.execute(text(statement), values or {})).scalar()
        return await run(index, operation, branch)

    def request(key):
        return Request({"type": "http", "app": app, "headers": [(b"idempotency-key", str(key).encode())],
                        "query_string": b"", "state": {"correlation_id": str(uuid.uuid4())}})

    overview = await run(2, lambda connection: PortalProjectionService(connection).admin_workspace(principals[2], BRANCH))
    with migration.connect() as connection:
        logo_before = connection.execute(text("SELECT logo_url,updated_at FROM branches WHERE id=:id"), {"id": BRANCH}).one()
    logo = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXN8AAAAASUVORK5CYII="
    logo_body = BranchUpdateRequest.model_validate({"logoUrl": logo, "expectedUpdatedAt": logo_before.updated_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")})
    async def logo_write_then_roll_back(connection):
        result = await OrganizationService(connection, BranchCursorCodec(b"f" * 32)).update_branch(principals[2], BRANCH, logo_body)
        assert result.logo_url == logo
        raise ServiceExecutionError("state_conflict")
    await previous.denied(run(2, logo_write_then_roll_back), "state_conflict")
    with migration.connect() as connection:
        assert connection.execute(text("SELECT logo_url,updated_at FROM branches WHERE id=:id"), {"id": BRANCH}).one() == logo_before
    await previous.denied(run(0, lambda connection: OrganizationService(connection, BranchCursorCodec(b"f" * 32)).update_branch(principals[0], BRANCH, logo_body)), "operation_not_permitted")
    assert overview.active_employees > 0 and overview.insurance_policies == 1
    assert set(overview.alerts) == {"probation", "contracts", "certifications", "requests", "appraisals", "documents", "insurance", "policyRenewals", "payrollApproval", "wpsOverdue"}
    await previous.denied(run(0, lambda connection: PortalProjectionService(connection).admin_workspace(principals[0], BRANCH)), "operation_not_permitted")
    with migration.connect() as connection:
        insured_employee = connection.scalar(text("SELECT employee_id FROM employee_insurance WHERE branch_id=:branch LIMIT 1"), {"branch": BRANCH})
    coverage = await run(2, lambda connection: InsuranceService(connection).read_coverage(principals[2], BRANCH, insured_employee))
    assert coverage is not None
    await previous.denied(run(2, lambda connection: InsuranceService(connection).read_coverage(principals[2], seed.BRANCH_AUH, insured_employee), seed.BRANCH_AUH), "resource_not_found")
    await previous.denied(run(0, lambda connection: InsuranceService(connection).read_coverage(principals[0], BRANCH, insured_employee)), "operation_not_permitted")

    async def update_insurance_and_roll_back(connection):
        service = InsuranceService(connection)
        policy = await service.get_policy(principals[2], BRANCH, coverage.policy_id)
        wire = policy.model_dump(mode="json", by_alias=True)
        values = {key: wire[key] for key in ("insurerName", "policyNumber", "tierName", "annualPremium", "renewalDate", "brokerName", "brokerContact", "notes")}
        saved = await service.update_policy(principals[2], BRANCH, policy.id, InsurancePolicyUpdateRequest.model_validate({**values, "notes": "F synthetic rollback", "expectedUpdatedAt": wire["updatedAt"]}))
        assert saved.notes == "F synthetic rollback"
        source = coverage.model_dump(mode="json", by_alias=True)
        values = {key: source[key] for key in ("policyId", "memberId", "cardNumber", "effectiveDate", "expiryDate", "tierName")}
        saved_coverage = await service.replace_coverage(principals[2], BRANCH, insured_employee, CoverageReplaceRequest.model_validate({**values, "memberId": "F-ROLLBACK", "expectedUpdatedAt": source["updatedAt"]}))
        assert saved_coverage.member_id == "F-ROLLBACK"
        raise ServiceExecutionError("state_conflict")
    await previous.denied(run(2, update_insurance_and_roll_back), "state_conflict")
    restored_coverage = await run(2, lambda connection: InsuranceService(connection).read_coverage(principals[2], BRANCH, insured_employee))
    assert restored_coverage == coverage

    contract_source = await run(2, lambda connection: EmploymentContractService(connection).current(principals[2], BRANCH, insured_employee))
    async def record_contract_and_roll_back(connection):
        action = "new" if contract_source.latest_contract_event_id is None else "renewed" if contract_source.current_contract_type == "Limited" else "converted"
        body = ContractCommandRequest.model_validate({"contractType": "Limited", "startDate": "2027-01-01", "endDate": "2028-01-01", "notes": "F synthetic rollback", "expected": contract_source.model_dump(mode="json", by_alias=True)})
        result = await EmploymentContractService(connection).record(principals[2], BRANCH, insured_employee, action, body)
        assert result.notes == "F synthetic rollback"
        raise ServiceExecutionError("state_conflict")
    await previous.denied(run(2, record_contract_and_roll_back), "state_conflict")
    assert await run(2, lambda connection: EmploymentContractService(connection).current(principals[2], BRANCH, insured_employee)) == contract_source
    pdf = await download_employment_contract_pdf(insured_employee, request(uuid.uuid4()), previous.claims(previous.SUBJECTS[2]), principals[2], BRANCH)
    assert bytes(pdf.body).startswith(b'%PDF-') and pdf.headers['content-type'] == 'application/pdf'
    assert pdf.headers['cache-control'] == 'no-store'
    await previous.denied(download_employment_contract_pdf(insured_employee, request(uuid.uuid4()), previous.claims(previous.SUBJECTS[0]), principals[0], BRANCH), 'operation_not_permitted')
    await previous.denied(download_employment_contract_pdf(insured_employee, request(uuid.uuid4()), previous.claims(previous.SUBJECTS[2]), principals[2], seed.BRANCH_AUH), 'resource_not_found')
    with migration.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM audit_events WHERE entity_id=:id AND action='employment_contract_pdf_exported'"), {"id": insured_employee}) == 1

    async def archival(function, kind, record, expected, key=None):
        return await function(kind, record, VersionRequest.model_validate({"expectedUpdatedAt": expected}),
                              request(key or uuid.uuid4()), previous.claims(previous.SUBJECTS[2]), principals[2], BRANCH)

    for kind, record in (("appraisal", appraisal), ("incident_report", incident), ("expense_claim", expense)):
        service = lambda connection: RetainedRecordService(connection)
        original = await run(2, lambda connection: service(connection).read(principals[2], BRANCH, kind, record["id"]))
        expected = original.model_dump(mode="json", by_alias=True)["updatedAt"]
        await previous.denied(run(0, lambda connection: service(connection).archive(principals[0], BRANCH, kind, record["id"], original.updated_at, True)), "operation_not_permitted")
        assert await raw(2, "SELECT public.set_portal_record_archival(:kind,:id,:expected,true)", {"kind": kind, "id": record["id"], "expected": expected}, seed.BRANCH_AUH) == "resource_not_found"
        key = uuid.uuid4()
        first = await archival(archive_portal_record, kind, record["id"], expected, key)
        replay = await archival(archive_portal_record, kind, record["id"], expected, key)
        assert json.loads(first.body) == json.loads(replay.body)
        archived = json.loads(first.body)["data"]
        assert archived["archived"]
        listed = await run(2, lambda connection: service(connection).list(principals[2], BRANCH, kind, 101, None))
        assert record["id"] in {item.id for item in listed}
        table = {"appraisal": "appraisals", "incident_report": "incident_reports", "expense_claim": "expense_claims"}[kind]
        await previous.database_denied(raw(2, f"UPDATE {table} SET archived_at=NULL WHERE id=:id", {"id": record["id"]}), "42501")
        await previous.denied(archival(restore_portal_record, kind, record["id"], expected), "state_conflict")
        restored = json.loads((await archival(restore_portal_record, kind, record["id"], archived["updatedAt"])).body)["data"]
        assert not restored["archived"]
        with migration.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM audit_events WHERE entity_id=:id AND action IN ('portal_record_archived','portal_record_restored')"), {"id": record["id"]}) == 2

    with migration.connect() as connection:
        version = connection.scalar(text("SELECT updated_at FROM appraisals WHERE id=:id"), {"id": appraisal["id"]})
    rating = {"id": appraisal["id"], "section": appraisal["section_id"], "expected": version}
    assert await raw(0, "SELECT public.set_admin_appraisal_section_rating(:id,:section,:expected,4.0,'Synthetic rating')", rating) == "operation_not_permitted"
    assert await raw(2, "SELECT public.set_admin_appraisal_section_rating(:id,:section,:expected,4.0,'Synthetic rating')", rating) == "ok"
    assert await raw(2, "SELECT public.set_admin_appraisal_section_rating(:id,:section,:expected,5.0,'Stale rating')", rating) == "state_conflict"
    progress = await run(0, lambda connection: PortalProjectionService(connection).own_advance_progress(principals[0], advance, 1, None))
    assert progress.summary.amount == "1500.00" and progress.summary.total_paid == "500.00"
    assert progress.summary.outstanding_balance == "1000.00" and len(progress.data) == 1
    assert sum(Decimal(row.scheduled_amount) for row in progress.summary.schedule) == 1500
    assert sum(Decimal(row.paid_amount) for row in progress.summary.schedule) == 500
    assert sum(Decimal(row.remaining_amount) for row in progress.summary.schedule) == 1000
    await previous.denied(run(1, lambda connection: PortalProjectionService(connection).own_advance_progress(principals[1], advance, 1, None)), "resource_not_found")
    await previous.denied(run(2, lambda connection: PortalProjectionService(connection).own_advance_progress(principals[2], advance, 1, None)), "operation_not_permitted")
    expiry = await run(2, lambda connection: PortalProjectionService(connection).employee_expiry(principals[2], BRANCH, 101, None))
    assert expiry and len({row.id for row in expiry}) == len(expiry)
    with migration.begin() as connection:
        sample_training = connection.scalar(text("SELECT id FROM training_records WHERE company_id=:company AND branch_id=:branch ORDER BY id LIMIT 1"), {"company": COMPANY, "branch": BRANCH})
        connection.execute(text("""
INSERT INTO training_records
SELECT (jsonb_populate_record(NULL::training_records,to_jsonb(source)||jsonb_build_object(
 'id',('f3100000-0000-4000-8000-'||lpad(number::text,12,'0'))::uuid))).*
FROM training_records source CROSS JOIN generate_series(1,101) number WHERE source.id=:id
"""), {"id": sample_training})
    seen_training = []
    after = None
    while True:
        page = await run(2, lambda connection: DevelopmentService(connection, scanner_definition="synthetic-v1").list_training(principals[2], BRANCH, TrainingListQuery(None,None,None,None,None,101,after), scope="admin"))
        visible = page[:100]
        seen_training.extend(row.id for row in visible)
        if len(page) <= 100:
            break
        after = visible[-1].id
    assert len(seen_training) == len(set(seen_training))
    assert len([record for record in seen_training if str(record).startswith("f3100000-")]) == 101
    for table, prefix in (("certifications", "f3110000"), ("incident_reports", "f3120000")):
        with migration.begin() as connection:
            sample_id = connection.scalar(text(f"SELECT id FROM {table} WHERE company_id=:company AND branch_id=:branch ORDER BY id LIMIT 1"), {"company": COMPANY, "branch": BRANCH})
            assert sample_id is not None
            connection.execute(text(f"""
INSERT INTO {table}
SELECT (jsonb_populate_record(NULL::{table},to_jsonb(source)||jsonb_build_object(
 'id',('{prefix}-0000-4000-8000-'||lpad(number::text,12,'0'))::uuid))).*
FROM {table} source CROSS JOIN generate_series(1,101) number WHERE source.id=:id
"""), {"id": sample_id})
        after_id = None
        collected = []
        while True:
            if table == "certifications":
                records = await run(2, lambda connection: DevelopmentService(connection, scanner_definition="synthetic-v1").list_certifications(principals[2], BRANCH, CertificationListQuery(None, None, 101, after_id), scope="admin"))
            else:
                records = await run(2, lambda connection: IncidentService(connection).list(principals[2], BRANCH, IncidentListQuery(None, None, None, None, None, 101, after_id)))
            collected.extend(record.id for record in records[:100])
            if len(records) <= 100:
                break
            after_id = records[99].id
        assert len(collected) == len(set(collected))
        assert sum(str(record).startswith(prefix) for record in collected) == 101
        with migration.begin() as connection:
            connection.execute(text(f"DELETE FROM {table} WHERE id::text LIKE :prefix"), {"prefix": prefix + "-%"})
    with migration.begin() as connection:
        connection.execute(text("DELETE FROM training_records WHERE id::text LIKE 'f3100000-%'"))
    directory = await run(2, lambda connection: PortalProjectionService(connection).employee_directory_details(principals[2], BRANCH, 101, None))
    assert directory and all(row.mol_id for row in directory)
    await previous.denied(run(0, lambda connection: PortalProjectionService(connection).employee_directory_details(principals[0], BRANCH, 101, None)), "operation_not_permitted")
    cme = await run(2, lambda connection: DevelopmentService(connection, scanner_definition="synthetic-v1").branch_cme(principals[2], BRANCH, 2026, 101, None))
    for employee_summary in cme:
        contributions = await run(2, lambda connection: DevelopmentService(connection, scanner_definition="synthetic-v1").cme_contributions(principals[2], BRANCH, employee_summary.employee_id, 2026, 101, None))
        completed = sum((row.duration_hours or Decimal(0) for row in contributions if row.status == "completed"), Decimal(0))
        in_progress = sum((row.duration_hours or Decimal(0) for row in contributions if row.status in {"planned", "in_progress"}), Decimal(0))
        assert completed.quantize(Decimal("0.1")) == employee_summary.achieved_hours
        assert in_progress.quantize(Decimal("0.1")) == employee_summary.in_progress_hours
    for status in ("valid", "expiring", "expired"):
        details = await run(2, lambda connection: PortalProjectionService(connection).clinical_credentials(principals[2], BRANCH, status, "synthetic-v1", 101, None))
        assert all(row.status == status for row in details)
        snapshot = await run(2, lambda connection: SqlDashboardRepository(connection, "synthetic-v1").snapshot("clinical", company_id=COMPANY, branch_id=BRANCH, employee_id=None, clinical_types=tuple(CLINICAL_DOCUMENT_TYPES)))
        assert len(details) == snapshot[f"{status}_count"]
    workforce = await run(2, lambda connection: PortalProjectionService(connection).clinical_workforce_summary(principals[2], BRANCH, "synthetic-v1"))
    assert sum(item.headcount for item in workforce.departments) == workforce.counts["activeStaff"]
    assert sum(item.credentialled for item in workforce.departments) == workforce.compliant
    for group, count in workforce.counts.items():
        detail = await run(2, lambda connection: PortalProjectionService(connection).clinical_workforce_details(principals[2], BRANCH, "synthetic-v1", group, 101, None))
        assert len(detail) == count and len({item.id for item in detail}) == count, group
    await previous.denied(run(0, lambda connection: PortalProjectionService(connection).clinical_workforce_summary(principals[0], BRANCH, "synthetic-v1")), "operation_not_permitted")

    codec = EmployeeCursorCodec(b"F" * 32)
    queue, _ = await run(1, lambda connection: LeaveApprovalService(connection, codec).list_staff_queue(principals[1], ApprovalQueueQuery(100, None)))
    target = next(item for item in queue if item.can_decide)
    with migration.begin() as connection:
        connection.execute(text("""
INSERT INTO leave_balances(id,company_id,branch_id,employee_id,leave_type_id,leave_year,
 entitled_days,accrued_days,pending_days,remaining_days)
SELECT 'f3000000-0000-4000-8000-000000000101',company_id,branch_id,employee_id,
 leave_type_id,2026,100,100,days_requested,100-days_requested FROM leave_requests WHERE id=:id
"""), {"id": target.request.id})
    await run(1, lambda connection: LeaveApprovalService(connection, codec).decide_staff(principals[1], target.request.id, LeaveDecisionRequest.model_validate({"decision": "reject", "reason": "Synthetic F history proof", "expectedUpdatedAt": target.request.model_dump(mode="json", by_alias=True)["updatedAt"]})))
    async def history():
        return await run(1, lambda connection: PortalProjectionService(connection).recent_leave_actions(principals[1], 101, None))
    entries = await history()
    entry = next(item for item in entries if item.request_id == target.request.id)
    assert entry.actor_name == "You" and entry.reason == "Synthetic F history proof"
    assert "actorAppUserId" not in entry.model_dump(mode="json", by_alias=True)
    with migration.begin() as connection:
        old_manager = connection.scalar(text("SELECT reporting_manager_id FROM employees WHERE id=:id"), {"id": target.request.employee_id})
        connection.execute(text("UPDATE employees SET reporting_manager_id=NULL WHERE id=:id"), {"id": target.request.employee_id})
    assert all(item.request_id != target.request.id for item in await history())
    with migration.begin() as connection:
        delegator = connection.execute(text("SELECT employee.id,profile.app_user_id,profile.role FROM employees employee JOIN user_profiles profile ON profile.employee_id=employee.id WHERE employee.emp_no='H-DXB-005'")).one()
        connection.execute(text("UPDATE user_profiles SET role='manager' WHERE app_user_id=:id"), {"id": delegator.app_user_id})
        connection.execute(text("UPDATE employees SET reporting_manager_id=:manager WHERE id=:id"), {"manager": delegator.id, "id": target.request.employee_id})
        connection.execute(text("""
INSERT INTO leave_approval_delegates(id,company_id,branch_id,approver_employee_id,
 delegate_employee_id,from_date,to_date)
VALUES('f3000000-0000-4000-8000-000000000103',:company,:branch,:approver,:delegate,
 '2026-08-01','2026-08-31')
"""), {"company": COMPANY, "branch": BRANCH, "approver": delegator.id, "delegate": principals[1].employee_id})
    assert any(item.id == entry.id for item in await history())
    with migration.begin() as connection:
        connection.execute(text("UPDATE leave_approval_delegates SET to_date='2026-08-26' WHERE id='f3000000-0000-4000-8000-000000000103'"))
    assert all(item.id != entry.id for item in await history())
    with migration.begin() as connection:
        connection.execute(text("DELETE FROM leave_approval_delegates WHERE id='f3000000-0000-4000-8000-000000000103'"))
        connection.execute(text("UPDATE user_profiles SET role=:role WHERE app_user_id=:id"), {"id": delegator.app_user_id, "role": delegator.role})
    with migration.begin() as connection:
        connection.execute(text("UPDATE employees SET reporting_manager_id=:manager WHERE id=:id"), {"id": target.request.employee_id, "manager": old_manager})
        connection.execute(text("UPDATE leave_audit_log SET created_at=statement_timestamp()-interval '91 days' WHERE id=:id"), {"id": entry.id})
    assert all(item.id != entry.id for item in await history())

    with migration.begin() as connection:
        before = connection.execute(text("SELECT * FROM appraisals WHERE id=:id"), {"id": appraisal["id"]}).mappings().one()
        audits = connection.scalar(text("SELECT count(*) FROM audit_events WHERE entity_id=:id"), {"id": appraisal["id"]})
        connection.execute(text("""
CREATE FUNCTION public.restoration_f_fail_audit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'synthetic audit failure' USING ERRCODE='23514'; END $$;
CREATE TRIGGER restoration_f_fail_audit BEFORE INSERT ON audit_events
FOR EACH ROW EXECUTE FUNCTION public.restoration_f_fail_audit()
"""))
    try:
        await previous.database_denied(raw(2, "SELECT public.set_portal_record_archival('appraisal',:id,:expected,true)", {"id": appraisal["id"], "expected": before["updated_at"]}), "23514")
    finally:
        with migration.begin() as connection:
            connection.execute(text("DROP TRIGGER restoration_f_fail_audit ON audit_events; DROP FUNCTION public.restoration_f_fail_audit()"))
    with migration.connect() as connection:
        assert dict(connection.execute(text("SELECT * FROM appraisals WHERE id=:id"), {"id": appraisal["id"]}).mappings().one()) == dict(before)
        assert connection.scalar(text("SELECT count(*) FROM audit_events WHERE entity_id=:id"), {"id": appraisal["id"]}) == audits
    outcomes = await asyncio.gather(*[raw(2, "SELECT public.set_admin_appraisal_section_rating(:id,:section,:expected,4.5,'Concurrent proof')", {**rating, "expected": before["updated_at"]}) for _ in range(2)])
    assert sorted(outcomes) == ["ok", "state_conflict"]
    with migration.begin() as connection:
        pending = connection.execute(text("""
INSERT INTO salary_advances(id,company_id,branch_id,employee_id,amount,outstanding_balance,
 repayment_months,monthly_deduction,repayment_start_month,status)
SELECT 'f3000000-0000-4000-8000-000000000102',company_id,branch_id,employee_id,
 100,100,1,100,'2026-10-01','pending' FROM salary_advances WHERE id=:id
RETURNING id,updated_at
"""), {"id": advance}).mappings().one()
    pending_version = pending["updated_at"].isoformat()
    key = uuid.uuid4()
    body = VersionRequest.model_validate({"expectedUpdatedAt": pending_version})
    cancelled = await cancel_pending_admin_advance(pending["id"], body, request(key), previous.claims(previous.SUBJECTS[2]), principals[2], BRANCH)
    replay = await cancel_pending_admin_advance(pending["id"], body, request(key), previous.claims(previous.SUBJECTS[2]), principals[2], BRANCH)
    assert json.loads(cancelled.body) == json.loads(replay.body)
    assert json.loads(cancelled.body)["data"]["status"] == "cancelled"
    with migration.connect() as connection:
        active_version = connection.scalar(text("SELECT updated_at FROM salary_advances WHERE id=:id"), {"id": advance})
        assert connection.scalar(text("SELECT count(*) FROM audit_events WHERE entity_id=:id AND action='salary_advance_admin_cancelled'"), {"id": pending["id"]}) == 1
    assert await raw(2, "SELECT public.cancel_pending_advance(:id,:expected)", {"id": advance, "expected": active_version}) == "state_conflict"
    app.state.employee_cursor_codec = codec
    employee_id = principals[0].employee_id
    profile = await run(2, lambda connection: EmployeeService(connection, codec).get_employee(principals[2], BRANCH, employee_id))
    original = profile.model_dump(mode="json", by_alias=True)
    with migration.connect() as connection:
        department = connection.scalar(text("SELECT name FROM departments WHERE branch_id=:branch AND name<>:name ORDER BY id LIMIT 1"), {"branch": BRANCH, "name": original["department"]})
    values = {
        "expectedUpdatedAt": original["updatedAt"], "reason": "Part F synthetic profile",
        "profile": {"expectedUpdatedAt": original["updatedAt"], "phone": "+971500000901"},
        "jobTitle": "Part F synthetic clinician", "department": department or original["department"],
        "reportingManagerId": None,
        **{field: original[field] for field in ("allowance", "housingAllowance", "transportAllowance", "otherAllowances", "otherAllowancesLabel")},
        "basicSalary": f"{Decimal(original['basicSalary']) + Decimal('0.01'):.2f}",
    }
    async def profile_command(payload, key=None, branch=BRANCH):
        return await save_employee_profile(request(key or uuid.uuid4()), EmployeeProfileSaveRequest.model_validate(payload), str(employee_id), previous.claims(previous.SUBJECTS[2]), principals[2], branch)
    await previous.denied(profile_command({**values, "reportingManagerId": str(employee_id)}), "manager_reassignment_conflict")
    manager = await run(2, lambda connection: EmployeeService(connection, codec).get_employee(principals[2], BRANCH, principals[1].employee_id))
    manager_values = {**values, "expectedUpdatedAt": manager.model_dump(mode="json", by_alias=True)["updatedAt"], "profile": {"expectedUpdatedAt": manager.model_dump(mode="json", by_alias=True)["updatedAt"], "phone": manager.phone}, "reportingManagerId": str(employee_id)}
    await previous.denied(save_employee_profile(request(uuid.uuid4()), EmployeeProfileSaveRequest.model_validate(manager_values), str(manager.id), previous.claims(previous.SUBJECTS[2]), principals[2], BRANCH), "manager_reassignment_conflict")
    await previous.denied(profile_command(values, branch=seed.BRANCH_AUH), "resource_not_found")
    stale = {**values, "expectedUpdatedAt": "2020-01-01T00:00:00.000Z", "profile": {**values["profile"], "expectedUpdatedAt": "2020-01-01T00:00:00.000Z"}}
    await previous.denied(profile_command(stale), "state_conflict")
    with migration.begin() as connection:
        before_employee = dict(connection.execute(text("SELECT * FROM employees WHERE id=:id"), {"id": employee_id}).mappings().one())
        before_history = connection.scalar(text("SELECT count(*) FROM employee_job_history WHERE employee_id=:id"), {"id": employee_id})
        connection.execute(text("""
CREATE FUNCTION public.restoration_f_fail_audit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'synthetic profile audit failure' USING ERRCODE='23514'; END $$;
CREATE TRIGGER restoration_f_fail_audit BEFORE INSERT ON audit_events
FOR EACH ROW EXECUTE FUNCTION public.restoration_f_fail_audit()
"""))
    try:
        await previous.database_denied(profile_command(values), "23514")
    finally:
        with migration.begin() as connection:
            connection.execute(text("DROP TRIGGER restoration_f_fail_audit ON audit_events; DROP FUNCTION public.restoration_f_fail_audit()"))
    with migration.connect() as connection:
        assert dict(connection.execute(text("SELECT * FROM employees WHERE id=:id"), {"id": employee_id}).mappings().one()) == before_employee
        assert connection.scalar(text("SELECT count(*) FROM employee_job_history WHERE employee_id=:id"), {"id": employee_id}) == before_history
    profile_key = uuid.uuid4()
    first = await profile_command(values, profile_key)
    replay = await profile_command(values, profile_key)
    assert json.loads(first.body) == json.loads(replay.body)
    saved = json.loads(first.body)["data"]
    assert saved["phone"] == values["profile"]["phone"] and saved["jobTitle"] == values["jobTitle"]
    assert saved["department"] == values["department"] and saved["basicSalary"] == values["basicSalary"]
    assert saved["reportingManagerId"] is None
    with migration.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM employee_job_history WHERE employee_id=:id"), {"id": employee_id}) == before_history + (3 if department else 2)
        assert connection.scalar(text("SELECT count(*) FROM audit_events WHERE entity_id=:id AND action='employee_manager_changed' AND reason='Part F synthetic profile'"), {"id": employee_id}) == 1
    await previous.denied(profile_command(values), "state_conflict")
    with migration.begin() as connection:
        full_id = connection.scalar(text("SELECT a.id FROM appraisals a JOIN employees e ON e.id=a.employee_id WHERE e.emp_no='H-DXB-004' AND a.status='reviewed'"))
        connection.execute(text("UPDATE appraisals SET status='pending',overall_rating=NULL,reviewed_at=NULL,reviewed_by_app_user_id=NULL WHERE id=:id"), {"id": full_id})
        connection.execute(text("UPDATE appraisal_sections SET rating=NULL,comments='' WHERE appraisal_id=:id"), {"id": full_id})
    full = await run(2, lambda connection: AppraisalService(connection).get_appraisal(principals[2], BRANCH, full_id))
    review_body = AppraisalAdminReviewRequest.model_validate({
        "expectedUpdatedAt": full.model_dump(mode="json", by_alias=True)["updatedAt"],
        "sections": [{"id": section.id, "rating": "4.0", "comments": "Synthetic section review"} for section in full.sections],
        "reviewerComments": "Synthetic overall review", "developmentPlan": "Synthetic development plan",
    })
    async def review_command(key=None):
        return await save_admin_appraisal_review(full_id, review_body, request(key or uuid.uuid4()), previous.claims(previous.SUBJECTS[2]), principals[2], BRANCH)
    with migration.begin() as connection:
        connection.execute(text("""
CREATE FUNCTION public.restoration_f_fail_review() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN IF NEW.action='appraisal_reviewed' THEN
 RAISE EXCEPTION 'synthetic review audit failure' USING ERRCODE='23514'; END IF;
RETURN NEW; END $$;
CREATE TRIGGER restoration_f_fail_review BEFORE INSERT ON audit_events
FOR EACH ROW EXECUTE FUNCTION public.restoration_f_fail_review()
"""))
    try:
        await previous.database_denied(review_command(), "23514")
    finally:
        with migration.begin() as connection:
            connection.execute(text("DROP TRIGGER restoration_f_fail_review ON audit_events; DROP FUNCTION public.restoration_f_fail_review()"))
    after_failure = await run(2, lambda connection: AppraisalService(connection).get_appraisal(principals[2], BRANCH, full_id))
    assert after_failure == full
    review_key = uuid.uuid4()
    first_review = await review_command(review_key)
    replay_review = await review_command(review_key)
    assert json.loads(first_review.body) == json.loads(replay_review.body)
    final_review = json.loads(first_review.body)["data"]
    assert final_review["overallRating"] == "4.0" and final_review["status"] == "reviewed"
    assert all(section["rating"] == "4.0" for section in final_review["sections"])
    await previous.denied(review_command(), "state_conflict")
    with migration.begin() as connection:
        manager_review_id = full_id
        connection.execute(text("UPDATE appraisals SET status='pending',overall_rating=NULL,reviewed_at=NULL,reviewed_by_app_user_id=NULL WHERE id=:id"), {"id": manager_review_id})
        connection.execute(text("UPDATE employees SET reporting_manager_id=:manager WHERE id=(SELECT employee_id FROM appraisals WHERE id=:id)"), {"id": manager_review_id, "manager": principals[1].employee_id})
    manager_current = await run(1, lambda connection: AppraisalService(connection).get_appraisal(principals[1], BRANCH, manager_review_id))
    section_body = AppraisalSectionRatingRequest.model_validate({
        "expectedUpdatedAt": manager_current.model_dump(mode="json", by_alias=True)["updatedAt"],
        "rating": "3.0", "comments": "Synthetic manager section",
    })
    manager_rated = await run(1, lambda connection: AppraisalService(connection).rate_section(principals[1], BRANCH, manager_review_id, manager_current.sections[0].id, section_body))
    assert manager_rated.sections[0].rating == 3
    await previous.denied(run(1, lambda connection: AppraisalService(connection).rate_section(principals[1], BRANCH, manager_review_id, manager_current.sections[0].id, section_body)), "state_conflict")
    manager_body = AppraisalManagerReviewRequest.model_validate({
        "expectedUpdatedAt": manager_rated.model_dump(mode="json", by_alias=True)["updatedAt"],
        "sections": [{"id": section.id, "rating": "4.0", "comments": "Synthetic complete manager review"} for section in manager_rated.sections],
    })
    async def manager_command(key=None, index=1):
        return await submit_manager_appraisal_review(manager_review_id, request(key or uuid.uuid4()), manager_body, previous.claims(previous.SUBJECTS[index]), principals[index])
    await previous.denied(manager_command(index=0), "operation_not_permitted")
    await previous.denied(manager_command(index=2), "operation_not_permitted")
    with migration.begin() as connection:
        connection.execute(text("UPDATE employees SET reporting_manager_id=NULL WHERE id=(SELECT employee_id FROM appraisals WHERE id=:id)"), {"id": manager_review_id})
    await previous.denied(manager_command(), "resource_not_found")
    with migration.begin() as connection:
        connection.execute(text("UPDATE employees SET reporting_manager_id=:manager WHERE id=(SELECT employee_id FROM appraisals WHERE id=:id)"), {"id": manager_review_id, "manager": principals[1].employee_id})
        connection.execute(text("""
CREATE FUNCTION public.restoration_f_fail_manager_review() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN IF NEW.action='appraisal_manager_reviewed' THEN
 RAISE EXCEPTION 'synthetic manager review audit failure' USING ERRCODE='23514'; END IF;
RETURN NEW; END $$;
CREATE TRIGGER restoration_f_fail_manager_review BEFORE INSERT ON audit_events
FOR EACH ROW EXECUTE FUNCTION public.restoration_f_fail_manager_review()
"""))
    try:
        await previous.database_denied(manager_command(), "23514")
    finally:
        with migration.begin() as connection:
            connection.execute(text("DROP TRIGGER restoration_f_fail_manager_review ON audit_events; DROP FUNCTION public.restoration_f_fail_manager_review()"))
    after_manager_failure = await run(1, lambda connection: AppraisalService(connection).get_appraisal(principals[1], BRANCH, manager_review_id))
    assert after_manager_failure == manager_rated
    manager_key = uuid.uuid4()
    manager_saved = await manager_command(manager_key)
    manager_replay = await manager_command(manager_key)
    assert json.loads(manager_saved.body) == json.loads(manager_replay.body)
    manager_result = json.loads(manager_saved.body)["data"]
    assert manager_result["status"] == "reviewed" and manager_result["overallRating"] == "4.0"
    assert all(section["rating"] == "4.0" for section in manager_result["sections"])
    await previous.denied(manager_command(), "state_conflict")
    with migration.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM audit_events WHERE entity_id=:id AND action='appraisal_manager_reviewed'"), {"id": manager_review_id}) == 1
    config = Config("/app/alembic.ini")
    try:
        alembic_command.downgrade(config, "e2c4f6a8b0d3")
    except DBAPIError as error:
        assert "portal_retained_data_requires_preservation" in str(error.orig)
    else:
        raise AssertionError("retained portal audit was downgraded")
    with migration.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "f3a5c7e9b1d4"
        connection.execute(text("DELETE FROM audit_events WHERE company_id=:company AND action IN ('portal_record_archived','portal_record_restored','appraisal_section_admin_rated','salary_advance_admin_cancelled','appraisal_manager_reviewed','employment_contract_pdf_exported')"), {"company": COMPANY})
    alembic_command.downgrade(config, "e2c4f6a8b0d3")
    with migration.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "e2c4f6a8b0d3"
    alembic_command.upgrade(config, "head")
    alembic_command.upgrade(config, "head")
    with migration.begin() as connection:
        for table in ("idempotency_records", "audit_events", "leave_audit_log", "notifications"):
            connection.execute(text(f"DELETE FROM {table} WHERE company_id=:company"), {"company": COMPANY})
        connection.execute(text("DELETE FROM leave_balances WHERE id='f3000000-0000-4000-8000-000000000101'"))
        connection.execute(text("DELETE FROM salary_advances WHERE id='f3000000-0000-4000-8000-000000000102'"))
        connection.execute(text("DELETE FROM employee_job_history WHERE company_id=:company AND reason='Part F synthetic profile'"), {"company": COMPANY})
        connection.execute(text("DELETE FROM leave_approval_delegates WHERE id='f3000000-0000-4000-8000-000000000103'"))
        clean(connection, rows)
    await runtime.dispose()
    migration.dispose()
    print("Restoration F retained commands and scoped projections passed")


if __name__ == "__main__":
    asyncio.run(main())
