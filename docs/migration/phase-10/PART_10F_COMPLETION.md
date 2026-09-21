# Part 10F completion

Status: complete.

## Result

Part 10F makes FastAPI the sole authority for selected-branch attendance-period reads, atomic close,
append-only amendment versions, and the closed attendance projection consumed by payroll. Close
derives every blocker on the server, locks the period and all current inputs, freezes the complete
record set, and commits its actor, time, canonical source version, immutable member snapshots, and
audit entry together.

The payroll projection accepts only the current closed, payroll-ready version. It verifies the
canonical digest and member count before returning deterministic employee aggregates for absence,
lateness, approved standard overtime, approved rest-day overtime, and source row IDs. Phase 9 turns
those rows into deterministic automatic deductions and additions with the attendance source version
embedded in each input snapshot.

Alembic revision `d0f6b8e2a753` follows `c9e5a7d1f642`. It adds close versions, immutable record
snapshots, period audit, source-version and state constraints, append-only guards, forced RLS,
runtime grants, and narrowly scoped protected lock functions. Its downgrade restores the exact 10E
catalogue and function invariant.

The `attendance-period-close` cutover is complete with `migration-fastapi` as its only read and write
authority. Matching legacy period-close and attendance-payroll paths fail closed.

## Review corrections

The inherited implementation was reviewed before completion. The review fixed nondeterministic test
shift assumptions, partial-failure cleanup, an invalid SQL bind cast, a migration delete-trigger
edge case, undeclared digest dependencies, insufficient lock privileges, and current-head verifier
drift. It also closed calculation and event-ingestion races at the shared period lock, prevented
amendments without new evidence, and added table-level event locking so close cannot miss a
concurrent insert.

## Gate evidence

The final database-sensitive gate ran in the fresh `workloop-phase10f-gate` stack:

- Ruff formatting and lint, strict Pyright, dependency checks, and all 554 backend tests passed.
- All 203 frontend unit tests, changed-file ESLint, and both legacy and migration production builds
  passed.
- The migration applied twice. Single-head, model-drift, exact 10E predecessor rollback, deterministic
  replay, schema, RLS, grants, and protected-function checks passed.
- Focused database proof covered readiness blockers, exact money, stable source rows, concurrent
  close, canonical integrity, Phase 9 projection consumption, no-op amendment rejection, changed
  evidence, forced rollback, branch isolation, and closed-record immutability.
- FastAPI and Keycloak were healthy after a no-build restart, and the signed-in migration browser
  journey passed.
- The database catalogue fingerprint and Keycloak signing-key identifiers were unchanged across the
  restart.

The routed GitHub result is reported in the task handoff after the final push. This local gate record
does not contain a workflow URL.

## Resource boundary

Verification used synthetic local data. The protected volume `workloop-clinic_postgres_data` was
never attached, modified, deleted, or recreated. Only named disposable Phase 10F development and
gate volumes were used. The isolated gate stack remains available for the next authorized subphase.

## Writing review

The repository-required `.opencode/skill/unslop/SKILL.md` was absent. New prose received a manual
review for direct language, concrete claims, sentence-case headings, and consistent terms.

## Next subphase

Part 10G is authorized next. It owns selected-branch roster drafts, leave-conflict validation,
staffing gates, and immutable compliance overrides. Publication, employee schedules, actual-hours
authority, payroll projection, swaps, reports, and Phase 11 remain outside 10G.
