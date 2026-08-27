# SQL Schema Inventory

Phase 0 inventory of the repository's PostgreSQL and Supabase SQL. This document records the checked-in state before rebuilding the database under Alembic. It is an inventory, not a declaration that every script is safe, complete, or suitable for replay on a fresh database.

No canonical migration runner is present. The application documentation says to run `sql/*.sql` manually in numeric order, while those files depend on unnumbered root schemas. Two recovered root migrations now supply the previously missing employee/Auth mapping and self-service SQL, but their presence does not establish that the root chain is canonical, current, idempotent, or safe to replay unchanged.

## Executive Counts

| Item | Count | Notes |
|---|---:|---|
| Root-level `*.sql` scripts | 12 | Includes schemas, recovered employee/Auth migrations, ad hoc migrations, one RLS fix, and one destructive test-data reset. |
| Numbered `sql/*.sql` scripts | 50 | Numbered from `001` through `055`, with five missing numbers. |
| Missing numbered migrations | 5 | `010`, `011`, `015`, `018`, `020`. Only `015` is explicitly documented as skipped. |
| Tables explicitly created | 52 | Includes the recovered `user_profiles` definition. |
| Required but undefined application tables | 0 | Every application table referenced by the inventoried SQL now has a checked-in definition. |
| Effective application table set | 52 | All 52 definitions are checked in, although deployed production structure still requires catalog verification. |
| Views/materialized views | 0 | No `CREATE VIEW` or `CREATE MATERIALIZED VIEW` found. |
| Custom enums/domains/composite types | 0 | Statuses and categories use `TEXT`, sometimes with `CHECK` constraints. |
| Distinct function names | 29 | Includes 2 trigger helpers and 27 application/RPC names. Some are replaced later. |
| Distinct frontend-referenced RPC names | 27 | 26 map to checked-in SQL; only `manager_get_leave_queue` remains undefined. |
| Named trigger definitions | 19 | Several tables receive two timestamp triggers if root and numbered SQL are both applied. |
| Active extension declarations | 0 | `uuid-ossp` appears only in a comment. `gen_random_uuid()` is assumed available. |
| Expected storage buckets | 2 | `employee-documents` and `expense-receipts`; neither is created in SQL. |
| Checked-in storage object policy names | 2 | Employee INSERT and SELECT policies for `employee-documents`; both are duplicated by a later migration. |

## Sources and Ordering Authority

- `README.md:130-140` instructs operators to run every file in `sql/` in numerical order and calls the migrations idempotent.
- `CLAUDE.md:237-244` repeats the manual numeric-order instruction and the idempotence claim.
- Neither document gives a complete fresh-install order for the root schemas and recovered migrations.
- No `supabase/migrations/` directory, timestamped migration chain, or Alembic history exists.
- Root scripts contain their own partial ordering comments, such as `supabase_leave_rls_fix.sql` requiring `supabase_leave_schema.sql` first.

## Root SQL Inventory

The following is the dependency-based order inferred from the SQL. It is not a documented canonical order.

| Inferred order | Path | Role and dependencies |
|---:|---|---|
| 1 | `supabase_schema.sql` | Intended base schema for `companies`, `employees`, `employee_job_history`, `payroll_runs`, and `payroll_entries`; defines `handle_updated_at()`. |
| 2 | `supabase_migration_employee_auth_mapping.sql` | Recovered migration. Depends on `employees`; adds unique nullable `employees.auth_user_id`, creates `user_profiles`, adds three RLS policies, and defines `link_employee_account()`. Its profile role constraint allows only `admin` and `employee` until numbered migration `034`. |
| 3 | `supabase_leave_schema.sql` | Creates six leave tables. Depends on `employees` and `public.handle_updated_at()`. |
| 4 | `supabase_attendance_schema.sql` | Creates eight attendance tables. Depends on `employees` and `public.handle_updated_at()`. |
| 5 | `supabase_leave_rls_fix.sql` | Explicitly says to run after `supabase_leave_schema.sql`; grants leave-table access and replaces six leave policies. |
| 6 | `supabase_migration_employee_rls.sql` | Recovered migration. Must run after employee/Auth mapping plus leave and attendance schemas. Adds ten employee read policies and defines four employee write RPCs. Its `employee_record_clock_event()` contains the UUID/text bug later fixed by `sql/023_fix_clock_event_rpc_entered_by.sql`. |
| 7 | `supabase_migration_payslips.sql` | Creates `payslips`; depends on `payroll_runs`, `employees`, and `employees.auth_user_id` from the recovered Auth mapping. |
| 8 | `supabase_migration_leave_warnings.sql` | Adds `leave_requests.warnings` and creates a ten-parameter `employee_submit_leave_request(...)`; depends on leave tables and employee/Auth mapping. Because PostgreSQL identifies functions by input argument types, this does not remove the recovered nine-parameter overload. |
| 9a | `supabase_migration_employee_company_read.sql` | Creates `employees: read own company` through `user_profiles.company_user_id`; depends on recovered Auth mapping. |
| 9b | `supabase_migration_grants.sql` | Grants access to `user_profiles` and `payslips`, then drops and replaces `employees: read own company` with an `employees.auth_user_id` lookup. If this runs before the preceding file, the preceding unguarded `CREATE POLICY` can fail. |
| Alternative/backfill | `supabase_migration_existing_db.sql` | Recreates `employee_job_history` and adds many columns already present in `supabase_schema.sql`. It is an existing-database backfill, not an independent base schema. |
| Destructive utility | `supabase_reset_test_data.sql` | Deletes application data in an intended FK-safe order. It is not a migration and does not delete Auth users. |

### Recovered Root Prerequisites

The exact original-project files `supabase_migration_employee_auth_mapping.sql` and `supabase_migration_employee_rls.sql` are now present. They account for the employee/Auth objects and self-service policies/RPCs that were previously absent from this repository.

Their recovered status matters:

- They are unnumbered and no manifest proves their exact position among every root script.
- Their unguarded policies are not replay-idempotent.
- `supabase_migration_employee_rls.sql` contains the clock-event UUID/text defect that numbered migration `023` later repairs.
- Its nine-parameter leave submission function remains alongside the ten-parameter warnings overload unless explicitly dropped.
- Production may contain later manual edits not represented by either recovered file.

The files close the checked-in definition gap; they do not remove the need to compare the deployed catalog before constructing the Alembic baseline.

## Numbered Migration Inventory

The exact checked-in numeric sequence is below.

