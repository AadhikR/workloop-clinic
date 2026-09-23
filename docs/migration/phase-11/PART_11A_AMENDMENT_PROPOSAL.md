# Part 11A amendment proposal

## Status

This proposal is documentation only. It reserves append-only revisions and fixes the intended schema
before implementation. No revision exists yet. Each implementing part must prove exact predecessor
rollback and empty-schema replay.

## Revision sequence

| Part | Revision | Down revision | Purpose |
| --- | --- | --- | --- |
| 11B | `d8f0a2c4e6b1` | `c6e8a1b3d927` | File-security scan queue, scanner role, grants, RLS, audit actions, and common recovery indexes. |
| 11C | `e9a1b3d5f7c2` | `d8f0a2c4e6b1` | Document scan linkage and metadata, insurance lock timestamps, and contract audit actions. |
| 11D | `f0b2c4d6e8a3` | `e9a1b3d5f7c2` | Asset, training, certification, CME lock fields and private-file linkage. |
| 11E | `a1c3e5f7b9d4` | `f0b2c4d6e8a3` | Appraisal template identity, mutable timestamps, incident actions, and audit coverage. |
| 11F | `b2d4f6a8c0e5` | `a1c3e5f7b9d4` | Request snapshot and optimistic-lock fields. |
| 11G | `c3e5a7b9d1f6` | `b2d4f6a8c0e5` | Task provenance and immutable settlement records under settlement policy `1.0.0`. |

## 11B file-security scan queue

Create `public.file_security_scans`:

