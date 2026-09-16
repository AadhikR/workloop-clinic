# Phase 9B completion

Status: implementation and local verification complete. Phase 9C is authorized but not started.

## Delivered

- Added employee expense submission, listing, and deletion; current direct-manager queues and
  decisions; and selected-branch administrator queues, decisions, and deletion.
- Enforced the approved state transitions, self-decision restrictions, final-actor separation,
  fixed-decimal inputs, database business date, optimistic timestamps, safe missing responses,
  scoped cursors, exact replay, and changed-payload conflicts.
- Added private PDF, PNG, and JPEG receipt submission, upload, binding, download, expiry, and
  cleanup. Object keys remain server-owned, download links last five minutes, and cleanup uses the
  durable storage-operation outbox.
- Added revision `f9b2c4d6e8a1` with `expense_receipts`, scoped foreign keys, lifecycle checks,
  indexes, forced RLS, least-privilege grants, protected claim and reporting-line locks, protected
  receipt audit actions, and `expense_claim` idempotency replay support.
- Added the employee, manager, and administrator migration views with strict projections and no
  Supabase dependency.
- Froze legacy expense claim, queue, decision, deletion, and receipt paths. The legacy payroll
  reimbursement helpers remain available until Part 9F owns expense application to payroll.
- Completed the expense cutover with `migration-fastapi` as the sole claim and receipt read/write
  authority. Phase 11 still owns production storage selection and common recovery proof.

## Evidence

- The backend gate passed 473 tests, Ruff lint and formatting, strict Pyright, application import,
  and OpenAPI generation.
- The focused frontend gate passed the expense client and legacy-freeze tests, targeted ESLint,
  and the migration production build. The existing browser authentication journey also passed.
- A fresh `workloop-phase9b-9a72` PostgreSQL 17 environment applied the migration repeatedly,
  finished at the single `f9b2c4d6e8a1` head with no model/schema drift, restored
  `e8f4c7b2a610` with an identical predecessor-function digest, and replayed the head.
- The deep database verifier covered employee, direct-manager, and selected-branch scope;
  reporting-line changes; fixed-decimal claims; receipt binding; stale commands; identical replay;
  changed-payload conflict; concurrent decisions; final-actor separation; RLS; protected audit;
  staged expiry; deletion cleanup; and durable storage operations.
- The stack restarted without rebuilding its data volumes. The database catalog fingerprint,
  Keycloak signing keys, private synthetic object, and storage signing key survived the restart;
  authentication passed afterward.
- `workloop-clinic_postgres_data` was not attached, upgraded, seeded, recreated, or deleted.
- The required GitHub result is recorded in the task report after the single phase push.
