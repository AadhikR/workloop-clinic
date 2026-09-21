# Part 10E completion

Status: complete.

## Result

Part 10E makes FastAPI the sole authority for attendance corrections, absence resolution, overtime
approval, and attendance audit reads. Employees can submit and page through their own correction
history. Administrators can review a selected-branch queue, decide one current request, resolve an
absence from current evidence, approve calculated overtime, and read a redacted audit projection.

Every mutation requires idempotency, locks the affected state, checks a version, derives scope and
actors from the authenticated principal, and commits evidence, recalculation, workflow state, and
audit together. Approved corrections supersede only their named source events and add new manual
evidence; they never rewrite or delete raw punches. Absence resolutions run the server calculation
again, and overtime approval records a trusted timestamp and source digest.

Alembic revision `c9e5a7d1f642` follows `f2d4a8c6b901`. It adds workflow versions and trusted
resolution and overtime evidence, narrows pending-request uniqueness, preserves legacy audit
actions, normalizes empty legacy reasons, and adds the protected correction and submission helpers.
Its downgrade restores the exact 10D catalogue and function invariant.

The `attendance-exceptions` cutover is complete with `migration-fastapi` as its only read and write
authority. Matching legacy correction, decision, resolution, overtime, and audit paths fail closed.

## Review corrections

The inherited draft was reviewed before completion. The review added missing mutation idempotency,
cursor pagination, trusted source evidence, exact event supersession, server-owned absence
recalculation, append-only audit protection, and concurrency and rollback proofs. The final gate also
caught and fixed a truncated database constraint name, legacy audit-action compatibility, upgrade
handling for empty legacy reasons, stale current-head assertions in shared verifiers, React effect
dependencies, and strict test-constructor typing.

## Gate evidence

The final database-sensitive gate ran in the fresh `workloop-phase10e-gate` stack:

- Ruff lint and formatting, strict Pyright, dependency checks, and all 547 backend tests passed.
- All 199 frontend unit tests, changed-file ESLint, and both legacy and migration production builds
  passed.
- Repeat migration, the empty-schema chain, single-head and no-drift checks, the exact 10D rollback
  and replay, and the current schema compatibility smoke passed.
- The complete current-head deep verifier chain from repository scope through Phase 10E passed.
  Focused 10E proof covered submission limits, replay and changed payloads, branch and self scope,
  exact supersession, concurrent decisions, every absence resolution, overtime approval, closed
  periods, append-only audit, and forced transaction rollback.
- FastAPI and Keycloak authentication, the complete administrator, manager, and employee browser
  journey, service health, and service-log safety passed after a no-rebuild restart.
- The normalized database catalogue fingerprint, both Keycloak signing-key identifiers, and the
  synthetic storage fingerprint were unchanged across the restart.

The routed GitHub result is reported in the task handoff after the final push. This local gate record
does not contain a workflow URL.

## Resource boundary

Verification used synthetic local data. The protected volume `workloop-clinic_postgres_data` was
never attached, modified, deleted, or recreated. Only explicitly named disposable Phase 10E proof
and gate volumes were recreated during verification. Generated credentials, installed frontend
dependencies, build outputs, and the stopped isolated gate resources remain local for the next
authorized subphase.

## Writing review

The repository-required `.opencode/skill/unslop/SKILL.md` was absent. New prose received a manual
review for direct language, concrete claims, sentence-case headings, and consistent terms.

## Next subphase

Part 10F is authorized next. It owns atomic attendance-period close, blocker calculation, closed
record immutability, and the Phase 9 attendance payroll-input projection. Roster drafting,
publication, schedules, swaps, reports, and Phase 11 remain outside 10F.
