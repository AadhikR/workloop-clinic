# Part 9A financial dependency inventory

## Purpose

This inventory fixes the owner of every known legacy financial dependency before a migration writer
is enabled. `Phase 9` means the named Phase 9 part. `Retained` means the legacy dependency may remain
available outside the migration flow until its later owner replaces it. It does not permit Supabase
access from a migration route.

## Browser screens and callers

| ID | Legacy caller | Dependency | Owner and disposition |
| --- | --- | --- | --- |
| UI-01 | `src/components/PayrollManager.jsx` | Payroll run list, edit, validation, approval, finalization, payslip, WPS, and Nafis orchestration | 9D through 9G replace the financial state calls. Phase 12 owns files, reports, and notifications. |
| UI-02 | `src/components/PayrollList.jsx` | Payroll list, deletion, and run selection | 9D replaces it. |
| UI-03 | `src/components/PayrollEditor.jsx` | Browser calculation, manual adjustments, automatic inputs, and save | 9D replaces draft calculation and save. 9E replaces automatic input reads. |
| UI-04 | `src/components/AdvancesManager.jsx` | Administrator advance decisions, schedules, repayments, and settlement | 9C replaces it. |
| UI-05 | `src/components/ExpensesManager.jsx` | Administrator expense queue, decisions, deletion, and receipt access | 9B replaces it. |
| UI-06 | `src/components/manager/ManagerExpenseQueue.jsx` | Direct-report expense queue and manager decisions | 9B replaces it. |
| UI-07 | `src/components/employee/EmpExpenses.jsx` | Employee expense submission, list, deletion, and receipt upload | 9B replaces it. |
| UI-08 | `src/components/employee/EmpAdvances.jsx` | Employee advance request, list, and withdrawal | 9C replaces it. |
| UI-09 | `src/components/employee/EmpPayslips.jsx` | Employee payslip list and details | 9F replaces the data path. Phase 12 owns PDF generation and download. |
| UI-10 | `src/components/SIFPreviewModal.jsx` | SIF preview, corrected rows, and file creation | 9G supplies the strict input projection. Phase 12 owns file bytes and download. |
| UI-11 | `src/components/NafisReportModal.jsx` | Nafis snapshot and report display | 9G owns the snapshot. Phase 12 owns report output. |
| UI-12 | `src/components/Dashboard.jsx` | Payroll aggregates and financial summaries | Phase 12 owns the replacement report projection. Retained until then. |
| UI-13 | `src/components/Reports.jsx` | Payroll, expense, and salary reports and exports | Phase 12 owns it. Retained until then. |
| UI-14 | `src/components/EndOfServiceScreen.jsx` | Advance balance and final-settlement deductions | Phase 11 owns it. Phase 9 exposes settled advance state but performs no offboarding calculation. |
| UI-15 | `src/components/RosterManager.jsx` | Published roster and actual-hours input | Phase 10 owns source mutation. 9E consumes only its approved projection. |
| UI-16 | `src/components/TasksPanel.jsx` | Expense, advance, and payroll task links | Phase 12 owns replacement tasks and notification delivery. |

## JavaScript utilities and storage methods

