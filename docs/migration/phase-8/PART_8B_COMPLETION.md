# Phase 8B completion

Status: complete. Phase 8B is closed and Phase 8C remains out of scope.

## Delivered

- Added FastAPI schemas, repositories, services, and routes for branch-scoped leave settings,
  leave types, and public holidays.
- Kept administrator reads and writes inside the selected branch. Staff reads use their trusted
  branch and return only active leave types.
- Used row locks and the existing `updated_at` version for settings and leave-type writes.
- Added idempotent default leave-type and named-holiday seeding through the existing unique keys.
- Soft-deactivation is the only leave-type removal path. Past holidays and holidays referenced by
  leave or attendance stay unchanged. Future unused holidays use guarded edits and deletion.
- Added the migration leave configuration page and API client. It has no Supabase import or call.
- Added `scripts/verify-phase-8b-configuration.py` for the three-table boundary, exact projections,
  route inventory, no-schema-change protection, and frontend provider checks.

## Evidence

- Existing focused backend checks: 65 passed.
- FastAPI application import passed.
- Migration frontend production build passed.
- Ruff checks and formatting passed for all new backend files.
- `git diff --check` passed.
- No Alembic revision, schema, constraint, index, RLS policy, grant, role, or protected function
  changed.
- `workloop-clinic_postgres_data` was not attached, upgraded, seeded, recreated, or deleted.
- The retained empty FRA1 default VPC was not changed.

The branch remains synthetic-only. The final commit, branch synchronization, and GitHub workflow
result are recorded in the phase handoff after the single push.
