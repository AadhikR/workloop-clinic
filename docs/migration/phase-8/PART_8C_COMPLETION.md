# Phase 8C completion

Status: complete. Phase 8C is closed and Phase 8D remains out of scope.

## Delivered

- Added server-owned working-day and calendar-day counting, half days, accrual, carry-forward,
  probation, sick-pay tiers, pending reservations, used days, and remaining-day calculations.
- Added strict employee, administrator, and approver balance and leave-calendar projections. The
  routes use trusted company and branch context and encrypted cursors bound to the principal,
  operation, role, year, and filters.
- Added idempotent administrator initialization and deterministic recalculation for one selected
  branch and leave year. Recalculation locks employees, leave types, leave requests, and balances
  in a fixed order before deriving and writing balances.
- Kept direct-manager access current and limited delegated access to active same-branch leave
  delegation through the protected database predicate.
- Added the migration leave overview and API client with no Supabase dependency.
- Froze only the legacy balance readers and writers. Submission, cancellation, attachment,
  approval, delegation, audit, payroll, attendance, reporting, and later-phase paths remain active
  on their existing authority.
- Added focused arithmetic, service, frontend, route-inventory, structural, legacy-freeze, and
  disposable-database verification.

## Evidence

- The complete backend suite passed with 446 tests. The focused Phase 8C service suite contributed
  seven tests.
- The complete frontend unit suite passed with 130 tests. The focused balance and legacy-freeze
  suites contributed five tests.
- The Phase 8C database verifier passed against a disposable PostgreSQL 17 database. It covered
  idempotent initialization, repeatable concurrent recalculation, direct-manager and active-delegate
  access, expired delegation, unrelated actors, cross-branch and cross-tenant denial, unchanged
  non-balance leave tables, nonnegative balances, and duplicate prevention.
- FastAPI import, exact route inventory, Ruff, strict Pyright, dependency checks, the complete
  frontend suite, production builds, structural checks, cutover validation, and the final
  boundary-matched local gate passed.
- No Alembic revision, schema, constraint, index, RLS policy, grant, role, or protected function
  changed.
- `workloop-clinic_postgres_data` was not attached, upgraded, seeded, recreated, or deleted.
- The retained empty FRA1 default VPC was not changed.

The branch remains synthetic-only. The final commit, branch synchronization, and routed GitHub
workflow result are recorded in the phase handoff.