| ID | Legacy dependency | Call or behavior | Owner and disposition |
| --- | --- | --- | --- |
| JS-01 | `src/utils/storage.js` | `getPayrolls` | 9D |
| JS-02 | `src/utils/storage.js` | `savePayroll`, `savePayrolls`, `deletePayroll` | 9D |
| JS-03 | `src/utils/storage.js` | `createPayslipRecords` | 9F |
| JS-04 | `src/utils/storage.js` | payroll submit, approve, reject, recall, and approval-log calls | 9F |
| JS-05 | `src/utils/storage.js` | `getAdvances`, `saveAdvance`, `withdrawEmployeeAdvance` | 9C |
| JS-06 | `src/utils/storage.js` | `updateAdvanceBalance`, `getAdvanceRepayments`, `saveAdvanceRepayment` | 9C |
| JS-07 | `src/utils/storage.js` | `saveWpsTracking` | 9G |
| JS-08 | `src/utils/storage.js` | `getNafisReports`, `saveNafisReport` | 9G |
| JS-09 | `src/utils/storage.js` | `saveComplianceOverride` | 9G |
| JS-10 | `src/utils/storage.js` | `cascadeBankRoutingCodeToDrafts` | 9D replaces this with trusted branch-bank refresh. Generated runs never change. |
| JS-11 | `src/utils/payrollCalculator.js` | Float-based fixed pay, variable pay, deduction, net, and WPS-variable calculation | 9D replaces it with decimal arithmetic. Browser output becomes preview-only. |
| JS-12 | `src/utils/payrollValidation.js` | Payroll input and net-pay validation | 9D owns draft validation. 9F rechecks frozen sources before approval and generation. |
| JS-13 | `src/utils/advanceSchedule.js` | Installment amount, month sequence, and final installment | 9C replaces it. |
| JS-14 | `src/utils/expenseStorage.js` | Claim CRUD, decisions, receipt path, and payroll application helpers | 9B owns claim state and receipt binding. 9F owns application to a finalized payroll. |
| JS-15 | `src/utils/sifGenerator.js` | EDR rows, ordering, integer-AED values, and SIF bytes | 9G owns the input rows. Phase 12 owns CRLF file bytes. |
| JS-16 | `src/utils/sifCompliance.js` | WPS validation and override handling | 9G |
| JS-17 | `src/utils/payslipGenerator.js` | Payslip document generation | Phase 12. 9F owns the immutable data snapshot only. |
| JS-18 | `src/utils/reportUtils.js` | Financial report shaping and exports | Phase 12 |
| JS-19 | `src/utils/taskStorage.js` | Financial task rows | Phase 12 |
| JS-20 | `src/utils/notificationStorage.js` | Payroll and payslip notifications | Phase 12 |
| JS-21 | `src/utils/leaveEngine.js`, `src/utils/leaveStorage.js` | Approved leave and deduction inputs | Phase 8 owns the source. 9E consumes the approved read-only projection. |
| JS-22 | `src/utils/attendanceEngine.js`, `src/utils/attendanceStorage.js` | Attendance, overtime, absence, and late inputs | Phase 10 owns the source. 9E fails closed until the approved projection exists. |
| JS-23 | `src/utils/gratuityCalculator.js` | Final salary and end-of-service arithmetic | Phase 11. Its month-day rule is not a Phase 9 payroll contract. |

## Database objects and RPCs

