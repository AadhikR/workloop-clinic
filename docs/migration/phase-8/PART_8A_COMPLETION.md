# Phase 8A completion record

Status: prepared for project-owner review. Phase 8A remains documentation-only and stops before Phase 8B.

## Scope completed

- Mapped all seven canonical leave tables, legacy readers and writers, leave RPCs, converters, calculations, object paths, callers, protected-function dependencies, and downstream consumers.
- Defined camelCase projections, decimal/date/null rules, server-owned authority, trusted UAE business date, calendar-year derivation, status transitions, balance effects, attachment binding, transaction ownership, idempotency, and rollback order.
- Assigned payroll, attendance, roster, storage and offboarding, notifications, tasks, dashboards, reports, and exports to Phases 9 through 12.
- Created five preparation-state cutover records under `cutover/`.
- Added the focused structural verifier at `scripts/verify-phase-8a-contract.py`.
- Recorded amendment proposals without changing schema, RLS, grants, roles, protected functions, storage, or Alembic history.

## Owner decisions and review gates

The contract adopts `public.workloop_business_date()` and calendar-year leave derivation, keeps all authority-sensitive values server-owned, and removes `Info Requested` from the persisted status set. The attachment path is blocked pending approval of a minimum Phase 11-owned signing and orphan-recovery prerequisite. Legal leave-policy interpretation and every schema, constraint, index, RLS, grant, role, protected-function, audit, or storage amendment require project-owner review before implementation.

## Verification evidence

- `python scripts/verify-phase-8a-contract.py` passed with five preparation records and 42 unique inventory IDs.
- The five records are intended for `node scripts/cutover-record-validator.mjs` validation. Their evidence digests must be refreshed if the contract or evidence files change.
- `git diff --check` passed.
- Alembic head remains `8f6b2d1a4c70`; no revision was created or modified.
- No backend, frontend, browser, Docker, migration, authentication, storage, cloud, or full-stack gate was run because the phase changed documentation and a structural verifier only.

## Source control and stop condition

The starting commit was `e9295e9a818a4b062be6c0451d77a82316d5a916` on `migration/fastapi-keycloak`, with the working tree clean and one local commit ahead of origin. This record does not claim a commit, push, or GitHub result. Commit and push require the project-owner decision that the contract and amendment proposals are settled. Do not begin Phase 8B, create an Alembic revision, change runtime behavior, touch `workloop-clinic_postgres_data`, or change the retained empty FRA1 default VPC from this phase.
