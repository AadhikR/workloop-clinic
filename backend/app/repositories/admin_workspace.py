ADMIN_WORKSPACE = """
WITH day AS (SELECT public.workloop_business_date() business_date), staff AS (
 SELECT * FROM public.employees
 WHERE company_id=:company_id AND branch_id=:branch_id AND active
 AND employment_status IN ('Active','Probation','On Leave')
), runs AS (
 SELECT * FROM public.payroll_runs WHERE company_id=:company_id AND branch_id=:branch_id
), coverage AS (
 SELECT insurance.* FROM public.employee_insurance insurance
 JOIN staff ON staff.id=insurance.employee_id
 WHERE insurance.company_id=:company_id AND insurance.branch_id=:branch_id
), policies AS (
 SELECT * FROM public.insurance_policies WHERE company_id=:company_id AND branch_id=:branch_id
)
SELECT day.business_date,
 (SELECT count(*) FROM staff)::integer active_employees,
 (SELECT count(*) FROM runs)::integer payroll_runs,
 (SELECT count(*) FROM runs WHERE status='draft')::integer draft_payrolls,
 (SELECT count(*) FROM runs WHERE wps_status<>'draft')::integer sif_generated,
 (SELECT count(*) FROM policies)::integer insurance_policies,
 (SELECT count(*) FROM staff WHERE employment_status='Probation'
   AND probation_end_date<=day.business_date+14)::integer probation,
 (SELECT count(*) FROM staff WHERE contract_type='Limited'
   AND contract_end_date<=day.business_date+60)::integer contracts,
 (SELECT count(*) FROM public.certifications certification
   JOIN staff ON staff.id=certification.employee_id
   WHERE certification.company_id=:company_id AND certification.branch_id=:branch_id
   AND certification.status='verified'
   AND certification.expiry_date BETWEEN day.business_date-30 AND day.business_date+60
 )::integer certifications,
 (SELECT count(*) FROM public.letter_requests request
   WHERE request.company_id=:company_id AND request.branch_id=:branch_id
   AND request.status='pending')::integer requests,
 (SELECT count(*) FROM public.appraisals appraisal
   JOIN staff ON staff.id=appraisal.employee_id
   JOIN public.appraisal_cycles cycle ON cycle.id=appraisal.cycle_id
     AND cycle.company_id=appraisal.company_id AND cycle.branch_id=appraisal.branch_id
   WHERE appraisal.company_id=:company_id AND appraisal.branch_id=:branch_id
   AND appraisal.status='pending' AND appraisal.archived_at IS NULL
   AND cycle.status='active')::integer appraisals,
 (SELECT count(*) FROM staff CROSS JOIN LATERAL (VALUES
   (staff.visa_expiry),(staff.passport_expiry),(staff.emirates_id_expiry),
   (staff.labour_card_expiry),
   (CASE WHEN staff.licence_authority<>'' AND staff.licence_authority<>'None'
     THEN staff.licence_expiry END)
 ) expiry(expiry_date) WHERE expiry_date<=day.business_date+60)::integer documents,
 (SELECT count(*) FROM coverage WHERE expiry_date
   BETWEEN day.business_date-30 AND day.business_date+60)::integer insurance,
 (SELECT count(*) FROM policies WHERE renewal_date
   BETWEEN day.business_date-30 AND day.business_date+60)::integer policy_renewals,
 (SELECT count(*) FROM runs WHERE approval_status='pending_approval')::integer payroll_approval,
 (SELECT count(*) FROM runs WHERE status='generated' AND approval_status='approved'
   AND wps_status IN ('sif_generated','submitted')
   AND payment_date<day.business_date-14)::integer wps_overdue
FROM day
"""
