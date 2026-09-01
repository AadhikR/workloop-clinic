# Phase 4A schema catalogue and design decisions

## Status

**Phase 4A design artifact approved by the project owner on 2026-09-01.**

The project owner approved the design directions and final document review on 2026-09-01. This file
records Phase 4A decisions. Phase 4B requires separate project-owner authorization and may implement
only its approved core identity and organization schema.

## Reading and counting rules

The review used this precedence order:

1. `DIGITALOCEAN_MIGRATION_PLAN.md` and the approved decisions dated 2026-09-01.
2. Every document under `docs/migration/phase-0/` and `docs/migration/phase-3/`.
3. `docs/migration/phase-4/SUBPHASE_PLAN.md`.
4. The immutable Phase 3 revision `f41c9a7b23d1`, `backend/app/models/identity.py`,
   `backend/app/db/base.py`, and `backend/app/auth/application_user.py`.
5. The 12 root SQL files in the dependency order recorded by Phase 0.
6. The 50 checked-in numbered files from `sql/001` through `sql/055`, in numeric order. Numbers
   `010`, `011`, `015`, `018`, and `020` do not exist. Only `015` is documented as intentionally
   skipped.
7. Active frontend producers and consumers recorded by the Phase 0 contract documents when two SQL
   versions disagree.

The document sources were `docs/migration/phase-0/README.md`, `SQL_SCHEMA_INVENTORY.md`,
`SUPABASE_DEPENDENCY_INVENTORY.md`, `FEATURE_AND_CONTRACT_MATRIX.md`, and
`SYNTHETIC_TEST_DATA.md`; and `docs/migration/phase-3/AUTHENTICATION_DESIGN.md`,
`IDENTITY_SCHEMA.md`, `KEYCLOAK_CONFIGURATION.md`, `FASTAPI_TOKEN_VALIDATION.md`,
`APPLICATION_USER_RESOLUTION.md`, `SEPARATE_REACT_MIGRATION_BUILD.md`,
`SYNTHETIC_LOGIN_AND_ACCOUNT_LIFECYCLE.md`, and `SECURITY_RESTART_COMPLETION_GATE.md`.

The inferred root SQL order was:

```text
supabase_schema.sql
supabase_migration_employee_auth_mapping.sql
supabase_leave_schema.sql
supabase_attendance_schema.sql
supabase_leave_rls_fix.sql
supabase_migration_employee_rls.sql
supabase_migration_payslips.sql
supabase_migration_leave_warnings.sql
supabase_migration_employee_company_read.sql
supabase_migration_grants.sql
supabase_migration_existing_db.sql          existing-database alternative/backfill
supabase_reset_test_data.sql                destructive utility, not a migration
```

The numbered SQL order was:

```text
001_emiratization.sql, 002_document_storage.sql, 003_medical_insurance.sql,
004_notifications.sql, 005_salary_advances.sql, 006_multi_level_leave.sql,
007_shift_roster.sql, 008_wps_tracking.sql, 009_probation_management.sql,
012_contract_renewal.sql, 013_offboarding.sql, 014_expense_claims.sql,
016_asset_management.sql, 017_payroll_approval.sql, 019_training_records.sql,
021_multi_company.sql, 022_admin_clock_events_access.sql,
023_fix_clock_event_rpc_entered_by.sql, 024_employee_self_upload.sql,
025_letter_requests.sql, 026_clinical_duty_rota.sql, 027_biometric_integration.sql,
028_probation_leave_rules.sql, 029_department_hierarchy.sql,
030_expense_manager_approval.sql, 031_appraisal_module.sql,
032_roster_compliance.sql, 033_clinical_gaps.sql, 034_manager_role.sql,
035_manager_employee_read.sql, 036_advance_rejection_reason.sql,
037_leave_manager_read.sql, 038_appraisal_manager_update.sql,
039_shifts_read_policy.sql, 040_training_manager_policies.sql,
041_employee_contact_update.sql, 042_certification_self_service.sql,
043_employee_portal_fixes.sql, 044_phase1_data_protection.sql,
045_core_rls_baseline.sql, 046_phase4_db_hardening.sql, 047_cme_tracking.sql,
048_incident_reports.sql, 049_feature_toggles.sql,
050_advance_repayment_scheduling.sql, 051_employee_request_actions.sql,
052_shift_swap_execution.sql, 053_roster_company_scope.sql,
054_certification_file_upload.sql, 055_custom_requests.sql
```

An object means a table name, function name, trigger name, or policy identity. A policy identity is
the pair `(table, policy name)`. Re-creations and replacements of the same identity count once and
their source chain stays in one row. Function overloads count under one function name because the
Phase 0 count is 29 distinct names. The undefined `manager_get_leave_queue` is not one of those 29.
Trigger replacements with different names remain separate legacy trigger identities. Tables count
by distinct application table name, not by repeated `CREATE TABLE IF NOT EXISTS` statements.

The legacy set has 52 tables. `app_users` is the Phase 3 addition. `branches` is the approved Phase
4 addition. No legacy table is removed, so the target has exactly 54 tables:

```text
52 legacy tables + app_users + branches = 54 target tables
```

## Global schema rules

### Names, keys, and types

- PostgreSQL names use `snake_case`. Constraint names follow `backend/app/db/base.py`: `pk_*`,
  `fk_*`, `uq_*`, `ck_*`, and `ix_*`.
- New database-generated UUID keys use core PostgreSQL 17 `gen_random_uuid()`. No extension is
  required. Python-side UUID defaults in `f41c9a7b23d1` remain untouched.
- `timestamptz` represents an instant. PostgreSQL persists UTC; APIs and displays convert zones.
  `date` remains a calendar date. `time` remains a wall-clock or shift-template time.
- Every new `created_at`, `updated_at`, submitted, approved, issued, generated, closed, completed,
  read, reviewed, or renewed instant uses `timestamptz`.
- All scalar money uses `numeric(12,2)`, except `payroll_runs.total_disbursed`, which uses
  `numeric(14,2)`. JSON money stays JSONB and FastAPI must validate every embedded amount as a
  two-decimal decimal before persistence.
- Only `app_role` and `account_status` are native PostgreSQL enums. Business states use `text` plus
  named checks.

### PostgreSQL 17

PostgreSQL 17 is the target. This replaces Phase 0's provisional PostgreSQL 16 choice.

