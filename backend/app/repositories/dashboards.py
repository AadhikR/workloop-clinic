from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

DashboardKind = Literal["admin", "clinical", "self"]

ADMIN_SNAPSHOT = text(
    """
WITH snapshot AS (
  SELECT statement_timestamp() AS as_of,public.workloop_business_date() AS business_date
), active_staff AS (
  SELECT count(*)::integer AS active_headcount
  FROM public.employees
  WHERE company_id=:company_id AND branch_id=:branch_id AND active
    AND employment_status IN ('Active','Probation','On Leave')
), payrolls AS (
  SELECT period,total_disbursed,employee_count,wps_status,
         row_number() OVER (ORDER BY period DESC,sequence_no DESC,id DESC) AS position
  FROM public.payroll_runs
  WHERE company_id=:company_id AND branch_id=:branch_id
    AND status='generated' AND approval_status='approved'
), payroll AS (
  SELECT max(period) FILTER (WHERE position=1) AS payroll_period,
         max(total_disbursed) FILTER (WHERE position=1) AS payroll_total,
         max(employee_count) FILTER (WHERE position=1) AS payroll_employee_count,
         max(wps_status) FILTER (WHERE position=1) AS wps_status,
         max(total_disbursed) FILTER (WHERE position=2) AS previous_payroll_total
  FROM payrolls WHERE position<=2
), nafis AS (
  SELECT period,ratio_percent,required_percent,compliant,total_headcount,emirati_count
  FROM public.nafis_reports
  WHERE company_id=:company_id AND branch_id=:branch_id
  ORDER BY period DESC,id DESC LIMIT 1
), expiry_sources AS (
  SELECT employee.id::text||':'||source.kind AS source_key,source.expiry_date,source.thresholds
  FROM public.employees employee
  CROSS JOIN LATERAL (VALUES
    ('visa',employee.visa_expiry,ARRAY[60,30,14]),
    ('passport',employee.passport_expiry,ARRAY[60,30,14]),
    ('emirates_id',employee.emirates_id_expiry,ARRAY[60,30,14]),
    ('labour_card',employee.labour_card_expiry,ARRAY[60,30,14]),
    ('licence',CASE WHEN employee.licence_authority IS NOT NULL
      AND employee.licence_authority<>'None' THEN employee.licence_expiry END,ARRAY[60,30,14]),
    ('contract',CASE WHEN employee.contract_type='Limited' THEN employee.contract_end_date END,
      ARRAY[60,30,14,7]),
    ('probation',CASE WHEN employee.employment_status='Probation'
      THEN employee.probation_end_date END,ARRAY[14,7])
  ) source(kind,expiry_date,thresholds)
  WHERE employee.company_id=:company_id AND employee.branch_id=:branch_id AND employee.active
    AND employee.employment_status<>'Terminated'
  UNION ALL
  SELECT document.id::text,document.expiry_date,
    CASE WHEN document.document_type=ANY(:clinical_types) THEN ARRAY[90,30,14]
         ELSE ARRAY[60,30,14] END
  FROM public.employee_documents document
  WHERE document.company_id=:company_id AND document.branch_id=:branch_id
    AND document.status='verified'
  UNION ALL
  SELECT certification.id::text,certification.expiry_date,ARRAY[60,30,14]
  FROM public.certifications certification
  WHERE certification.company_id=:company_id AND certification.branch_id=:branch_id
    AND certification.status='verified'
  UNION ALL
  SELECT coverage.id::text,coverage.expiry_date,ARRAY[60,30]
  FROM public.employee_insurance coverage
  WHERE coverage.company_id=:company_id AND coverage.branch_id=:branch_id
  UNION ALL
  SELECT policy.id::text,policy.renewal_date,ARRAY[60,30]
  FROM public.insurance_policies policy
  WHERE policy.company_id=:company_id AND policy.branch_id=:branch_id
), expiry AS (
  SELECT count(*) FILTER (WHERE expiry_date IS NOT NULL AND
    (expiry_date-(SELECT business_date FROM snapshot))=ANY(thresholds))::integer AS expiry_due
  FROM expiry_sources
)
SELECT snapshot.as_of,snapshot.business_date,active_staff.active_headcount,
       payroll.payroll_period,payroll.payroll_total,payroll.payroll_employee_count,
       payroll.wps_status,payroll.previous_payroll_total,
       nafis.period AS nafis_period,nafis.ratio_percent,nafis.required_percent,
       nafis.compliant AS nafis_compliant,nafis.total_headcount AS nafis_headcount,
       nafis.emirati_count,expiry.expiry_due
FROM snapshot CROSS JOIN active_staff CROSS JOIN payroll CROSS JOIN expiry LEFT JOIN nafis ON true
"""
)