| Number | Path | Main schema effect |
|---:|---|---|
| 001 | `sql/001_emiratization.sql` | Adds `companies.sector`, `companies.nafis_quota_percent`, and `employees.nafis_registration_no`; creates `nafis_reports`. |
| 002 | `sql/002_document_storage.sql` | Creates `employee_documents`; documents manual `employee-documents` bucket setup. |
| 003 | `sql/003_medical_insurance.sql` | Creates `insurance_policies`, `employee_insurance`, and `insurance_dependants`. |
| 004 | `sql/004_notifications.sql` | Creates `notifications`. |
| 005 | `sql/005_salary_advances.sql` | Creates `salary_advances` and `advance_repayments`; defines `employee_request_advance`. |
| 006 | `sql/006_multi_level_leave.sql` | Extends `leave_requests`; creates `leave_approval_delegates`; defines leave-manager and portal-role RPCs. |
| 007 | `sql/007_shift_roster.sql` | Adds `shifts.color`; creates `roster_assignments` and `shift_swap_requests`; defines three employee roster RPCs. |
| 008 | `sql/008_wps_tracking.sql` | Adds WPS workflow fields to `payroll_runs` and `payroll_entries`. |
| 009 | `sql/009_probation_management.sql` | Adds `employees.probation_extended`. |
| 010 | **Missing** | No file or explanation found. |
| 011 | **Missing** | No file or explanation found. |
| 012 | `sql/012_contract_renewal.sql` | Creates `employee_contracts`. |
| 013 | `sql/013_offboarding.sql` | Creates `offboarding_checklists`, `offboarding_tasks`, and `offboarding_task_templates`. |
| 014 | `sql/014_expense_claims.sql` | Creates `expense_claims`; defines `employee_submit_expense`; documents manual `expense-receipts` setup. |
| 015 | **Missing by design** | `sql/016_asset_management.sql:3` says “015 (GPS Attendance) was skipped.” |
| 016 | `sql/016_asset_management.sql` | Creates `assets` and `asset_assignments`. |
| 017 | `sql/017_payroll_approval.sql` | Adds approval fields to `payroll_runs`; creates `payroll_approval_log`. |
| 018 | **Missing** | No file or explanation found. |
| 019 | `sql/019_training_records.sql` | Creates `training_records` and `certifications`. |
| 020 | **Missing** | No file or explanation found. |
| 021 | `sql/021_multi_company.sql` | Adds branch support; removes unique `companies.user_id`; adds `company_id` to employees/payroll runs and backfills it. |
| 022 | `sql/022_admin_clock_events_access.sql` | Adds admin SELECT access to employee clock events. |
| 023 | `sql/023_fix_clock_event_rpc_entered_by.sql` | Defines/replaces `employee_record_clock_event` to fix UUID/text handling. |
| 024 | `sql/024_employee_self_upload.sql` | Adds document review metadata; defines employee submission RPC and two `storage.objects` policies. |
| 025 | `sql/025_letter_requests.sql` | Creates `letter_requests`; defines `employee_request_letter`. |
| 026 | `sql/026_clinical_duty_rota.sql` | Adds shift code/category and planned/actual/co-hours to roster assignments. |
| 027 | `sql/027_biometric_integration.sql` | Creates `biometric_mappings`. |
| 028 | `sql/028_probation_leave_rules.sql` | Adds and backfills `leave_types.probation_eligible`. |
| 029 | `sql/029_department_hierarchy.sql` | Creates `departments`. |
| 030 | `sql/030_expense_manager_approval.sql` | Adds manager expense fields and three manager expense RPCs. |
| 031 | `sql/031_appraisal_module.sql` | Creates `appraisal_cycles`, `appraisals`, and `appraisal_sections`. |
| 032 | `sql/032_roster_compliance.sql` | Adds `shifts.min_staff`. |
| 033 | `sql/033_clinical_gaps.sql` | Adds employee licence fields; creates `compliance_overrides` and `department_staffing_rules`; adds manager appraisal policies. |
| 034 | `sql/034_manager_role.sql` | Expands the profile role constraint and replaces `admin_set_employee_portal_role`. |
| 035 | `sql/035_manager_employee_read.sql` | Defines `get_manager_employee_id()` and manager employee-read policy. |
| 036 | `sql/036_advance_rejection_reason.sql` | Adds `salary_advances.rejection_reason`. |
| 037 | `sql/037_leave_manager_read.sql` | Adds manager leave/balance reads and authenticated leave-type reads. |
| 038 | `sql/038_appraisal_manager_update.sql` | Adds manager UPDATE access to appraisals. |
| 039 | `sql/039_shifts_read_policy.sql` | Adds admin shift policy and global authenticated shift-template read. |
| 040 | `sql/040_training_manager_policies.sql` | Adds manager training/certification access and employee training writes. |
| 041 | `sql/041_employee_contact_update.sql` | Adds broad employee UPDATE access to the employee's own row. |
| 042 | `sql/042_certification_self_service.sql` | Adds certification review status and employee INSERT/UPDATE policies. |
| 043 | `sql/043_employee_portal_fixes.sql` | Repeats storage policies and broad employee contact UPDATE policy. |
| 044 | `sql/044_phase1_data_protection.sql` | Adds payroll uniqueness; defines atomic payroll/repayment RPCs; removes broad employee UPDATE and adds contact RPC. |
| 045 | `sql/045_core_rls_baseline.sql` | Adds overlapping baseline core policies and broad public-schema table grants. |
| 046 | `sql/046_phase4_db_hardening.sql` | Adds indexes, financial checks, timestamp columns, `set_updated_at()`, and six triggers. |
| 047 | `sql/047_cme_tracking.sql` | Creates `cme_requirements`; adds `training_records.is_cme`. |
| 048 | `sql/048_incident_reports.sql` | Creates `incident_reports`. |
| 049 | `sql/049_feature_toggles.sql` | Adds three company feature flags; defines the first `employee_cancel_advance` version. |
| 050 | `sql/050_advance_repayment_scheduling.sql` | Adds repayment start month and uniqueness; replaces repayment RPC with locked/idempotent version. |
| 051 | `sql/051_employee_request_actions.sql` | Replaces advance cancellation with boolean-returning version; adds `employee_delete_expense`. |
| 052 | `sql/052_shift_swap_execution.sql` | Defines atomic `admin_execute_shift_swap`. |
| 053 | `sql/053_roster_company_scope.sql` | Adds and backfills `company_id` on roster/swap tables. |
| 054 | `sql/054_certification_file_upload.sql` | Adds storage path/file name to certifications and training records. |
| 055 | `sql/055_custom_requests.sql` | Adds `letter_requests.request_kind`; defines `employee_request_custom`. |

## Table Inventory

### Core Identity, Company, and Payroll

| Table | Definition | Important later changes |
|---|---|---|
| `companies` | `supabase_schema.sql` | `001`: Nafis fields. `021`: branch name and removal of one-company-per-user uniqueness. `049`: feature flags. |
| `employees` | `supabase_schema.sql` | `supabase_migration_employee_auth_mapping.sql` adds unique nullable `auth_user_id`; existing-db backfill duplicates many other columns; `001`, `009`, `021`, `033`, and `046` extend it. |
| `employee_job_history` | `supabase_schema.sql` and `supabase_migration_existing_db.sql` | Duplicate logical definition. |
| `payroll_runs` | `supabase_schema.sql` | Extended by `008`, `017`, `021`, `044`, and `046`. |
| `payroll_entries` | `supabase_schema.sql` | Extended by `008`; used by the replacement RPC in `044`. |
| `payslips` | `supabase_migration_payslips.sql` | Immutable payroll snapshot intent, although UPDATE policy is also provided. |
| `user_profiles` | `supabase_migration_employee_auth_mapping.sql` | Auth-user PK, role, employer/admin `company_user_id`, optional employee FK, and timestamp. Initial role check allows `admin`/`employee`; `sql/034_manager_role.sql` replaces it to include `manager`. |

