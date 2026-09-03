#!/bin/sh
set -eu

# Phase 4C schema gate. Proves the 54-table target exists, that a connected row
# graph spanning every business domain satisfies the foreign-key and scope
# constraints end to end, and that a cross-tenant branch and cross-branch
# employee reference are both rejected. The runtime grant boundary moved to
# Phase 4D and is proven by scripts/verify-phase-4d-grants.sh.

"${DOCKER:-docker}" compose exec -T postgres psql --username postgres --dbname workloop --set ON_ERROR_STOP=1 \
  --command "
BEGIN;
DO \$\$
DECLARE
  table_count integer;
BEGIN
  SELECT count(*) INTO table_count
  FROM pg_tables
  WHERE schemaname = 'public' AND tablename <> 'alembic_version';
  IF table_count <> 54 THEN
    RAISE EXCEPTION 'expected 54 target tables, found %', table_count;
  END IF;

  -- Identity and organization seed (two tenants, one branch each).
  INSERT INTO companies (id, name) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Tenant One'),
    ('00000000-0000-0000-0000-000000000002', 'Tenant Two');
  INSERT INTO branches (id, company_id, name) VALUES
    ('00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001', 'One Main'),
    ('00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000002', 'Two Main');
  INSERT INTO app_users (id, identity_issuer, identity_subject, status) VALUES
    ('00000000-0000-0000-0000-000000000031', 'https://issuer.test', 'employee', 'active'),
    ('00000000-0000-0000-0000-000000000032', 'https://issuer.test', 'admin', 'active');
  INSERT INTO employees (id, company_id, branch_id, name, mol_id) VALUES
    ('00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'Employee One', 'MOL-1'),
    ('00000000-0000-0000-0000-000000000022', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'Employee Two', 'MOL-2');
  INSERT INTO user_profiles (app_user_id, company_id, employee_id, role) VALUES
    ('00000000-0000-0000-0000-000000000031', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000021', 'employee'),
    ('00000000-0000-0000-0000-000000000032', '00000000-0000-0000-0000-000000000001', NULL, 'admin');

  -- People and organization.
  INSERT INTO departments (id, company_id, branch_id, name)
    VALUES ('00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'Nursing');
  INSERT INTO department_staffing_rules (company_id, branch_id, department, shift_category)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'Nursing', 'morning');
  INSERT INTO employee_job_history (company_id, branch_id, employee_id, changed_by_app_user_id, change_type)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000032', 'salary_change');

  -- Attendance and roster.
  INSERT INTO shifts (id, company_id, branch_id, name)
    VALUES ('00000000-0000-0000-0000-000000000201', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'Day');
  INSERT INTO attendance_settings (company_id, branch_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011');
  INSERT INTO shift_assignments (company_id, branch_id, employee_id, shift_id, effective_from)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000201', '2026-01-01');
  INSERT INTO roster_assignments (company_id, branch_id, employee_id, shift_id, date)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000201', '2026-01-02');
  INSERT INTO attendance_records (company_id, branch_id, employee_id, date)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', '2026-01-02');
  INSERT INTO attendance_periods (company_id, branch_id, period)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '2026-01');
  INSERT INTO attendance_audit_log (company_id, branch_id, employee_id, action, actor_app_user_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', 'edit', '00000000-0000-0000-0000-000000000032');
  INSERT INTO regularisation_requests (company_id, branch_id, employee_id, attendance_date, correct_clock_in, correct_clock_out)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', '2026-01-02', '2026-01-02T09:00:00Z', '2026-01-02T17:00:00Z');
  INSERT INTO clock_events (company_id, branch_id, employee_id, event_type, event_time)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', 'CLOCK_IN', '2026-01-02T09:00:00Z');
  INSERT INTO shift_swap_requests (company_id, branch_id, requester_employee_id, target_employee_id, requester_date)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000022', '2026-01-03');
  INSERT INTO biometric_mappings (company_id, branch_id, badge_no, employee_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'BADGE-1', '00000000-0000-0000-0000-000000000021');

  -- Leave.
  INSERT INTO leave_settings (company_id, branch_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011');
  INSERT INTO leave_types (id, company_id, branch_id, code, name)
    VALUES ('00000000-0000-0000-0000-000000000301', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'ANNUAL', 'Annual');
  INSERT INTO public_holidays (company_id, branch_id, date, name, year)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '2026-01-01', 'New Year', 2026);
  INSERT INTO leave_balances (company_id, branch_id, employee_id, leave_type_id, leave_year)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000301', 2026);
  INSERT INTO leave_requests (id, company_id, branch_id, employee_id, leave_type_id, start_date, end_date, days_requested)
    VALUES ('00000000-0000-0000-0000-000000000302', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000301', '2026-02-01', '2026-02-02', 2);
  INSERT INTO leave_audit_log (company_id, branch_id, leave_request_id, action, actor_app_user_id, new_status)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000302', 'submit', '00000000-0000-0000-0000-000000000031', 'Pending');
  INSERT INTO leave_approval_delegates (company_id, branch_id, approver_employee_id, delegate_employee_id, from_date, to_date)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000022', '2026-02-01', '2026-02-10');

  -- Payroll, finance, and compliance.
  INSERT INTO payroll_runs (id, company_id, branch_id, period)
    VALUES ('00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '2026-01');
  INSERT INTO payroll_entries (company_id, branch_id, payroll_run_id, employee_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000021');
  INSERT INTO payslips (company_id, branch_id, payroll_run_id, employee_id, period)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000021', '2026-01');
  INSERT INTO payroll_approval_log (company_id, branch_id, payroll_run_id, action, performed_by_app_user_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000401', 'submitted', '00000000-0000-0000-0000-000000000032');
  INSERT INTO nafis_reports (company_id, branch_id, period)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '2026-01');
  INSERT INTO salary_advances (id, company_id, branch_id, employee_id, amount)
    VALUES ('00000000-0000-0000-0000-000000000402', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', 1000);
  INSERT INTO advance_repayments (company_id, branch_id, advance_id, idempotency_key, amount)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000402', '00000000-0000-0000-0000-000000000403', 250);
  INSERT INTO expense_claims (company_id, branch_id, employee_id, amount, expense_date)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', 75, '2026-01-05');
  INSERT INTO compliance_overrides (company_id, branch_id, override_type, reason, created_by_app_user_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'payroll_sif', 'audit', '00000000-0000-0000-0000-000000000032');

  -- Documents, benefits, people operations, and clinical records.
  INSERT INTO employee_documents (company_id, branch_id, employee_id, document_type, file_name, status)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', 'passport', 'passport.pdf', 'pending_verification');
  INSERT INTO insurance_policies (id, company_id, branch_id)
    VALUES ('00000000-0000-0000-0000-000000000501', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011');
  INSERT INTO employee_insurance (company_id, branch_id, employee_id, policy_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000501');
  INSERT INTO insurance_dependants (company_id, branch_id, employee_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021');
  INSERT INTO notifications (company_id, branch_id, recipient_app_user_id, type)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000031', 'leave_submitted');
  INSERT INTO employee_contracts (company_id, branch_id, employee_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021');
  INSERT INTO offboarding_checklists (id, company_id, branch_id, employee_id)
    VALUES ('00000000-0000-0000-0000-000000000601', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021');
  INSERT INTO offboarding_tasks (company_id, branch_id, checklist_id, task_name)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000601', 'Return laptop');
  INSERT INTO offboarding_task_templates (company_id, branch_id, task_name)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'Return laptop');
  INSERT INTO assets (id, company_id, branch_id, name)
    VALUES ('00000000-0000-0000-0000-000000000602', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'Laptop');
  INSERT INTO asset_assignments (company_id, branch_id, asset_id, employee_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000602', '00000000-0000-0000-0000-000000000021');
  INSERT INTO training_records (company_id, branch_id, employee_id)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021');
  INSERT INTO certifications (company_id, branch_id, employee_id, status)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', 'pending_review');
  INSERT INTO cme_requirements (company_id, branch_id, employee_id, year)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', 2026);
  INSERT INTO incident_reports (company_id, branch_id, incident_date)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '2026-01-06');
  INSERT INTO letter_requests (company_id, branch_id, employee_id, letter_type)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', 'salary_certificate');
  INSERT INTO appraisal_cycles (id, company_id, branch_id, name, review_from, review_to)
    VALUES ('00000000-0000-0000-0000-000000000701', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '2026 H1', '2026-01-01', '2026-06-30');
  INSERT INTO appraisals (id, company_id, branch_id, cycle_id, employee_id)
    VALUES ('00000000-0000-0000-0000-000000000702', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000701', '00000000-0000-0000-0000-000000000021');
  INSERT INTO appraisal_sections (company_id, branch_id, appraisal_id, section_name)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000702', 'Clinical skills');

  -- A branch belonging to another tenant must fail the composite branch scope.
  BEGIN
    INSERT INTO leave_types (company_id, branch_id, code, name)
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000012', 'SICK', 'Sick');
    RAISE EXCEPTION 'cross-tenant branch scope was accepted';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;

  -- An employee reference from the wrong branch must fail the scoped employee key.
  BEGIN
    INSERT INTO leave_requests (company_id, branch_id, employee_id, leave_type_id, start_date, end_date, days_requested)
    VALUES ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000301', '2026-02-01', '2026-02-02', 1);
    RAISE EXCEPTION 'cross-scope employee reference was accepted';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
END
\$\$;
ROLLBACK;
"