CLINICAL_SNAPSHOT = text(
    """
WITH snapshot AS (
  SELECT statement_timestamp() AS as_of,public.workloop_business_date() AS business_date
), active_staff AS (
  SELECT count(*)::integer AS active_headcount FROM public.employees
  WHERE company_id=:company_id AND branch_id=:branch_id AND active
    AND employment_status IN ('Active','Probation','On Leave')
), eligible_credentials AS (
  SELECT document.id,document.expiry_date
  FROM public.employee_documents document
  WHERE document.company_id=:company_id AND document.branch_id=:branch_id
    AND document.document_type=ANY(:clinical_types) AND document.status='verified'
    AND document.content_type IS NOT NULL AND document.cleanup_requested_at IS NULL
    AND public.file_security_scan_allows_download(
      document.file_security_scan_id,'employee_document',document.id,document.storage_path,
      document.content_type,document.file_size,document.sha256,:scanner_definition)
  UNION ALL
  SELECT certification.id,certification.expiry_date
  FROM public.certifications certification
  WHERE certification.company_id=:company_id AND certification.branch_id=:branch_id
    AND certification.status='verified' AND certification.content_type IS NOT NULL
    AND public.file_security_scan_allows_download(
      certification.file_security_scan_id,'certification_evidence',certification.id,
      certification.storage_path,certification.content_type,certification.size_bytes,
      certification.sha256,:scanner_definition)
), credential_counts AS (
  SELECT count(*) FILTER (WHERE expiry_date IS NULL OR
      expiry_date>(SELECT business_date FROM snapshot)+90)::integer AS valid_count,
    count(*) FILTER (WHERE expiry_date BETWEEN (SELECT business_date FROM snapshot)
      AND (SELECT business_date FROM snapshot)+90)::integer AS expiring_count,
    count(*) FILTER (WHERE expiry_date<(SELECT business_date FROM snapshot))::integer
      AS expired_count
  FROM eligible_credentials
), publication AS (
  SELECT month.current_version_id,month.source_version,month.published_at,
         version.record_count,version.kind
  FROM public.roster_months month
  JOIN public.roster_publication_versions version ON version.id=month.current_version_id
  WHERE month.company_id=:company_id AND month.branch_id=:branch_id
    AND month.period=to_char((SELECT business_date FROM snapshot),'YYYY-MM')
    AND month.status='published'
), today_roster AS (
  SELECT count(membership.id)::integer AS assignment_count
  FROM publication
  LEFT JOIN public.roster_publication_memberships membership
    ON membership.publication_version_id=publication.current_version_id
   AND membership.company_id=:company_id AND membership.branch_id=:branch_id
   AND membership.date=(SELECT business_date FROM snapshot)
), attendance AS (
  SELECT count(*) FILTER (WHERE status IN ('PRESENT','LATE','EARLY_DEPARTURE','HALF_DAY',
    'OVERTIME','PRESENT_REMOTE','MISSING_CLOCK_OUT'))::integer AS on_duty_count
  FROM public.attendance_records
  WHERE company_id=:company_id AND branch_id=:branch_id
    AND date=(SELECT business_date FROM snapshot) AND NOT source_stale
)
SELECT snapshot.as_of,snapshot.business_date,active_staff.active_headcount,
  credential_counts.valid_count,credential_counts.expiring_count,
  credential_counts.expired_count,coalesce(today_roster.assignment_count,0) assignment_count,
  attendance.on_duty_count,publication.current_version_id,publication.source_version roster_version,
  publication.published_at,publication.record_count,publication.kind publication_kind
FROM snapshot CROSS JOIN active_staff CROSS JOIN credential_counts CROSS JOIN attendance
LEFT JOIN publication ON true LEFT JOIN today_roster ON true
"""
)