### Leave

Defined in `supabase_leave_schema.sql` unless stated otherwise:

- `leave_settings`
- `leave_types`
- `public_holidays`
- `leave_requests`
- `leave_audit_log`
- `leave_balances`
- `leave_approval_delegates` from `sql/006_multi_level_leave.sql`

Important evolution:

- `sql/006_multi_level_leave.sql` adds manager approval/delegation fields to `leave_requests`.
- `supabase_migration_employee_rls.sql` defines the original employee leave submission and cancellation RPCs.
- `supabase_migration_leave_warnings.sql` adds `leave_requests.warnings`.
- `sql/028_probation_leave_rules.sql` adds `leave_types.probation_eligible` and updates existing rows.
- `sql/037_leave_manager_read.sql` adds manager read paths and globally readable leave types for authenticated users.

### Attendance, Roster, and Biometric Data

Defined in `supabase_attendance_schema.sql`:

- `attendance_settings`
- `shifts`
- `shift_assignments`
- `clock_events`
- `attendance_records`
- `attendance_periods`
- `regularisation_requests`
- `attendance_audit_log`

Defined later:

- `roster_assignments` in `sql/007_shift_roster.sql`
- `shift_swap_requests` in `sql/007_shift_roster.sql`
- `biometric_mappings` in `sql/027_biometric_integration.sql`
- `department_staffing_rules` in `sql/033_clinical_gaps.sql`

Important evolution:

- `supabase_attendance_schema.sql` adds `employees.shift_id`.
- `supabase_migration_employee_rls.sql` adds employee attendance reads and the original clock-event/regularisation RPCs.
- `sql/007_shift_roster.sql`, `026`, and `032` extend shifts/rosters.
- `sql/053_roster_company_scope.sql` adds branch scope to roster and swap rows.
- `shift_assignments` and `roster_assignments` are separate concepts and both remain present.

### Finance, Compliance, and Requests

- `nafis_reports` — `sql/001_emiratization.sql`
- `salary_advances` — `sql/005_salary_advances.sql`
- `advance_repayments` — `sql/005_salary_advances.sql`
- `expense_claims` — `sql/014_expense_claims.sql`
- `payroll_approval_log` — `sql/017_payroll_approval.sql`
- `letter_requests` — `sql/025_letter_requests.sql`
- `compliance_overrides` — `sql/033_clinical_gaps.sql`

`letter_requests` is reused for custom requests by `sql/055_custom_requests.sql`; `letter_type` stores the custom subject and `purpose` stores custom details.

### Documents, Benefits, and Notifications

- `employee_documents` — `sql/002_document_storage.sql`
- `insurance_policies` — `sql/003_medical_insurance.sql`
- `employee_insurance` — `sql/003_medical_insurance.sql`
- `insurance_dependants` — `sql/003_medical_insurance.sql`
- `notifications` — `sql/004_notifications.sql`

### Contracts, Offboarding, and Assets

- `employee_contracts` — `sql/012_contract_renewal.sql`
- `offboarding_checklists` — `sql/013_offboarding.sql`
- `offboarding_tasks` — `sql/013_offboarding.sql`
- `offboarding_task_templates` — `sql/013_offboarding.sql`
- `assets` — `sql/016_asset_management.sql`
- `asset_assignments` — `sql/016_asset_management.sql`

### Training, Organisation, Appraisal, and Clinical Data

- `training_records` — `sql/019_training_records.sql`
- `certifications` — `sql/019_training_records.sql`
- `departments` — `sql/029_department_hierarchy.sql`
- `appraisal_cycles` — `sql/031_appraisal_module.sql`
- `appraisals` — `sql/031_appraisal_module.sql`
- `appraisal_sections` — `sql/031_appraisal_module.sql`
- `cme_requirements` — `sql/047_cme_tracking.sql`
- `incident_reports` — `sql/048_incident_reports.sql`

## Views, Types, and Extensions

### Views

No application views or materialized views are defined.

### Types

No PostgreSQL enums, domains, or custom composite types are defined. The schema uses `TEXT` for workflow states and categories. A minority have `CHECK` constraints:

- `salary_advances.status`
- `shift_swap_requests.status`
- `appraisal_cycles.status`
- `appraisals.status`
- `department_staffing_rules.shift_category`
- `user_profiles.role`, initially `admin`/`employee` and later expanded to include `manager`
- `letter_requests.request_kind`

Many other documented status/category sets are comments only. Alembic must preserve current permissiveness or deliberately introduce validated constraints after data profiling.

### Extensions

No extension is actively installed. `supabase_schema.sql:7` comments out:

```sql
create extension if not exists "uuid-ossp";
```

The schema uses `gen_random_uuid()` throughout and assumes the target PostgreSQL environment provides it. The Alembic bootstrap must explicitly decide whether to install `pgcrypto`, rely on built-in target-version behavior, or use another UUID default.

## Function and RPC Inventory

### Trigger Helpers

| Function | Path | Purpose |
|---|---|---|
| `public.handle_updated_at()` | `supabase_schema.sql` | Original `updated_at` trigger function. |
| `set_updated_at()` | `sql/046_phase4_db_hardening.sql` | Later timestamp trigger function. |

### Application Functions

