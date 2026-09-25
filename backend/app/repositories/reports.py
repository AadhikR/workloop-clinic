from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

REPORT_QUERIES = {
    "headcount": """
SELECT employee.id "employeeId",employee.emp_no "employeeNumber",employee.name "employeeName",
 employee.department,employee.nationality,employee.contract_type "contractType",employee.gender,
 employee.employment_status status
FROM public.employees employee
WHERE employee.company_id=:company_id AND employee.branch_id=:branch_id AND employee.active
 AND employee.employment_status IN ('Active','Probation','On Leave')
 AND (CAST(:status AS text) IS NULL OR employee.employment_status=:status)
 AND (CAST(:department AS text) IS NULL OR employee.department=:department)
ORDER BY lower(employee.name),employee.id
""",
    "payrollCost": """
SELECT run.id "runId",run.period,run.payment_date "paymentDate",
 count(entry.id)::integer "employeeCount",
 coalesce(sum(entry.basic_salary),0)::numeric(14,2) basic,
 coalesce(sum(entry.housing_allowance+entry.transport_allowance+entry.allowance),0)
   ::numeric(14,2) allowances,
 coalesce(sum(entry.increment+entry.bonus+entry.other_pay+entry.variable_allowance),0)
   ::numeric(14,2) "otherEarnings",
 coalesce(sum(entry.basic_salary+entry.housing_allowance+entry.transport_allowance+entry.allowance+
   entry.increment+entry.bonus+entry.other_pay+entry.variable_allowance),0)::numeric(14,2) gross,
 (coalesce(sum(entry.basic_salary+entry.housing_allowance+entry.transport_allowance+entry.allowance+
   entry.increment+entry.bonus+entry.other_pay+entry.variable_allowance),0)-run.total_disbursed)
   ::numeric(14,2) deductions,
 run.total_disbursed::numeric(14,2) net
FROM public.payroll_runs run
JOIN public.payroll_entries entry ON entry.payroll_run_id=run.id AND entry.company_id=run.company_id
 AND entry.branch_id=run.branch_id AND NOT entry.excluded
WHERE run.company_id=:company_id AND run.branch_id=:branch_id
 AND run.status='generated' AND run.approval_status='approved'
 AND (CAST(:period AS text) IS NULL OR run.period=:period)
GROUP BY run.id,run.period,run.payment_date,run.total_disbursed
ORDER BY run.period DESC,run.id DESC
""",
    "leaveUtilization": """
SELECT employee.id "employeeId",employee.name "employeeName",employee.department,
 leave_type.name "leaveType",count(request.id)::integer "requestCount",
 sum(request.days_requested)::numeric(10,2) days
FROM public.leave_requests request
JOIN public.employees employee ON employee.id=request.employee_id
 AND employee.company_id=request.company_id AND employee.branch_id=request.branch_id
JOIN public.leave_types leave_type ON leave_type.id=request.leave_type_id
 AND leave_type.company_id=request.company_id AND leave_type.branch_id=request.branch_id
WHERE request.company_id=:company_id AND request.branch_id=:branch_id AND request.status='Approved'
 AND (CAST(:date_from AS date) IS NULL OR request.end_date>=:date_from)
 AND (CAST(:date_to AS date) IS NULL OR request.start_date<=:date_to)
 AND (CAST(:employee_id AS uuid) IS NULL OR request.employee_id=:employee_id)
 AND (CAST(:department AS text) IS NULL OR employee.department=:department)
GROUP BY employee.id,employee.name,employee.department,leave_type.id,leave_type.name
ORDER BY lower(employee.name),employee.id,leave_type.name,leave_type.id
""",
    "attendanceSummary": """
SELECT employee.id "employeeId",employee.name "employeeName",employee.department,
 count(record.id)::integer days,
 count(*) FILTER (WHERE record.status IN ('PRESENT','LATE','EARLY_DEPARTURE','HALF_DAY',
   'OVERTIME','PRESENT_REMOTE','MISSING_CLOCK_OUT'))::integer present,
 count(*) FILTER (WHERE record.status='ABSENT')::integer absent,
 count(*) FILTER (WHERE record.late_minutes>0)::integer late,
 count(*) FILTER (WHERE record.early_departure_minutes>0)::integer "earlyDeparture",
 coalesce(sum(record.total_hours),0)::numeric(12,2) hours
FROM public.attendance_records record
JOIN public.employees employee ON employee.id=record.employee_id
 AND employee.company_id=record.company_id AND employee.branch_id=record.branch_id
WHERE record.company_id=:company_id AND record.branch_id=:branch_id AND record.source_stale=false
 AND (CAST(:period AS text) IS NULL OR to_char(record.date,'YYYY-MM')=:period)
 AND (CAST(:status AS text) IS NULL OR record.status=:status)
 AND (CAST(:employee_id AS uuid) IS NULL OR record.employee_id=:employee_id)
 AND (CAST(:department AS text) IS NULL OR employee.department=:department)
GROUP BY employee.id,employee.name,employee.department
ORDER BY lower(employee.name),employee.id
""",
    "overtime": """
SELECT record.id "recordId",record.date,employee.id "employeeId",employee.name "employeeName",
 employee.department,record.overtime_hours::numeric(10,2) hours,
 record.overtime_amount::numeric(14,2) amount,record.overtime_approved_at "approvedAt"
FROM public.attendance_records record
JOIN public.employees employee ON employee.id=record.employee_id
 AND employee.company_id=record.company_id AND employee.branch_id=record.branch_id
WHERE record.company_id=:company_id AND record.branch_id=:branch_id AND record.source_stale=false
 AND record.overtime_approved AND record.overtime_hours>0
 AND (CAST(:period AS text) IS NULL OR to_char(record.date,'YYYY-MM')=:period)
 AND (CAST(:employee_id AS uuid) IS NULL OR record.employee_id=:employee_id)
 AND (CAST(:department AS text) IS NULL OR employee.department=:department)
ORDER BY record.date,record.overtime_approved_at NULLS LAST,record.id
""",
    "documentExpiry": """
WITH sources AS (
 SELECT employee.id "sourceId",employee.id "employeeId",employee.name "employeeName",
  employee.department,source.kind "sourceKind",source.label "documentType",
  source.expiry_date "expiryDate",
  employee.employment_status status
 FROM public.employees employee
 CROSS JOIN LATERAL (VALUES
  ('identity:visa','Visa',employee.visa_expiry),
  ('identity:passport','Passport',employee.passport_expiry),
  ('identity:emiratesId','Emirates ID',employee.emirates_id_expiry),
  ('identity:labourCard','Labour card',employee.labour_card_expiry),
  ('identity:licence','Professional licence',employee.licence_expiry)
 ) source(kind,label,expiry_date)
 WHERE employee.company_id=:company_id AND employee.branch_id=:branch_id
  AND source.expiry_date IS NOT NULL
 UNION ALL
 SELECT document.id,employee.id,employee.name,employee.department,'employeeDocument',
  document.document_type,document.expiry_date,document.status
 FROM public.employee_documents document
 JOIN public.employees employee ON employee.id=document.employee_id
  AND employee.company_id=document.company_id AND employee.branch_id=document.branch_id
 WHERE document.company_id=:company_id AND document.branch_id=:branch_id
  AND document.status='verified' AND document.expiry_date IS NOT NULL
)
SELECT * FROM sources
WHERE (CAST(:date_from AS date) IS NULL OR "expiryDate">=:date_from)
 AND (CAST(:date_to AS date) IS NULL OR "expiryDate"<=:date_to)
 AND (CAST(:status AS text) IS NULL OR status=:status)
 AND (CAST(:employee_id AS uuid) IS NULL OR "employeeId"=:employee_id)
 AND (CAST(:department AS text) IS NULL OR department=:department)
ORDER BY "expiryDate",lower("employeeName"),"sourceKind","sourceId"
""",
    "salaryMovement": """
SELECT history.id "eventId",history.changed_at "effectiveAt",employee.id "employeeId",
 employee.name "employeeName",employee.department,
 history.old_value::numeric(14,2) "oldSalary",history.new_value::numeric(14,2) "newSalary",
 history.reason
FROM public.employee_job_history history
JOIN public.employees employee ON employee.id=history.employee_id
 AND employee.company_id=history.company_id AND employee.branch_id=history.branch_id
WHERE history.company_id=:company_id AND history.branch_id=:branch_id
 AND history.change_type='salary_change'
 AND (CAST(:date_from AS date) IS NULL OR history.changed_at::date>=:date_from)
 AND (CAST(:date_to AS date) IS NULL OR history.changed_at::date<=:date_to)
 AND (CAST(:employee_id AS uuid) IS NULL OR history.employee_id=:employee_id)
 AND (CAST(:department AS text) IS NULL OR employee.department=:department)
ORDER BY history.changed_at,history.id
""",
    "turnover": """
WITH events AS (
 SELECT employee.id "employeeId",'joiner' "eventType",employee.employment_start_date "eventDate",
  employee.name "employeeName",employee.department,employee.employment_status status,
  NULL::integer "tenureDays"
 FROM public.employees employee
 WHERE employee.company_id=:company_id AND employee.branch_id=:branch_id
  AND employee.employment_start_date IS NOT NULL
 UNION ALL
 SELECT employee.id,'leaver',employee.termination_date,employee.name,employee.department,
  employee.employment_status,
  (employee.termination_date-employee.employment_start_date)::integer
 FROM public.employees employee
 WHERE employee.company_id=:company_id AND employee.branch_id=:branch_id
  AND employee.termination_date IS NOT NULL AND employee.employment_start_date IS NOT NULL
)
SELECT * FROM events WHERE (CAST(:date_from AS date) IS NULL OR "eventDate">=:date_from)
 AND (CAST(:date_to AS date) IS NULL OR "eventDate"<=:date_to)
 AND (CAST(:status AS text) IS NULL OR status=:status)
 AND (CAST(:department AS text) IS NULL OR department=:department)
ORDER BY "eventDate","eventType","employeeId"
""",
    "staffingCompliance": """
SELECT override.id "overrideId",(override.violation_snapshot->>'date')::date date,
 override.violation_snapshot->>'department' department,
 override.violation_snapshot->>'shiftCategory' "shiftCategory",
 (override.violation_snapshot->>'required')::integer required,
 (override.violation_snapshot->>'assigned')::integer assigned,
 (override.violation_snapshot->>'deficit')::integer shortage,true overridden,
 override.reason "overrideReason"
FROM public.compliance_overrides override
JOIN public.roster_months month ON month.company_id=override.company_id
 AND month.branch_id=override.branch_id AND month.period=override.roster_month
WHERE override.company_id=:company_id AND override.branch_id=:branch_id
 AND override.rule_code='staffing_shortfall' AND month.status='published'
 AND (CAST(:period AS text) IS NULL OR override.roster_month=:period)
 AND (CAST(:department AS text) IS NULL OR override.violation_snapshot->>'department'=:department)
ORDER BY date,department,"shiftCategory",override.id
""",
    "wpsCompliance": """
SELECT entry.id "entryId",run.period,employee.id "employeeId",employee.name "employeeName",
 employee.department,run.wps_status "runStatus",entry.wps_payment_status "entryStatus",
 entry.wps_rejection_reason "rejectionReason"
FROM public.payroll_entries entry
JOIN public.payroll_runs run ON run.id=entry.payroll_run_id AND run.company_id=entry.company_id
 AND run.branch_id=entry.branch_id
JOIN public.employees employee ON employee.id=entry.employee_id
 AND employee.company_id=entry.company_id AND employee.branch_id=entry.branch_id
WHERE entry.company_id=:company_id AND entry.branch_id=:branch_id AND NOT entry.excluded
 AND run.status='generated' AND run.approval_status='approved'
 AND (CAST(:period AS text) IS NULL OR run.period=:period)
 AND (CAST(:status AS text) IS NULL OR entry.wps_payment_status=:status)
 AND (CAST(:employee_id AS uuid) IS NULL OR entry.employee_id=:employee_id)
 AND (CAST(:department AS text) IS NULL OR employee.department=:department)
ORDER BY run.period DESC,lower(employee.name),employee.id,entry.id
""",
    "emiratization": """
SELECT report.id "snapshotId",report.period,report.total_headcount "headcount",
 report.emirati_count "emiratiCount",report.ratio_percent::numeric(7,2) "ratioPercent",
 report.required_percent::numeric(7,2) "requiredPercent",report.compliant,
 report.generated_at "generatedAt"
FROM public.nafis_reports report
WHERE report.company_id=:company_id AND report.branch_id=:branch_id
 AND (CAST(:period AS text) IS NULL OR report.period=:period)
ORDER BY report.period DESC,report.id DESC
""",
    "eosLiability": """
WITH unpaid AS (
 SELECT request.employee_id,coalesce(sum(request.days_requested),0)::integer days
 FROM public.leave_requests request JOIN public.leave_types leave_type
  ON leave_type.id=request.leave_type_id AND leave_type.company_id=request.company_id
  AND leave_type.branch_id=request.branch_id
 WHERE request.company_id=:company_id AND request.branch_id=:branch_id
  AND request.status='Approved' AND leave_type.code='UNPAID'
 GROUP BY request.employee_id
), policy AS (
 SELECT EXISTS(SELECT 1 FROM public.settlement_policy_versions
  WHERE jurisdiction_key='uae-mainland-private-sector-foreign-full-time'
  AND semantic_version='1.0.0') available
), snapshot AS (SELECT public.workloop_business_date() business_date)
SELECT employee.id "employeeId",employee.name "employeeName",employee.department,
 '1.0.0' "policyVersion",
 greatest(0,(snapshot.business_date-employee.employment_start_date)+1-coalesce(unpaid.days,0))
   ::integer "serviceDays",
 employee.nationality,employee.work_location_type "workLocationType",
 employee.basic_salary "basicSalary",policy.available "policyAvailable"
FROM public.employees employee CROSS JOIN policy CROSS JOIN snapshot
LEFT JOIN unpaid ON unpaid.employee_id=employee.id
WHERE employee.company_id=:company_id AND employee.branch_id=:branch_id AND employee.active
 AND employee.employment_status IN ('Active','Probation','On Leave')
 AND employee.employment_start_date IS NOT NULL
 AND (CAST(:status AS text) IS NULL OR employee.employment_status=:status)
 AND (CAST(:employee_id AS uuid) IS NULL OR employee.id=:employee_id)
 AND (CAST(:department AS text) IS NULL OR employee.department=:department)
ORDER BY lower(employee.name),employee.id
""",
    "leaveBalance": """
SELECT balance.id "balanceId",employee.id "employeeId",employee.name "employeeName",
 employee.department,balance.leave_year "leaveYear",leave_type.name "leaveType",
 balance.entitled_days::numeric(10,2) entitled,balance.accrued_days::numeric(10,2) accrued,
 balance.used_days::numeric(10,2) used,balance.pending_days::numeric(10,2) pending,
 balance.carried_forward::numeric(10,2) "carriedForward",
 balance.remaining_days::numeric(10,2) remaining
FROM public.leave_balances balance
JOIN public.employees employee ON employee.id=balance.employee_id
 AND employee.company_id=balance.company_id AND employee.branch_id=balance.branch_id
JOIN public.leave_types leave_type ON leave_type.id=balance.leave_type_id
 AND leave_type.company_id=balance.company_id AND leave_type.branch_id=balance.branch_id
WHERE balance.company_id=:company_id AND balance.branch_id=:branch_id
 AND (CAST(:date_from AS date) IS NULL
  OR balance.leave_year>=extract(year FROM CAST(:date_from AS date)))
 AND (CAST(:date_to AS date) IS NULL
  OR balance.leave_year<=extract(year FROM CAST(:date_to AS date)))
 AND (CAST(:employee_id AS uuid) IS NULL OR balance.employee_id=:employee_id)
 AND (CAST(:department AS text) IS NULL OR employee.department=:department)
ORDER BY lower(employee.name),employee.id,balance.leave_year DESC,leave_type.name,leave_type.id
""",
}


class SqlReportRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def resolve_employee(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> bool:
        return bool(
            await self.connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM public.employees WHERE id=:employee_id "
                    "AND company_id=:company_id AND branch_id=:branch_id)"
                ),
                {"company_id": company_id, "branch_id": branch_id, "employee_id": employee_id},
            )
        )

    async def resolve_department(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, department_id: uuid.UUID
    ) -> str | None:
        return await self.connection.scalar(
            text(
                "SELECT name FROM public.departments WHERE id=:department_id "
                "AND company_id=:company_id AND branch_id=:branch_id"
            ),
            {"company_id": company_id, "branch_id": branch_id, "department_id": department_id},
        )

    async def read(
        self,
        report_id: str,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        filters: dict[str, object],
    ) -> tuple[datetime, list[dict[str, object]]]:
        statement = REPORT_QUERIES[report_id]
        values = {"company_id": company_id, "branch_id": branch_id, **filters}
        as_of = await self.connection.scalar(text("SELECT statement_timestamp()"))
        rows = (await self.connection.execute(text(statement), values)).mappings()
        return as_of, [dict(row) for row in rows]