SELF_SNAPSHOT = text(
    """
WITH snapshot AS (
  SELECT statement_timestamp() AS as_of,public.workloop_business_date() AS business_date
), employee AS (
  SELECT id,employment_status FROM public.employees
  WHERE id=:employee_id AND company_id=:company_id AND branch_id=:branch_id
), leave_total AS (
  SELECT coalesce(sum(remaining_days),0)::numeric(8,2) AS remaining_days
  FROM public.leave_balances
  WHERE employee_id=:employee_id AND company_id=:company_id AND branch_id=:branch_id
    AND leave_year=extract(year FROM (SELECT business_date FROM snapshot))::integer
), payslip AS (
  SELECT period,net_pay FROM public.payslips
  WHERE employee_id=:employee_id AND company_id=:company_id AND branch_id=:branch_id
  ORDER BY period DESC,id DESC LIMIT 1
), attendance AS (
  SELECT status FROM public.attendance_records
  WHERE employee_id=:employee_id AND company_id=:company_id AND branch_id=:branch_id
    AND date=(SELECT business_date FROM snapshot) AND NOT source_stale
  ORDER BY calculation_version DESC,id DESC LIMIT 1
), assets AS (
  SELECT count(*)::integer AS assigned_assets FROM public.asset_assignments
  WHERE employee_id=:employee_id AND company_id=:company_id AND branch_id=:branch_id
    AND return_date IS NULL
), schedule AS (
  SELECT membership.shift_name,month.source_version
  FROM public.roster_months month
  JOIN public.roster_publication_memberships membership
    ON membership.publication_version_id=month.current_version_id
  WHERE month.company_id=:company_id AND month.branch_id=:branch_id
    AND month.status='published' AND membership.employee_id=:employee_id
    AND membership.date=(SELECT business_date FROM snapshot)
  ORDER BY membership.source_assignment_id LIMIT 1
)
SELECT snapshot.as_of,snapshot.business_date,employee.employment_status,
  leave_total.remaining_days,payslip.period AS payslip_period,payslip.net_pay,
  attendance.status AS attendance_status,assets.assigned_assets,
  schedule.shift_name,schedule.source_version AS roster_version
FROM snapshot CROSS JOIN employee CROSS JOIN leave_total CROSS JOIN assets
LEFT JOIN payslip ON true LEFT JOIN attendance ON true LEFT JOIN schedule ON true
"""
)


class SqlDashboardRepository:
    def __init__(self, connection: AsyncConnection, scanner_definition: str) -> None:
        self.connection = connection
        self.scanner_definition = scanner_definition

    async def snapshot(
        self,
        kind: DashboardKind,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID | None,
        clinical_types: tuple[str, ...],
    ) -> dict[str, object]:
        statement = {
            "admin": ADMIN_SNAPSHOT,
            "clinical": CLINICAL_SNAPSHOT,
            "self": SELF_SNAPSHOT,
        }[kind]
        values = {
            "branch_id": branch_id,
            "clinical_types": list(clinical_types),
            "company_id": company_id,
            "employee_id": employee_id,
            "scanner_definition": self.scanner_definition,
        }
        row = (await self.connection.execute(statement, values)).mappings().one_or_none()
        if row is None:
            raise RuntimeError("dashboard source unavailable")
        return dict(row)
