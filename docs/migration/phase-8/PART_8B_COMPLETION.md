# Phase 8B completion

Status: complete. Phase 8B is closed and Phase 8C remains out of scope.

## Delivered

- Added FastAPI schemas, repositories, services, and routes for branch-scoped leave settings,
  leave types, and public holidays.
- Kept administrator reads and writes inside the selected branch. Staff reads use their trusted
  branch and return only active leave types.
- Used row locks and the existing `updated_at` version for settings and leave-type writes.
- Required exact settings and leave-type versions for updates, advanced each successful version by at least one millisecond, and required exact holiday snapshots for edits and deletion.
- Added idempotent default leave-type and named-holiday seeding through the existing unique keys.
- Soft-deactivation is the only leave-type removal path. Past holidays and holidays referenced by
  any leave request or attendance stay unchanged. Future unused holidays use guarded edits and deletion. Consumer-table locks close concurrent insertion races during these checks.
- Added the migration leave configuration page and API client. It has no Supabase import or call.
- Froze every legacy Supabase configuration entry point after the migration reader and writer became authoritative. Leave requests, balances, attachments, approvals, and later consumers remain untouched.
- Added `scripts/verify-phase-8b-configuration.py` for the three-table boundary, exact projections,
  route inventory, pagination, focused tests, no-schema-change protection, and frontend provider checks.
- Added `scripts/verify-phase-8b-configuration-database.py` for transaction, branch, concurrency, seed, and retained-row checks in the isolated CI stack.

## Evidence

- Complete backend suite: 439 passed. The focused Phase 8B service suite contributed seven tests.
- Complete frontend unit suite: 125 passed. The focused configuration and legacy-freeze suites contributed six tests.
- FastAPI application import passed.
- Legacy and migration frontend production builds passed, including the isolated migration graph check.
- Ruff checks and formatting, strict Pyright, and dependency checks passed.
- The Phase 8A and 8B structural verifiers passed, as did all five cutover record validators.
- The Phase 8B database verifier passed against a disposable PostgreSQL 17 database with synthetic fixtures and no password credentials.
- Routed GitHub run `34768984495` exposed an incorrect SQLAlchemy Core lock read before any later phase began. The correction uses locked row mappings for settings, leave types, and holidays, preserves protected-holiday errors, and adds a repository regression test. The corrective workflow result is reported in the handoff.
- `git diff --check` passed.
- No Alembic revision, schema, constraint, index, RLS policy, grant, role, or protected function
  changed.
- `workloop-clinic_postgres_data` was not attached, upgraded, seeded, recreated, or deleted.
- The retained empty FRA1 default VPC was not changed.

No local database credential was created. The database verifier used trust authentication inside an isolated disposable container and never attached the preserved volume. The branch remains synthetic-only. The final commit, branch synchronization, and corrective GitHub workflow result are recorded in the phase handoff.
