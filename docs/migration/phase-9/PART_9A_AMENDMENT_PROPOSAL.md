# Part 9A schema and audit amendments

## Decision

The project owner authorized Phase 9A and directed the task to proceed without pausing for routine
contract approvals. This document therefore approves the exact amendment envelope below for Parts
9B through 9G. It does not create a revision or change runtime behavior. Each later part owns its
revision, downgrade, model changes, focused verifier, and full database gate.

The review found no need for a new human role. `admin`, `manager`, and `employee` remain the only
roles. FastAPI repositories retain tenant and branch predicates even when RLS also applies.

## 9B receipt metadata

Add `expense_receipts`, patterned after `leave_attachments`, with these fields:

- identity and scope: `id`, `company_id`, `branch_id`, `employee_id`, nullable `expense_claim_id`;
- ownership: `created_by_app_user_id`;
- upload claim: unique `submission_token_digest`, `token_consumed_at`, and `expires_at`;
- private object metadata: `object_key`, `file_name`, `content_type`, `size_bytes`, and `sha256`;
- lifecycle: `status`, `uploaded_at`, `attached_at`, `created_at`, and `updated_at`.

The status set is `pending`, `uploading`, `staged`, `attached`, `cleanup_pending`, and `removed`.
Allow at most one receipt per claim. Add composite foreign keys for company and branch scope, an
employee-scope index, an expiry index for staged cleanup, and checks equivalent to the Phase 8
attachment lifecycle. Extend `storage_operations.entity_type` to admit `expense_receipt`.

The existing `expense_claims.receipt_url` remains empty for new migration claims. A cutover
converter may import a safe legacy reference into evidence, but it must not turn that URL into
private-object authority. Phase 13 may remove the column after receipt migration and recovery are
complete.

Add RLS policies for the receipt owner, current direct manager, and selected-branch administrator.
Grant no table mutation to browser roles. `workloop_runtime` receives only the service operations
needed by the repository. Add protected audit actions `expense_receipt_uploaded` and
`expense_receipt_cleanup_requested`, with the same storage-operation linkage checks used for leave
attachments.

## 9C advance audit correction

The existing advance tables and `record_advance_repayment` function are sufficient. No new table or
role is approved. The current base audit allowlist names `disbursement_date`, but the canonical
column is `disbursed_date`. The 9C audit wrapper must validate the canonical name and must not pass a
field that does not exist.

Add protected actions:

| Action | Entity | Exact changed fields |
| --- | --- | --- |
| `salary_advance_requested` | `salary_advance` | `amount`, `reason`, `repayment_months`, `repayment_start_month`, `monthly_deduction`, `outstanding_balance`, `status` |
| `salary_advance_schedule_changed` | `salary_advance` | `amount`, `repayment_months`, `repayment_start_month`, `monthly_deduction`, `outstanding_balance` |
| `salary_advance_withdrawn` | `salary_advance` | `status`, `rejection_reason` |
| `salary_advance_approved` | `salary_advance` | `status`, `disbursed_date`, `monthly_deduction`, `outstanding_balance` |
| `salary_advance_rejected` | `salary_advance` | `status`, `rejection_reason` |
| `salary_advance_repayment_recorded` | `salary_advance` | `outstanding_balance`, `status` |
| `salary_advance_settled` | `salary_advance` | `status`, `outstanding_balance` |

Repayment metadata is limited to `repayment_id`, `payroll_run_id`, and `repayment_kind`. The kind is
`manual`, `payroll`, or `settlement`. All referenced rows must share trusted company and branch
scope. The wrapper rejects unknown metadata.

## 9D immutable input snapshot

Add `payroll_entries.source_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb`. The server writes a closed
object containing salary values and effective date, employment dates, employee source version,
manual adjustment metadata, and automatic input rows with source type, ID, version, inputs, and
rounded result. Public requests cannot supply automatic source fields.

Add `payroll_runs.source_snapshot_digest text NOT NULL DEFAULT ''`. It is empty only before the first
successful refresh. A refreshed draft stores the lowercase SHA-256 of the canonical entry snapshots.
Submission requires a 64-character digest. Recall retains it; refresh replaces it. Generation
recomputes it and fails on mismatch.