| Function | Defining or replacing path | Notes |
|---|---|---|
| `link_employee_account()` | `supabase_migration_employee_auth_mapping.sql` | Recovered security-definer function; matches `auth.email()` to unlinked `employees.work_email`, sets `auth_user_id`, and upserts `user_profiles`. |
| `employee_submit_leave_request(...)` | `supabase_migration_employee_rls.sql`; ten-parameter overload in `supabase_migration_leave_warnings.sql` | Recovered nine-parameter version inserts leave request plus audit row; later overload stores warnings. Both signatures can coexist. Neither file explicitly grants function execution. |
| `employee_cancel_leave_request(uuid)` | `supabase_migration_employee_rls.sql` | Recovered security-definer function; caller-owned pending request cancellation with audit row. |
| `employee_submit_regularisation(...)` | `supabase_migration_employee_rls.sql` | Recovered security-definer function; inserts caller-owned pending regularisation request under employer/admin `user_id`. |
| `employee_request_advance(decimal,text)` | `sql/005_salary_advances.sql` | Employee lookup through recovered `employees.auth_user_id`. |
| `manager_approve_leave(uuid)` | `sql/006_multi_level_leave.sql` | Direct-report/delegate validation; directly reads `auth.users`. |
| `manager_reject_leave(uuid,text)` | `sql/006_multi_level_leave.sql` | Same dependencies. |
| `admin_set_employee_portal_role(uuid,text)` | `sql/006_multi_level_leave.sql`, replaced by `sql/034_manager_role.sql` | Later replacement removes company-admin and company-ownership validation. |
| `admin_get_employee_portal_role(uuid)` | `sql/006_multi_level_leave.sql` | Reads recovered `user_profiles`. |
| `employee_get_my_roster(date,date)` | `sql/007_shift_roster.sql` | Returns published roster with shift data. |
| `employee_get_colleagues()` | `sql/007_shift_roster.sql` | Returns active colleagues under the same admin owner. |
| `employee_request_shift_swap(...)` | `sql/007_shift_roster.sql` | Inserts pending shift swap. |
| `employee_submit_expense(...)` | `sql/014_expense_claims.sql` | Inserts under employer/admin `user_id`. |
| `employee_record_clock_event(text,text)` | `supabase_migration_employee_rls.sql`, replaced by `sql/023_fix_clock_event_rpc_entered_by.sql` | Recovered original casts `auth.uid()` to text for UUID `entered_by`; migration `023` removes the bad cast. |
| `employee_submit_document(...)` | `sql/024_employee_self_upload.sql` | Inserts employee document under employer/admin `user_id`. |
| `employee_request_letter(text,text)` | `sql/025_letter_requests.sql` | Inserts employee letter request. |
| `manager_get_expense_queue()` | `sql/030_expense_manager_approval.sql` | Security-definer direct-report queue. |
| `manager_approve_expense(uuid)` | `sql/030_expense_manager_approval.sql` | Direct-report status transition. |
| `manager_reject_expense(uuid,text)` | `sql/030_expense_manager_approval.sql` | Direct-report rejection transition. |
| `get_manager_employee_id()` | `sql/035_manager_employee_read.sql` | Security-definer helper used to avoid recursive employee RLS. |
| `replace_payroll_entries(uuid,jsonb)` | `sql/044_phase1_data_protection.sql` | Atomic delete/insert, but no caller ownership validation. |
| `record_advance_repayment(...)` | `sql/044_phase1_data_protection.sql`, replaced by `sql/050_advance_repayment_scheduling.sql` | Later version adds row locking, ownership validation, amount capping, and duplicate detection. |
| `employee_update_contact(...)` | `sql/044_phase1_data_protection.sql` | Replaces broad employee row UPDATE policy with a column-limited operation. |
| `employee_cancel_advance(uuid)` | `sql/049_feature_toggles.sql`, dropped/recreated by `sql/051_employee_request_actions.sql` | Return type changes from `TABLE` to `BOOLEAN`; explicit drop is required. |
| `employee_delete_expense(uuid)` | `sql/051_employee_request_actions.sql` | Deletes only caller-owned pending/rejected claims. |
| `admin_execute_shift_swap(uuid)` | `sql/052_shift_swap_execution.sql` | Locks and atomically mutates roster rows. |
| `employee_request_custom(text,text)` | `sql/055_custom_requests.sql` | Stores custom request in `letter_requests`. |

## Frontend RPC Mapping

| RPC called by frontend | Frontend path(s) | Defining SQL | Status |
|---|---|---|---|
| `admin_execute_shift_swap` | `src/utils/attendanceStorage.js:814` | `sql/052_shift_swap_execution.sql` | Found. |
| `employee_get_my_roster` | `src/utils/attendanceStorage.js:880` | `sql/007_shift_roster.sql` | Found. |
| `employee_get_colleagues` | `src/utils/attendanceStorage.js:939` | `sql/007_shift_roster.sql` | Found. |
| `employee_request_shift_swap` | `src/utils/attendanceStorage.js:948` | `sql/007_shift_roster.sql` | Found. |
| `employee_delete_expense` | `src/utils/expenseStorage.js:164` | `sql/051_employee_request_actions.sql` | Found. |
| `manager_get_expense_queue` | `src/utils/expenseStorage.js:207`; `src/utils/taskStorage.js:288` | `sql/030_expense_manager_approval.sql` | Found. |
| `manager_get_leave_queue` | `src/utils/taskStorage.js:287` | **No checked-in definition** | Missing; task aggregation assumes a manager-scoped leave result. |
| `manager_approve_expense` | `src/utils/expenseStorage.js:217` | `sql/030_expense_manager_approval.sql` | Found. |
| `manager_reject_expense` | `src/utils/expenseStorage.js:227` | `sql/030_expense_manager_approval.sql` | Found. |
| `manager_approve_leave` | `src/utils/leaveStorage.js:603` | `sql/006_multi_level_leave.sql` | Found. |
| `manager_reject_leave` | `src/utils/leaveStorage.js:611` | `sql/006_multi_level_leave.sql` | Found. |
| `employee_submit_regularisation` | `src/components/employee/EmpAttendance.jsx:137` | `supabase_migration_employee_rls.sql` | Found in recovered root migration. |
| `employee_request_advance` | `src/components/employee/EmpAdvances.jsx:67` | `sql/005_salary_advances.sql` | Found. |
| `employee_submit_document` | `src/components/employee/EmpDocuments.jsx:110` | `sql/024_employee_self_upload.sql` | Found. |
| `employee_request_custom` | `src/components/employee/EmpRequests.jsx:69` | `sql/055_custom_requests.sql` | Found. |
| `employee_request_letter` | `src/components/employee/EmpRequests.jsx:73` | `sql/025_letter_requests.sql` | Found. |
| `link_employee_account` | `src/utils/profileStorage.js:76` | `supabase_migration_employee_auth_mapping.sql` | Found in recovered root migration. |
| `admin_get_employee_portal_role` | `src/utils/profileStorage.js:132` | `sql/006_multi_level_leave.sql` | Found. |
| `admin_set_employee_portal_role` | `src/utils/profileStorage.js:145` | `sql/006_multi_level_leave.sql`, replaced by `sql/034_manager_role.sql` | Found, but final authorization is unsafe. |
| `employee_cancel_leave_request` | `src/components/employee/EmpLeave.jsx:123` | `supabase_migration_employee_rls.sql` | Found in recovered root migration. |
| `employee_submit_leave_request` | `src/components/employee/EmpLeave.jsx:188` | `supabase_migration_employee_rls.sql`; warnings overload in `supabase_migration_leave_warnings.sql` | Found outside numbered chain; frontend supplies `p_warnings` and targets the ten-parameter overload. |
| `employee_submit_expense` | `src/components/employee/EmpExpenses.jsx:124` | `sql/014_expense_claims.sql` | Found. |
| `get_manager_employee_id` | `src/utils/appraisalStorage.js:150,194`; `src/utils/trainingStorage.js:298,314,564` | `sql/035_manager_employee_read.sql` | Found. |
| `replace_payroll_entries` | `src/utils/storage.js:469` | `sql/044_phase1_data_protection.sql` | Found, with authorization gap. |
| `employee_cancel_advance` | `src/utils/storage.js:911` | `sql/049_feature_toggles.sql`, final version in `sql/051_employee_request_actions.sql` | Found. |
| `record_advance_repayment` | `src/utils/storage.js:999` | `sql/044_phase1_data_protection.sql`, final version in `sql/050_advance_repayment_scheduling.sql` | Found. |
| `employee_update_contact` | `src/components/employee/EmpProfile.jsx:98` | `sql/044_phase1_data_protection.sql` | Found. |

`employee_record_clock_event()` is defined in SQL, but no current frontend `.rpc()` call was found. Attendance code currently contains direct `clock_events` operations.

## Triggers and Overlaps

### Original `handle_updated_at()` Triggers

From `supabase_schema.sql`:

- `companies_updated_at` on `companies`
- `employees_updated_at` on `employees`
- `payroll_runs_updated_at` on `payroll_runs`
- `payroll_entries_updated_at` on `payroll_entries`

