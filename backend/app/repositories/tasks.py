from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal

_CATEGORY_SQL = {
    "leaveApprovals": """
SELECT request.id entity_id,employee.name title,
       leave_type.name||', '||request.days_requested::text||' days' subtitle,
       request.start_date due_date,request.created_at,NULL::text task_key
FROM public.leave_requests request
JOIN public.employees employee ON employee.id=request.employee_id
JOIN public.leave_types leave_type ON leave_type.id=request.leave_type_id
WHERE request.company_id=:company_id AND request.branch_id=:branch_id
  AND ((:role='admin' AND request.status IN ('Pending','ManagerApproved'))
    OR (:role='manager' AND request.status='Pending'
      AND employee.reporting_manager_id=CAST(:employee_id AS uuid)))
""",
    "expenseApprovals": """
SELECT claim.id entity_id,employee.name title,
       'AED '||claim.amount::text||
       CASE WHEN claim.description='' THEN '' ELSE ': '||claim.description END subtitle,
       claim.expense_date due_date,claim.created_at,NULL::text task_key
FROM public.expense_claims claim
JOIN public.employees employee ON employee.id=claim.employee_id
WHERE claim.company_id=:company_id AND claim.branch_id=:branch_id
  AND ((:role='admin' AND claim.status IN ('pending','manager_approved'))
    OR (:role='manager' AND claim.status='pending'
      AND employee.reporting_manager_id=CAST(:employee_id AS uuid)))
""",
    "advanceApprovals": """
SELECT advance.id entity_id,employee.name title,'AED '||advance.amount::text subtitle,
       advance.disbursed_date due_date,advance.created_at,NULL::text task_key
FROM public.salary_advances advance
JOIN public.employees employee ON employee.id=advance.employee_id
WHERE advance.company_id=:company_id AND advance.branch_id=:branch_id
  AND advance.status='pending' AND :role='admin'
""",
    "letterRequests": """
SELECT request.id entity_id,employee.name title,
       replace(request.letter_type,'_',' ') subtitle,NULL::date due_date,
       request.requested_at created_at,NULL::text task_key
FROM public.letter_requests request
JOIN public.employees employee ON employee.id=request.employee_id
WHERE request.company_id=:company_id AND request.branch_id=:branch_id
  AND request.status='pending' AND :role='admin'
""",
    "documentVerification": """
SELECT document.id entity_id,employee.name title,
       replace(document.document_type,'_',' ') subtitle,document.expiry_date due_date,
       document.uploaded_at created_at,NULL::text task_key
FROM public.employee_documents document
JOIN public.employees employee ON employee.id=document.employee_id
WHERE document.company_id=:company_id AND document.branch_id=:branch_id
  AND document.status='pending_verification' AND :role='admin'
""",
    "certificationReview": """
SELECT certification.id entity_id,employee.name title,
       certification.certification_name subtitle,certification.expiry_date due_date,
       certification.created_at,NULL::text task_key
FROM public.certifications certification
JOIN public.employees employee ON employee.id=certification.employee_id
WHERE certification.company_id=:company_id AND certification.branch_id=:branch_id
  AND certification.status='pending_review' AND :role='admin'
""",
    "regularisationRequests": """
SELECT request.id entity_id,employee.name title,'Attendance correction' subtitle,
       request.attendance_date due_date,request.created_at,NULL::text task_key
FROM public.regularisation_requests request
JOIN public.employees employee ON employee.id=request.employee_id
WHERE request.company_id=:company_id AND request.branch_id=:branch_id
  AND request.status='Pending' AND :role='admin'
""",
    "shiftSwapRequests": """
SELECT request.id entity_id,employee.name title,'Shift swap request' subtitle,
       LEAST(request.requester_date,request.target_date) due_date,request.created_at,
       NULL::text task_key
FROM public.shift_swap_requests request
JOIN public.employees employee ON employee.id=request.requester_employee_id
WHERE request.company_id=:company_id AND request.branch_id=:branch_id
  AND request.status='pending' AND :role='admin'
""",
    "payrollApproval": """
SELECT run.id entity_id,'Payroll '||run.period::text title,
       'Awaiting approval' subtitle,run.payment_date due_date,run.created_at,NULL::text task_key
FROM public.payroll_runs run
WHERE run.company_id=:company_id AND run.branch_id=:branch_id
  AND run.approval_status='pending_approval' AND :role='admin'
""",
    "documentExpiry": """
SELECT employee.id entity_id,employee.name title,document.label subtitle,
       document.expiry_date due_date,employee.created_at,document.code task_key
FROM public.employees employee
CROSS JOIN LATERAL (VALUES
  ('visa','Visa',employee.visa_expiry),
  ('passport','Passport',employee.passport_expiry),
  ('emiratesId','Emirates ID',employee.emirates_id_expiry),
  ('labourCard','Labour card',employee.labour_card_expiry),
  ('professionalLicence','Professional licence',employee.licence_expiry)
) document(code,label,expiry_date)
WHERE employee.company_id=:company_id AND employee.branch_id=:branch_id
  AND employee.active AND employee.employment_status IN ('Active','Probation','On Leave')
  AND document.expiry_date IS NOT NULL
  AND document.expiry_date<=CAST(:business_date AS date)+60
  AND (:role='admin' OR (:role='employee' AND employee.id=CAST(:employee_id AS uuid)))
""",
    "certificationExpiry": """
SELECT certification.id entity_id,employee.name title,
       certification.certification_name subtitle,certification.expiry_date due_date,
       certification.created_at,NULL::text task_key
FROM public.certifications certification
JOIN public.employees employee ON employee.id=certification.employee_id
WHERE certification.company_id=:company_id AND certification.branch_id=:branch_id
  AND certification.status='verified' AND certification.expiry_date IS NOT NULL
  AND certification.expiry_date<=CAST(:business_date AS date)+60
  AND (:role='admin' OR (:role='employee'
    AND certification.employee_id=CAST(:employee_id AS uuid)))
""",
    "probationEnding": """
SELECT employee.id entity_id,employee.name title,'Probation ending' subtitle,
       employee.probation_end_date due_date,employee.created_at,NULL::text task_key
FROM public.employees employee
WHERE employee.company_id=:company_id AND employee.branch_id=:branch_id
  AND employee.active AND employee.employment_status='Probation'
  AND employee.probation_end_date BETWEEN CAST(:business_date AS date)
    AND CAST(:business_date AS date)+30 AND :role='admin'
""",
    "contractExpiry": """
SELECT contract.id entity_id,employee.name title,'Limited contract ending' subtitle,
       contract.end_date due_date,contract.created_at,NULL::text task_key
FROM public.employee_contracts contract
JOIN public.employees employee ON employee.id=contract.employee_id
WHERE contract.company_id=:company_id AND contract.branch_id=:branch_id
  AND contract.contract_type='Limited' AND contract.end_date BETWEEN CAST(:business_date AS date)
    AND CAST(:business_date AS date)+60 AND :role='admin'
""",
    "offboardingInProgress": """
SELECT checklist.id entity_id,employee.name title,
       count(*) FILTER (WHERE task.completed)::text||'/'||count(*)::text||
       ' tasks complete' subtitle,
       NULL::date due_date,checklist.created_at,NULL::text task_key
FROM public.offboarding_checklists checklist
JOIN public.employees employee ON employee.id=checklist.employee_id
JOIN public.offboarding_tasks task ON task.checklist_id=checklist.id
WHERE checklist.company_id=:company_id AND checklist.branch_id=:branch_id
  AND checklist.status='in_progress' AND :role='admin'
GROUP BY checklist.id,employee.name,checklist.created_at
HAVING bool_or(NOT task.completed)
""",
    "appraisalCalibration": """
SELECT appraisal.id entity_id,employee.name title,'Awaiting HR calibration' subtitle,
       NULL::date due_date,appraisal.created_at,NULL::text task_key
FROM public.appraisals appraisal
JOIN public.employees employee ON employee.id=appraisal.employee_id
WHERE appraisal.company_id=:company_id AND appraisal.branch_id=:branch_id
  AND appraisal.status='reviewed' AND :role='admin'
""",
    "teamAppraisals": """
SELECT appraisal.id entity_id,employee.name title,'Manager review required' subtitle,
       NULL::date due_date,appraisal.created_at,NULL::text task_key
FROM public.appraisals appraisal
JOIN public.employees employee ON employee.id=appraisal.employee_id
WHERE appraisal.company_id=:company_id AND appraisal.branch_id=:branch_id
  AND appraisal.status='pending' AND :role='manager'
  AND employee.reporting_manager_id=CAST(:employee_id AS uuid)
""",
    "teamCertificationExpiry": """
SELECT certification.id entity_id,employee.name title,
       certification.certification_name subtitle,certification.expiry_date due_date,
       certification.created_at,NULL::text task_key
FROM public.certifications certification
JOIN public.employees employee ON employee.id=certification.employee_id
WHERE certification.company_id=:company_id AND certification.branch_id=:branch_id
  AND certification.status='verified' AND certification.expiry_date IS NOT NULL
  AND certification.expiry_date<=CAST(:business_date AS date)+60 AND :role='manager'
  AND employee.reporting_manager_id=CAST(:employee_id AS uuid)
""",
    "rejectedCertifications": """
SELECT certification.id entity_id,certification.certification_name title,
       'Resubmission required' subtitle,certification.expiry_date due_date,
       certification.created_at,NULL::text task_key
FROM public.certifications certification
WHERE certification.company_id=:company_id AND certification.branch_id=:branch_id
  AND certification.employee_id=CAST(:employee_id AS uuid)
  AND certification.status='rejected' AND :role='employee'
""",
    "rejectedDocuments": """
SELECT document.id entity_id,replace(document.document_type,'_',' ') title,
       'Resubmission required' subtitle,document.expiry_date due_date,
       document.uploaded_at created_at,NULL::text task_key
FROM public.employee_documents document
WHERE document.company_id=:company_id AND document.branch_id=:branch_id
  AND document.employee_id=CAST(:employee_id AS uuid)
  AND document.status='rejected' AND :role='employee'
""",
    "missingClockOuts": """
SELECT record.id entity_id,'Missing clock-out: '||record.date::text title,
       'Submit a regularisation request' subtitle,record.date due_date,
       record.created_at,NULL::text task_key
FROM public.attendance_records record
WHERE record.company_id=:company_id AND record.branch_id=:branch_id
  AND record.employee_id=CAST(:employee_id AS uuid) AND record.missing_clock_out
  AND record.date<CAST(:business_date AS date) AND :role='employee'
""",
    "pendingLeave": """
SELECT request.id entity_id,leave_type.name title,
       request.days_requested::text||' days awaiting approval' subtitle,
       request.start_date due_date,request.created_at,NULL::text task_key
FROM public.leave_requests request
JOIN public.leave_types leave_type ON leave_type.id=request.leave_type_id
WHERE request.company_id=:company_id AND request.branch_id=:branch_id
  AND request.employee_id=CAST(:employee_id AS uuid)
  AND request.status IN ('Pending','ManagerApproved') AND :role='employee'
""",
    "pendingAdvances": """
SELECT advance.id entity_id,'Advance: AED '||advance.amount::text title,
       'Awaiting approval' subtitle,advance.disbursed_date due_date,
       advance.created_at,NULL::text task_key
FROM public.salary_advances advance
WHERE advance.company_id=:company_id AND advance.branch_id=:branch_id
  AND advance.employee_id=CAST(:employee_id AS uuid)
  AND advance.status='pending' AND :role='employee'
""",
    "pendingExpenses": """
SELECT claim.id entity_id,'Expense: AED '||claim.amount::text title,
       CASE WHEN claim.status='manager_approved' THEN 'Awaiting HR approval'
         ELSE 'Awaiting approval' END subtitle,
       claim.expense_date due_date,claim.created_at,NULL::text task_key
FROM public.expense_claims claim
WHERE claim.company_id=:company_id AND claim.branch_id=:branch_id
  AND claim.employee_id=CAST(:employee_id AS uuid)
  AND claim.status IN ('pending','manager_approved') AND :role='employee'
""",
    "pendingLetters": """
SELECT request.id entity_id,replace(request.letter_type,'_',' ') title,
       'Awaiting HR' subtitle,NULL::date due_date,request.requested_at created_at,
       NULL::text task_key
FROM public.letter_requests request
WHERE request.company_id=:company_id AND request.branch_id=:branch_id
  AND request.employee_id=CAST(:employee_id AS uuid)
  AND request.status='pending' AND :role='employee'
""",
}


class SqlTaskRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def snapshot(self) -> dict[str, object]:
        row = (
            (
                await self.connection.execute(
                    text(
                        "SELECT statement_timestamp() AS as_of,"
                        "public.workloop_business_date() AS business_date"
                    )
                )
            )
            .mappings()
            .one()
        )
        return dict(row)

    async def read_category(
        self,
        *,
        code: str,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        business_date: date,
    ) -> list[dict[str, object]]:
        statement = _CATEGORY_SQL[code]
        values = {
            "branch_id": branch_id,
            "business_date": business_date,
            "company_id": principal.company_id,
            "employee_id": principal.employee_id,
            "role": principal.role.value,
        }
        async with self.connection.begin_nested():
            rows = (await self.connection.execute(text(statement), values)).mappings()
            return [dict(row) for row in rows]