Update `replace_payroll_entries` so each validated replacement writes `source_snapshot` and updates
the run digest and totals in the same transaction. Keep execution restricted to
`workloop_runtime`. The function does not calculate money or infer scope.

Add protected actions:

| Action | Entity | Exact changed fields |
| --- | --- | --- |
| `payroll_draft_created` | `payroll_run` | `period`, `payment_date`, `sequence_no`, `scr_bank_routing_code`, `status`, `approval_status` |
| `payroll_draft_refreshed` | `payroll_run` | `source_snapshot_digest`, `employee_count`, `total_disbursed`, `updated_at` |
| `payroll_entries_replaced` | `payroll_run` | `source_snapshot_digest`, `employee_count`, `total_disbursed`, `updated_at` |
| `payroll_draft_deleted` | `payroll_run` | `status` |

Deletion audit metadata carries only a canonical summary digest because the row is removed in the
same transaction.

## 9E source application

No Phase 10 table or policy is approved here. Phase 10 owns its source schema. 9E may add no fallback
column that treats provisional browser data as final.

Add `payroll_inputs_refreshed` for `payroll_run` with changed fields
`source_snapshot_digest`, `employee_count`, `total_disbursed`, and `updated_at`. Metadata contains
counts and canonical digests for `leave`, `attendance`, `roster`, `expense`, and `advance`, not raw
salary, bank, government, or receipt values.

## 9F approval and generation audit

The existing payroll actor columns and `payroll_approval_log` table are sufficient. The synthetic
fixtures need a second administrator in the same branch so separation tests do not weaken the rule.

Wrap the existing audit actions to match canonical columns:

| Action | Exact changed fields |
| --- | --- |
| `payroll_submitted` | `approval_status`, `submitted_by_app_user_id`, `submitted_for_approval_at` |
| `payroll_recalled` | `approval_status`, `submitted_by_app_user_id`, `submitted_for_approval_at` |
| `payroll_approved` | `approval_status`, `approved_by_app_user_id`, `approved_at` |
| `payroll_rejected` | `approval_status`, `rejection_reason`, `rejected_by_app_user_id`, `rejected_at` |
| `payroll_generated` | `status`, `total_disbursed`, `employee_count` |
| `expense_paid` | `status`, `payroll_run_id` |

Add `payslips_issued` for `payroll_run`, with changed fields `status`, `total_disbursed`, and
`employee_count`. Metadata contains payslip count and a canonical snapshot digest. It contains no
employee financial values. Every action verifies the trusted actor and current row state.

## 9G WPS and Nafis audit

The base `payroll_wps_changed` rule refers to nonexistent `sif_status`. Replace it with exact
canonical fields. Add protected actions:

| Action | Entity | Exact changed fields |
| --- | --- | --- |
| `payroll_wps_changed` | `payroll_run` | `wps_status`, `wps_submitted_at`, `wps_confirmed_at`, `wps_reference_no` |
| `wps_entry_paid` | `payroll_entry` | `wps_payment_status`, `wps_rejection_reason` |
| `wps_entry_rejected` | `payroll_entry` | `wps_payment_status`, `wps_rejection_reason` |
| `sif_projection_recorded` | `payroll_run` | `wps_status`, `updated_at` |
| `compliance_override_created` | `compliance_override` | `rule_code`, `reason` |
| `nafis_snapshot_replaced` | `nafis_report` | `total_headcount`, `emirati_count`, `ratio_percent`, `required_percent`, `compliant`, `snapshot`, `generated_at` |

SIF projection metadata contains only mode, row count, integer total, and SHA-256 digest. WPS entry
metadata may contain the corrected projection digest. The Nafis audit metadata contains the period
and source digest, not the full snapshot.

## Constraints, indexes, and downgrade rules

Each part must add only the constraints and indexes named above or required by its foreign keys. New
JSON fields receive server validation plus database shape checks for object type and digest format.
RLS remains forced where the surrounding financial table uses forced RLS. Direct grants cannot
bypass protected functions.

Each revision is append-only and has one exact predecessor. Its downgrade removes only objects that
revision added and restores the prior audit function name and grants. A downgrade must fail safely
if later financial data would be made invalid. Parts 9B through 9G prove empty-schema upgrade,
repeatable current-head upgrade, and exact predecessor restoration under the migration workflow.
