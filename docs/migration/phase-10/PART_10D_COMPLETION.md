# Part 10D completion

Status: complete.

## Result

Part 10D makes FastAPI the authority for calculated attendance and scoped calculated-attendance
reads. The server now selects published roster rows before effective shift assignments, owns Dubai
event windows and decimal arithmetic, snapshots every calculation input, and persists a digest with
a monotonically increasing calculation version. Recalculation compares both values, so concurrent
requests produce one winner. Daily batches accept at most 100 unique employees for one date, lock
them in deterministic UUID order, and roll back the whole batch on any failure.

Administrators can calculate one day or an atomic daily batch and list records in the selected
branch. Employees and managers can read only their own current and historical attendance. The
today route returns a self-only raw-event fallback only when no calculated record exists. Late
events mark open records stale, while closed periods reject recalculation.

Alembic revision `f2d4a8c6b901` follows `b7d9e1f3a5c6`. It adds calculation snapshots, source
digests, versions, event identities, evidence flags, stale state, a scoped stale index, and the
clock-event stale trigger. Its downgrade restores the exact 10C catalogue and replay constraint.

The `attendance-calculation` cutover is complete with `migration-fastapi` as its sole read and write
authority. Legacy calculated-attendance reads and calculation writers fail closed.

## Gate evidence

The final database-sensitive gate ran in the fresh `workloop-phase10d-gate` stack:

- Ruff lint and formatting, Pyright, dependency installation, and all 541 backend tests passed.
- All 194 frontend unit tests and both legacy and migration production builds passed.
- The empty-schema chain, repeat migration, single-head check, autogeneration check, exact 10C
  rollback and replay, invariant hash, and Phase 10B through 10D database authority checks passed.
- Focused proof covered canonical statuses, decimal money, Ramadan, flexible, split and overnight
  shifts, rest-day and night overtime, source snapshots, stale events, closed periods, branch and
  self scope, concurrent recalculation, and atomic batch rollback.
- FastAPI and Keycloak authentication, the browser journey, database and storage persistence,
  signing-key persistence, health, synthetic cleanup, and service-log safety passed after restart.
- Follow-up isolated checks passed the hardened function ACLs, the exact 10D rollback and replay,
  and the complete current database-boundary chain from Phase 4 through Phase 10D.

The routed GitHub result is reported in the task handoff after the final push. This local gate record
does not contain a workflow URL.

## Resource boundary

Verification used synthetic local data. The protected volume `workloop-clinic_postgres_data` was
never attached, modified, deleted, or recreated; its creation timestamp remained
`2026-08-31T07:31:48Z`. The Phase 10D development and gate containers, networks, PostgreSQL and
storage volumes, generated credentials, installed frontend dependencies, and build outputs were
removed after evidence was recorded.

## Writing review

The repository-required `.opencode/skill/unslop/SKILL.md` was absent. New prose received a manual
review for direct language, concrete claims, sentence-case headings, and consistent terms.

## Stop condition

Part 10E is the next phase and must run as a separate task. Corrections, absence resolution,
overtime approval, audit workflows, period close, reports, roster management, swaps, and Phase 11
remain outside Part 10D.