| Column | Type | Null | Default |
| --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` |
| `company_id` | `uuid` | No | none |
| `branch_id` | `uuid` | No | none |
| `employee_id` | `uuid` | Yes | none |
| `created_by_app_user_id` | `uuid` | No | none |
| `entity_type` | `text` | No | none |
| `entity_id` | `uuid` | No | none |
| `object_key` | `text` | No | none |
| `content_type` | `text` | No | none |
| `size_bytes` | `bigint` | No | none |
| `sha256` | `text` | No | none |
| `status` | `text` | No | `'pending'` |
| `scanner_name` | `text` | No | `''` |
| `scanner_definition` | `text` | No | none |
| `result_signature` | `text` | No | `''` |
| `attempt_count` | `integer` | No | `0` |
| `last_error_code` | `text` | No | `''` |
| `next_attempt_at` | `timestamptz` | Yes | none |
| `claimed_at` | `timestamptz` | Yes | none |
| `lease_expires_at` | `timestamptz` | Yes | none |
| `scanned_at` | `timestamptz` | Yes | none |
| `valid_until` | `timestamptz` | Yes | none |
| `created_at` | `timestamptz` | No | `statement_timestamp()` |
| `updated_at` | `timestamptz` | No | `statement_timestamp()` |

Use restrictive company, branch, optional employee, and creator-profile foreign keys. Add
`uq_file_security_scans_id_company_id_branch_id`, unique `(entity_type,entity_id)`, and unique
`object_key`. The entity type allowlist is `leave_attachment`, `expense_receipt`,
`employee_document`, `training_evidence`, and `certification_evidence`. Content type, size, SHA-256,
and object-key checks are identical to the Phase 8 file contract. `scanner_name`, definition,
signature, and error code use 1 through 64 lowercase letters, digits, dot, underscore, or hyphen
when nonempty.

Status is `pending`, `claimed`, `clean`, `infected`, or `failed`:

- pending has attempt zero, no result, error, claim, lease, scan, validity, or retry;
- claimed has attempt one through eight, claim and future lease, and no result, error, scan,
  validity, or retry;
- clean has a scanner name, definition, result signature, scan time, and validity exactly 30 days
  later, with no error, claim, lease, or retry;
- infected has scanner name, definition, result signature, and scan time, with no validity, error,
  claim, lease, or retry; and
- failed has attempt one through eight, one safe error code, and a retry only below attempt eight.

Create claim index `(status,next_attempt_at,lease_expires_at,created_at,id)`, expiry index
`(valid_until,id) WHERE status='clean'`, and entity index `(entity_type,entity_id)`. Do not index or
log object keys.

Create direct login `workloop_file_scanner` as `LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEDB
NOCREATEROLE NOREPLICATION`. Its credential is absent from web and reconciler containers. Under
actor kind `scheduled_job` and actor key `file_security_scan`, a null-scope transaction can discover
and claim due rows below eight attempts, plus expired leases at eight for no-call terminalization.
After copying scope, it can update only state fields on that scan row. It receives no grant on a
business table, `audit_events`, or `storage_operations`.

Runtime can insert a pending scan only in the same authorized transaction that commits uploaded
domain metadata and upload success. Runtime can read only scan ID, entity identity, safe state,
scanner definition, scanned time, and valid-until time within current scope. It cannot select object
key through ordinary repository projections. The scanner role selects the object fields needed for
the provider call.

Extend protected audit actions with `file_scan_clean`, `file_scan_infected`,
`file_scan_retry_scheduled`, `file_scan_terminal`, `storage_backup_completed`,
`storage_restore_verified`, `storage_credential_rotated`, and `storage_manual_requeue`. Metadata is
restricted to operation or scan UUID, entity type, attempt number, scanner definition, backup
manifest digest, and safe error code. No action accepts a filename, object key, signed URL, file
digest, employee ID, or free text.

## Private-file linkage

Add nullable composite scan references during the empty-baseline migration path, then require a
current clean scan in service logic before signing:

| Table | Added columns |
| --- | --- |
| `leave_attachments` | `file_security_scan_id uuid`; composite FK `(file_security_scan_id,company_id,branch_id)` to scan identity. |
| `expense_receipts` | Same scan linkage. |
| `employee_documents` | `content_type text`, `sha256 text`, `file_security_scan_id uuid`, `created_by_app_user_id uuid`, `updated_at timestamptz NN statement_timestamp()`. Existing `file_size` and internal `storage_path` remain authoritative metadata. |
| `training_records` | `content_type text`, `size_bytes bigint`, `sha256 text`, `file_security_scan_id uuid`, `created_by_app_user_id uuid`, `updated_at timestamptz NN statement_timestamp()`. Existing internal `storage_path` and `file_name` remain. |
| `certifications` | The same five private-file fields and `updated_at`. |

For employee documents, training evidence, and certification evidence, the five object metadata
fields are all null or all present. A complete set has normalized filename, internal key, size 1
through 10,485,760, allowlisted media type, lowercase SHA-256, and same-scope scan link. The browser
never receives internal `storage_path`, SHA-256, or scan internals.

## Optimistic-lock fields

Add `updated_at timestamptz NOT NULL DEFAULT statement_timestamp()` and the canonical update trigger
where the table does not already have one:

- `employee_documents`, `insurance_policies`, `employee_insurance`, and `insurance_dependants` in
  11C;
- `assets`, `training_records`, `certifications`, and `cme_requirements` in 11D;
- `appraisal_cycles` and `appraisal_sections` in 11E; and
- `letter_requests` in 11F.

`appraisals` and `incident_reports` already have `updated_at`. Section updates must advance both the
section and parent appraisal timestamp. Append-only `employee_contracts` does not gain an update
path. Offboarding timestamps are added with the 11G fields below.

## Domain amendments

### Employee documents, insurance, and contracts

Add document review and file audit actions, insurance policy and coverage actions, and
`employment_contract_recorded`. Each action validates the current row and trusted actor. Insurance
policy delete remains guarded by coverage references. Coverage replacement keeps the existing
unique employee constraint. Contract rows remain append-only and receive no UPDATE or DELETE grant.

### Assets, training, certifications, and CME

Add `updated_at` to `assets` and the training tables named above. Add audit actions for asset create,
edit, state, assign, return, and delete; training enrolment and completion; certification submit,
verify, reject, and cleanup; and CME target maintenance. Keep one open assignment and retained
history. Keep planned-only training deletion and pending or rejected certification deletion.

### Appraisals and incidents

Add `template_version text NOT NULL DEFAULT 'clinic-v1'` to `appraisals`, checked as
`^[a-z][a-z0-9-]{0,31}$`. Add the two timestamps named above. The service enforces the five fixed
sections, unique names, total weight `7.50`, full rating before review, and parent locking. Existing
database rating bounds remain.

Add audit actions for cycle create, edit, activate, generate, close, and guarded delete; section
rating, review, calibration; incident create, investigate, corrective action, and close. Incident
audit metadata contains only type, severity, from state, and to state. It excludes descriptions,
people, causes, actions, location, department, and notes.

### Letter and custom requests

Add these trusted snapshot columns to `letter_requests`:

| Column | Type | Null | Default |
| --- | --- | --- | --- |
| `employee_name_snapshot` | `text` | No | `''` |
| `job_title_snapshot` | `text` | No | `''` |
| `department_snapshot` | `text` | No | `''` |
| `employment_start_date_snapshot` | `date` | Yes | none |
| `branch_name_snapshot` | `text` | No | `''` |
| `basic_salary_snapshot` | `numeric(12,2)` | Yes | none |
| `allowance_snapshot` | `numeric(12,2)` | Yes | none |
| `updated_at` | `timestamptz` | No | `statement_timestamp()` |

Salary snapshots are present only for a letter type that requires them. Add checks for nonnegative
money and required snapshot fields in decided rows. Add submit, complete, and reject audit actions.
No HTML or generated bytes enter PostgreSQL.

## 11G task provenance and settlement

Add to `offboarding_tasks`:

| Column | Type | Null | Default |
| --- | --- | --- | --- |
| `source` | `text` | No | `'template'` |
| `template_id` | `uuid` | Yes | none |
| `updated_at` | `timestamptz` | No | `statement_timestamp()` |

`source` is `template` or `custom`. Template source requires `template_id`; custom source requires
null. The same-scope template FK uses `ON DELETE RESTRICT`. Add unique
`(checklist_id,template_id) WHERE template_id IS NOT NULL`. Runtime delete policy and grant permit
only an incomplete custom task while its checklist is in progress.

Add `updated_at` to `offboarding_checklists`. Add one-to-one nullable
`final_settlement_id` only after the settlement table exists.

Create append-only `settlement_policy_versions`. Each row contains a jurisdiction key, semantic
version, effective date, canonical JSON policy, `sha256:` digest, approval authority, approval time,
and creation time. Policy `1.0.0` records the project owner's delegated decision. No row can update
or delete.

Create `final_settlements` after policy approval:

| Column group | Exact fields |
| --- | --- |
| Identity | `id`, `company_id`, `branch_id`, `employee_id`, `checklist_id`, `policy_version_id` as UUIDs, all required. |
| Source proof | `source_snapshot jsonb`, `source_digest text`, `source_captured_at timestamptz`, all required. Digest uses `sha256:` plus 64 lowercase hex. |
| Earnings | `final_salary`, `leave_encashment`, `gratuity`, `notice_pay`, `other_earnings`, each `numeric(14,2)` nonnegative. |
| Deductions | `advance_deduction`, `asset_deduction`, `notice_deduction`, `other_deductions`, each `numeric(14,2)` nonnegative. |
| Totals | `gross_amount`, `total_deductions`, and `net_amount` as `numeric(14,2)`. Gross and deductions are nonnegative. Net behavior waits for owner approval. |
| Evidence | `calculation_breakdown jsonb`, `completed_by_app_user_id uuid`, `reviewed_by_app_user_id uuid`, and `completed_at timestamptz`, all required. The reviewer and completer are the same second administrator and must differ from the checklist initializer. |

Use restrictive same-scope FKs and unique checklist ID. Runtime gets INSERT and SELECT through the
named completion workflow only. No UPDATE or DELETE grant or policy exists. A protected audit action
validates source digest, policy version, actor, checklist completion, and exact totals.

## Explicit non-amendments

- Do not change Phase 8 leave or Phase 9 expense authorization.
- Do not add manager document, insurance dependant, incident, or offboarding access.
- Do not add self appraisal rating.
- Do not add a notification, task, dashboard, report, expiry, CSV, PDF, ZIP, SIF, or rendering table.
- Do not add a cloud resource, external credential, or production retention schedule.
- Do not remove Supabase or legacy tables in Phase 11.