| Provider evidence | Supported majors | Official source | Source date | Captured |
|---|---|---|---|---|
| DigitalOcean Managed PostgreSQL Standard | 14, 15, 16, 17, 18 | [Create PostgreSQL clusters](https://docs.digitalocean.com/products/databases/postgresql/how-to/create/) | Last verified 2026-08-19 | 2026-09-01 |
| DigitalOcean PostgreSQL Advanced Edition public preview | 16, 17, 18 | [Create Advanced Edition clusters](https://docs.digitalocean.com/products/databases/postgresql/how-to/use-advanced-edition-clusters/) | Last verified 2026-08-19 | 2026-09-01 |
| Azure Database for PostgreSQL Flexible Server | 11 through 18, with 11 through 13 in extended support | [Supported versions](https://learn.microsoft.com/en-us/azure/postgresql/configure-maintain/concepts-supported-versions) | Microsoft page date 2026-08-26, updated 2026-08-27 | 2026-09-01 |
| Core UUID function | `gen_random_uuid()` is built in | [PostgreSQL 17 UUID functions](https://www.postgresql.org/docs/17/functions-uuid.html) | PostgreSQL 17.11 documentation viewed 2026-09-01 | 2026-09-01 |

PostgreSQL 17 is in every provider range and avoids a `pgcrypto` dependency for UUID defaults.
Advanced Edition is a preview, so its availability does not make it the default deployment choice.

### Company, branch, and identity ownership

`companies` is the tenant and legal group. `branches` is the operating and payroll location.
Phase 3 `user_profiles.company_id` remains the tenant link. `employees.company_id` remains required
and `employees.branch_id` becomes required. The Phase 3 composite employee/profile foreign key and
role-link check remain exact.

The following rules replace legacy `auth.users` ownership:

- A legacy owner `user_id` does not become `app_users.id`. It becomes required `company_id`, and
  required `branch_id` where the row belongs to an operating location.
- A legacy `employees.auth_user_id` disappears. `user_profiles.employee_id` is the one account to
  employee link and `user_profiles.app_user_id` is its identity.
- A true recipient or actor identity becomes an `app_users.id` foreign key with an `_app_user_id`
  suffix. Text email audit fields become application-user foreign keys where the action is trusted.
- Every branch foreign key is paired with `company_id` through a composite foreign key to
  `branches(id, company_id)`. Every employee reference on a branch-owned row is similarly paired to
  `employees(id, company_id, branch_id)`. These checks prevent cross-tenant and cross-branch rows
  even before RLS exists.
- A nullable scoped reference uses PostgreSQL 17 column-list action syntax. For example,
  `FOREIGN KEY (reporting_manager_id, company_id, branch_id) ... ON DELETE SET NULL
  (reporting_manager_id)` clears only the optional reference. It never clears required scope.
  PostgreSQL documents this syntax under [CREATE TABLE](https://www.postgresql.org/docs/17/sql-createtable.html).
- Tenant-wide rows have `company_id` only. Branch settings and operating records have both keys.
  Child rows that inherit scope from an immutable parent do not duplicate the keys unless they were
  independently queried or written in the legacy API.
- `offboarding_tasks` and `appraisal_sections` are directly written tables. They therefore carry
  required company and branch columns and same-scope composite parent FKs rather than relying on an
  application join to infer scope.

Branch-owned tables are `employees`, `payroll_runs`, `payroll_entries`, `payslips`, all leave tables,
all attendance and roster tables, `nafis_reports`, document and insurance tables, advances,
expenses, contracts, offboarding tables, assets, training and certification tables, departments,
appraisal tables, CME, incidents, and letter requests. `notifications` and `compliance_overrides`
carry nullable `branch_id` because a notification or override may apply to the whole tenant.
`companies`, `branches`, `user_profiles`, and `app_users` follow their identity-specific shapes.

## Target table catalogue

Notation in the column lists is `name type nullability default [source or transformation]`. `NN`
means not null and `N` means nullable. Unquoted `none` means no default. All UUID PK defaults below
are `gen_random_uuid()` except the four Phase 3 keys, whose existing Python-side behavior remains
unchanged until a later revision deliberately adds a server default.

### Identity and organization

| # | Table | Final columns |
|---:|---|---|
| 1 | `companies` | `id uuid NN none` [Phase 3]; `name text NN ''` [legacy company name, legal-group value]; `sector text NN ''`; `nafis_quota_percent numeric(5,2) NN 2.00`; `enable_nafis boolean NN true`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. Legacy branch/location columns move to `branches`; legacy `user_id` and its dropped uniqueness do not survive. |
| 2 | `branches` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `name text NN ''` [legacy `branch_name`, fallback legacy `companies.name`]; `mol_employer_id text NN ''`; `default_bank_routing_code text NN ''`; `address text NN ''`; `contact_email text NN ''`; `default_salary_day integer N 25`; `work_location_type text NN 'Mainland'`; `free_zone_name text NN ''`; `logo_url text NN ''`; `enable_staffing_rules boolean NN true`; `enable_biometric_import boolean NN true`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()` [all location fields from legacy `companies`]. |
| 3 | `app_users` | `id uuid NN none`; `identity_issuer text NN none`; `identity_subject text NN none`; `status account_status NN 'pending_identity'`; `created_at timestamptz NN CURRENT_TIMESTAMP` [exact Phase 3 shape]. |
| 4 | `employees` | `id uuid NN none`; `company_id uuid NN none`; `branch_id uuid NN none`; `emp_no text NN ''`; `name text NN none`; `mol_id text NN none`; `bank_name text NN ''`; `bank_routing_code text NN ''`; `iban text NN ''`; `basic_salary numeric(12,2) NN 0`; `allowance numeric(12,2) NN 0`; `active boolean NN true`; `personal_email text NN ''`; `work_email text NN ''`; `phone text NN ''`; `date_of_birth date N none`; `gender text NN ''`; `marital_status text NN ''`; `home_country_address text NN ''`; `photo_url text NN ''`; `emergency_contact_name text NN ''`; `emergency_contact_relationship text NN ''`; `emergency_contact_phone text NN ''`; `job_title text NN ''`; `department text NN ''`; `reporting_manager_id uuid N none`; `employment_start_date date N none`; `probation_end_date date N none`; `probation_extended boolean NN false`; `contract_type text NN 'Unlimited'`; `contract_end_date date N none`; `employment_status text NN 'Active'`; `termination_date date N none`; `termination_reason text NN ''`; `housing_allowance numeric(12,2) NN 0`; `transport_allowance numeric(12,2) NN 0`; `other_allowances numeric(12,2) NN 0`; `other_allowances_label text NN ''`; `bank_account_holder text NN ''`; `nationality text NN ''`; `visa_type text NN ''` [canonical temporary-visitor value is `Tourist (Temp)`]; `visa_number text NN ''`; `visa_expiry date N none`; `passport_number text NN ''`; `passport_expiry date N none`; `emirates_id text NN ''`; `emirates_id_expiry date N none`; `labour_card_number text NN ''`; `labour_card_expiry date N none`; `sponsoring_entity text NN ''`; `work_location_type text NN 'Mainland'`; `free_zone_name text NN ''`; `nafis_registration_no text NN ''`; `shift_id uuid N none`; `licence_authority text NN 'None'`; `licence_number text NN ''`; `licence_expiry date N none`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. `auth_user_id` and owner `user_id` are removed; Phase 3 identity linking replaces them. |
| 5 | `user_profiles` | `app_user_id uuid NN none`; `company_id uuid NN none`; `employee_id uuid N none`; `role app_role NN none`; `created_at timestamptz NN CURRENT_TIMESTAMP` [Phase 3 columns remain exact; target adds an eligible unique key on `(app_user_id,company_id)` without changing resolver columns]. |
| 6 | `employee_job_history` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `changed_at timestamptz NN now()`; `changed_by_app_user_id uuid N none` [legacy email text becomes app identity]; `change_type text NN none` [normalized lowercase snake case]; `old_value text NN ''`; `new_value text NN ''`; `reason text NN ''`. The duplicate root definitions are one table. |
| 7 | `departments` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `name text NN none`; `parent_id uuid N none`; `head_employee_id uuid N none`; `color text NN '#6366f1'`; `description text NN ''`; `sort_order integer NN 0`; `created_at timestamptz NN now()`. |
| 8 | `department_staffing_rules` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `department text NN none`; `shift_category text NN none`; `min_staff integer NN 1`; `effective_from date N none`; `effective_to date N none`. |

### Payroll, finance, and compliance

| # | Table | Final columns |
|---:|---|---|
| 9 | `payroll_runs` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `period text NN none`; `payment_date date N none` [legacy text parsed]; `sequence_no text NN ''`; `scr_bank_routing_code text NN ''`; `description text NN ''`; `status text NN 'draft'`; `run_by_app_user_id uuid N none`; `total_disbursed numeric(14,2) NN 0`; `employee_count integer NN 0`; `wps_status text NN 'draft'`; `wps_submitted_at timestamptz N none`; `wps_confirmed_at timestamptz N none`; `wps_reference_no text NN ''`; `approval_status text NN 'draft'`; `submitted_for_approval_at timestamptz N none`; `submitted_by_app_user_id uuid N none`; `approved_by_app_user_id uuid N none`; `approved_at timestamptz N none`; `rejection_reason text NN ''`; `rejected_at timestamptz N none`; `rejected_by_app_user_id uuid N none` [new lifecycle actor]; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. |
| 10 | `payroll_entries` | `id uuid NN gen_random_uuid()`; `payroll_run_id uuid NN none`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none` [legacy soft reference becomes FK]; `basic_salary numeric(12,2) NN 0`; `housing_allowance numeric(12,2) NN 0`; `transport_allowance numeric(12,2) NN 0`; `allowance numeric(12,2) NN 0`; `increment numeric(12,2) NN 0`; `bonus numeric(12,2) NN 0`; `other_pay numeric(12,2) NN 0`; `leave_deduction numeric(12,2) NN 0` [renamed from misleading `du_cost`]; `variable_allowance numeric(12,2) NN 0`; `additional_allowances jsonb NN '[]'`; `deductions jsonb NN '[]'`; `excluded boolean NN false`; `wps_payment_status text NN 'pending'`; `wps_rejection_reason text NN ''`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. |
| 11 | `payslips` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `payroll_run_id uuid NN none`; `employee_id uuid NN none`; `period text NN none`; `payment_date date N none`; `gross_pay numeric(12,2) NN 0`; `net_pay numeric(12,2) NN 0`; `data_snapshot jsonb NN '{}'`; `issued_at timestamptz NN now()`. |
| 12 | `payroll_approval_log` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `payroll_run_id uuid NN none`; `action text NN none`; `performed_by_app_user_id uuid NN none` [required history actor]; `notes text NN ''`; `created_at timestamptz NN now()`. |
| 13 | `nafis_reports` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `period text NN none`; `total_headcount integer NN 0`; `emirati_count integer NN 0`; `ratio_percent numeric(5,2) NN 0`; `required_percent numeric(5,2) NN 0`; `compliant boolean NN false`; `snapshot jsonb N none`; `generated_at timestamptz NN now()`. |
| 14 | `salary_advances` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `amount numeric(12,2) NN none`; `disbursed_date date N none`; `repayment_start_month date NN date_trunc('month',CURRENT_DATE)::date`; `reason text NN ''`; `repayment_months integer NN 1`; `monthly_deduction numeric(12,2) NN 0`; `outstanding_balance numeric(12,2) NN 0`; `status text NN 'active'`; `rejection_reason text N none`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. |
| 15 | `advance_repayments` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none` [new required denormalized scope]; `branch_id uuid NN none` [new required denormalized scope]; `advance_id uuid NN none`; `payroll_run_id uuid N none`; `idempotency_key uuid NN none` [caller-supplied request key persisted for every repayment]; `amount numeric(12,2) NN none`; `paid_date date NN CURRENT_DATE`; `created_at timestamptz NN now()`. Scope must agree with the advance and, when present, payroll run. |
| 16 | `expense_claims` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `category text NN 'other'`; `amount numeric(12,2) NN none`; `expense_date date NN none`; `description text NN ''`; `receipt_url text NN ''`; `status text NN 'pending'`; `rejection_reason text NN ''`; `payroll_run_id uuid N none`; `approved_by_app_user_id uuid N none`; `approved_at timestamptz N none`; `manager_approved_at timestamptz N none`; `manager_approved_by_app_user_id uuid N none`; `manager_rejection_reason text NN ''`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. |
| 17 | `compliance_overrides` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid N none`; `override_type text NN none`; `employee_ids jsonb N none`; `reason text NN none`; `created_by_app_user_id uuid NN none`; `created_at timestamptz NN now()`. |

### Leave

| # | Table | Final columns |
|---:|---|---|
| 18 | `leave_settings` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `leave_year_type text NN 'calendar'`; `weekend_definition text NN 'fri-sat'`; `carry_forward_enabled boolean NN true`; `carry_forward_max_days integer NN 15`; `approval_chain text NN '1-level'`; `ramadan_active boolean NN false`; `ramadan_start date N none`; `ramadan_end date N none`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. |
| 19 | `leave_types` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `code text NN none`; `name text NN none`; `color text NN '#6b7280'`; `is_paid boolean NN true`; `is_unlimited boolean NN false`; `requires_approval boolean NN true`; `requires_attachment boolean NN false`; `requires_reason boolean NN false`; `min_notice_days integer NN 0`; `annual_entitlement_days numeric(6,2) NN 0`; `accrual_type text NN 'fixed'`; `day_count_type text NN 'calendar'`; `auto_approve boolean NN false`; `carry_forward_allowed boolean NN false`; `carry_forward_max_days integer NN 0`; `gender_restriction text N none`; `min_service_months integer NN 0`; `once_per_career boolean NN false`; `not_deducted_from_annual boolean NN false`; `affects_payroll boolean NN false`; `law_reference text NN ''`; `is_active boolean NN true`; `sort_order integer NN 0`; `probation_eligible boolean NN true`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. |
| 20 | `public_holidays` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `date date NN none`; `name text NN none`; `type text NN 'federal'`; `year integer NN none`; `created_at timestamptz NN now()`. |
| 21 | `leave_requests` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `leave_type_id uuid NN none`; `start_date date NN none`; `end_date date NN none`; `is_half_day boolean NN false`; `half_day_period text N none`; `days_requested numeric(6,2) NN 0`; `status text NN 'Pending'`; `reason text NN ''`; `attachment_url text NN ''`; `rejection_reason text NN ''`; `approved_by_app_user_id uuid N none`; `approved_at timestamptz N none`; `relationship text NN ''`; `deceased_name text NN ''`; `date_of_death date N none`; `child_birth_date date N none`; `child_name text NN ''`; `expected_due_date date N none`; `institution_name text NN ''`; `exam_dates text NN ''`; `manager_approved_at timestamptz N none`; `manager_approved_by_app_user_id uuid N none`; `manager_rejection_reason text NN ''`; `substitute_employee_id uuid N none`; `approval_level_required integer NN 1`; `approval_comment text NN ''`; `warnings jsonb NN '[]'`; `submitted_at timestamptz NN now()`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. `leave_type_code` is removed and derived through `leave_type_id`. |
| 22 | `leave_audit_log` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `leave_request_id uuid NN none`; `action text NN none`; `actor_app_user_id uuid NN none`; `reason text NN ''`; `old_status text NN ''`; `new_status text NN none`; `created_at timestamptz NN now()`. `employee_id` is removed and derived through the scoped request FK. |
| 23 | `leave_balances` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `leave_type_id uuid NN none`; `leave_year integer NN none`; `entitled_days numeric(6,2) NN 0`; `accrued_days numeric(6,2) NN 0`; `used_days numeric(6,2) NN 0`; `pending_days numeric(6,2) NN 0`; `carried_forward numeric(6,2) NN 0`; `remaining_days numeric(6,2) NN 0`; `sick_full_pay_used numeric(6,2) NN 0`; `sick_half_pay_used numeric(6,2) NN 0`; `sick_unpaid_used numeric(6,2) NN 0`; `hajj_taken boolean NN false`; `updated_at timestamptz NN now()`. `leave_type_code` is removed and derived through `leave_type_id`. |
| 24 | `leave_approval_delegates` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `approver_employee_id uuid NN none`; `delegate_employee_id uuid NN none`; `from_date date NN none`; `to_date date NN none`; `created_at timestamptz NN now()`. |

### Attendance and roster

| # | Table | Final columns |
|---:|---|---|
| 25 | `attendance_settings` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `working_days text[] NN ARRAY['Mon','Tue','Wed','Thu']`; `weekend_days text[] NN ARRAY['Fri','Sat']`; `default_hours_per_day numeric(4,2) NN 8`; `late_grace_minutes integer NN 10`; `early_departure_grace_minutes integer NN 10`; `overtime_requires_approval boolean NN true`; `max_daily_overtime_hours numeric(4,2) NN 2`; `late_deduction_policy text NN 'none'`; `late_deduction_amount numeric(12,2) NN 0` [widened from 10,2]; `wfh_enabled boolean NN false`; `regularisation_max_days_per_month integer NN 2`; `regularisation_window_days integer NN 7`; `biometric_api_enabled boolean NN false`; `biometric_api_key text NN ''`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. |
| 26 | `shifts` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `name text NN none`; `shift_type text NN 'fixed'`; `start_time time N none`; `end_time time N none`; `break_minutes integer NN 60`; `expected_hours numeric(4,2) NN 8`; `late_grace_minutes integer NN 10`; `early_departure_grace_minutes integer NN 10`; `split_start_time time N none`; `split_end_time time N none`; `is_overnight boolean NN false`; `min_hours_flexible numeric(4,2) N none`; `is_active boolean NN true`; `color text NN '#6366f1'`; `code text N none`; `shift_category text NN 'morning'`; `min_staff integer NN 1`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. `min_staff` remains for per-template compatibility even though department rules later became preferred. |
| 27 | `shift_assignments` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `shift_id uuid NN none`; `effective_from date NN none`; `effective_to date N none`; `created_at timestamptz NN now()`. |
| 28 | `clock_events` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `event_type text NN none`; `event_time timestamptz NN none`; `method text NN 'WEB'` [canonical biometric value `BIOMETRIC`; future conversion maps `BIOMETRIC_API`]; `ip_address text N none`; `gps_lat numeric(10,7) N none`; `gps_lng numeric(10,7) N none`; `entered_by_app_user_id uuid N none` [resolves the legacy employee UUID versus Auth UUID conflict]; `notes text NN ''`; `is_superseded boolean NN false`; `superseded_by uuid N none`; `created_at timestamptz NN now()`. |
| 29 | `attendance_records` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `date date NN none`; `shift_id uuid N none`; `clock_in_time timestamptz N none`; `clock_out_time timestamptz N none`; `total_hours numeric(5,2) NN 0`; `status text NN 'ABSENT'`; `late_minutes integer NN 0`; `early_departure_minutes integer NN 0`; `overtime_hours numeric(5,2) NN 0`; `overtime_type text N none`; `overtime_amount numeric(12,2) NN 0`; `overtime_approved_by_app_user_id uuid N none`; `overtime_approved boolean NN false`; `worked_on_rest_day boolean NN false`; `rest_day_substitute boolean NN false`; `missing_clock_out boolean NN false`; `is_ramadan_day boolean NN false`; `absence_deduction numeric(12,2) NN 0`; `late_deduction numeric(12,2) NN 0`; `period_closed boolean NN false`; `resolved_by_app_user_id uuid N none`; `resolution_type text NN ''`; `resolution_notes text NN ''`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. All three monetary columns widen from 10,2 to 12,2. |
| 30 | `attendance_periods` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `period text NN none`; `status text NN 'open'`; `closed_at timestamptz N none`; `closed_by_app_user_id uuid N none`; `payroll_ready boolean NN false`; `open_items integer NN 0`; `created_at timestamptz NN now()`. |
| 31 | `regularisation_requests` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `attendance_date date NN none`; `correct_clock_in timestamptz NN none`; `correct_clock_out timestamptz NN none` [active producer sends ISO instants; replaces contradictory base `time` declaration]; `reason text NN ''`; `status text NN 'Pending'`; `approved_by_app_user_id uuid N none`; `approved_at timestamptz N none`; `rejection_reason text NN ''`; `original_clock_in timestamptz N none`; `original_clock_out timestamptz N none`; `submitted_at timestamptz NN now()`; `created_at timestamptz NN now()`. |
| 32 | `attendance_audit_log` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `attendance_date date N none`; `action text NN none`; `actor_app_user_id uuid NN none` [required history actor]; `old_value text NN ''`; `new_value text NN ''`; `reason text NN ''`; `created_at timestamptz NN now()`. |
| 33 | `roster_assignments` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `shift_id uuid NN none`; `date date NN none`; `published boolean NN false`; `notes text NN ''`; `planned_hours numeric(4,2) N none`; `actual_hours numeric(4,2) N none`; `co_hours numeric(4,2) NN 0` [approved tightening]; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. Legacy `company_id` means branch and becomes `branch_id`; tenant `company_id` is added. |
| 34 | `shift_swap_requests` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `requester_employee_id uuid NN none`; `target_employee_id uuid NN none`; `requester_date date NN none`; `target_date date N none`; `reason text NN ''`; `status text NN 'pending'`; `admin_approved_at timestamptz N none`; `admin_approved_by_app_user_id uuid N none`; `rejection_reason text NN ''`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. |
| 35 | `biometric_mappings` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `badge_no text NN none`; `employee_id uuid NN none`; `device_name text NN 'Default'` [approved tightening]; `created_at timestamptz NN now()` [approved tightening]. |

### Documents, benefits, people operations, and clinical records

| # | Table | Final columns |
|---:|---|---|
| 36 | `employee_documents` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `document_type text NN none`; `document_number text NN ''`; `file_name text NN none`; `file_size integer NN 0`; `storage_path text NN ''`; `expiry_date date N none`; `notes text NN ''`; `status text NN 'verified'`; `rejection_reason text NN ''`; `submitted_by text NN 'hr'`; `reviewed_by_app_user_id uuid N none` [new lifecycle actor]; `reviewed_at timestamptz N none` [new lifecycle instant]; `uploaded_at timestamptz NN now()`. Stale `doc_type` is not added. |
| 37 | `insurance_policies` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `insurer_name text NN ''`; `policy_number text NN ''`; `tier_name text NN ''`; `annual_premium numeric(12,2) NN 0`; `renewal_date date N none`; `broker_name text NN ''`; `broker_contact text NN ''`; `notes text NN ''`; `created_at timestamptz NN now()`. |
| 38 | `employee_insurance` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `policy_id uuid N none`; `member_id text NN ''`; `card_number text NN ''`; `effective_date date N none`; `expiry_date date N none`; `tier_name text NN ''`; `created_at timestamptz NN now()`. |
| 39 | `insurance_dependants` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `name text NN ''`; `relationship text NN ''`; `date_of_birth date N none`; `card_number text NN ''`; `created_at timestamptz NN now()`. |
| 40 | `notifications` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid N none`; `created_by_app_user_id uuid N none`; `recipient_app_user_id uuid NN none`; `type text NN none`; `title text NN ''`; `body text NN ''`; `related_entity_type text NN ''`; `related_entity_id text NN ''`; `read_at timestamptz N none`; `created_at timestamptz NN now()`. Recipient and nullable creator are company-scoped through composite profile FKs. |
| 41 | `employee_contracts` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `contract_type text NN 'Limited'`; `start_date date N none`; `end_date date N none`; `renewed_at timestamptz NN now()`; `renewed_by_app_user_id uuid N none`; `action text NN 'new'`; `notes text NN ''`; `created_at timestamptz NN now()`. |
| 42 | `offboarding_checklists` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `status text NN 'in_progress'`; `visa_cancellation_status text NN 'not_started'`; `visa_cancellation_date date N none`; `created_at timestamptz NN now()`; `completed_at timestamptz N none`; `completed_by_app_user_id uuid N none` [new lifecycle actor]. |
| 43 | `offboarding_tasks` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none` [required direct-write scope]; `branch_id uuid NN none` [required direct-write scope]; `checklist_id uuid NN none`; `task_name text NN none`; `completed boolean NN false`; `completed_at timestamptz N none`; `completed_by_app_user_id uuid N none`; `notes text NN ''`; `sort_order integer NN 0`; `created_at timestamptz NN now()`. Legacy owner `user_id` is replaced by exact company/branch scope, which must agree with the checklist. |
| 44 | `offboarding_task_templates` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `task_name text NN none`; `default_order integer NN 0`; `created_at timestamptz NN now()`. |
| 45 | `assets` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `name text NN none`; `asset_code text NN ''`; `category text NN 'other'`; `brand text NN ''`; `model text NN ''`; `serial_number text NN ''`; `purchase_date date N none`; `purchase_cost numeric(12,2) N none`; `status text NN 'available'`; `notes text NN ''`; `created_at timestamptz NN now()`. |
| 46 | `asset_assignments` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `asset_id uuid NN none`; `employee_id uuid NN none`; `assigned_date date NN CURRENT_DATE`; `return_date date N none`; `condition_at_handover text NN 'good'`; `condition_at_return text N none`; `notes text NN ''`; `assigned_by_app_user_id uuid N none`; `created_at timestamptz NN now()`. |
| 47 | `training_records` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `training_title text NN ''`; `training_type text NN 'external'`; `provider text NN ''`; `start_date date N none`; `end_date date N none`; `duration_hours numeric(6,2) N none`; `cost numeric(12,2) NN 0`; `status text NN 'planned'`; `score text NN ''`; `passed boolean N none`; `certificate_url text NN ''`; `storage_path text NN ''`; `file_name text NN ''`; `notes text NN ''`; `is_cme boolean NN false`; `created_at timestamptz NN now()`. |
| 48 | `certifications` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `certification_name text NN ''`; `issuing_body text NN ''`; `certificate_no text NN ''`; `issued_date date N none`; `expiry_date date N none`; `certificate_url text NN ''`; `storage_path text NN ''`; `file_name text NN ''`; `notes text NN ''`; `status text NN 'verified'`; `reviewed_by_app_user_id uuid N none` [new lifecycle actor]; `reviewed_at timestamptz N none` [new lifecycle instant]; `created_at timestamptz NN now()`. |
| 49 | `appraisal_cycles` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `name text NN none`; `review_from date NN none`; `review_to date NN none`; `status text NN 'draft'`; `closed_by_app_user_id uuid N none` [new lifecycle actor]; `closed_at timestamptz N none` [new lifecycle instant]; `created_at timestamptz NN now()`. |
| 50 | `appraisals` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `cycle_id uuid NN none`; `employee_id uuid NN none`; `overall_rating numeric(3,1) N none`; `self_rating numeric(3,1) N none`; `status text NN 'pending'`; `reviewer_comments text N none`; `development_plan text N none`; `reviewed_at timestamptz N none`; `reviewed_by_app_user_id uuid N none`; `created_at timestamptz NN now()`; `updated_at timestamptz NN now()`. |
| 51 | `appraisal_sections` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none` [required direct-write scope]; `branch_id uuid NN none` [required direct-write scope]; `appraisal_id uuid NN none`; `section_name text NN none`; `weight numeric(4,2) NN 1.0`; `rating numeric(3,1) N none`; `self_rating numeric(3,1) N none`; `comments text N none`; `sort_order integer NN 0`. Scope must agree with the parent appraisal. |
| 52 | `cme_requirements` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `year integer NN none`; `required_hours numeric(6,1) NN 25`; `notes text NN ''` [approved tightening]; `created_at timestamptz NN now()` [approved tightening]; `updated_at timestamptz NN now()` [approved tightening]. |
| 53 | `incident_reports` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none` [legacy `company_id` was a branch key]; `incident_date date NN none`; `incident_time time N none`; `location text NN ''` [approved tightening]; `department text NN ''` [approved tightening]; `incident_type text NN 'other'`; `severity text NN 'low'`; `description text NN ''`; `reported_by_id uuid N none`; `involved_emp_id uuid N none`; `immediate_action text NN ''` [approved tightening]; `root_cause text NN ''` [approved tightening]; `corrective_action text NN ''` [approved tightening]; `status text NN 'open'`; `closed_date date N none`; `closed_by_app_user_id uuid N none`; `notes text NN ''` [approved tightening]; `created_at timestamptz NN now()` [approved tightening]; `updated_at timestamptz NN now()` [approved tightening]. |
| 54 | `letter_requests` | `id uuid NN gen_random_uuid()`; `company_id uuid NN none`; `branch_id uuid NN none`; `employee_id uuid NN none`; `request_kind text NN 'letter'`; `letter_type text NN none`; `purpose text NN ''`; `status text NN 'pending'`; `notes text NN ''`; `rejection_reason text NN ''`; `requested_at timestamptz NN now()`; `completed_at timestamptz N none`; `actioned_at timestamptz N none` [new lifecycle instant]; `actioned_by_app_user_id uuid N none` [new lifecycle actor]. `letter_type` remains the custom subject and `purpose` the custom details for `request_kind='custom'`. |

### Per-table provenance

The catalogue rows state nontrivial column transformations inline. This map supplies the complete
table-level DDL, constraint, index, and trigger source trail for columns that carry through
unchanged. Policy-only, grant-only, function-only, and data-only files are excluded here. Their
complete source chains appear in the RLS, grants, function, and backfill sections. This rule applies
to every row below. `Phase 3` means the revision, model, identity design, and resolver contract
reviewed above.

| # | Target table | Source provenance |
|---:|---|---|
| 1 | `companies` | `supabase_schema.sql`; `001`; `021`; `049`; Phase 3. Branch fields split out; owner `user_id` removed. |
| 2 | `branches` | New target table from legacy `companies` location/payroll columns in root, `021`, and `049`. |
| 3 | `app_users` | Phase 3 only. |
| 4 | `employees` | `supabase_schema.sql`; existing-db duplicate column chain; recovered Auth mapping; attendance root; `001`, `009`, `021`, `033`, `046`; Phase 3. Auth ownership removed and branch scope added. |
| 5 | `user_profiles` | Recovered Auth mapping; `034`; Phase 3 final shape wins. |
| 6 | `employee_job_history` | Duplicate definitions in root schema and existing-db script; actor and normalized change type are target transformations. |
| 7 | `departments` | `029`; company and branch scope replace owner `user_id`. |
| 8 | `department_staffing_rules` | `033`; company and branch scope replace owner `user_id`; approved flexible category added. |
| 9 | `payroll_runs` | Root schema; existing-db duplicate additions; `008`, `017`, `021`, `044`, `046`; payment date, actor, and scope transformations inline. |
| 10 | `payroll_entries` | Root schema; existing-db duplicate additions; `008`, `046`; soft employee reference becomes scoped FK; `du_cost` becomes `leave_deduction`. |
| 11 | `payslips` | Payslip root migration; owner replaced by company and branch scope. |
| 12 | `payroll_approval_log` | `017`; owner and actor transformed. |
| 13 | `nafis_reports` | `001`; owner replaced by company and branch scope. |
| 14 | `salary_advances` | `005`; `036`; `046`; `050`; owner and employee scope transformed. |
| 15 | `advance_repayments` | `005`, `050`; required company/branch scope, request key, and composite parent FKs are new approved target decisions. |
| 16 | `expense_claims` | `014`; `030`; `046`; owner and actor fields transformed. |
| 17 | `compliance_overrides` | `033`; optional branch and explicit creator added from owner semantics. |
| 18 | `leave_settings` | Leave root; owner replaced by company and branch scope; approved weekend set applied. |
| 19 | `leave_types` | Leave root; `028`; owner replaced by company and branch scope. |
| 20 | `public_holidays` | Leave root; owner replaced by company and branch scope. |
| 21 | `leave_requests` | Leave root; warnings root migration; `006`; `046`; owner and actor fields transformed; redundant type code removed. |
| 22 | `leave_audit_log` | Leave root; owner and actor transformed; redundant employee ID removed. |
| 23 | `leave_balances` | Leave root; owner replaced by company and branch scope; redundant type code removed. |
| 24 | `leave_approval_delegates` | `006`; owner replaced by company and branch scope. |
| 25 | `attendance_settings` | Attendance root; attendance money widened and owner replaced by company and branch scope. |
| 26 | `shifts` | Attendance root; `007`, `026`, `032`; owner replaced by company and branch scope. |
| 27 | `shift_assignments` | Attendance root; owner replaced by company and branch scope. |
| 28 | `clock_events` | Attendance root; `046`; actor, scope, and biometric method transformed. |
| 29 | `attendance_records` | Attendance root; `046`; actor and scope transformed and money widened. |
| 30 | `attendance_periods` | Attendance root; owner and actor transformed. |
| 31 | `regularisation_requests` | Attendance root; correction clock values use producer-compatible instants. |
| 32 | `attendance_audit_log` | Attendance root; owner and actor transformed. |
| 33 | `roster_assignments` | `007`; `026`; `046`; `053`; legacy company key becomes branch key and tenant company is added. |
| 34 | `shift_swap_requests` | `007`; `053`; owner, branch, and actor transformed. |
| 35 | `biometric_mappings` | `027`; owner replaced by company and branch scope. |
| 36 | `employee_documents` | `002`; `024`; `046`; target keeps `document_type`, not stale `doc_type`; owner becomes company and branch; review actor/time are new lifecycle decisions. |
| 37 | `insurance_policies` | `003`; owner replaced by company and branch scope. |
| 38 | `employee_insurance` | `003`; owner replaced by company and branch scope. |
| 39 | `insurance_dependants` | `003`; owner replaced by company and branch scope. |
| 40 | `notifications` | `004`, `046`; Auth identities become company-scoped profile FKs; approved five-part dedup key and optional branch scope are target decisions. |
| 41 | `employee_contracts` | `012`, `046`; owner and actor transformed. |
| 42 | `offboarding_checklists` | `013`; owner replaced by company and branch scope; completion actor is a new lifecycle decision. |
| 43 | `offboarding_tasks` | `013`; owner becomes required company/branch scope; same-scope checklist FK and actor are target transformations. |
| 44 | `offboarding_task_templates` | `013`; owner replaced by company and branch scope. |
| 45 | `assets` | `016`; owner replaced by company and branch scope. |
| 46 | `asset_assignments` | `016`; owner and actor transformed; employee and asset references become scoped. |
| 47 | `training_records` | `019`, `046`, `047`, `054`; owner replaced by company and branch scope. |
| 48 | `certifications` | `019`, `042`, `046`, `054`; owner replaced by company and branch scope; review actor/time are new lifecycle decisions. |
| 49 | `appraisal_cycles` | `031`; active producer set resolves the stale `open` reader; close actor/time are new lifecycle decisions. |
| 50 | `appraisals` | `031`, `046`; actor and scope transformed; unused `self_reviewed` omitted. |
| 51 | `appraisal_sections` | `031`; required company/branch scope and same-scope appraisal FK are target transformations. |
| 52 | `cme_requirements` | `047`; owner replaced by company and branch scope. |
| 53 | `incident_reports` | `048`; legacy `company_id` becomes branch key; tenant, scoped employees, and actor transformed. |
| 54 | `letter_requests` | `025`, `046`, `055`; owner replaced by company and branch scope; custom requests retain subject/detail reuse; action actor is a new lifecycle decision. |

## Constraints and indexes

All PKs are the listed `id`, except `user_profiles.app_user_id`. Every listed FK uses `RESTRICT`
unless this section says otherwise. `RESTRICT` is deliberate for tenant, branch, identity, payroll,
and history parents. No target FK uses `CASCADE`. `SET NULL` is limited to optional non-lifecycle
links.

"Scoped employee," "scoped shift," and similar shorthand below always means a composite FK carrying
the row's required scope. Nullable scoped references use `ON DELETE SET NULL (<optional_id>)`, the
PostgreSQL 17 column-list form, so `company_id` and `branch_id` stay non-null. Required composite
reference targets are explicit unique constraints:

| Parent | Composite target |
|---|---|
| `branches` | `uq_branches_id_company_id (id,company_id)` |
| `employees` | preserved `uq_employees_id_company_id (id,company_id)` and `uq_employees_id_company_id_branch_id (id,company_id,branch_id)` |
| `shifts` | `uq_shifts_id_company_id_branch_id (id,company_id,branch_id)` |
| `payroll_runs` | `uq_payroll_runs_id_company_id_branch_id (id,company_id,branch_id)` |
| `leave_types` | `uq_leave_types_id_company_id_branch_id (id,company_id,branch_id)` |
| `leave_requests` | `uq_leave_requests_id_company_id_branch_id (id,company_id,branch_id)` |
| `regularisation_requests` | `uq_regularisation_requests_id_company_id_branch_id (id,company_id,branch_id)` |
| `regularisation_requests` | `uq_regularisation_requests_id_employee_id_company_id_branch_id (id,employee_id,company_id,branch_id)` for clock-event supersession agreement |
| `insurance_policies` | `uq_insurance_policies_id_company_id_branch_id (id,company_id,branch_id)` |
| `assets` | `uq_assets_id_company_id_branch_id (id,company_id,branch_id)` |
| `appraisal_cycles` | `uq_appraisal_cycles_id_company_id_branch_id (id,company_id,branch_id)` |
| `appraisals` | `uq_appraisals_id_company_id_branch_id (id,company_id,branch_id)` |
| `offboarding_checklists` | `uq_offboarding_checklists_id_company_id_branch_id (id,company_id,branch_id)` |
| `departments` | `uq_departments_id_company_id_branch_id (id,company_id,branch_id)` |
| `salary_advances` | `uq_salary_advances_id_company_id_branch_id (id,company_id,branch_id)` |
| `user_profiles` | `uq_user_profiles_app_user_id_company_id (app_user_id,company_id)` |

Create `employees` without its optional `shift_id` FK, create `shifts`, add
`uq_shifts_id_company_id_branch_id`, then add
`fk_employees_shift_id_shifts (shift_id,company_id,branch_id) ... ON DELETE SET NULL (shift_id)`.
This resolves the circular creation order without changing the target columns. The employee
reporting-manager FK can be created with the employee table because its unique target is on the same
table.

The compact table below uses these exact expansions. They are not descriptive shorthand:

- `branch scope RESTRICT` means
  `fk_<table>_company_id_companies (company_id)->companies(id) ON DELETE RESTRICT` and
  `fk_<table>_branch_id_branches (branch_id,company_id)->branches(id,company_id) ON DELETE RESTRICT`.
- `scoped employee RESTRICT` means
  `fk_<table>_employee_id_employees (employee_id,company_id,branch_id)->employees(id,company_id,branch_id) ON DELETE RESTRICT`.
  A differently named employee column substitutes that column name in both the constraint name and
  ordered column list.
- `scoped run RESTRICT` means
  `fk_<table>_payroll_run_id_payroll_runs (payroll_run_id,company_id,branch_id)->payroll_runs(id,company_id,branch_id) ON DELETE RESTRICT`.
- `scoped leave type RESTRICT`, `scoped request RESTRICT`, `scoped shift RESTRICT`, `scoped asset
  RESTRICT`, `scoped cycle RESTRICT`, `scoped checklist RESTRICT`, and `scoped appraisal RESTRICT`
  use the same ordered `(id,company_id,branch_id)` rule and names
  `fk_<table>_<column>_<parent>`.
- Every target table except `user_profiles` has exact PK `pk_<table> (id)`. `user_profiles` has
  `pk_user_profiles (app_user_id)`. There are 54 PKs.
- Lifecycle actor columns named in the exact lifecycle table use
  `fk_<table>_<column>_app_users (<column>)->app_users(id) ON DELETE RESTRICT`. Other nullable audit
  actor columns use the same name and target with `ON DELETE SET NULL`. The one length exception is
  `fk_attendance_records_ot_approved_by_app_users
  (overtime_approved_by_app_user_id)->app_users(id) ON DELETE RESTRICT`; its explicit shorter name
  stays within PostgreSQL's 63-byte identifier limit.
- The status/category rows below create exact check name `ck_<table>_<column>` with
  `<column> IN (<listed values>)`. Nullable closed sets add `<column> IS NULL OR` before that
  expression. Empty string is valid only when the listed set includes `''`.

Exact non-scope relationship FKs not covered by those expansions are:

| Constraint | Ordered source columns | Target | Delete |
|---|---|---|---|
| `fk_branches_company_id_companies` | `company_id` | `companies(id)` | RESTRICT |
| `fk_user_profiles_app_user_id_app_users` | `app_user_id` | `app_users(id)` | RESTRICT |
| `fk_user_profiles_company_id_companies` | `company_id` | `companies(id)` | RESTRICT |
| `fk_user_profiles_employee_id_employees` | `employee_id,company_id` | `employees(id,company_id)` | RESTRICT |
| `fk_employees_reporting_manager_id_employees` | `reporting_manager_id,company_id,branch_id` | `employees(id,company_id,branch_id)` | `SET NULL (reporting_manager_id)` |
| `fk_employees_shift_id_shifts` | `shift_id,company_id,branch_id` | `shifts(id,company_id,branch_id)` | `SET NULL (shift_id)`; add after shifts |
| `fk_departments_parent_id_departments` | `parent_id,company_id,branch_id` | `departments(id,company_id,branch_id)` | `SET NULL (parent_id)` |
| `fk_departments_head_employee_id_employees` | `head_employee_id,company_id,branch_id` | `employees(id,company_id,branch_id)` | `SET NULL (head_employee_id)` |
| `fk_advance_repayments_advance_id_salary_advances` | `advance_id,company_id,branch_id` | `salary_advances(id,company_id,branch_id)` | RESTRICT |
| `fk_advance_repayments_payroll_run_id_payroll_runs` | `payroll_run_id,company_id,branch_id` | `payroll_runs(id,company_id,branch_id)` | `SET NULL (payroll_run_id)` |
| `fk_expense_claims_payroll_run_id_payroll_runs` | `payroll_run_id,company_id,branch_id` | `payroll_runs(id,company_id,branch_id)` | `SET NULL (payroll_run_id)` |
| `fk_compliance_overrides_branch_id_branches` | `branch_id,company_id` | `branches(id,company_id)` | `SET NULL (branch_id)` |
| `fk_leave_requests_substitute_employee_id_employees` | `substitute_employee_id,company_id,branch_id` | `employees(id,company_id,branch_id)` | `SET NULL (substitute_employee_id)` |
| `fk_clock_events_superseded_by_regularisation_requests` | `superseded_by,employee_id,company_id,branch_id` | `regularisation_requests(id,employee_id,company_id,branch_id)` | `SET NULL (superseded_by)` |
| `fk_attendance_records_shift_id_shifts` | `shift_id,company_id,branch_id` | `shifts(id,company_id,branch_id)` | `SET NULL (shift_id)` |
| `fk_employee_insurance_policy_id_insurance_policies` | `policy_id,company_id,branch_id` | `insurance_policies(id,company_id,branch_id)` | `SET NULL (policy_id)` |
| `fk_notifications_recipient_app_user_id_user_profiles` | `recipient_app_user_id,company_id` | `user_profiles(app_user_id,company_id)` | RESTRICT |
| `fk_notifications_created_by_app_user_id_user_profiles` | `created_by_app_user_id,company_id` | `user_profiles(app_user_id,company_id)` | `SET NULL (created_by_app_user_id)` |
| `fk_notifications_branch_id_branches` | `branch_id,company_id` | `branches(id,company_id)` | `SET NULL (branch_id)` |
| `fk_incident_reports_reported_by_id_employees` | `reported_by_id,company_id,branch_id` | `employees(id,company_id,branch_id)` | `SET NULL (reported_by_id)` |
| `fk_incident_reports_involved_emp_id_employees` | `involved_emp_id,company_id,branch_id` | `employees(id,company_id,branch_id)` | `SET NULL (involved_emp_id)` |
| `fk_appraisal_sections_appraisal_id_appraisals` | `appraisal_id,company_id,branch_id` | `appraisals(id,company_id,branch_id)` | RESTRICT |
| `fk_offboarding_tasks_checklist_id_offboarding_checklists` | `checklist_id,company_id,branch_id` | `offboarding_checklists(id,company_id,branch_id)` | RESTRICT |

Exact unique and partial-unique objects are:

| Name | Table and ordered columns or expression | Null semantics |
|---|---|---|
| `uq_app_users_identity_issuer` | `app_users(identity_issuer,identity_subject)` | Both non-null. Preserves Phase 3 generated name. |
| `uq_user_profiles_app_user_id_company_id` | `user_profiles(app_user_id,company_id)` | Both non-null; eligible notification FK target. |
| `uq_user_profiles_employee_id` | unique index `user_profiles(employee_id) WHERE employee_id IS NOT NULL` | Null employee IDs repeat; a linked employee has one profile. |
| `uq_employees_id_company_id` | `employees(id,company_id)` | Preserved Phase 3 target. |
| `uq_employees_id_company_id_branch_id` | `employees(id,company_id,branch_id)` | All non-null. |
| `uq_branches_id_company_id` | `branches(id,company_id)` | Both non-null. |
| `uq_branches_company_id_name` | `branches(company_id,name)` | Both non-null. |
| `uq_employees_work_email_nonempty` | unique index `employees(company_id,lower(btrim(work_email))) WHERE btrim(work_email) <> ''` | Empty email repeats; normalized nonempty email is tenant-unique. |
| `uq_payroll_runs_id_company_id_branch_id` | `payroll_runs(id,company_id,branch_id)` | All non-null. |
| `uq_payroll_runs_branch_id_period` | `payroll_runs(branch_id,period)` | Both non-null. |
| `uq_payroll_entries_payroll_run_id_employee_id` | `payroll_entries(payroll_run_id,employee_id)` | Both non-null. |
| `uq_payslips_payroll_run_id_employee_id` | `payslips(payroll_run_id,employee_id)` | Both non-null. |
| `uq_salary_advances_id_company_id_branch_id` | `salary_advances(id,company_id,branch_id)` | All non-null. |
| `uq_advance_repayment_payroll` | unique index `advance_repayments(advance_id,payroll_run_id) WHERE payroll_run_id IS NOT NULL` | One repayment per advance/payroll pair; distinct keyed manual repayments may use null run. |
| `uq_advance_repayments_advance_id_idempotency_key` | `advance_repayments(advance_id,idempotency_key)` | Both non-null; every manual or payroll repayment request is idempotent. |
| `uq_nafis_reports_branch_id_period` | `nafis_reports(branch_id,period)` | Both non-null. |
| `uq_notifications_dedup` | `notifications(company_id,recipient_app_user_id,type,related_entity_type,related_entity_id)` | All key columns non-null. |
| `uq_leave_settings_branch_id` | `leave_settings(branch_id)` | Non-null. |
| `uq_leave_types_id_company_id_branch_id` | `leave_types(id,company_id,branch_id)` | All non-null. |
| `uq_leave_types_branch_id_code` | `leave_types(branch_id,code)` | Both non-null. |
| `uq_public_holidays_branch_id_date` | `public_holidays(branch_id,date)` | Both non-null. |
| `uq_leave_requests_id_company_id_branch_id` | `leave_requests(id,company_id,branch_id)` | All non-null. |
| `uq_leave_balances_employee_id_leave_type_id_leave_year` | `leave_balances(employee_id,leave_type_id,leave_year)` | All non-null. |
| `uq_attendance_settings_branch_id` | `attendance_settings(branch_id)` | Non-null. |
| `uq_shifts_id_company_id_branch_id` | `shifts(id,company_id,branch_id)` | All non-null. |
| `uq_shifts_branch_id_name` | `shifts(branch_id,name)` | Both non-null. |
| `uq_shifts_branch_id_code_nonempty` | unique index `shifts(branch_id,code) WHERE code IS NOT NULL AND btrim(code) <> ''` | Null/empty codes repeat. |
| `uq_attendance_records_employee_id_date` | `attendance_records(employee_id,date)` | Both non-null. |
| `uq_attendance_periods_branch_id_period` | `attendance_periods(branch_id,period)` | Both non-null. |
| `uq_regularisation_requests_id_company_id_branch_id` | `regularisation_requests(id,company_id,branch_id)` | All non-null. |
| `uq_regularisation_requests_id_employee_id_company_id_branch_id` | `regularisation_requests(id,employee_id,company_id,branch_id)` | All non-null; clock supersession target. |
| `uq_roster_assignments_employee_id_date` | `roster_assignments(employee_id,date)` | Both non-null. |
| `uq_biometric_mappings_branch_id_badge_no` | `biometric_mappings(branch_id,badge_no)` | Both non-null. |
| `uq_insurance_policies_id_company_id_branch_id` | `insurance_policies(id,company_id,branch_id)` | All non-null. |
| `uq_employee_insurance_employee_id` | `employee_insurance(employee_id)` | Non-null. |
| `uq_offboarding_checklists_employee_id` | `offboarding_checklists(employee_id)` | Non-null. |
| `uq_offboarding_checklists_id_company_id_branch_id` | `offboarding_checklists(id,company_id,branch_id)` | All non-null; scoped task parent target. |
| `uq_offboarding_task_templates_branch_id_task_name` | `offboarding_task_templates(branch_id,task_name)` | Both non-null. |
| `uq_assets_id_company_id_branch_id` | `assets(id,company_id,branch_id)` | All non-null. |
| `uq_assets_branch_id_asset_code_nonempty` | unique index `assets(branch_id,asset_code) WHERE btrim(asset_code) <> ''` | Empty codes repeat. |
| `uq_asset_assignments_open_asset` | unique index `asset_assignments(asset_id) WHERE return_date IS NULL` | One open assignment per asset. |
| `uq_appraisal_cycles_id_company_id_branch_id` | `appraisal_cycles(id,company_id,branch_id)` | All non-null. |
| `uq_appraisal_cycles_branch_id_name` | `appraisal_cycles(branch_id,name)` | Both non-null. |
| `uq_appraisals_cycle_id_employee_id` | `appraisals(cycle_id,employee_id)` | Both non-null. |
| `uq_appraisals_id_company_id_branch_id` | `appraisals(id,company_id,branch_id)` | All non-null; scoped section parent target. |
| `uq_appraisal_sections_appraisal_id_section_name` | `appraisal_sections(appraisal_id,section_name)` | Both non-null. |
| `uq_cme_requirements_employee_id_year` | `cme_requirements(employee_id,year)` | Both non-null. |
| `uq_departments_id_company_id_branch_id` | `departments(id,company_id,branch_id)` | All non-null. |
| `uq_departments_branch_id_name` | `departments(branch_id,name)` | Both non-null. |
| `uq_department_staffing_rules_branch_department_category` | `department_staffing_rules(branch_id,department,shift_category)` | All non-null. |

The next table is a coverage cross-reference only. The exact expansions, unique-object table,
explicit-index table, lifecycle table, non-lifecycle table, and status/category table are normative.
A prose summary in this cross-reference creates no unnamed constraint.

| Table | FK coverage | Unique/check coverage | Index coverage |
|---|---|---|---|
| `companies` | none | `ck_companies_nafis_quota_percent` | `ix_companies_name` |
| `branches` | `(company_id)->companies` RESTRICT | `uq_branches_id_company_id`; `uq_branches_company_id_name`; salary day 1..31 | `ix_branches_company_id` |
| `app_users` | none | exact Phase 3 unique `(identity_issuer,identity_subject)` | unique backing index only |
| `employees` | `(company_id)->companies`; `(branch_id,company_id)->branches`; `(reporting_manager_id,company_id,branch_id)->employees ON DELETE SET NULL (reporting_manager_id)`; deferred `(shift_id,company_id,branch_id)->shifts ON DELETE SET NULL (shift_id)` | preserve `uq_employees_id_company_id`; add `uq_employees_id_company_id_branch_id`; named nonnegative checks on five money fields; `ck_employees_visa_type` in `'',Employment Visa,Investor Visa,Dependent Visa,Tourist (Temp),Exempt` | `ix_employees_company_id`; `ix_employees_branch_id`; `ix_employees_active`; `ix_employees_reporting_manager_id`; partial unique normalized nonempty `work_email` |
| `user_profiles` | exact Phase 3 FKs: app user, company, and `(employee_id,company_id)->employees`, all RESTRICT | exact `ck_user_profiles_role_employee_link`; PK provides one profile per app user; employee link unique when non-null | `ix_user_profiles_company_id`; partial unique `employee_id` |
| `employee_job_history` | scoped employee RESTRICT; actor app user SET NULL | `ck_employee_job_history_change_type` in `title_change,department_change,salary_change,status_change` | `ix_employee_job_history_employee_id_changed_at` |
| `departments` | branch scope RESTRICT; `(parent_id,company_id,branch_id)->departments ON DELETE SET NULL (parent_id)`; `(head_employee_id,company_id,branch_id)->employees ON DELETE SET NULL (head_employee_id)` | unique `(branch_id,name)`; `uq_departments_id_company_id_branch_id` | `ix_departments_company_id_branch_id`; `ix_departments_parent_id` |
| `department_staffing_rules` | branch scope RESTRICT | unique `(branch_id,department,shift_category)`; `ck_department_staffing_rules_shift_category` in `morning,afternoon,night,flexible`; `min_staff>=0`; valid date range | `ix_department_staffing_rules_branch_id` |
| `payroll_runs` | branch scope RESTRICT; `run_by_app_user_id` SET NULL; submitted, approved, and rejected lifecycle actors RESTRICT | unique `(branch_id,period)` replaces nullable expression index; employee count and total nonnegative | `ix_payroll_runs_company_id`; `ix_payroll_runs_branch_id`; `ix_payroll_runs_status` |
| `payroll_entries` | scoped run RESTRICT; scoped employee RESTRICT; branch scope RESTRICT | unique `(payroll_run_id,employee_id)`; `basic_salary`, `housing_allowance`, `transport_allowance`, `allowance`, `increment`, `bonus`, `other_pay`, and `leave_deduction` each >=0; only `variable_allowance` may be negative | `ix_payroll_entries_payroll_run_id`; `ix_payroll_entries_employee_id` |
| `payslips` | scoped run RESTRICT; scoped employee RESTRICT; branch scope RESTRICT | unique `(payroll_run_id,employee_id)`; `ck_payslips_gross_pay` and `ck_payslips_net_pay` require nonnegative finalized totals | `ix_payslips_employee_id_period` |
| `payroll_approval_log` | scoped run RESTRICT; branch scope RESTRICT; actor RESTRICT | action check | `ix_payroll_approval_log_payroll_run_id_created_at` |
| `nafis_reports` | branch scope RESTRICT | unique `(branch_id,period)`; counts and percentages nonnegative, percentages <=100 | `ix_nafis_reports_branch_id_period` |
| `salary_advances` | scoped employee RESTRICT; branch scope RESTRICT | amount >0; months >0; monthly and outstanding >=0; repayment start is first day of month; status check | `ix_salary_advances_employee_id`; `ix_salary_advances_status`; `ix_salary_advances_branch_id` |
| `advance_repayments` | `(company_id)->companies` RESTRICT; `(branch_id,company_id)->branches` RESTRICT; `(advance_id,company_id,branch_id)->salary_advances` RESTRICT; `(payroll_run_id,company_id,branch_id)->payroll_runs ON DELETE SET NULL (payroll_run_id)` | `uq_advance_repayment_payroll`; `uq_advance_repayments_advance_id_idempotency_key`; `ck_advance_repayments_amount` | `ix_advance_repayments_advance_id`; `ix_advance_repayments_payroll_run_id`; `ix_advance_repayments_company_id_branch_id` |
| `expense_claims` | scoped employee RESTRICT; `(payroll_run_id,company_id,branch_id)->payroll_runs ON DELETE SET NULL (payroll_run_id)`; HR and manager lifecycle actors RESTRICT; branch scope RESTRICT | amount >0; status check | `ix_expense_claims_employee_id`; `ix_expense_claims_status`; `ix_expense_claims_branch_id` |
| `compliance_overrides` | company RESTRICT; `(branch_id,company_id)->branches ON DELETE SET NULL (branch_id)`; creator RESTRICT | override type in `payroll_sif,roster_publish` | `ix_compliance_overrides_company_id_branch_id` |
| `leave_settings` | branch scope RESTRICT | unique `branch_id`; `ck_leave_settings_weekend_definition` in `fri-sat,sat-sun`; valid Ramadan range; chain check | `ix_leave_settings_company_id_branch_id` |
| `leave_types` | branch scope RESTRICT | unique `(branch_id,code)`; day balances and notice/service values >=0 | `ix_leave_types_branch_id_active_sort` |
| `public_holidays` | branch scope RESTRICT | unique `(branch_id,date)`; year equals date year | `ix_public_holidays_branch_id_date` |
| `leave_requests` | scoped employee RESTRICT; scoped leave type RESTRICT; `(substitute_employee_id,company_id,branch_id)->employees ON DELETE SET NULL (substitute_employee_id)`; approval and manager-decision lifecycle actors RESTRICT; branch scope RESTRICT | end >= start; days >0; level >=1; status and half-day checks; `uq_leave_requests_id_company_id_branch_id` | `ix_leave_requests_employee_id`; `ix_leave_requests_status`; `ix_leave_requests_branch_id_start_date` |
| `leave_audit_log` | scoped request RESTRICT; actor RESTRICT; branch scope RESTRICT | none | `ix_leave_audit_log_request_id_created_at` |
| `leave_balances` | scoped employee RESTRICT; scoped leave type RESTRICT; branch scope RESTRICT | unique `(employee_id,leave_type_id,leave_year)`; all day values >=0 | `ix_leave_balances_branch_id_year`; `ix_leave_balances_employee_id` |
| `leave_approval_delegates` | both scoped employees RESTRICT; branch scope RESTRICT | approver differs from delegate; `to_date>=from_date` | `ix_leave_approval_delegates_approver_dates`; `ix_leave_approval_delegates_delegate_dates` |
| `attendance_settings` | branch scope RESTRICT | unique `branch_id`; nonnegative hours/minutes/money; policy check | `ix_attendance_settings_company_id_branch_id` |
| `shifts` | branch scope RESTRICT | `uq_shifts_id_company_id_branch_id`; unique `(branch_id,name)`; optional unique nonempty `(branch_id,code)`; nonnegative hours/minutes/staff; shift type/category checks | `ix_shifts_branch_id_active` |
| `shift_assignments` | scoped employee RESTRICT; scoped shift RESTRICT; branch scope RESTRICT | valid effective range | `ix_shift_assignments_employee_id_effective_from` |
| `clock_events` | scoped employee RESTRICT; `entered_by_app_user_id` SET NULL; `(superseded_by,employee_id,company_id,branch_id)->regularisation_requests ON DELETE SET NULL (superseded_by)`; branch scope RESTRICT | event check; `ck_clock_events_method` in `WEB,MOBILE,MANUAL,BIOMETRIC,EMPLOYEE_APP`; latitude/longitude ranges | `ix_clock_events_employee_id_event_time`; `ix_clock_events_event_time`; `ix_clock_events_branch_id` |
| `attendance_records` | scoped employee RESTRICT; `(shift_id,company_id,branch_id)->shifts ON DELETE SET NULL (shift_id)`; overtime and resolution lifecycle actors RESTRICT; branch scope RESTRICT | unique `(employee_id,date)`; status, OT, resolution, duration, minute, and nonnegative money checks | `ix_attendance_records_employee_id_date`; `ix_attendance_records_branch_id_date`; `ix_attendance_records_status` |
| `attendance_periods` | branch scope RESTRICT; close lifecycle actor RESTRICT | unique `(branch_id,period)`; status check; open items >=0 | `ix_attendance_periods_branch_id_period` |
| `regularisation_requests` | scoped employee RESTRICT; decision lifecycle actor RESTRICT; branch scope RESTRICT | corrected out > corrected in; status check | `ix_regularisation_requests_employee_id_attendance_date`; `ix_regularisation_requests_status` |
| `attendance_audit_log` | scoped employee RESTRICT; actor RESTRICT; branch scope RESTRICT | none | `ix_attendance_audit_log_employee_id_date` |
| `roster_assignments` | scoped employee RESTRICT; scoped shift RESTRICT; branch scope RESTRICT | unique `(employee_id,date)`; hours >=0 | `ix_roster_assignments_employee_id`; `ix_roster_assignments_date`; `ix_roster_assignments_branch_id` |
| `shift_swap_requests` | both scoped employees RESTRICT; decision lifecycle actor RESTRICT; branch scope RESTRICT | requester differs from target; status check | `ix_shift_swap_requests_branch_id`; `ix_shift_swap_requests_status`; `ix_shift_swap_requests_requester_employee_id` |
| `biometric_mappings` | scoped employee RESTRICT; branch scope RESTRICT | unique `(branch_id,badge_no)` | `ix_biometric_mappings_employee_id` |
| `employee_documents` | scoped employee RESTRICT; branch scope RESTRICT | file size >=0; status and submitter checks | `ix_employee_documents_employee_id`; `ix_employee_documents_branch_id_expiry_date` |
| `insurance_policies` | branch scope RESTRICT | annual premium >=0 | `ix_insurance_policies_branch_id_renewal_date` |
| `employee_insurance` | scoped employee RESTRICT; `(policy_id,company_id,branch_id)->insurance_policies ON DELETE SET NULL (policy_id)`; branch scope RESTRICT | unique `employee_id`; valid date range | `ix_employee_insurance_branch_id_expiry_date` |
| `insurance_dependants` | scoped employee RESTRICT; branch scope RESTRICT | none | `ix_insurance_dependants_employee_id` |
| `notifications` | company RESTRICT; `(branch_id,company_id)->branches ON DELETE SET NULL (branch_id)`; `(recipient_app_user_id,company_id)->user_profiles(app_user_id,company_id)` RESTRICT; `(created_by_app_user_id,company_id)->user_profiles(app_user_id,company_id) ON DELETE SET NULL (created_by_app_user_id)` | unique `(company_id,recipient_app_user_id,type,related_entity_type,related_entity_id)` | `ix_notifications_recipient_app_user_id`; partial `ix_notifications_unread`; `ix_notifications_company_id_branch_id` |
| `employee_contracts` | scoped employee RESTRICT; `renewed_by_app_user_id` SET NULL; branch scope RESTRICT | `ck_employee_contracts_action`; `ck_employee_contracts_contract_type`; `ck_employee_contracts_dates` | `ix_employee_contracts_employee_id`; `ix_employee_contracts_branch_id_end_date` |
| `offboarding_checklists` | scoped employee RESTRICT; branch scope RESTRICT | unique `employee_id`; status and visa status checks | `ix_offboarding_checklists_branch_id_status` |
| `offboarding_tasks` | branch scope RESTRICT; scoped checklist RESTRICT; completed actor RESTRICT | `ck_offboarding_tasks_completed_fields` | `ix_offboarding_tasks_checklist_id_sort_order`; `ix_offboarding_tasks_company_id_branch_id` |
| `offboarding_task_templates` | branch scope RESTRICT | unique `(branch_id,task_name)` | `ix_offboarding_task_templates_branch_id` |
| `assets` | branch scope RESTRICT | status check; purchase cost >=0 | `ix_assets_branch_id_status`; optional unique nonempty `(branch_id,asset_code)` |
| `asset_assignments` | scoped asset RESTRICT; scoped employee RESTRICT; nullable non-lifecycle `assigned_by_app_user_id` SET NULL; branch scope RESTRICT | return date >= assigned date | `ix_asset_assignments_asset_id`; `ix_asset_assignments_employee_id`; partial unique open assignment per asset |
| `training_records` | scoped employee RESTRICT; branch scope RESTRICT | cost >=0; dates valid; status check; duration >=0 | `ix_training_records_employee_id`; `ix_training_records_branch_id_status` |
| `certifications` | scoped employee RESTRICT; branch scope RESTRICT | dates valid; status check | `ix_certifications_employee_id`; `ix_certifications_branch_id_expiry_date` |
| `appraisal_cycles` | branch scope RESTRICT | review dates valid; status check; unique `(branch_id,name)` | `ix_appraisal_cycles_branch_id_status` |
| `appraisals` | scoped cycle RESTRICT; scoped employee RESTRICT; actor RESTRICT; branch scope RESTRICT | unique `(cycle_id,employee_id)`; ratings 1..5; status check | `ix_appraisals_cycle_id`; `ix_appraisals_employee_id`; `ix_appraisals_branch_id_status` |
| `appraisal_sections` | branch scope RESTRICT; scoped appraisal RESTRICT | exact rating/weight checks; `uq_appraisal_sections_appraisal_id_section_name` | `ix_appraisal_sections_appraisal_id_sort_order`; `ix_appraisal_sections_company_id_branch_id` |
| `cme_requirements` | scoped employee RESTRICT; branch scope RESTRICT | unique `(employee_id,year)`; hours >=0 | `ix_cme_requirements_employee_id`; `ix_cme_requirements_year` |
| `incident_reports` | branch scope RESTRICT; `(reported_by_id,company_id,branch_id)->employees ON DELETE SET NULL (reported_by_id)`; `(involved_emp_id,company_id,branch_id)->employees ON DELETE SET NULL (involved_emp_id)`; close lifecycle actor RESTRICT | type, severity, and status checks | `ix_incident_reports_branch_id_incident_date`; `ix_incident_reports_status`; `ix_incident_reports_department`; `ix_incident_reports_severity` |
| `letter_requests` | scoped employee RESTRICT; branch scope RESTRICT | request kind and status checks; custom subject/details length checks conditional on kind | `ix_letter_requests_employee_id`; `ix_letter_requests_branch_id_status` |

### Exact explicit indexes

Unique objects are listed above. These are the remaining explicit indexes; omitted tables have no
additional index beyond PK and unique backing indexes.

| Table | Exact indexes |
|---|---|
| `companies` | `ix_companies_name (name)` |
| `branches` | `ix_branches_company_id (company_id)` |
| `employees` | `ix_employees_company_id (company_id)`; `ix_employees_branch_id (branch_id)`; `ix_employees_active (active)`; `ix_employees_reporting_manager_id (reporting_manager_id)` |
| `user_profiles` | `ix_user_profiles_company_id (company_id)` |
| `employee_job_history` | `ix_employee_job_history_employee_id_changed_at (employee_id,changed_at DESC)` |
| `departments` | `ix_departments_company_id_branch_id (company_id,branch_id)`; `ix_departments_parent_id (parent_id)` |
| `department_staffing_rules` | `ix_department_staffing_rules_branch_id (branch_id)` |
| `payroll_runs` | `ix_payroll_runs_company_id (company_id)`; `ix_payroll_runs_branch_id (branch_id)`; `ix_payroll_runs_status (status)` |
| `payroll_entries` | `ix_payroll_entries_payroll_run_id (payroll_run_id)`; `ix_payroll_entries_employee_id (employee_id)` |
| `payslips` | `ix_payslips_employee_id_period (employee_id,period DESC)` |
| `payroll_approval_log` | `ix_payroll_approval_log_payroll_run_id_created_at (payroll_run_id,created_at DESC)` |
| `nafis_reports` | `ix_nafis_reports_branch_id_period (branch_id,period DESC)` |
| `salary_advances` | `ix_salary_advances_employee_id (employee_id)`; `ix_salary_advances_status (status)`; `ix_salary_advances_branch_id (branch_id)` |
| `advance_repayments` | `ix_advance_repayments_advance_id (advance_id)`; `ix_advance_repayments_payroll_run_id (payroll_run_id)`; `ix_advance_repayments_company_id_branch_id (company_id,branch_id)` |
| `expense_claims` | `ix_expense_claims_employee_id (employee_id)`; `ix_expense_claims_status (status)`; `ix_expense_claims_branch_id (branch_id)` |
| `compliance_overrides` | `ix_compliance_overrides_company_id_branch_id (company_id,branch_id)` |
| `leave_settings` | `ix_leave_settings_company_id_branch_id (company_id,branch_id)` |
| `leave_types` | `ix_leave_types_branch_id_active_sort (branch_id,is_active,sort_order)` |
| `public_holidays` | `ix_public_holidays_branch_id_date (branch_id,date)` |
| `leave_requests` | `ix_leave_requests_employee_id (employee_id)`; `ix_leave_requests_status (status)`; `ix_leave_requests_branch_id_start_date (branch_id,start_date)` |
| `leave_audit_log` | `ix_leave_audit_log_request_id_created_at (leave_request_id,created_at)` |
| `leave_balances` | `ix_leave_balances_branch_id_year (branch_id,leave_year)`; `ix_leave_balances_employee_id (employee_id)` |
| `leave_approval_delegates` | `ix_leave_approval_delegates_approver_dates (approver_employee_id,from_date,to_date)`; `ix_leave_approval_delegates_delegate_dates (delegate_employee_id,from_date,to_date)` |
| `attendance_settings` | `ix_attendance_settings_company_id_branch_id (company_id,branch_id)` |
| `shifts` | `ix_shifts_branch_id_active (branch_id,is_active)` |
| `shift_assignments` | `ix_shift_assignments_employee_id_effective_from (employee_id,effective_from DESC)` |
| `clock_events` | `ix_clock_events_employee_id_event_time (employee_id,event_time)`; `ix_clock_events_event_time (event_time)`; `ix_clock_events_branch_id (branch_id)` |
| `attendance_records` | `ix_attendance_records_employee_id_date (employee_id,date)`; `ix_attendance_records_branch_id_date (branch_id,date)`; `ix_attendance_records_status (status)` |
| `attendance_periods` | `ix_attendance_periods_branch_id_period (branch_id,period)` |
| `regularisation_requests` | `ix_regularisation_requests_employee_id_attendance_date (employee_id,attendance_date)`; `ix_regularisation_requests_status (status)` |
| `attendance_audit_log` | `ix_attendance_audit_log_employee_id_date (employee_id,attendance_date)` |
| `roster_assignments` | `ix_roster_assignments_employee_id (employee_id)`; `ix_roster_assignments_date (date)`; `ix_roster_assignments_branch_id (branch_id)` |
| `shift_swap_requests` | `ix_shift_swap_requests_branch_id (branch_id)`; `ix_shift_swap_requests_status (status)`; `ix_shift_swap_requests_requester_employee_id (requester_employee_id)` |
| `biometric_mappings` | `ix_biometric_mappings_employee_id (employee_id)` |
| `employee_documents` | `ix_employee_documents_employee_id (employee_id)`; `ix_employee_documents_branch_id_expiry_date (branch_id,expiry_date)` |
| `insurance_policies` | `ix_insurance_policies_branch_id_renewal_date (branch_id,renewal_date)` |
| `employee_insurance` | `ix_employee_insurance_branch_id_expiry_date (branch_id,expiry_date)` |
| `insurance_dependants` | `ix_insurance_dependants_employee_id (employee_id)` |
| `notifications` | `ix_notifications_recipient_app_user_id (recipient_app_user_id)`; `ix_notifications_unread (recipient_app_user_id,created_at DESC) WHERE read_at IS NULL`; `ix_notifications_company_id_branch_id (company_id,branch_id)` |
| `employee_contracts` | `ix_employee_contracts_employee_id (employee_id)`; `ix_employee_contracts_branch_id_end_date (branch_id,end_date)` |
| `offboarding_checklists` | `ix_offboarding_checklists_branch_id_status (branch_id,status)` |
| `offboarding_tasks` | `ix_offboarding_tasks_checklist_id_sort_order (checklist_id,sort_order)`; `ix_offboarding_tasks_company_id_branch_id (company_id,branch_id)` |
| `offboarding_task_templates` | `ix_offboarding_task_templates_branch_id (branch_id)` |
| `assets` | `ix_assets_branch_id_status (branch_id,status)` |
| `asset_assignments` | `ix_asset_assignments_asset_id (asset_id)`; `ix_asset_assignments_employee_id (employee_id)` |
| `training_records` | `ix_training_records_employee_id (employee_id)`; `ix_training_records_branch_id_status (branch_id,status)` |
| `certifications` | `ix_certifications_employee_id (employee_id)`; `ix_certifications_branch_id_expiry_date (branch_id,expiry_date)` |
| `appraisal_cycles` | `ix_appraisal_cycles_branch_id_status (branch_id,status)` |
| `appraisals` | `ix_appraisals_cycle_id (cycle_id)`; `ix_appraisals_employee_id (employee_id)`; `ix_appraisals_branch_id_status (branch_id,status)` |
| `appraisal_sections` | `ix_appraisal_sections_appraisal_id_sort_order (appraisal_id,sort_order)`; `ix_appraisal_sections_company_id_branch_id (company_id,branch_id)` |
| `cme_requirements` | `ix_cme_requirements_employee_id (employee_id)`; `ix_cme_requirements_year (year)` |
| `incident_reports` | `ix_incident_reports_branch_id_incident_date (branch_id,incident_date)`; `ix_incident_reports_status (status)`; `ix_incident_reports_department (department)`; `ix_incident_reports_severity (severity)` |
| `letter_requests` | `ix_letter_requests_employee_id (employee_id)`; `ix_letter_requests_branch_id_status (branch_id,status)` |

### Shift-assignment overlap invariant

No extension or exclusion constraint is added. FastAPI must enforce non-overlap in a locked
transaction. For a proposed `[effective_from,effective_to]`, where null `effective_to` means
infinity, lock the employee row first and then all that employee's `shift_assignments` rows in
ascending `(effective_from,id)` order. Reject when an existing row satisfies
`existing.effective_from <= coalesce(proposed.effective_to,'infinity'::date)` and
`proposed.effective_from <= coalesce(existing.effective_to,'infinity'::date)`. Insert or update only
after the locked recheck. Concurrent requests for the same employee serialize on the employee row.
FastAPI returns deterministic conflict code `shift_assignment_overlap` and commits no partial
change. Cross-company or cross-branch requests fail before overlap evaluation.

### Nullability tightening

The empty-baseline decision makes these nullable legacy additions safe to declare `NOT NULL` from
creation. There is no data backfill in Phase 4.

| Target columns | Reliable default and reason |
|---|---|
| `leave_types.probation_eligible` | `true`; `028` supplied the default and the empty baseline has no old rows. |
| `salary_advances.repayment_start_month` | First day of current month; later API writes an explicit schedule month. |
| `shifts.color`, `shifts.shift_category` | `#6366f1` and `morning`; both additions supplied defaults. |
| `roster_assignments.co_hours` | `0`; `026` supplied the default. |
| `biometric_mappings.device_name`, `biometric_mappings.created_at` | `Default` and `now()`; `027` supplied both defaults. |
| `training_records.is_cme` | `false`; `047` supplied the default. |
| `training_records.storage_path`, `training_records.file_name`, `certifications.storage_path`, `certifications.file_name` | `''`; `054` supplied defaults. |
| `cme_requirements.notes`, `cme_requirements.created_at`, `cme_requirements.updated_at` | `''`, `now()`, `now()`; `047` supplied defaults. |
| `incident_reports.location`, `department`, `immediate_action`, `root_cause`, `corrective_action`, `notes`, `created_at`, `updated_at` | Empty text or `now()` exactly as supplied by `048`. |
| Every new required `company_id` and `branch_id` | No default. FastAPI must derive and provide scope; omission fails. |

### Retention and delete behavior

No target FK uses `ON DELETE CASCADE`. History and financial records use `RESTRICT`; optional links
use the exact column-list `SET NULL` actions catalogued above. In particular, payroll entries and
payslips restrict payroll-run deletion; approval logs restrict payroll runs; leave and attendance
audit logs restrict their request or employee parents; asset assignments restrict assets and
employees; offboarding tasks restrict checklists; appraisals restrict cycles and employees; and
appraisal sections restrict appraisals.

FastAPI may explicitly purge an eligible draft or unactioned aggregate only in one transaction,
after locking the parent and checking that it has no finalization, approval, payment, audit, or
history use. It must delete eligible non-history children explicitly before the parent. Finalized or
historical parents are archived or retained, not cascaded. Payroll snapshots, used payroll entries,
approval logs, audit logs, assignment history, appraisals, and appraisal sections have no ordinary
hard-delete path.

### Exact lifecycle checks

All actor FKs named below use `ON DELETE RESTRICT`. That choice keeps a later identity deletion from
invalidating history. Disable the account instead. Exact expressions are:

| Exact check | Expression |
|---|---|
| `ck_payroll_runs_submission_fields` | `approval_status <> 'pending_approval' OR (submitted_by_app_user_id IS NOT NULL AND submitted_for_approval_at IS NOT NULL)` |
| `ck_payroll_runs_approval_fields` | `approval_status <> 'approved' OR (approved_by_app_user_id IS NOT NULL AND approved_at IS NOT NULL)` |
| `ck_payroll_runs_rejection_fields` | `(rejected_at IS NULL AND rejected_by_app_user_id IS NULL AND rejection_reason = '') OR (rejected_at IS NOT NULL AND rejected_by_app_user_id IS NOT NULL AND btrim(rejection_reason) <> '')` |
| `ck_payroll_runs_generated_fields` | `status <> 'generated' OR (approval_status = 'approved' AND approved_by_app_user_id IS NOT NULL AND approved_at IS NOT NULL)` |
| `ck_payroll_runs_wps_submitted_at` | `wps_status NOT IN ('submitted','confirmed','partial_rejection') OR wps_submitted_at IS NOT NULL` |
| `ck_payroll_runs_wps_confirmed_at` | `wps_status NOT IN ('confirmed','partial_rejection') OR wps_confirmed_at IS NOT NULL` |
| `ck_payroll_entries_wps_rejection_reason` | `wps_payment_status <> 'rejected' OR btrim(wps_rejection_reason) <> ''` |
| `ck_leave_requests_approved_fields` | `status <> 'Approved' OR (approved_by_app_user_id IS NOT NULL AND approved_at IS NOT NULL)` |
| `ck_leave_requests_manager_approved_fields` | `status <> 'ManagerApproved' OR (manager_approved_by_app_user_id IS NOT NULL AND manager_approved_at IS NOT NULL)` |
| `ck_leave_requests_rejected_fields` | `status <> 'Rejected' OR (approved_by_app_user_id IS NOT NULL AND approved_at IS NOT NULL AND btrim(rejection_reason) <> '')` |
| `ck_leave_requests_manager_rejected_fields` | `status <> 'ManagerRejected' OR (manager_approved_by_app_user_id IS NOT NULL AND manager_approved_at IS NOT NULL AND btrim(manager_rejection_reason) <> '')` |
| `ck_regularisation_requests_decision_fields` | `status = 'Pending' OR (approved_by_app_user_id IS NOT NULL AND approved_at IS NOT NULL)` |
| `ck_regularisation_requests_rejection_fields` | `status <> 'Rejected' OR btrim(rejection_reason) <> ''` |
| `ck_shift_swap_requests_approved_fields` | `status <> 'approved' OR (admin_approved_by_app_user_id IS NOT NULL AND admin_approved_at IS NOT NULL)` |
| `ck_shift_swap_requests_rejected_fields` | `status <> 'rejected' OR (admin_approved_by_app_user_id IS NOT NULL AND admin_approved_at IS NOT NULL AND btrim(rejection_reason) <> '')` |
| `ck_expense_claims_manager_approved_fields` | `status <> 'manager_approved' OR (manager_approved_by_app_user_id IS NOT NULL AND manager_approved_at IS NOT NULL)` |
| `ck_expense_claims_manager_rejected_fields` | `status <> 'manager_rejected' OR (manager_approved_by_app_user_id IS NOT NULL AND manager_approved_at IS NOT NULL AND btrim(manager_rejection_reason) <> '')` |
| `ck_expense_claims_hr_decision_fields` | `status NOT IN ('approved','paid','rejected') OR (approved_by_app_user_id IS NOT NULL AND approved_at IS NOT NULL)` |
| `ck_expense_claims_rejection_fields` | `status <> 'rejected' OR btrim(rejection_reason) <> ''` |
| `ck_employee_documents_review_fields` | `status = 'pending_verification' OR (reviewed_by_app_user_id IS NOT NULL AND reviewed_at IS NOT NULL)` |
| `ck_employee_documents_rejection_fields` | `status <> 'rejected' OR btrim(rejection_reason) <> ''` |
| `ck_certifications_review_fields` | `status = 'pending_review' OR (reviewed_by_app_user_id IS NOT NULL AND reviewed_at IS NOT NULL)` |
| `ck_certifications_rejection_fields` | `status <> 'rejected' OR btrim(notes) <> ''` |
| `ck_appraisal_cycles_closed_fields` | `status <> 'closed' OR (closed_by_app_user_id IS NOT NULL AND closed_at IS NOT NULL)` |
| `ck_appraisals_review_fields` | `status = 'pending' OR (reviewed_by_app_user_id IS NOT NULL AND reviewed_at IS NOT NULL)` |
| `ck_attendance_periods_closed_fields` | `status <> 'closed' OR (closed_by_app_user_id IS NOT NULL AND closed_at IS NOT NULL)` |
| `ck_attendance_records_overtime_actor` | `NOT overtime_approved OR overtime_approved_by_app_user_id IS NOT NULL` |
| `ck_attendance_records_resolution_actor` | `resolution_type = '' OR resolved_by_app_user_id IS NOT NULL` |
| `ck_offboarding_checklists_completed_fields` | `status <> 'completed' OR (completed_by_app_user_id IS NOT NULL AND completed_at IS NOT NULL)` |
| `ck_offboarding_tasks_completed_fields` | `NOT completed OR (completed_by_app_user_id IS NOT NULL AND completed_at IS NOT NULL)` |
| `ck_incident_reports_closed_fields` | `status <> 'closed' OR (closed_by_app_user_id IS NOT NULL AND closed_date IS NOT NULL)` |
| `ck_letter_requests_completed_fields` | `status <> 'completed' OR (actioned_by_app_user_id IS NOT NULL AND actioned_at IS NOT NULL AND completed_at IS NOT NULL)` |
| `ck_letter_requests_rejected_fields` | `status <> 'rejected' OR (actioned_by_app_user_id IS NOT NULL AND actioned_at IS NOT NULL AND btrim(rejection_reason) <> '')` |
| `ck_training_records_completed_fields` | `status <> 'completed' OR end_date IS NOT NULL` |

Statuses without a rejected, closed, completed, approved, or final state do not get a fabricated
lifecycle check. `salary_advances.cancelled` covers both withdrawal and rejection and lacks a stable
decision timestamp in the current contract, so only its nonempty rejection reason rule is enforced:
`ck_salary_advances_cancelled_reason: status <> 'cancelled' OR coalesce(btrim(rejection_reason),'') <> ''`.

### Exact non-lifecycle checks

Every money-catalogue `Check` entry other than "signed, bounded by type" creates
`ck_<table>_<column>` with the exact expression shown there. The business status/category table
creates the exact `IN` checks under the naming rule above. The remaining checks are:

| Exact check | Expression |
|---|---|
| `ck_companies_nafis_quota_percent` | `nafis_quota_percent BETWEEN 0 AND 100` |
| `ck_branches_default_salary_day` | `default_salary_day IS NULL OR default_salary_day BETWEEN 1 AND 31` |
| `ck_user_profiles_role_employee_link` | `(role = 'admin' AND employee_id IS NULL) OR (role IN ('manager','employee') AND employee_id IS NOT NULL)` |
| `ck_department_staffing_rules_min_staff` | `min_staff >= 0` |
| `ck_department_staffing_rules_effective_dates` | `effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from` |
| `ck_payroll_runs_employee_count` | `employee_count >= 0` |
| `ck_nafis_reports_counts` | `total_headcount >= 0 AND emirati_count >= 0 AND emirati_count <= total_headcount` |
| `ck_nafis_reports_percentages` | `ratio_percent BETWEEN 0 AND 100 AND required_percent BETWEEN 0 AND 100` |
| `ck_salary_advances_repayment_months` | `repayment_months > 0` |
| `ck_salary_advances_repayment_start_month` | `repayment_start_month = date_trunc('month',repayment_start_month)::date` |
| `ck_leave_settings_ramadan_dates` | `ramadan_end IS NULL OR ramadan_start IS NULL OR ramadan_end >= ramadan_start` |
| `ck_leave_settings_approval_chain` | `approval_chain IN ('1-level','2-level')` |
| `ck_leave_types_nonnegative_rules` | `min_notice_days >= 0 AND annual_entitlement_days >= 0 AND carry_forward_max_days >= 0 AND min_service_months >= 0` |
| `ck_public_holidays_year` | `year = extract(year FROM date)::integer` |
| `ck_leave_requests_dates` | `end_date >= start_date` |
| `ck_leave_requests_days_requested` | `days_requested > 0` |
| `ck_leave_requests_approval_level` | `approval_level_required >= 1` |
| `ck_leave_requests_half_day` | `(NOT is_half_day AND half_day_period IS NULL) OR (is_half_day AND half_day_period IN ('AM','PM'))` |
| `ck_leave_balances_nonnegative_days` | `entitled_days >= 0 AND accrued_days >= 0 AND used_days >= 0 AND pending_days >= 0 AND carried_forward >= 0 AND remaining_days >= 0 AND sick_full_pay_used >= 0 AND sick_half_pay_used >= 0 AND sick_unpaid_used >= 0` |
| `ck_leave_approval_delegates_distinct` | `approver_employee_id <> delegate_employee_id` |
| `ck_leave_approval_delegates_dates` | `to_date >= from_date` |
| `ck_attendance_settings_nonnegative` | `default_hours_per_day >= 0 AND late_grace_minutes >= 0 AND early_departure_grace_minutes >= 0 AND max_daily_overtime_hours >= 0 AND regularisation_max_days_per_month >= 0 AND regularisation_window_days >= 0` |
| `ck_shifts_nonnegative` | `break_minutes >= 0 AND expected_hours >= 0 AND late_grace_minutes >= 0 AND early_departure_grace_minutes >= 0 AND (min_hours_flexible IS NULL OR min_hours_flexible >= 0) AND min_staff >= 0` |
| `ck_shift_assignments_dates` | `effective_to IS NULL OR effective_to >= effective_from` |
| `ck_clock_events_latitude` | `gps_lat IS NULL OR gps_lat BETWEEN -90 AND 90` |
| `ck_clock_events_longitude` | `gps_lng IS NULL OR gps_lng BETWEEN -180 AND 180` |
| `ck_attendance_records_nonnegative` | `total_hours >= 0 AND late_minutes >= 0 AND early_departure_minutes >= 0 AND overtime_hours >= 0` |
| `ck_attendance_periods_open_items` | `open_items >= 0` |
| `ck_regularisation_requests_clock_order` | `correct_clock_out > correct_clock_in` |
| `ck_roster_assignments_hours` | `(planned_hours IS NULL OR planned_hours >= 0) AND (actual_hours IS NULL OR actual_hours >= 0) AND co_hours >= 0` |
| `ck_shift_swap_requests_distinct_employees` | `requester_employee_id <> target_employee_id` |
| `ck_employee_documents_file_size` | `file_size >= 0` |
| `ck_employee_insurance_dates` | `expiry_date IS NULL OR effective_date IS NULL OR expiry_date >= effective_date` |
| `ck_employee_contracts_dates` | `end_date IS NULL OR start_date IS NULL OR end_date >= start_date` |
| `ck_asset_assignments_dates` | `return_date IS NULL OR return_date >= assigned_date` |
| `ck_training_records_dates` | `end_date IS NULL OR start_date IS NULL OR end_date >= start_date` |
| `ck_training_records_duration_hours` | `duration_hours IS NULL OR duration_hours >= 0` |
| `ck_certifications_dates` | `expiry_date IS NULL OR issued_date IS NULL OR expiry_date >= issued_date` |
| `ck_appraisal_cycles_dates` | `review_to >= review_from` |
| `ck_appraisals_overall_rating` | `overall_rating IS NULL OR overall_rating BETWEEN 1 AND 5` |
| `ck_appraisals_self_rating` | `self_rating IS NULL OR self_rating BETWEEN 1 AND 5` |
| `ck_appraisal_sections_weight` | `weight > 0` |
| `ck_appraisal_sections_rating` | `rating IS NULL OR rating BETWEEN 1 AND 5` |
| `ck_appraisal_sections_self_rating` | `self_rating IS NULL OR self_rating BETWEEN 1 AND 5` |
| `ck_cme_requirements_required_hours` | `required_hours >= 0` |
| `ck_letter_requests_custom_lengths` | `request_kind <> 'custom' OR (char_length(btrim(letter_type)) BETWEEN 3 AND 120 AND char_length(btrim(purpose)) BETWEEN 5 AND 2000)` |

## Money catalogue

The 29 persisted scalar money columns are accounted for individually. `>=0` means zero is a valid
stored amount. `>0` means a row has no business meaning at zero. `payroll_entries.variable_allowance`
is the sole signed fixed scalar. JSON adjustment amounts are separate validated values, not fixed
scalar columns.

| # | Column | Target | Check | Reason |
|---:|---|---|---|---|
| 1 | `employees.basic_salary` | `numeric(12,2)` | `>=0` | Contractual base pay. |
| 2 | `employees.allowance` | `numeric(12,2)` | `>=0` | Fixed allowance. |
| 3 | `employees.housing_allowance` | `numeric(12,2)` | `>=0` | Fixed allowance. |
| 4 | `employees.transport_allowance` | `numeric(12,2)` | `>=0` | Fixed allowance. |
| 5 | `employees.other_allowances` | `numeric(12,2)` | `>=0` | Fixed aggregate allowance. |
| 6 | `payroll_runs.total_disbursed` | `numeric(14,2)` | `>=0` | Run aggregate needs more headroom than one employee amount. |
| 7 | `payroll_entries.basic_salary` | `numeric(12,2)` | `>=0` | Payroll snapshot base pay. |
| 8 | `payroll_entries.housing_allowance` | `numeric(12,2)` | `>=0` | Payroll snapshot allowance. |
| 9 | `payroll_entries.transport_allowance` | `numeric(12,2)` | `>=0` | Payroll snapshot allowance. |
| 10 | `payroll_entries.allowance` | `numeric(12,2)` | `>=0` | Payroll snapshot allowance. |
| 11 | `payroll_entries.increment` | `numeric(12,2)` | `>=0` | Fixed increment cannot be negative. |
| 12 | `payroll_entries.bonus` | `numeric(12,2)` | `>=0` | Fixed bonus cannot be negative. |
| 13 | `payroll_entries.other_pay` | `numeric(12,2)` | `>=0` | Fixed other pay cannot be negative. |
| 14 | `payroll_entries.leave_deduction` | `numeric(12,2)` | `>=0` | Renamed from `du_cost`; it stores leave deduction. |
| 15 | `payroll_entries.variable_allowance` | `numeric(12,2)` | signed, bounded by type | This is the only fixed scalar money column that may be negative. |
| 16 | `payslips.gross_pay` | `numeric(12,2)` | `>=0` | Immutable displayed total. |
| 17 | `payslips.net_pay` | `numeric(12,2)` | `>=0` | Immutable displayed total. |
| 18 | `attendance_settings.late_deduction_amount` | `numeric(12,2)` | `>=0` | Widened from 10,2; configured deduction cannot be negative. |
| 19 | `attendance_records.overtime_amount` | `numeric(12,2)` | `>=0` | Widened from 10,2; approved earning. |
| 20 | `attendance_records.absence_deduction` | `numeric(12,2)` | `>=0` | Widened from 10,2; deduction magnitude. |
| 21 | `attendance_records.late_deduction` | `numeric(12,2)` | `>=0` | Widened from 10,2; deduction magnitude. |
| 22 | `insurance_policies.annual_premium` | `numeric(12,2)` | `>=0` | Annual policy cost. |
| 23 | `salary_advances.amount` | `numeric(12,2)` | `>0` | A zero advance is invalid. |
| 24 | `salary_advances.monthly_deduction` | `numeric(12,2)` | `>=0` | Pending advances can start at zero. |
| 25 | `salary_advances.outstanding_balance` | `numeric(12,2)` | `>=0` | Balance cannot cross below zero. |
| 26 | `advance_repayments.amount` | `numeric(12,2)` | `>0` | A repayment row must reduce debt. |
| 27 | `expense_claims.amount` | `numeric(12,2)` | `>0` | Resolves 014 `>0` versus 046 `>=0` in favor of the active form and UI. |
| 28 | `assets.purchase_cost` | `numeric(12,2)` nullable | `>=0` when present | Unknown cost remains null; a known cost cannot be negative. |
| 29 | `training_records.cost` | `numeric(12,2)` | `>=0` | Free training is valid. |

`record_advance_repayment.p_amount` is a function argument, not a persisted column. Adding
`advance_repayments.idempotency_key` does not add money. The persisted money-column count therefore
remains 29, not 30.

`payroll_entries.additional_allowances`, `payroll_entries.deductions`, and monetary values inside
`payslips.data_snapshot` remain JSONB. FastAPI must reject non-decimal, non-finite, more-than-two-
decimal, or out-of-range amounts. Additional-allowance amounts must be nonnegative. Deduction
amounts must be nonnegative magnitudes. The API, not a signed JSON number, determines whether an
item adds to earnings or reduces pay.

## Business status and closed category checks

Each row below becomes a named `ck_<table>_<name>` check. These values follow active producers,
including their existing casing. No unrelated global normalization is planned.

| Column | Exact values | Default | Resolution |
|---|---|---|---|
| `employees.employment_status` | `Active`, `Probation`, `On Leave`, `Terminated` | `Active` | Active archive and employee producers. |
| `employees.contract_type` | `Limited`, `Unlimited` | `Unlimited` | Active employee and contract UI. |
| `employees.visa_type` | `''`, `Employment Visa`, `Investor Visa`, `Dependent Visa`, `Tourist (Temp)`, `Exempt` | `''` | Named `ck_employees_visa_type`; `Tourist (Temp)` is canonical and a future converter maps legacy `Tourist`. |
| `employee_job_history.change_type` | `title_change`, `department_change`, `salary_change`, `status_change` | none | Named `ck_employee_job_history_change_type`; normalize legacy title-case labels in any future converter. |
| `payroll_runs.status` | `draft`, `generated` | `draft` | Run lifecycle producer. |
| `payroll_runs.approval_status` | `draft`, `pending_approval`, `approved` | `draft` | Approval producer. |
| `payroll_runs.wps_status` | `draft`, `sif_generated`, `submitted`, `confirmed`, `partial_rejection`, `failed` | `draft` | WPS producer. |
| `payroll_entries.wps_payment_status` | `pending`, `paid`, `rejected` | `pending` | WPS entry producer. |
| `salary_advances.status` | `pending`, `active`, `settled`, `cancelled` | `active` | Existing check and active actions. |
| `expense_claims.status` | `pending`, `manager_approved`, `manager_rejected`, `approved`, `paid`, `rejected` | `pending` | Includes migration 030 producers. |
| `leave_requests.status` | `Pending`, `ManagerApproved`, `ManagerRejected`, `Approved`, `Rejected`, `Cancelled` | `Pending` | Existing case-sensitive workflow. |
| `leave_settings.weekend_definition` | `fri-sat`, `sat-sun` | `fri-sat` | Named `ck_leave_settings_weekend_definition`; Friday-Saturday stays the default. |
| `attendance_records.status` | `PRESENT`, `ABSENT`, `ON_LEAVE`, `PUBLIC_HOLIDAY`, `WEEKEND`, `LATE`, `EARLY_DEPARTURE`, `HALF_DAY`, `OVERTIME`, `UNEXPLAINED_ABSENCE`, `PRESENT_REMOTE`, `MISSING_CLOCK_OUT` | `ABSENT` | Attendance engine output. |
| `attendance_records.resolution_type` | `''`, `LEAVE_LINKED`, `UNAUTHORISED`, `WFH` | `''` | Existing resolution producer. |
| `attendance_records.overtime_type` | `STANDARD`, `REST_DAY_NO_SUB`, `REST_DAY_WITH_SUB`, `NIGHT_SHIFT` | null | Existing calculator categories. |
| `attendance_periods.status` | `open`, `closed` | `open` | Period close workflow. |
| `regularisation_requests.status` | `Pending`, `Approved`, `Rejected` | `Pending` | Existing correction workflow. |
| `shift_swap_requests.status` | `pending`, `approved`, `rejected`, `cancelled` | `pending` | `cancelled` is produced by the direct update path and was already in the 007 check. |
| `employee_documents.status` | `pending_verification`, `verified`, `rejected` | `verified` | HR-created rows start verified; employee rows start pending. |
| `employee_documents.submitted_by` | `hr`, `employee` | `hr` | This is provenance, not app role. |
| `training_records.status` | `planned`, `in_progress`, `completed`, `cancelled` | `planned` | Active producer. |
| `certifications.status` | `pending_review`, `verified`, `rejected` | `verified` | HR and employee producers. |
| `appraisal_cycles.status` | `draft`, `active`, `closed` | `draft` | Owner approved omission of the stale read-only `open` value. |
| `appraisals.status` | `pending`, `reviewed`, `calibrated` | `pending` | Owner approved omission of SQL-only `self_reviewed`. |
| `letter_requests.request_kind` | `letter`, `custom` | `letter` | Migration 055 final form. |
| `letter_requests.status` | `pending`, `completed`, `rejected` | `pending` | Active producer. |
| `assets.status` | `available`, `assigned`, `under_repair`, `retired`, `lost` | `available` | Active producer. |
| `offboarding_checklists.status` | `in_progress`, `completed` | `in_progress` | Active producer. |
| `offboarding_checklists.visa_cancellation_status` | `not_started`, `initiated`, `submitted_gdrfa`, `cancelled` | `not_started` | Active producer. |
| `employee_contracts.action` | `new`, `renewed`, `converted`, `not_renewed` | `new` | Active producer. |
| `employee_contracts.contract_type` | `Limited`, `Unlimited` | `Limited` | Named `ck_employee_contracts_contract_type`; exact values match employee contract vocabulary. |
| `incident_reports.status` | `open`, `investigating`, `closed` | `open` | Active producer. |
| `incident_reports.severity` | `low`, `moderate`, `high`, `critical` | `low` | Active producer. |
| `incident_reports.incident_type` | `patient_safety`, `medication_error`, `injury`, `needlestick`, `infection`, `equipment`, `near_miss`, `workplace`, `other` | `other` | Active incident form. |
| `payroll_approval_log.action` | `submitted`, `approved`, `rejected`, `recalled` | none | Approval writer. |
| `shifts.shift_type` | `fixed`, `flexible`, `split`, `overnight` | `fixed` | Base shift form. |
| `shifts.shift_category` | `morning`, `afternoon`, `night`, `flexible`, `split` | `morning` | Includes active shift fixtures beyond the 033 staffing-rule subset. |
| `department_staffing_rules.shift_category` | `morning`, `afternoon`, `night`, `flexible` | none | Named `ck_department_staffing_rules_shift_category`; `split` is a shift template category, not an approved staffing-rule category. |
| `attendance_settings.late_deduction_policy` | `none`, `per_minute`, `per_occurrence` | `none` | Base settings producer. |
| `clock_events.event_type` | `CLOCK_IN`, `CLOCK_OUT` | none | Active direct event writer. |
| `clock_events.method` | `WEB`, `MOBILE`, `MANUAL`, `BIOMETRIC`, `EMPLOYEE_APP` | `WEB` | Named `ck_clock_events_method`; a future converter maps legacy `BIOMETRIC_API` to `BIOMETRIC`. |

Other category-like text fields remain text without a closed check where users enter values or the
source never established a complete active set. Examples are notification type, leave type code,
document type, insurance relationship, employee gender, and expense category. FastAPI
may validate a UI list without pretending it is a complete database state machine.

## Function reconciliation

Exactly 29 legacy function names appear once below. The target keeps three business functions and
one canonical trigger helper. It moves 22 names to FastAPI, omits two names outright, and merges
`handle_updated_at` into `set_updated_at`. `PG` means retained in PostgreSQL. `API` means FastAPI
owns the transaction and authorization. Every retained function is internal, has a pinned
`search_path`, has execution revoked from `PUBLIC`, and is callable only through reviewed runtime
grants. It must not read `auth.*` or Supabase roles.

| # | Legacy name | Source or version chain | Disposition |
|---:|---|---|---|
| 1 | `handle_updated_at` | `supabase_schema.sql` | Merged and superseded by canonical `set_updated_at`; not an additional outright omission. |
| 2 | `set_updated_at` | `046` | PG, canonical trigger helper. |
| 3 | `link_employee_account` | recovered Auth mapping | API; Keycloak/application provisioning replaces email-based linking. |
| 4 | `employee_submit_leave_request` | recovered 9-argument version -> warnings 10-argument overload | API; one warning-aware request contract, no overload. |
| 5 | `employee_cancel_leave_request` | recovered employee RLS | API. |
| 6 | `employee_record_clock_event` | recovered defective version -> `023` type fix | Omit as unused; direct clock-event API replaces it. |
| 7 | `employee_submit_regularisation` | recovered employee RLS | API. |
| 8 | `employee_request_advance` | `005` | API. |
| 9 | `manager_approve_leave` | `006` | API. |
| 10 | `manager_reject_leave` | `006` | API. |
| 11 | `admin_set_employee_portal_role` | `006` scoped version -> unsafe `034` replacement | API; enforce approved tenant and employee scope. |
| 12 | `admin_get_employee_portal_role` | `006` | API query. |
| 13 | `employee_get_my_roster` | `007` | API query. |
| 14 | `employee_get_colleagues` | `007` | API query, company and branch scoped. |
| 15 | `employee_request_shift_swap` | `007` | API. |
| 16 | `employee_submit_expense` | `014` | API. |
| 17 | `employee_submit_document` | `024` | API plus storage adapter transaction/reconciliation. |
| 18 | `employee_request_letter` | `025` | API. |
| 19 | `manager_get_expense_queue` | `030` | API query. |
| 20 | `manager_approve_expense` | `030` | API. |
| 21 | `manager_reject_expense` | `030` | API. |
| 22 | `get_manager_employee_id` | `035` | Omit; it exists only to break recursive Supabase RLS. |
| 23 | `replace_payroll_entries` | `044` | PG, retained after removing caller-controlled ownership. |
| 24 | `record_advance_repayment` | unsafe `044` -> locked/idempotent `050` | PG, final locked and idempotent behavior. |
| 25 | `employee_update_contact` | `044`, replacing policies from `041/043` | API with field allowlist. |
| 26 | `employee_cancel_advance` | broken table return in `049` -> boolean `051` | API; final behavior permits only caller-owned pending requests. |
| 27 | `employee_delete_expense` | `051` | API. |
| 28 | `admin_execute_shift_swap` | `052` | PG, retained atomic operation. |
| 29 | `employee_request_custom` | `055` | API. |

`manager_get_leave_queue` is undefined in every SQL source. It is not added to the 29-name count.
Phase 5 specifies it as a FastAPI query over direct reports, active delegates, leave requests,
balances, probation, and warning data.

### Final target database functions

| Function | Final signature and behavior |
|---|---|
| `set_updated_at` | `set_updated_at() returns trigger`; before update, sets `NEW.updated_at=clock_timestamp()` and returns `NEW`. |
| `replace_payroll_entries` | `replace_payroll_entries(p_payroll_run_id uuid, p_entries jsonb) returns void`. Require a JSON array. Each object accepts exactly `employee_id`, `basic_salary`, `housing_allowance`, `transport_allowance`, `allowance`, `increment`, `bonus`, `other_pay`, `leave_deduction`, `variable_allowance`, `additional_allowances`, `deductions`, `excluded`, `wps_payment_status`, and `wps_rejection_reason`. Reject unknown keys. Require `employee_id`; default missing scalar money to `0`, arrays to `[]`, `excluded` to false, WPS status to `pending`, and WPS reason to `''`. Reject duplicate employees. Lock the run `FOR UPDATE`; require draft run and draft approval state; derive company and branch from the run; require every employee in that scope. Validate every scalar as finite decimal with scale <=2 and absolute value <=9999999999.99. Require all fixed scalar money except `variable_allowance` to be >=0. Validate each JSON adjustment object and its sign rules in FastAPI before the call. Delete and replace only draft entries in one transaction. Unknown, malformed, out-of-range, or wrong-scope input aborts the whole call. |
| `record_advance_repayment` | `record_advance_repayment(p_advance_id uuid, p_payroll_run_id uuid, p_idempotency_key uuid, p_amount numeric, p_paid_date date default current_date) returns jsonb`. Require non-null advance and idempotency UUIDs. Normalize the date after applying its default and reject null; normalize amount without rounding, then require finite numeric input, scale <=2, and `0 < p_amount <= 9999999999.99`. Do not rely on argument typmod. Lock the advance row `FOR UPDATE`. Before checking current status or balance, select the repayment by `(p_advance_id,p_idempotency_key)`. Return `alreadyRecorded=true` only when its `advance_id`, `payroll_run_id IS NOT DISTINCT FROM p_payroll_run_id`, normalized `amount`, `paid_date`, `company_id`, and `branch_id` exactly match the locked advance and request. Otherwise raise `advance_repayment_idempotency_conflict` without mutation. If no key row exists and a payroll run was supplied, look up `(advance_id,payroll_run_id)`; any existing row with another key or different normalized request raises `advance_repayment_payroll_conflict`. Only after both replay checks pass require the advance to be active with positive balance, validate the optional run has the locked advance's company and branch, and reject `p_amount > outstanding_balance` with `advance_repayment_exceeds_outstanding`. Insert the exact amount with locked scope and request key, decrement once, settle at zero, and return `alreadyRecorded=false`. Manual and payroll retries use the same persisted UUID mechanism; a retry after rollback inserts normally because no key row committed. |
| `admin_execute_shift_swap` | `admin_execute_shift_swap(p_swap_id uuid, p_actor_app_user_id uuid) returns boolean`. Require `(p_actor_app_user_id,swap.company_id)` to resolve through `user_profiles` to role `admin` and join an `app_users.status='active'` row before mutation. Lock the swap and both source roster rows in ascending UUID order. Require pending state, distinct employees, same company and branch for request, employees, shifts, and roster rows. Reject missing requester assignment. For two-way swaps reject null target assignment, same employee/date destination, or any third row where `(employee_id,target_date)` or `(target_employee_id,requester_date)` would collide. For one-way coverage reject any existing target row on requester date. Apply all roster changes and approval fields atomically. Return deterministic not-found, stale-state, scope, missing-assignment, same-day, and destination-conflict errors. FastAPI authorizes the operation before the internal call; the function repeats profile/company validation. |

## Trigger reconciliation

All 19 named legacy triggers appear once. Overlap is resolved by one target name per covered table.

| # | Legacy trigger | Source | Target decision |
|---:|---|---|---|
| 1 | `companies_updated_at` | root schema | Replace with `trg_companies_set_updated_at`. |
| 2 | `employees_updated_at` | root schema | Omit superseded by target canonical trigger. |
| 3 | `payroll_runs_updated_at` | root schema | Omit superseded by target canonical trigger. |
| 4 | `payroll_entries_updated_at` | root schema | Replace with `trg_payroll_entries_set_updated_at`. |
| 5 | `leave_settings_updated_at` | leave root | Replace with canonical trigger. |
| 6 | `leave_types_updated_at` | leave root | Replace with canonical trigger. |
| 7 | `leave_requests_updated_at` | leave root | Omit superseded by target canonical trigger. |
| 8 | `leave_balances_updated_at` | leave root | Replace with canonical trigger. |
| 9 | `attendance_settings_updated_at` | attendance root | Replace with canonical trigger. |
| 10 | `shifts_updated_at` | attendance root | Replace with canonical trigger. |
| 11 | `attendance_records_updated_at` | attendance root | Omit superseded by target canonical trigger. |
| 12 | `trg_employees_updated_at` | `046` | Rename to canonical target convention. |
| 13 | `trg_payroll_runs_updated_at` | `046` | Rename to canonical target convention. |
| 14 | `trg_advances_updated_at` | `046` | Rename to canonical target convention. |
| 15 | `trg_leave_requests_updated_at` | `046` | Rename to canonical target convention. |
| 16 | `trg_attendance_updated_at` | `046` | Rename to canonical target convention. |
| 17 | `trg_expenses_updated_at` | `046` | Rename to canonical target convention. |
| 18 | `trg_cme_requirements_updated_at` | `047` | Rename to canonical target convention. |
| 19 | `trg_incidents_updated_at` | `048` | Rename to canonical target convention. |

Every target trigger is `BEFORE UPDATE FOR EACH ROW EXECUTE FUNCTION set_updated_at()`. Exact target
coverage follows. "New target decision" means no legacy trigger existed on that table even though
the final table has `updated_at`.

| Exact target trigger | Table | Source and reason |
|---|---|---|
| `trg_companies_set_updated_at` | `companies` | Replaces root trigger. |
| `trg_branches_set_updated_at` | `branches` | New target decision; branch settings need the same concurrency timestamp as legacy company rows. |
| `trg_employees_set_updated_at` | `employees` | Resolves root/046 overlap. |
| `trg_payroll_runs_set_updated_at` | `payroll_runs` | Resolves root/046 overlap. |
| `trg_payroll_entries_set_updated_at` | `payroll_entries` | Replaces root trigger. |
| `trg_salary_advances_set_updated_at` | `salary_advances` | Renames 046 trigger. |
| `trg_leave_settings_set_updated_at` | `leave_settings` | Replaces leave-root trigger. |
| `trg_leave_types_set_updated_at` | `leave_types` | Replaces leave-root trigger. |
| `trg_leave_requests_set_updated_at` | `leave_requests` | Resolves leave-root/046 overlap. |
| `trg_leave_balances_set_updated_at` | `leave_balances` | Replaces leave-root trigger. |
| `trg_attendance_settings_set_updated_at` | `attendance_settings` | Replaces attendance-root trigger. |
| `trg_shifts_set_updated_at` | `shifts` | Replaces attendance-root trigger. |
| `trg_attendance_records_set_updated_at` | `attendance_records` | Resolves attendance-root/046 overlap. |
| `trg_roster_assignments_set_updated_at` | `roster_assignments` | New target decision; publication and swap mutations must advance optimistic-lock state. |
| `trg_shift_swap_requests_set_updated_at` | `shift_swap_requests` | New target decision; request decisions must advance optimistic-lock state. |
| `trg_expense_claims_set_updated_at` | `expense_claims` | Renames 046 trigger. |
| `trg_appraisals_set_updated_at` | `appraisals` | New target decision; section-driven review transitions must advance parent optimistic-lock state. |
| `trg_cme_requirements_set_updated_at` | `cme_requirements` | Renames 047 trigger. |
| `trg_incident_reports_set_updated_at` | `incident_reports` | Renames 048 trigger. |

There are 19 final target triggers. The count matching the 19 legacy names is coincidental; four
target triggers are new decisions and four legacy duplicate triggers disappear.

## Legacy RLS policy reconciliation

Phase 4 creates no new policy. PostgreSQL RLS remains the approved defense in depth, but Phase 5
will generate policies from the approved permission matrix and transaction-local request context.
Legacy Supabase policies are not copied. `Replace in Phase 5` means the capability needs a reviewed
replacement. `Omit superseded` means another row or API rule covers it and the named legacy policy
must not return.

There are 119 distinct legacy policy identities by `(table, name)`. The SQL has more `CREATE POLICY`
statements because six leave policies, one company-read policy, and two storage policies are
dropped and recreated. `043` only conditionally repeats the `041` employee-contact definition when
the policy is absent; it does not recreate an existing policy. This reconciles Phase 0's accurate
"over 100" description without mistaking statement occurrences for distinct policies.

### Root and core policy identities

| Table | Policy name | Source or replacement chain | Decision |
|---|---|---|---|
| `companies` | `Users can manage their own company` | root schema | Replace in Phase 5. |
| `employees` | `Users can manage their own employees` | root schema | Replace in Phase 5. |
| `employee_job_history` | `Users can manage their own job history` | root schema + existing-db duplicate | Replace in Phase 5. |
| `payroll_runs` | `Users can manage their own payroll runs` | root schema | Replace in Phase 5. |
| `payroll_entries` | `Users can manage their own payroll entries` | root schema | Replace in Phase 5. |
| `user_profiles` | `user_profiles: read own` | recovered Auth mapping | Replace in Phase 5. |
| `user_profiles` | `user_profiles: insert own` | recovered Auth mapping | Omit superseded by provisioning API. |
| `employees` | `employees: read own via auth_user_id` | recovered Auth mapping | Replace in Phase 5. |
| `leave_types` | `employees: read leave types` | recovered employee RLS | Replace in Phase 5. |
| `public_holidays` | `employees: read public holidays` | recovered employee RLS | Replace in Phase 5. |
| `leave_settings` | `employees: read leave settings` | recovered employee RLS | Replace in Phase 5. |
| `leave_requests` | `employees: read own leave requests` | recovered employee RLS | Replace in Phase 5. |
| `leave_balances` | `employees: read own leave balances` | recovered employee RLS | Replace in Phase 5. |
| `payroll_entries` | `employees: read own payroll entries` | recovered employee RLS | Omit superseded by payslip/API contract. |
| `payroll_runs` | `employees: read payroll runs for own entries` | recovered employee RLS | Omit superseded by payslip/API contract. |
| `attendance_records` | `employees: read own attendance records` | recovered employee RLS | Replace in Phase 5. |
| `clock_events` | `employees: read own clock events` | recovered employee RLS | Replace in Phase 5. |
| `regularisation_requests` | `employees: read own regularisation requests` | recovered employee RLS | Replace in Phase 5. |
| `leave_settings` | `Users manage their own leave settings` | leave root -> leave RLS fix | Replace in Phase 5. |
| `leave_types` | `Users manage their own leave types` | leave root -> leave RLS fix | Replace in Phase 5. |
| `public_holidays` | `Users manage their own public holidays` | leave root -> leave RLS fix | Replace in Phase 5. |
| `leave_requests` | `Users manage their own leave requests` | leave root -> leave RLS fix | Replace in Phase 5. |
| `leave_audit_log` | `Users view their own leave audit log` | leave root -> leave RLS fix | Replace in Phase 5. |
| `leave_balances` | `Users manage their own leave balances` | leave root -> leave RLS fix | Replace in Phase 5. |
| `attendance_settings` | `Users manage their own attendance settings` | attendance root | Replace in Phase 5. |
| `shifts` | `Users manage their own shifts` | attendance root | Replace in Phase 5. |
| `shift_assignments` | `Users manage their own shift assignments` | attendance root | Replace in Phase 5. |
| `clock_events` | `Users manage their own clock events` | attendance root | Replace in Phase 5. |
| `attendance_records` | `Users manage their own attendance records` | attendance root | Replace in Phase 5. |
| `attendance_periods` | `Users manage their own attendance periods` | attendance root | Replace in Phase 5. |
| `regularisation_requests` | `Users manage their own regularisation requests` | attendance root | Replace in Phase 5. |
| `attendance_audit_log` | `Users view their own attendance audit log` | attendance root | Replace in Phase 5. |
| `companies` | `employees: read own company` | employee-company root -> grants root replacement | Replace in Phase 5. |
| `payslips` | `payslips: admin read own` | payslip root | Omit superseded by owner policy replacement. |
| `payslips` | `payslips: employee read own` | payslip root | Replace in Phase 5. |
| `payslips` | `payslips: admin insert` | payslip root | Omit superseded by owner policy replacement. |
| `payslips` | `payslips: admin update` | payslip root | Omit superseded; finalized snapshots are API-controlled. |

### Numbered feature policy identities

| Table | Policy names | Source | Decision |
|---|---|---|---|
| `nafis_reports` | `nafis_reports_owner` | `001` | Replace in Phase 5. |
| `employee_documents` | `employee_documents_admin`; `employee_documents_self_read`; `employee_documents_self_update_pending` | `002`, `024` | Replace in Phase 5. |
| `insurance_policies` | `insurance_policies_admin` | `003` | Replace in Phase 5. |
| `employee_insurance` | `employee_insurance_admin`; `employee_insurance_self` | `003` | Replace in Phase 5. |
| `insurance_dependants` | `insurance_dependants_admin` | `003` | Replace in Phase 5. |
| `notifications` | `notifications_select`; `notifications_insert`; `notifications_update`; `notifications_delete` | `004` | Replace in Phase 5. |
| `salary_advances` | `salary_advances_admin`; `salary_advances_employee_read` | `005` | Replace in Phase 5. |
| `advance_repayments` | `advance_repayments_admin`; `advance_repayments_employee_read` | `005` | Replace in Phase 5. |
| `leave_approval_delegates` | `leave_approval_delegates_admin`; `leave_approval_delegates_actor_read` | `006` | Replace in Phase 5. |
| `roster_assignments` | `roster_assignments_admin_all`; `roster_assignments_employee_read` | `007` | Replace in Phase 5. |
| `shift_swap_requests` | `shift_swap_requests_admin_all`; `shift_swap_requests_employee_read` | `007` | Replace in Phase 5. |
| `employee_contracts` | `employee_contracts_admin` | `012` | Replace in Phase 5. |
| `offboarding_checklists` | `offboarding_checklists_admin` | `013` | Replace in Phase 5. |
| `offboarding_tasks` | `offboarding_tasks_admin` | `013` | Replace in Phase 5. |
| `offboarding_task_templates` | `offboarding_task_templates_admin` | `013` | Replace in Phase 5. |
| `expense_claims` | `expense_claims_admin`; `expense_claims_employee_read` | `014` | Replace in Phase 5. |
| `assets` | `assets_admin`; `assets_employee_read` | `016` | Replace in Phase 5. |
| `asset_assignments` | `asset_assignments_admin`; `asset_assignments_employee_read` | `016` | Replace in Phase 5. |
| `payroll_approval_log` | `payroll_approval_log_admin` | `017` | Replace in Phase 5. |
| `training_records` | `training_records_admin`; `training_records_employee_read`; `training_records_manager_all`; `training_records_employee_insert`; `training_records_employee_update` | `019`, `040` | Replace in Phase 5. |
| `certifications` | `certifications_admin`; `certifications_employee_read`; `certifications_manager_all`; `certifications_employee_insert`; `certifications_employee_update` | `019`, `040`, `042` | Replace in Phase 5. |
| `clock_events` | `Admins view their employees' clock events` | `022` | Omit superseded by branch owner policy replacement. |
| `letter_requests` | `letter_requests_admin`; `letter_requests_employee_read` | `025` | Replace in Phase 5. |
| `biometric_mappings` | `biometric_mappings_admin` | `027` | Replace in Phase 5. |
| `departments` | `departments_admin` | `029` | Replace in Phase 5. |
| `appraisal_cycles` | `appraisal_cycles_admin`; `appraisal_cycles_manager_read` | `031`, `033` | Replace in Phase 5. |
| `appraisals` | `appraisals_admin`; `appraisals_employee_read`; `appraisals_manager_read`; `appraisals_manager_update` | `031`, `033`, `038` | Replace in Phase 5. |
| `appraisal_sections` | `appraisal_sections_admin`; `appraisal_sections_employee_read`; `appraisal_sections_manager_read`; `appraisal_sections_manager_update` | `031`, `033` | Replace in Phase 5. |
| `compliance_overrides` | `compliance_overrides_admin` | `033` | Replace in Phase 5. |
| `department_staffing_rules` | `dept_staffing_admin` | `033` | Replace in Phase 5. |
| `employees` | `employees_manager_read` | `035` | Replace in Phase 5. |
| `employees` | `employees_self_update_contact` | `041`; `043` conditionally repeats the same definition without dropping/recreating it; `044` drops it | Omit superseded by field-limited FastAPI action. |
| `leave_requests` | `leave_requests_manager_read` | `037` | Replace in Phase 5. |
| `leave_balances` | `leave_balances_manager_read` | `037` | Replace in Phase 5. |
| `leave_types` | `leave_types_authenticated_read` | `037` | Omit superseded; it was cross-tenant. |
| `shifts` | `shifts_admin_all` | `039` | Omit superseded by branch owner policy replacement. |
| `shifts` | `shifts_authenticated_read` | `039` | Omit superseded; it was cross-tenant. |
| `cme_requirements` | `cme_requirements_admin_all` | `047` | Replace in Phase 5. |
| `incident_reports` | `incident_reports_admin_all` | `048` | Replace in Phase 5. |

### Baseline 045 policy identities

| Table | Policy name | Decision |
|---|---|---|
| `companies` | `companies_owner_all` | Replace in Phase 5; supersedes the root owner name. |
| `user_profiles` | `user_profiles_owner_all` | Replace in Phase 5. |
| `employees` | `employees_owner_all` | Replace in Phase 5; supersedes the root owner name. |
| `employees` | `employees_self_read` | Replace in Phase 5. |
| `payroll_runs` | `payroll_runs_owner_all` | Replace in Phase 5; supersedes the root owner name. |
| `payroll_entries` | `payroll_entries_owner_all` | Replace in Phase 5; supersedes the root owner name. |
| `payslips` | `payslips_owner_all` | Replace in Phase 5; supersedes three admin policies. |
| `payslips` | `payslips_employee_read` | Omit superseded by the earlier same-capability employee policy row. |
| `attendance_records` | `attendance_records_owner_all` | Replace in Phase 5; supersedes the root owner name. |
| `attendance_records` | `attendance_records_employee_read` | Omit superseded by recovered self-read capability. |
| `clock_events` | `clock_events_owner_all` | Replace in Phase 5; supersedes root owner/admin-read capability. |

### Storage object policies

| Table | Policy name | Source chain | Decision |
|---|---|---|---|
| `storage.objects` | `employee_documents_employee_upload` | `024` -> dropped/recreated `043` | Omit superseded. FastAPI and the private storage adapter authorize upload. |
| `storage.objects` | `employee_documents_employee_read_own` | `024` -> dropped/recreated `043` | Omit superseded. FastAPI authorizes short-lived downloads. |

The comments describing `expense_receipts_admin` never execute `CREATE POLICY`, so it is a storage
reference, not a named SQL policy. It is recorded below rather than inflating the policy count.

## Grants and storage references

This phase implements no grants. Later revisions must keep the Phase 3 principle: the migration
identity owns schema objects; `workloop_runtime` gets explicit per-table and per-function privileges;
no `PUBLIC`, default privilege, `GRANT ... ON ALL TABLES`, `authenticated`, `anon`, or `service_role`
grant survives. Phase 4D must review reads and writes table by table, revoke function execution from
`PUBLIC`, and avoid granting direct browser access.

Legacy grant sources are the leave RLS fix, root grants file, most numbered feature files, blanket
service-role grants, blanket authenticated grants in `045`, and function EXECUTE grants. They are
all historical evidence only. The Phase 3 `SELECT` grants on `companies`, `employees`, `app_users`,
and `user_profiles` remain untouched until an append-only revision changes them.

Storage references reconcile as follows:

| Legacy reference | Sources | Target decision |
|---|---|---|
| `employee-documents` bucket | `002`, `024`, `043`, leave attachment and training consumers | Private provider-neutral object storage. Metadata remains in domain tables. Do not create a PostgreSQL storage table or Supabase policy. |
| `expense-receipts` bucket and commented `expense_receipts_admin` | `014` and expense consumer | Same private storage adapter. The commented policy is not executable SQL. |
| `storage.objects`, `storage.foldername`, signed URLs | `024`, `043`, frontend | Remove from database schema. FastAPI chooses object keys and authorizes short-lived downloads. |
| Certification path mismatch | `024` policy versus training `{uid}/certs/{employee}` path | Replace both with server-generated opaque keys tied to metadata IDs. Do not preserve Auth UUID path ownership. |

No seed design or fixture generation belongs in this document.

## Data and backfill classification

The owner approved an empty portable baseline and synthetic data only. Phase 4 will not import or
convert a legacy dump. The project has no real production records. The statements below classify
legacy operations and fix rules for a possible future converter; they do not authorize that
converter, a backfill, or fixture work in this subphase.

| Legacy operation | Source | Classification and target treatment |
|---|---|---|
| Recreate/add existing columns | root schema and `supabase_migration_existing_db.sql` | Existing-database compatibility DDL, not a target backfill. Catalogue only the final column once. |
| Employee and payroll company assignment to first legacy company | `021` | Do not copy. A future converter must use an explicit company-to-branch map and fail on unresolved rows. |
| Roster/swap company assignment from employee | `053` | Future conversion maps legacy `company_id` to target `branch_id`, derives tenant company through the branch, and fails on mismatch. |
| `leave_types.probation_eligible` | `028` | A future converter preserves true and maps `ANNUAL`, `HAJJ`, and `STUDY` to false. |
| `salary_advances.repayment_start_month` | `050` | A future converter uses the first day of `disbursed_date` month, else `created_at` month, then requires non-null. |
| `letter_requests.request_kind` | `055` | A future converter maps legacy rows to `letter` and fails on values outside `letter,custom`. |
| `roster_assignments.planned_hours` | `026` | A future converter fills null from the linked shift's expected hours. |
| Actor text/email to app identity | many roots and numbered files | A future converter needs an explicit Auth-to-app-user map. It leaves nullable historical actor fields null when no verified mapping exists and never matches mutable email automatically. |
| `payroll_runs.payment_date` text to date | root schema | A future converter parses strict ISO dates, maps empty string to null, and quarantines and fails on every invalid nonempty value. |
| `clock_events.method` | attendance root and biometric producers | A future converter maps `BIOMETRIC_API` to canonical `BIOMETRIC`; other approved values remain unchanged. |
| `employees.visa_type` | root schema | A future converter maps `Tourist` to canonical `Tourist (Temp)` and fails on other values outside the named check. |
| `employee_job_history.change_type` | duplicate root definitions | A future converter maps `Title Change`, `Department Change`, `Salary Change`, and `Status Change` to their lowercase snake-case values and fails on unknown nonempty values. |
| `payroll_entries.du_cost` | root and active converter | A future converter copies it to `leave_deduction`. The target never creates `du_cost`. |
| `supabase_reset_test_data.sql` | root | Destructive developer utility, not migration, fixture, seed, or backfill. Never include it in Alembic. |

## Supersession decision log

| Issue | Final decision |
|---|---|
| Duplicate `employee_job_history` | One target table using the identical final column set; both root definitions are source evidence. |
| Job-history change type | Use `title_change`, `department_change`, `salary_change`, and `status_change`; map the four legacy title-case labels only in a future converter. |
| Existing-db duplicate columns | Keep the base/final definition once. Conditional add blocks are compatibility history, not extra columns. |
| Company user uniqueness removal | Legacy `companies.user_id` and both possible unique names are removed. Tenant ownership uses `user_profiles.company_id`; branches are unique by company and name. |
| Role check `034` versus Phase 3 | Keep native `app_role` and the exact Phase 3 `role_employee_link` check. Do not recreate the text role check. |
| Leave submit overloads | FastAPI exposes one warning-aware operation. Neither PostgreSQL overload survives. |
| Clock event replacement | The `023` UUID fix is the final legacy version, but the unused function is omitted. `entered_by_app_user_id` removes the original type ambiguity. |
| Unsafe admin portal role replacement | Do not retain either function. FastAPI checks tenant, employee, activation, and allowed target role. The unsafe `034` scope loss is rejected. |
| Repayment `044` to `050` | Start from `050` locking and payroll uniqueness, then apply the approved target rule: persist a caller UUID request key for every repayment, compare retries before state checks, reject mismatched retries, and reject rather than cap an amount above locked outstanding balance. |
| Cancel advance `049` to `051` | FastAPI implements the boolean `051` behavior. The broken table-return shape is not preserved. |
| Contact policy `041/043` to `044` | Omit the broad row UPDATE policy. FastAPI accepts only the four contact fields. |
| Storage policy `024` to `043` | Treat as one duplicate chain per policy. Omit both in favor of FastAPI plus private object storage. |
| `request_kind` | Require `letter,custom`, default and backfill to `letter`. |
| `repayment_start_month` | Require first-of-month date after deterministic backfill. |
| `probation_eligible` | Require boolean, default true, and preserve the three-code false backfill. |
| Company ID backfills | Never assign "first company." Create parent company and branch mappings explicitly; fail unresolved or cross-scope records. |
| `min_staff` despite replacement comment | Keep `shifts.min_staff` for current compatibility and keep department staffing rules. Later API logic prefers department rules when enabled. |
| Staffing flexible category | `department_staffing_rules.shift_category` accepts `flexible` in addition to `morning`, `afternoon`, and `night`. |
| Weekend definitions | Default to `fri-sat` and accept `fri-sat` or `sat-sun` through a named check. |
| Biometric clock method | Store `BIOMETRIC`; map legacy `BIOMETRIC_API` only in a future converter. |
| Visa wording | Store `Tourist (Temp)`; map legacy `Tourist` only in a future converter. |
| Duplicate timestamp helpers/triggers | Keep `set_updated_at` only and one canonical trigger per covered table. |
| Auth identity conversion | Remove all `auth.users`, `auth.uid()`, `auth.email()`, `auth.role()`, and `employees.auth_user_id` dependencies. Keep Phase 3 issuer/subject mapping and profile links. |
| Stale `doc_type` | Omit. The target column is `document_type`. |
| Stale payroll `month/year` | Omit. The target column is `period`. |
| Stale `eid_expiry` | Omit. The target column is `emirates_id_expiry`. |
| Payroll `du_cost` | Rename to `leave_deduction`; current persisted and converter behavior proves that meaning. FastAPI may expose a separate calculated direct deduction without overloading this column. |
| Finalized payslip net pay | Require `payslips.net_pay >= 0`; finalization must fail before persisting a negative net amount. |
| Appraisal stale states | Omit `appraisals.self_reviewed` and appraisal-cycle `open`; neither has an active producer. |
| Phase 4 data source | Build an empty portable baseline and use synthetic data only. Do not design or run legacy dump conversion in Phase 4. |
| Future invalid payroll dates | A future converter quarantines and fails on invalid nonempty payment dates; it does not preserve invalid text. |
| Repayment scope | Add required `company_id` and `branch_id`; enforce composite same-scope advance and optional payroll-run FKs. |
| Repayment idempotency and amount | Require persisted `idempotency_key`, unique `(advance_id,idempotency_key)`, retain the partial advance/payroll unique index, and reject requests above locked outstanding balance. |
| Notification identity and dedup | Recipient and nullable creator reference `(app_user_id,company_id)` in `user_profiles`; dedup uses company, recipient, type, entity type, and entity ID. |
| Redundant leave fields | Remove request and balance `leave_type_code` and audit `employee_id`; derive all three through scoped FKs. |
| Clock supersession | Composite FK includes superseding request, employee, company, and branch, so a clock event cannot cite another employee's request. |
| Shift assignment overlap | FastAPI locks employee and assignment rows, rechecks closed-date-range intersection, and returns `shift_assignment_overlap`; no extension or exclusion constraint. |
| Signed payroll scalars | Only `payroll_entries.variable_allowance` may be negative. Other fixed scalar earnings and deductions are nonnegative. |
| Retention | No target FK cascades. FastAPI may transactionally purge only eligible draft/unactioned aggregates; finalized and historical records remain or are archived. |
| Lifecycle evidence | Exact named checks require actors, timestamps, and reasons for applicable final or decision states; those actor FKs use RESTRICT. |
| Nullable legacy additions | Tighten the approved defaulted additions at empty-baseline creation as listed in the nullability table. |
| New updated-at triggers | Add canonical triggers to branches, roster assignments, shift swaps, and appraisals for settings, publication/swap, decision, and parent-review concurrency. |
| Direct-write child scope | Add required company and branch to `offboarding_tasks` and `appraisal_sections`; enforce same-scope composite checklist/appraisal FKs. |
| Branch/location duplicate fields | Legal-group fields stay on `companies`; payroll/location fields move to `branches`; employee-specific work location remains on `employees` as an employment attribute. |
| `regularisation_requests` time mismatch | Use `timestamptz` because the active producer submits ISO instants and original values are instants. Shift template clock faces remain `time`. |

## Coverage matrix

These compact lists are machine-checkable by splitting on commas. Each legacy table appears once;
`app_users` and `branches` then bring the target to 54.

| Object class | Count | One-entry coverage |
|---|---:|---|
| Legacy tables | 52 | `advance_repayments, appraisal_cycles, appraisal_sections, appraisals, asset_assignments, assets, attendance_audit_log, attendance_periods, attendance_records, attendance_settings, biometric_mappings, certifications, clock_events, cme_requirements, companies, compliance_overrides, department_staffing_rules, departments, employee_contracts, employee_documents, employee_insurance, employee_job_history, employees, expense_claims, insurance_dependants, insurance_policies, incident_reports, leave_approval_delegates, leave_audit_log, leave_balances, leave_requests, leave_settings, leave_types, letter_requests, nafis_reports, notifications, offboarding_checklists, offboarding_task_templates, offboarding_tasks, payroll_approval_log, payroll_entries, payroll_runs, payslips, public_holidays, regularisation_requests, roster_assignments, salary_advances, shift_assignments, shift_swap_requests, shifts, training_records, user_profiles` |
| Added target tables | 2 | `app_users, branches` |
| Target tables | 54 | Catalogue rows 1 through 54. |
| Legacy function names | 29 | `admin_execute_shift_swap, admin_get_employee_portal_role, admin_set_employee_portal_role, employee_cancel_advance, employee_cancel_leave_request, employee_delete_expense, employee_get_colleagues, employee_get_my_roster, employee_record_clock_event, employee_request_advance, employee_request_custom, employee_request_letter, employee_request_shift_swap, employee_submit_document, employee_submit_expense, employee_submit_leave_request, employee_submit_regularisation, employee_update_contact, get_manager_employee_id, handle_updated_at, link_employee_account, manager_approve_expense, manager_approve_leave, manager_get_expense_queue, manager_reject_expense, manager_reject_leave, record_advance_repayment, replace_payroll_entries, set_updated_at` |
| Undefined call outside function count | 1 | `manager_get_leave_queue` |
| Legacy named triggers | 19 | `attendance_records_updated_at, attendance_settings_updated_at, companies_updated_at, employees_updated_at, leave_balances_updated_at, leave_requests_updated_at, leave_settings_updated_at, leave_types_updated_at, payroll_entries_updated_at, payroll_runs_updated_at, shifts_updated_at, trg_advances_updated_at, trg_attendance_updated_at, trg_cme_requirements_updated_at, trg_employees_updated_at, trg_expenses_updated_at, trg_incidents_updated_at, trg_leave_requests_updated_at, trg_payroll_runs_updated_at` |
| Target canonical triggers | 19 | Exact target trigger table above; four are new target decisions. |
| Legacy policy identities | 119 | 37 root/core rows, 69 numbered-feature identities, 11 baseline-045 identities, and 2 `storage.objects` identities. Grouped rows above expand by semicolon-delimited name. |
| Scalar money columns | 29 | Money catalogue rows 1 through 29. |
| Target database functions | 4 | Three business functions: `admin_execute_shift_swap, record_advance_repayment, replace_payroll_entries`; one trigger helper: `set_updated_at`. |
| Function disposition arithmetic | 29 | `4 retained + 22 FastAPI + 2 omitted outright + 1 merged/superseded = 29`; `handle_updated_at` is the merged item. |
| Repayment idempotency mechanisms | 2 | Required unique request key for every repayment plus retained partial advance/payroll uniqueness. |
| Direct-write children with added scope | 2 | `offboarding_tasks, appraisal_sections`. |

Policy arithmetic is `37 + 69 + 11 + 2 = 119`. Recreated SQL statements stay in their identity's
source chain and do not add another policy. This is why the result is auditable and still agrees with
Phase 0's "over 100" wording.

## Open decisions

There are zero open design decisions. The owner answered former OD-1 through OD-3 on 2026-09-01:

- Omit `appraisals.self_reviewed` and appraisal-cycle `open`.
- Build an empty portable baseline with synthetic data only. Phase 4 performs no legacy dump
  conversion.
- Any future converter quarantines and fails on invalid nonempty payroll payment dates.

The later repayment, direct-write child scope, lifecycle, retention, and normative-catalogue audit
decisions are also approved and introduce no new open item.

Final owner review of the complete document remains pending. That review is a gate, not an open
schema-design question.

## Approval record

The project owner approved these design directions on **2026-09-01**:

- [x] Parent companies plus child branches; preserve `user_profiles.company_id`; require employee
  company and branch scope; propagate both deliberately; do not alter `f41c9a7b23d1`.
- [x] PostgreSQL 17, supported by current DigitalOcean Standard, DigitalOcean Advanced Edition, and
  Azure Flexible Server ranges cited above.
- [x] Core `gen_random_uuid()` without `pgcrypto` for new database defaults; leave Phase 3 Python UUID
  behavior untouched.
- [x] `numeric(12,2)` for 28 individual scalar money columns and `numeric(14,2)` for
  `payroll_runs.total_disbursed`; widen attendance money; validate JSON money in the API.
- [x] `timestamptz` and UTC for instants; `date` for calendar dates; `time` for wall-clock and shift
  template times.
- [x] Keep only `app_role` and `account_status` as native enums; use named text checks for business
  statuses.
- [x] Keep four target PostgreSQL functions, move the approved 22 functions to FastAPI, omit the two
  Supabase/unused functions, and treat undefined `manager_get_leave_queue` separately.
- [x] Retain PostgreSQL RLS as defense in depth, design new policies in Phase 5 from the permission
  matrix, catalogue rather than copy legacy policies, and keep least-privilege grants.
- [x] Omit `appraisals.self_reviewed` and appraisal-cycle `open`.
- [x] Use an empty portable baseline and synthetic data only in Phase 4, with no legacy dump
  conversion.
- [x] Require any future converter to quarantine and fail on invalid nonempty payroll payment dates.
- [x] Default leave weekends to Friday-Saturday while accepting `fri-sat` and `sat-sun`.
- [x] Store clock method `BIOMETRIC` and map legacy `BIOMETRIC_API` only in a future conversion.
- [x] Allow `flexible` in department staffing-rule shift categories.
- [x] Require finalized `payslips.net_pay` to be nonnegative.
- [x] Store visa wording `Tourist (Temp)` and map legacy `Tourist` only in a future conversion.
- [x] Normalize job-history change types to four lowercase snake-case values.
- [x] Rename `payroll_entries.du_cost` to `leave_deduction`.
- [x] Add required repayment company/branch scope and same-scope composite parent FKs.
- [x] Scope notification recipient and creator through profiles and use the five-part company dedup
  key.
- [x] Remove the three redundant leave denormalizations and enforce full clock-supersession scope.
- [x] Reject overlapping shift assignments in a locked FastAPI transaction without an extension or
  exclusion constraint.
- [x] Permit only `payroll_entries.variable_allowance` to be negative among fixed scalar money
  columns.
- [x] Retain financial and historical records with RESTRICT FKs and explicit draft-only purge rules;
  use no target CASCADE FK.
- [x] Add exact lifecycle evidence checks and retain identities referenced by lifecycle evidence.
- [x] Tighten nullable legacy additions that have reliable defaults when creating the empty baseline.
- [x] Give every target `updated_at` column one canonical trigger, including four documented new
  target trigger decisions.
- [x] Reject repayment requests above the locked outstanding balance instead of capping them.
- [x] Require every manual and payroll repayment to persist a caller-supplied UUID idempotency key,
  unique with its advance, while retaining payroll-run uniqueness.
- [x] Add required company and branch scope to directly written offboarding tasks and appraisal
  sections, with exact same-scope composite parent FKs.

Final document review:

- [x] **Approved by the project owner on 2026-09-01.**

## Completion gate assessment

**Passed on 2026-09-01.** The catalogue covers 54 target tables, all 52
legacy tables, 29 legacy function names, 19 legacy trigger names, 119 policy identities, 29 scalar
money columns, exact constraints and indexes, storage references, grants, and backfill
classifications. The eight governing decisions and the additional decisions above were approved on
2026-09-01. There are zero open design decisions. An independent catalogue audit found no remaining
coverage, consistency, provenance, or PostgreSQL-validity defect, and the project owner approved the
final document.

Phase 4B received separate project-owner authorization on 2026-09-01. Parts 4C through 4F remain
unauthorized.
