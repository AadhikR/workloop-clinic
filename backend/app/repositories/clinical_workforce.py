from app.repositories.clinical_credentials import CLINICAL_CREDENTIALS

WORKFORCE_GROUPS = (
    "activeStaff",
    "credentialCompliance",
    "coverage",
    "probation",
    "newJoiners",
    "birthdays",
    "onLeaveToday",
    "pendingLeave",
    "onDutyNow",
)

CLINICAL_WORKFORCE = f"""
WITH snapshot AS (SELECT public.workloop_business_date() business_date),
staff AS (
 SELECT * FROM public.employees WHERE company_id=:company_id AND branch_id=:branch_id
 AND active AND employment_status IN ('Active','Probation','On Leave')
), credentials AS (
{CLINICAL_CREDENTIALS}
), covered AS (
 SELECT DISTINCT membership.employee_id FROM public.roster_months month
 JOIN public.roster_publication_memberships membership
 ON membership.publication_version_id=month.current_version_id
 AND membership.company_id=month.company_id AND membership.branch_id=month.branch_id
 WHERE month.company_id=:company_id AND month.branch_id=:branch_id AND month.status='published'
 AND month.period=to_char((SELECT business_date FROM snapshot),'YYYY-MM')
 AND membership.date=(SELECT business_date FROM snapshot)
), base AS (
 SELECT staff.id,staff.name,staff.department,staff.job_title,staff.employment_status,
 staff.employment_start_date,staff.probation_end_date,staff.date_of_birth,
 EXISTS(SELECT 1 FROM credentials WHERE employee_id=staff.id) has_credentials,
 EXISTS(SELECT 1 FROM credentials WHERE employee_id=staff.id
 AND (expiry_date IS NULL OR expiry_date>=(SELECT business_date FROM snapshot))) compliant,
 EXISTS(SELECT 1 FROM covered WHERE employee_id=staff.id) rostered
 FROM staff
), groups AS (
 SELECT 'activeStaff' group_code,id::text id,id employee_id,name employee_name,department,
 job_title,employment_status status,NULL::date source_date,NULL::timestamptz source_time,
 ''::text source_label FROM base
 UNION ALL
 SELECT 'credentialCompliance',id::text,id,name,department,job_title,
 CASE WHEN compliant THEN 'valid' ELSE 'expired' END,NULL,NULL,'' FROM base WHERE has_credentials
 UNION ALL
 SELECT 'coverage',id::text,id,name,department,job_title,
 CASE WHEN rostered THEN 'rostered' ELSE 'unrostered' END,NULL,NULL,'' FROM base
 UNION ALL
 SELECT 'probation',id::text,id,name,department,job_title,employment_status,
 probation_end_date,NULL,'' FROM base WHERE employment_status='Probation'
 UNION ALL
 SELECT 'newJoiners',id::text,id,name,department,job_title,employment_status,
 employment_start_date,NULL,'' FROM base WHERE date_trunc('month',employment_start_date)
 =date_trunc('month',(SELECT business_date FROM snapshot))
 UNION ALL
 SELECT 'birthdays',id::text,id,name,department,job_title,employment_status,
 date_of_birth,NULL,'' FROM base WHERE EXTRACT(month FROM date_of_birth)
 =EXTRACT(month FROM (SELECT business_date FROM snapshot))
 UNION ALL
 SELECT 'onLeaveToday',request.id::text,base.id,base.name,base.department,base.job_title,
 request.status,request.start_date,NULL,type.name||' · Returns '||request.end_date::text
 FROM public.leave_requests request JOIN base ON base.id=request.employee_id
 JOIN public.leave_types type ON type.id=request.leave_type_id
 AND type.company_id=request.company_id AND type.branch_id=request.branch_id
 WHERE request.company_id=:company_id AND request.branch_id=:branch_id AND request.status='Approved'
 AND (SELECT business_date FROM snapshot) BETWEEN request.start_date AND request.end_date
 UNION ALL
 SELECT 'pendingLeave',request.id::text,base.id,base.name,base.department,base.job_title,
 request.status,request.start_date,NULL,type.name||' · To '||request.end_date::text
 FROM public.leave_requests request JOIN base ON base.id=request.employee_id
 JOIN public.leave_types type ON type.id=request.leave_type_id
 AND type.company_id=request.company_id AND type.branch_id=request.branch_id
 WHERE request.company_id=:company_id AND request.branch_id=:branch_id
 AND request.status IN ('Pending','ManagerApproved')
 UNION ALL
 SELECT 'onDutyNow',record.id::text,base.id,base.name,base.department,base.job_title,
 record.status,record.date,record.clock_in_time,'' FROM public.attendance_records record
 JOIN base ON base.id=record.employee_id WHERE record.company_id=:company_id
 AND record.branch_id=:branch_id AND record.date=(SELECT business_date FROM snapshot)
 AND record.clock_in_time IS NOT NULL AND record.clock_out_time IS NULL AND NOT record.source_stale
)
"""