From `supabase_leave_schema.sql`:

- `leave_settings_updated_at` on `leave_settings`
- `leave_types_updated_at` on `leave_types`
- `leave_requests_updated_at` on `leave_requests`
- `leave_balances_updated_at` on `leave_balances`

From `supabase_attendance_schema.sql`:

- `attendance_settings_updated_at` on `attendance_settings`
- `shifts_updated_at` on `shifts`
- `attendance_records_updated_at` on `attendance_records`

### Later `set_updated_at()` Triggers

From `sql/046_phase4_db_hardening.sql`:

- `trg_employees_updated_at` on `employees`
- `trg_payroll_runs_updated_at` on `payroll_runs`
- `trg_advances_updated_at` on `salary_advances`
- `trg_leave_requests_updated_at` on `leave_requests`
- `trg_attendance_updated_at` on `attendance_records`
- `trg_expenses_updated_at` on `expense_claims`

Additional triggers:

- `trg_cme_requirements_updated_at` on `cme_requirements` from `sql/047_cme_tracking.sql`
- `trg_incidents_updated_at` on `incident_reports` from `sql/048_incident_reports.sql`

### Overlap

If the root schemas and numbered chain are both applied, these tables receive two timestamp triggers:

- `employees`
- `payroll_runs`
- `leave_requests`
- `attendance_records`

Both helper functions set `updated_at = NOW()`, so the second execution is mostly redundant. The extra trigger still adds work and leaves two competing schema conventions. Alembic should use one helper and one trigger per table.

## RLS Policy Inventory

PostgreSQL combines ordinary permissive policies with OR semantics. The duplicated owner and self-service policies below therefore widen the set of accepted operations rather than replacing earlier behavior unless a migration explicitly drops a policy.

### Root Core Policies

From `supabase_schema.sql`:

- `Users can manage their own company` on `companies`, ALL, owner by `user_id`.
- `Users can manage their own employees` on `employees`, ALL, owner by `user_id`.
- `Users can manage their own job history` on `employee_job_history`, ALL.
- `Users can manage their own payroll runs` on `payroll_runs`, ALL.
- `Users can manage their own payroll entries` on `payroll_entries`, ALL.

From recovered `supabase_migration_employee_auth_mapping.sql`:

- `user_profiles: read own` on `user_profiles`, SELECT by `user_id = auth.uid()`.
- `user_profiles: insert own` on `user_profiles`, INSERT with the same identity check.
- `employees: read own via auth_user_id` on `employees`, SELECT by `auth_user_id = auth.uid()`.

From recovered `supabase_migration_employee_rls.sql`:

- `employees: read leave types` on `leave_types`, SELECT for the linked employee's employer/admin `user_id`.
- `employees: read public holidays` on `public_holidays`, SELECT for the linked employee's employer/admin `user_id`.
- `employees: read leave settings` on `leave_settings`, SELECT for the linked employee's employer/admin `user_id`.
- `employees: read own leave requests` on `leave_requests`, SELECT by linked employee ID.
- `employees: read own leave balances` on `leave_balances`, SELECT by linked employee ID.
- `employees: read own payroll entries` on `payroll_entries`, SELECT by linked employee ID.
- `employees: read payroll runs for own entries` on `payroll_runs`, SELECT through the employee's payroll entries.
- `employees: read own attendance records` on `attendance_records`, SELECT by linked employee ID.
- `employees: read own clock events` on `clock_events`, SELECT by linked employee ID.
- `employees: read own regularisation requests` on `regularisation_requests`, SELECT by linked employee ID.

All 13 recovered policies are unguarded `CREATE POLICY` statements. Replaying either recovered file after those policies exist will fail.

From `supabase_leave_schema.sql`, then dropped/recreated by `supabase_leave_rls_fix.sql`:

- `Users manage their own leave settings` on `leave_settings`, ALL.
- `Users manage their own leave types` on `leave_types`, ALL.
- `Users manage their own public holidays` on `public_holidays`, ALL.
- `Users manage their own leave requests` on `leave_requests`, ALL.
- `Users view their own leave audit log` on `leave_audit_log`, ALL despite the read-oriented name.
- `Users manage their own leave balances` on `leave_balances`, ALL.

From `supabase_attendance_schema.sql`:

- `Users manage their own attendance settings` on `attendance_settings`, ALL.
- `Users manage their own shifts` on `shifts`, ALL.
- `Users manage their own shift assignments` on `shift_assignments`, ALL.
- `Users manage their own clock events` on `clock_events`, ALL.
- `Users manage their own attendance records` on `attendance_records`, ALL.
- `Users manage their own attendance periods` on `attendance_periods`, ALL.
- `Users manage their own regularisation requests` on `regularisation_requests`, ALL.
- `Users view their own attendance audit log` on `attendance_audit_log`, ALL despite the read-oriented name.

Company and payslip policies:

- `employees: read own company` on `companies` has two order-sensitive definitions in `supabase_migration_employee_company_read.sql` and `supabase_migration_grants.sql`.
- `payslips: admin read own` on `payslips`, SELECT.
- `payslips: employee read own` on `payslips`, SELECT.
- `payslips: admin insert` on `payslips`, INSERT.
- `payslips: admin update` on `payslips`, UPDATE.

### Numbered Feature Policies

