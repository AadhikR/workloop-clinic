# Phase 8A completion record

Status: complete. The project owner authorized Phase 8B after reviewing the Phase 8A package. Phase 8A itself remained documentation-only.

## Scope completed

- Mapped all seven canonical leave tables, legacy readers and writers, leave RPCs, converters, calculations, object paths, callers, protected-function dependencies, and downstream consumers.
- Defined camelCase projections, decimal/date/null rules, server-owned authority, trusted UAE business date, calendar-year derivation, status transitions, balance effects, attachment binding, transaction ownership, idempotency, and rollback order.
- Assigned payroll, attendance, roster, storage and offboarding, notifications, tasks, dashboards, reports, and exports to Phases 9 through 12.
- Created five cutover records under `cutover/`. The configuration record is complete; the four records for later subphases remain in preparation.
- Added the focused structural verifier at `scripts/verify-phase-8a-contract.py`.
- Recorded amendment proposals without changing schema, RLS, grants, roles, protected functions, storage, or Alembic history.

## Owner decisions and review gates

The contract adopts `public.workloop_business_date()` and calendar-year leave derivation, keeps all authority-sensitive values server-owned, and removes `Info Requested` from the persisted status set. The attachment path is blocked pending approval of a minimum Phase 11-owned signing and orphan-recovery prerequisite. Legal leave-policy interpretation and every schema, constraint, index, RLS, grant, role, protected-function, audit, or storage amendment require project-owner review before implementation.

## Verification evidence

- `python scripts/verify-phase-8a-contract.py` passed with five records and 42 unique `phase8a-*` inventory IDs.
- All five records passed `node scripts/cutover-record-validator.mjs` after their source and evidence digests were refreshed.
- `git diff --check` passed.
- Alembic head remains `8f6b2d1a4c70`; no revision was created or modified.
- The 8A verifier now proves that every cutover dependency ID matches the inventory or amendment register.

## Source control and stop condition

The settled commit, branch synchronization, and GitHub result are reported in the Phase 8B handoff after its single push. Phase 8C remains unauthorized. Do not create an Alembic revision, change schema or database security, touch `workloop-clinic_postgres_data`, or change the retained empty FRA1 default VPC without separate authorization.