| ID | Legacy object | Dependency | Owner and disposition |
| --- | --- | --- | --- |
| DB-01 | `payroll_runs`, `payroll_entries` | Draft, totals, approval state, WPS state, and employee lines | 9D through 9G use the Phase 4 PostgreSQL schema. |
| DB-02 | `payroll_approval_logs` | Submit, recall, approve, and reject history | 9F |
| DB-03 | `payslips` | Immutable employee payroll snapshots | 9F |
| DB-04 | `salary_advances`, `advance_repayments` | Requests, schedules, balances, and applied repayments | 9C and 9F |
| DB-05 | `expense_claims` | Claims, manager decisions, administrator decisions, receipt reference, and payroll link | 9B and 9F |
| DB-06 | `wps_entries` | Per-employee payment state and rejection | 9G |
| DB-07 | `nafis_reports` | Branch-period snapshot | 9G |
| DB-08 | `compliance_overrides` | Reasoned immutable override | 9G |
| DB-09 | `supabase_schema.sql` | Original financial tables, policies, and grants | Reference only. Alembic remains authoritative. |
| DB-10 | `supabase_migration_payslips.sql` | Legacy payslip creation | Replaced by 9F. |
| DB-11 | `sql/001_emiratization.sql` | Nafis schema and logic | 9G reconciles it with the Phase 4 schema. |
| DB-12 | `sql/005_salary_advances.sql` | Advance schema and policies | 9C uses the Phase 4 form. |
| DB-13 | `sql/008_wps_tracking.sql` | WPS schema and policies | 9G uses the Phase 4 form. |
| DB-14 | `sql/014_expense_claims.sql` | Expense schema and policies | 9B uses the Phase 4 form. |
| DB-15 | `sql/017_payroll_approval.sql` | Payroll approval schema and transitions | 9F uses the Phase 4 and Phase 5 contract. |
| DB-16 | `sql/021_multi_company.sql` | Tenant and branch scope | Phases 4, 5, and 7 already replace it. Every Phase 9 repository remains scoped. |
| DB-17 | `sql/030_expense_manager_approval.sql` | Manager decision state and RPCs | 9B replaces the RPCs with FastAPI services. |
| DB-18 | `sql/036_advance_rejection_reason.sql` | Advance rejection reason | 9C retains the Phase 4 field and reason rule. |
| DB-19 | `sql/044_phase1_data_protection.sql`, `sql/045_core_rls_baseline.sql`, `sql/046_phase4_db_hardening.sql` | RLS, grants, protected functions, and audit | Phase 5 is canonical. Parts 9B through 9G add only the amendments approved in 9A. |
| DB-20 | `sql/049_feature_toggles.sql` | Legacy feature flags | Cutover records replace these as migration authority. |
| DB-21 | `sql/050_advance_repayment_scheduling.sql` | Advance schedule and repayment behavior | 9C |
| DB-22 | `sql/051_employee_request_actions.sql` | Employee self actions | 9B and 9C replace these RPCs. |
| DB-23 | `employee_submit_expense`, `employee_delete_expense` | Employee expense mutation RPCs | 9B disables their legacy caller after cutover. |
| DB-24 | `manager_get_expense_queue`, `manager_approve_expense`, `manager_reject_expense` | Manager expense RPCs | 9B replaces them. |
| DB-25 | `employee_request_advance`, `employee_cancel_advance` | Employee advance RPCs | 9C replaces them. |
| DB-26 | `replace_payroll_entries` | Protected atomic replacement of a draft run's entries | 9D retains it behind FastAPI validation and locking. |
| DB-27 | `record_advance_repayment` | Protected repayment insertion and balance reduction | 9C retains it behind FastAPI validation and locking. 9F uses it during finalization. |
| DB-28 | legacy employee, manager, and administrator financial RLS roots | Browser database access | Removed from migration flows. FastAPI roles and service grants are the only migration authority. |

## Storage, files, tasks, reports, and notifications

| ID | Dependency | Owner and disposition |
| --- | --- | --- |
| EXT-01 | Private Supabase bucket `expense-receipts` | 9B uses the Phase 8 private-storage interface, not the bucket API. Phase 11 owns production adapter selection and recovery. |
| EXT-02 | Browser-supplied receipt URL | Rejected as authority. 9B binds a server-created receipt row to a verified private object. |
| EXT-03 | One-hour legacy receipt signed URL | Replaced in 9B by a five-minute authorized download URL. |
| EXT-04 | Payslip PDF and ZIP bytes | Phase 12 |
| EXT-05 | SIF bytes and download | Phase 12 |
| EXT-06 | Payroll, expense, WPS, and Nafis CSV or PDF reports | Phase 12 |
| EXT-07 | Expense, advance, and payroll task creation | Phase 12 |
| EXT-08 | Approval, finalization, and payslip notifications | Phase 12 |
| EXT-09 | Closed attendance period and approved overtime | Phase 10 source, 9E consumer |
| EXT-10 | Published roster actual hours | Phase 10 source, 9E consumer |
| EXT-11 | Approved leave and deduction projection | Phase 8 source, 9E consumer |

## Coverage result

The inventory assigns all known financial callers and data paths to Parts 9B through 9G or to the
named Phase 10, 11, or 12 owner. Phase 13 removes the retained Supabase build after those owners have
replaced it. No retained dependency is callable from a migration route.