| Table | Policy names | Path(s) |
|---|---|---|
| `nafis_reports` | `nafis_reports_owner` | `sql/001_emiratization.sql` |
| `employee_documents` | `employee_documents_admin`, `employee_documents_self_read`, `employee_documents_self_update_pending` | `sql/002_document_storage.sql`, `sql/024_employee_self_upload.sql` |
| `insurance_policies` | `insurance_policies_admin` | `sql/003_medical_insurance.sql` |
| `employee_insurance` | `employee_insurance_admin`, `employee_insurance_self` | `sql/003_medical_insurance.sql` |
| `insurance_dependants` | `insurance_dependants_admin` | `sql/003_medical_insurance.sql` |
| `notifications` | `notifications_select`, `notifications_insert`, `notifications_update`, `notifications_delete` | `sql/004_notifications.sql` |
| `salary_advances` | `salary_advances_admin`, `salary_advances_employee_read` | `sql/005_salary_advances.sql` |
| `advance_repayments` | `advance_repayments_admin`, `advance_repayments_employee_read` | `sql/005_salary_advances.sql` |
| `leave_approval_delegates` | `leave_approval_delegates_admin`, `leave_approval_delegates_actor_read` | `sql/006_multi_level_leave.sql` |
| `roster_assignments` | `roster_assignments_admin_all`, `roster_assignments_employee_read` | `sql/007_shift_roster.sql` |
| `shift_swap_requests` | `shift_swap_requests_admin_all`, `shift_swap_requests_employee_read` | `sql/007_shift_roster.sql` |
| `employee_contracts` | `employee_contracts_admin` | `sql/012_contract_renewal.sql` |
| `offboarding_checklists` | `offboarding_checklists_admin` | `sql/013_offboarding.sql` |
| `offboarding_tasks` | `offboarding_tasks_admin` | `sql/013_offboarding.sql` |
| `offboarding_task_templates` | `offboarding_task_templates_admin` | `sql/013_offboarding.sql` |
| `expense_claims` | `expense_claims_admin`, `expense_claims_employee_read` | `sql/014_expense_claims.sql` |
| `assets` | `assets_admin`, `assets_employee_read` | `sql/016_asset_management.sql` |
| `asset_assignments` | `asset_assignments_admin`, `asset_assignments_employee_read` | `sql/016_asset_management.sql` |
| `payroll_approval_log` | `payroll_approval_log_admin` | `sql/017_payroll_approval.sql` |
| `training_records` | `training_records_admin`, `training_records_employee_read`, `training_records_manager_all`, `training_records_employee_insert`, `training_records_employee_update` | `sql/019_training_records.sql`, `sql/040_training_manager_policies.sql` |
| `certifications` | `certifications_admin`, `certifications_employee_read`, `certifications_manager_all`, `certifications_employee_insert`, `certifications_employee_update` | `sql/019_training_records.sql`, `sql/040_training_manager_policies.sql`, `sql/042_certification_self_service.sql` |
| `clock_events` | `Admins view their employees' clock events` | `sql/022_admin_clock_events_access.sql` |
| `letter_requests` | `letter_requests_admin`, `letter_requests_employee_read` | `sql/025_letter_requests.sql` |
| `biometric_mappings` | `biometric_mappings_admin` | `sql/027_biometric_integration.sql` |
| `departments` | `departments_admin` | `sql/029_department_hierarchy.sql` |
| `appraisal_cycles` | `appraisal_cycles_admin`, `appraisal_cycles_manager_read` | `sql/031_appraisal_module.sql`, `sql/033_clinical_gaps.sql` |
| `appraisals` | `appraisals_admin`, `appraisals_employee_read`, `appraisals_manager_read`, `appraisals_manager_update` | `sql/031_appraisal_module.sql`, `sql/033_clinical_gaps.sql`, `sql/038_appraisal_manager_update.sql` |
| `appraisal_sections` | `appraisal_sections_admin`, `appraisal_sections_employee_read`, `appraisal_sections_manager_read`, `appraisal_sections_manager_update` | `sql/031_appraisal_module.sql`, `sql/033_clinical_gaps.sql` |
| `compliance_overrides` | `compliance_overrides_admin` | `sql/033_clinical_gaps.sql` |
| `department_staffing_rules` | `dept_staffing_admin` | `sql/033_clinical_gaps.sql` |
| `employees` | `employees_manager_read`; temporary `employees_self_update_contact` | `sql/035_manager_employee_read.sql`; `sql/041_employee_contact_update.sql`, repeated in `043`, dropped in `044` |
| `leave_requests` | `leave_requests_manager_read` | `sql/037_leave_manager_read.sql` |
| `leave_balances` | `leave_balances_manager_read` | `sql/037_leave_manager_read.sql` |
| `leave_types` | `leave_types_authenticated_read` | `sql/037_leave_manager_read.sql` |
| `shifts` | `shifts_admin_all`, `shifts_authenticated_read` | `sql/039_shifts_read_policy.sql` |
| `cme_requirements` | `cme_requirements_admin_all` | `sql/047_cme_tracking.sql` |
| `incident_reports` | `incident_reports_admin_all` | `sql/048_incident_reports.sql` |

### Baseline Policies Added in Migration 045

`sql/045_core_rls_baseline.sql` adds policies that coexist with earlier policies:

- `companies_owner_all`
- `user_profiles_owner_all`
- `employees_owner_all`
- `employees_self_read`
- `payroll_runs_owner_all`
- `payroll_entries_owner_all`
- `payslips_owner_all`
- `payslips_employee_read`
- `attendance_records_owner_all`
- `attendance_records_employee_read`
- `clock_events_owner_all`

### Broad Authenticated Reads

The following policies deliberately ignore tenant/company scope:

- `leave_types_authenticated_read`: every authenticated user can read every leave type row.
- `shifts_authenticated_read`: every authenticated user can read every shift row.

Whether that behavior is acceptable must be an explicit Alembic-era authorization decision.

## Grants

### Schema and Table Grants

- `supabase_leave_rls_fix.sql` grants `USAGE` on schema `public` to `authenticated` and `anon`.
- The same file grants `ALL` on all six leave tables to `authenticated`.
- `supabase_migration_grants.sql` grants `SELECT, INSERT, UPDATE` on `user_profiles` and `payslips` to `authenticated`.
- The recovered Auth mapping and employee RLS files create tables/policies/functions but contain no explicit table or function grants. Their behavior therefore depends on subsequent grants, Supabase defaults, and implicit PUBLIC function execution.
- Most numbered table-creation migrations grant `ALL` on their new tables to `authenticated`.
- Many migrations repeatedly grant `ALL ON ALL TABLES IN SCHEMA public TO service_role`.
- Several also grant `USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role`.
- `sql/045_core_rls_baseline.sql` grants `ALL ON ALL TABLES IN SCHEMA public` to both `authenticated` and `service_role`.

The migration 045 authenticated grant makes the individual table grants mostly redundant and leaves RLS as the primary boundary for every current public table.

No `ALTER DEFAULT PRIVILEGES` statement was found. Newly created tables after a blanket `GRANT ... ON ALL TABLES` do not automatically inherit that grant.

### Function Grants

Many RPC files grant EXECUTE to `authenticated`. PostgreSQL normally grants function execution to `PUBLIC` at creation time, so an authenticated grant does not restrict access by itself. The recovered `link_employee_account`, leave submission/cancellation, clock-event, and regularisation functions do not contain explicit grants or PUBLIC revocations.

Explicit `REVOKE ALL ... FROM PUBLIC` appears only for final functions in:

- `sql/050_advance_repayment_scheduling.sql`
- `sql/051_employee_request_actions.sql`
- `sql/052_shift_swap_execution.sql`
- `sql/055_custom_requests.sql`

Earlier security-definer functions generally retain implicit PUBLIC execution unless the deployed database was hardened separately.

## Storage Buckets and Policies

### `employee-documents`

Documented as a private, manually created bucket in:

- `sql/002_document_storage.sql`
- `README.md:142-145`

Used for:

- Employee documents
- Leave attachments
- Training and certification files

Executable policies on `storage.objects`:

- `employee_documents_employee_upload`, INSERT to `authenticated`
- `employee_documents_employee_read_own`, SELECT to `authenticated`

Both are defined in `sql/024_employee_self_upload.sql`, then dropped and recreated in `sql/043_employee_portal_fixes.sql`.

The policies require:

- `bucket_id = 'employee-documents'`
- Folder segment 1 equals the employer/admin `employees.user_id`
- Folder segment 2 equals `employees.id`
- Current Auth user equals `employees.auth_user_id`

No executable SQL defines:

- The bucket row in `storage.buckets`
- Admin CRUD policies
- Employee DELETE policy
- Employee UPDATE policy

The application attempts file cleanup with `.remove(...)`, including `src/components/employee/EmpDocuments.jsx:121`, but the checked-in employee policies do not permit DELETE.

### Certification Path Mismatch

`src/utils/trainingStorage.js:74-81` uploads certificates to:

```text
{current_auth_user_id}/certs/{employee_id}/...
```

