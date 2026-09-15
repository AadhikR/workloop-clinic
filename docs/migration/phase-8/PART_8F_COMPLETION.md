# Phase 8F completion

Status: implementation and local verification complete. Phase 8G is authorized but not started.

## Delivered

- Added direct-manager and active-delegate queues derived from the current reporting line, trusted
  business date, same-branch delegation, and eligible employee state. Added the selected-branch
  administrator queue for one-level pending and manager-approved requests.
- Added locked manager, delegate, and administrator decisions with the approved one- and two-level
  transitions. Request, balance, leave-domain audit, protected audit, and idempotency state share
  one transaction owner.
- Added same-key replay and changed-payload conflict handling. Optimistic request and delegation
  timestamps compare at the millisecond precision returned by the HTTP contract.
- Added administrator delegation list, create, update, and delete operations. Only future rows are
  mutable; active and expired rows remain history.
- Added the exact employee, request, leave type, balance, attachment, and permitted audit
  projections. No raw audit-table, employee-row, provider-key, or cross-branch response was added.
- Added the migration manager/delegate queue, administrator queue, decision controls, audit view,
  and delegation controls. The legacy queue, decision, delegation, and audit paths now fail closed.
- Completed the approval-workflow cutover with `migration-fastapi` as the only read and write
  authority. Notification delivery remains deferred to Phase 12.
- Added revision `e8f4c7b2a610` and recorded its delegation-version, protected authority, projection,
  domain-audit, and protected-audit amendments in `PART_8F_AMENDMENT_PROPOSAL.md`. No RLS policy,
  table grant, role, legal policy, constraint, or index changed.

## Evidence

- The complete backend gate passed with 469 tests, Ruff lint and formatting, strict Pyright,
  dependency validation, and the FastAPI import check.
- The complete frontend gate passed with 141 tests, the isolated migration build, main and
  single-file production builds, and targeted ESLint.
- A fresh `workloop-phase8f-verified` PostgreSQL 17 environment applied the migration twice,
  replayed the empty-schema chain, finished at the single `e8f4c7b2a610` head with no pending
  operations, and restored `d1e5f8a2c904` with an identical predecessor-function hash.
- The deep database verifier covered immediate reporting-line changes; current and future
  delegation scope; future delegation update and delete; active-row immutability; manager,
  delegate, and administrator transitions; self prevention; stale and repeated commands; identical
  replay; changed-payload conflict; concurrent decisions; balances; both audit stores; and safe
  audit projections.
- The stack restarted without rebuilding. Its database catalog fingerprint, both Keycloak signing
  keys, private synthetic object, and storage signing key were unchanged. Authentication passed
  before and after restart.
- The final browser journey rendered administrator and manager approval controls, created a future
  delegation, recorded one-level administrator and two-level manager decisions through the browser
  client, and completed the existing attachment, submission, cancellation, and session checks.
- Browser cleanup left zero synthetic companies, branches, employees, application users, profiles,
  requests, delegations, and attachments. All Phase 8F containers, networks, and eight named
  database, storage, and cache volumes were removed.
- `workloop-clinic_postgres_data` was not attached, upgraded, seeded, recreated, or deleted.
- The required GitHub result is recorded in the task report after the single phase push.