That path does not match the employee-document policy contract of:

```text
{admin_user_id}/{employee_id}/...
```

For employee sessions, folder segment 1 is the employee Auth UUID rather than employer/admin UUID, and folder segment 2 is `certs` rather than employee UUID. Employee certification uploads are therefore incompatible with the checked-in policies.

### `expense-receipts`

Documented in `sql/014_expense_claims.sql` and used in `src/utils/expenseStorage.js:176-195`.

No executable SQL creates:

- The bucket
- Any `storage.objects` policy for it

Its setup exists only as comments/dashboard instructions.

## Supabase-Specific Dependencies

### Authentication Schema and Helpers

The SQL depends on:

- `auth.users(id)` foreign keys across most tenant-owned tables
- `auth.uid()` in almost all ownership and employee-link policies
- `auth.email()` in leave and expense workflows
- `auth.role()` in the authenticated shift-read policy
- Direct reads from `auth.users` in `sql/006_multi_level_leave.sql` and `sql/052_shift_swap_execution.sql`

The recovered identity flow adds direct coupling to Supabase Auth semantics:

- `employees.auth_user_id` references `auth.users(id)` and is unique.
- `user_profiles.user_id` references `auth.users(id)` with cascading delete.
- `link_employee_account()` matches `auth.email()` to `employees.work_email` and stores `auth.uid()`.
- Employee self-service policies resolve the current application employee through `employees.auth_user_id = auth.uid()`.
- Employee write RPCs use `auth.email()` for audit actors and write tenant ownership as `employees.user_id`.

Supabase database roles referenced:

- `authenticated`
- `anon`
- `service_role`
- `PUBLIC`

### Storage Schema and Helpers

The SQL depends on:

- `storage.objects`
- `storage.foldername(name)`
- Supabase bucket IDs
- Signed URL behavior in the frontend

### Other PostgreSQL/Supabase Assumptions

- SQL Editor execution by a privileged owner is assumed.
- Security-definer functions are expected to bypass RLS.
- `gen_random_uuid()` is expected to exist without repository-managed extension setup.
- The frontend uses the Supabase anonymous key and relies on Auth JWT role mapping to `authenticated`.

## Fresh-Install Gaps

1. `README.md` instructs users to run only `sql/*.sql`, but `sql/001_emiratization.sql` immediately alters `companies` and `employees`, which are created only by `supabase_schema.sql`.
2. Leave, attendance, payroll, roster, employee/Auth mapping, and employee self-service depend on an undocumented order across unnumbered root files.
3. `manager_get_leave_queue()` remains the only frontend-called RPC with no checked-in definition.
4. The recovered employee RLS migration contains a known failing clock-event implementation unless numbered migration `023` runs later.
5. The recovered employee/Auth policies and employee self-service policies are unguarded and fail on replay.
6. Neither storage bucket is created in SQL.
7. Required admin and expense storage policies are not created in SQL.
8. No extension/bootstrap script guarantees UUID generation support.
9. No canonical checked-in sequence is documented to reproduce the deployed database from an empty PostgreSQL instance.
10. The recovered SQL may describe a historical state rather than the exact current production catalog; its presence is not proof that replaying it is safe.

## Conflicts and Duplicate Definitions

### Root and Numbered Schema Overlap

- `employee_job_history` is defined in both `supabase_schema.sql` and `supabase_migration_existing_db.sql`.
- Many columns in `supabase_schema.sql` are added again conditionally by `supabase_migration_existing_db.sql`.
- Leave policies are defined in `supabase_leave_schema.sql` and replaced by `supabase_leave_rls_fix.sql`.
- Recovered employee leave/attendance policies coexist with later broad and manager policies; they are not consolidated.
- Core owner policies from root schemas coexist with different owner-policy names from `sql/045_core_rls_baseline.sql`.
- Storage policies are duplicated between `sql/024_employee_self_upload.sql` and `sql/043_employee_portal_fixes.sql`.
- The broad employee contact policy is defined in `041`, repeated in `043`, and dropped by `044`.
- Four tables retain both original and hardening timestamp triggers.

### Function Replacement Chains

- `admin_set_employee_portal_role`: `006` then `034`.
- `employee_submit_leave_request`: recovered nine-parameter function plus a ten-parameter warnings overload. The later file does not drop the older signature.
- `employee_record_clock_event`: recovered `supabase_migration_employee_rls.sql`, then `sql/023_fix_clock_event_rpc_entered_by.sql` fixes the UUID/text insertion.
- `record_advance_repayment`: `044` then `050`.
- `employee_cancel_advance`: `049`, then dropped/recreated with a new return type in `051`.

Alembic should represent only the intended final signatures, while data migration or compatibility needs must be assessed separately.

### Order-Sensitive Policy Collision

`supabase_migration_employee_company_read.sql` and `supabase_migration_grants.sql` create the same `employees: read own company` policy name. Only the grants file drops the old policy first. Reversing the intended order causes duplicate-policy failure.

### One-Company Model Versus Multi-Company Model

`supabase_schema.sql` creates a unique `companies.user_id` constraint. `sql/021_multi_company.sql` drops it and introduces branch-level `company_id` on only some tables. The final data model is not consistently branch-scoped.

## Idempotence Problems

The repository documentation says all numbered migrations are idempotent, but many are not.

Examples:

- Early migrations use unguarded `CREATE POLICY`, including `001`, `002`, `003`, `004`, and `007`.
- Both recovered migrations use unguarded `CREATE POLICY`; replaying either one after successful application fails on duplicate policy names.
- `sql/037_leave_manager_read.sql` creates three policies without guards or drops.
- `sql/038_appraisal_manager_update.sql` creates a policy without a guard.
- `sql/047_cme_tracking.sql` and `sql/048_incident_reports.sql` create policies without guards.
- `sql/046_phase4_db_hardening.sql` adds named constraints without checking whether they already exist.
- Root `supabase_schema.sql` uses `ADD CONSTRAINT IF NOT EXISTS` and `CREATE POLICY IF NOT EXISTS`, syntax that is unsupported on common PostgreSQL versions.

The Alembic rebuild must not assume replay safety based on these comments.

## Security Risks

### Missing Tenant Check in Portal Role Setter

The `sql/006_multi_level_leave.sql` version of `admin_set_employee_portal_role`:

- Verifies the caller owns a company.
- Restricts employee lookup to `user_id = auth.uid()`.

The final `sql/034_manager_role.sql` version removes both checks and selects the employee by ID alone. As a security-definer function, it allows a caller with execution rights to change the portal role of an employee outside the caller's company if the UUID is known.

### Payroll Replacement RPC

`replace_payroll_entries` in `sql/044_phase1_data_protection.sql`:

- Runs as security definer.
- Does not verify that `p_payroll_run_id` belongs to `auth.uid()`.
- Deletes entries for the supplied run before inserting replacements.
- Accepts `user_id` and `employee_id` from caller-controlled JSON.
- Does not set a fixed search path.
- Does not revoke PUBLIC execution.

This is a cross-tenant mutation risk.

### Security-Definer Search Paths

Several early security-definer functions omit `SET search_path = public` or an equivalent locked search path, including functions in:

- `sql/005_salary_advances.sql`
- `sql/006_multi_level_leave.sql`
- `sql/007_shift_roster.sql`
- Parts of `sql/044_phase1_data_protection.sql`

### Implicit PUBLIC Function Execution

Most earlier RPCs grant EXECUTE to `authenticated` but never revoke the default privilege from `PUBLIC`. The apparent role restriction is therefore incomplete. The five functions defined by the recovered files rely entirely on default execution privileges because those files include no function grants or revocations.

### Recovered Auth-Link Assumptions

`link_employee_account()` is security definer and uses a fixed public search path, but it links the first unlinked employee whose `work_email` exactly equals `auth.email()`. The schema does not add a database uniqueness constraint on normalized `work_email`. Duplicate or case-variant work emails can therefore make the selected employee dependent on row order, while the function's PUBLIC execution privilege remains implicit.

### Broad Employee Writes

- `employees_self_update_contact` in migrations `041` and `043` is row-level, not column-level. Before `044` runs, employees can update any column on their own employee row.
- `certifications_employee_update` does not restrict columns or status transitions. An employee can potentially set their own certification status to `verified`.
- `training_records_employee_update` likewise permits broad row updates for a caller-owned training record.

### Broad Grants

`sql/045_core_rls_baseline.sql` grants all table privileges on every current public table to `authenticated`. A missing or accidentally disabled RLS policy would expose a table immediately.

### Cross-Tenant Reads

`leave_types_authenticated_read` and `shifts_authenticated_read` permit every authenticated user to read all rows, regardless of owner or company.

### Clock-Event Ownership Ambiguity

- Base attendance policies treat `clock_events.user_id` as the row owner.
- `sql/022_admin_clock_events_access.sql` says employee-recorded events use the employee Auth UUID.
- `employee_record_clock_event()` inserts `v_emp.user_id`, which is generally the employer/admin UUID.
- Direct frontend inserts and security-definer inserts can therefore produce different ownership semantics.

The Alembic model must define whether `user_id` means tenant owner, actor Auth user, or both. A dedicated `company_user_id`/`tenant_id` and actor field would remove this ambiguity.

### Partial Multi-Company Isolation

Migration `021` adds `company_id` only to `employees` and `payroll_runs`; migration `053` adds it to roster/swap tables. Most other feature tables remain scoped only by admin `user_id`. Multiple branches under one admin therefore share many datasets unless indirect relationships or frontend filtering separate them.

Frontend filtering is not an authorization boundary.

## Implications for the Alembic Rebuild

### Establish One Authoritative Baseline

The first Alembic revision should be derived from the intended final schema, not by mechanically wrapping the 62 existing scripts. It must explicitly include:

- All 52 required application tables, or a documented decision to remove unused tables.
- The recovered `user_profiles` structure, reconciled with the final three-role model.
- `employees.auth_user_id` with deliberate nullability and uniqueness.
- Final constraints, indexes, foreign keys, and defaults.
- One timestamp trigger convention.
- Final RPC signatures only.
- Reproducible roles/grants or an explicit replacement authorization model.

### Recover Production Truth Before Finalizing

The deployed Supabase catalog should be dumped and compared with this inventory because recovered SQL may be historical and checked-in SQL still cannot establish the exact deployed definitions of:

- `user_profiles` and its final constraints/grants
- `employees.auth_user_id` and existing data integrity
- `link_employee_account()`
- `employee_submit_regularisation()`
- `employee_cancel_leave_request()`
- Both `employee_submit_leave_request()` overloads and whether production retains the older signature
- `employee_record_clock_event()` after its bug-fix replacement
- The still-missing `manager_get_leave_queue()`
- Existing bucket rows and manually created storage policies
- Any manually patched function definitions or grants

Production catalog inspection should cover `pg_class`, `pg_attribute`, `pg_constraint`, `pg_indexes`, `pg_proc`, `pg_trigger`, `pg_policies`, grants, `auth` dependencies, and storage metadata.

### Separate Schema, Data, and Authorization Migrations

Existing scripts mix schema changes, policy changes, grants, data backfills, and destructive updates. Alembic revisions should separate or clearly order:

- Structural DDL
- Data backfills
- Constraint validation
- Function/RPC creation
- RLS and grants
- Storage/bootstrap operations outside ordinary PostgreSQL when needed

Backfills requiring attention include:

- `employees.company_id`
- `payroll_runs.company_id`
- Roster/swap `company_id`
- `leave_types.probation_eligible`
- `salary_advances.repayment_start_month`
- `letter_requests.request_kind`

### Define Tenant Identity Explicitly

The current schema alternates among:

- Auth user ownership through `user_id`
- Employer/admin identity through `employees.user_id`
- Branch identity through `company_id`
- Employee actor identity through `auth_user_id`

The rebuild must define a consistent tenant key and propagate it to every tenant-owned table. RLS and service-layer authorization should use that key rather than frontend filters.

### Rebuild RPC Authorization Deliberately

Every retained security-definer function should:

- Use a fixed, minimal search path.
- Revoke execution from `PUBLIC` before granting it to intended roles.
- Validate caller identity, tenant ownership, target-row ownership, and allowed state transitions.
- Avoid accepting tenant IDs from untrusted JSON when they can be derived server-side.
- Avoid direct dependency on `auth.users` if the new platform replaces Supabase Auth.

The one missing frontend RPC, `manager_get_leave_queue()`, must be recovered from production or re-specified from application behavior before cutover. The recovered RPCs must still be compared with production and reviewed rather than copied blindly.

### Decide Whether RLS Survives the Migration

If PostgreSQL RLS remains part of the target architecture:

- Recreate policies from a reviewed authorization matrix, not from the accumulated duplicate set.
- Do not reproduce blanket authenticated grants without a reason.
- Add automated tenant-isolation tests for every table and RPC.
- Replace globally authenticated reads with tenant-scoped reads unless intentionally public.

If authorization moves fully to the API layer:

- Remove browser-direct database access before dropping RLS.
- Use a restricted application role rather than a service/superuser role.
- Preserve database constraints even when policy logic moves to the service.

### Treat Storage as a Separate Migration Surface

Alembic cannot by itself replace all Supabase Storage behavior. The migration plan needs a separate, repeatable storage bootstrap that defines:

- Buckets/containers
- Private/public settings
- MIME and size limits
- Object key conventions
- Upload/download/delete authorization
- Signed URL behavior
- Migration of existing objects and paths

The certification path mismatch must be resolved before object migration.

### Validate Existing Data Before Enforcing Final Constraints

Several final constraints were added `NOT VALID`, or were described only in comments. Before Alembic validates them, profile the deployed data for:

- Duplicate payroll runs under the expression unique index
- Duplicate advance repayments per payroll run
- Invalid status/category values
- Negative financial values
- Orphaned soft references such as `payroll_entries.employee_id`
- Null or inconsistent company scope
- Multiple employee rows linked to one Auth account
- Policy assumptions about globally unique `employees.auth_user_id`

### Preserve Only Intentional Compatibility

The rebuild should not preserve accidental duplicate policies, duplicate triggers, unsafe function versions, or order-dependent intermediate behavior. Compatibility is required only where application calls, persisted data, or staged cutover procedures depend on it.
