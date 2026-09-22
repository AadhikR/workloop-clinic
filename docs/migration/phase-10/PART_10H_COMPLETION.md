# Part 10H completion

Status: complete.

## Result

Part 10H makes FastAPI the sole authority for versioned roster publication, published personal
schedules, actual-hours evidence, roster overtime approval, and the roster payroll projection. A
publication locks and rechecks the complete assignment set and every gate before it marks rows
published and records an immutable source version. The migration interface now reads every roster
page before sending that exact set, so a month with more than 100 assignments cannot be published
partially.

Published rows remain protected from ordinary updates. Actual hours and overtime use separate
append-only evidence and create a new publication source version. Staff can read only their own
published schedule and the minimal same-branch colleague fields approved for future swap requests.
Payroll receives only a published, non-overlapping, versioned projection. The golden roster case
produces four overtime hours and AED 288.46 with exact source identity.

Alembic revision `b4d7f9a2c816` follows `a1c3e5f7b902`. It adds month publication state, immutable
publication versions and memberships, actual-hours evidence, overtime approvals, protected
publication and schedule functions, row-level security, and the roster-publication idempotency
resource. Its downgrade restores the exact 10G catalogue and refuses to discard retained
publication data.

The `roster-publication` cutover is complete with `migration-fastapi` as its only read and write
authority. Matching legacy publication, personal-schedule, and roster-payroll paths fail closed.
Shift-swap mutations remain disabled until Part 10I.

## Review corrections

The inherited implementation was reviewed before completion. The review aligned the model foreign
key and publication timestamp with the migration, added complete client-side pagination before an
exact publication, and repaired every historical deep verifier to assert the current 10H head while
leaving exact-predecessor proofs unchanged. These corrections closed a schema-drift report, a
possible partial publication above 100 assignments, and a gate that would otherwise fail after the
new head was applied.

## Gate evidence

The final database-sensitive gate ran against the isolated `workloop-phase10h-gate` stack:

- All 565 backend tests and all 212 frontend unit tests passed. Backend Ruff checks, strict Pyright,
  changed-file ESLint, backend formatting, and the migration production build passed.
- Historical schema, migration round-trip, trigger, seed, repository, context, RLS, grant, security,
  and boundary checks passed at the current head.
- Deep database checks from employee lifecycle through Phase 10H passed. The 10H proof covered exact
  publication, stale input and forced rollback, staff privacy, source-version changes, actual-hours
  and overtime provenance, payroll overlap rejection, and the AED 288.46 golden calculation.
- The exact 10H predecessor rollback and deterministic replay passed, and Alembic reported no model
  drift at the restored head.
- Strict roster client tests cover all-page publication, response shape, idempotency, personal
  schedules, colleague redaction, and frozen legacy paths.

The routed GitHub result is reported in the task handoff after the final push. This local gate record
does not contain a workflow URL.

## Resource boundary

Verification used synthetic local data and disposable `workloop-phase10h-gate` volumes. The
protected volume `workloop-clinic_postgres_data` was never attached, modified, deleted, or
recreated.

## Writing review

The repository-required `.opencode/skill/unslop/SKILL.md` was absent. New prose received a manual
review for direct language, concrete claims, sentence-case headings, and consistent terms.

## Next subphase

Part 10I is authorized next. It owns same-branch swap requests, own pending cancellation,
administrator queues and rejection, protected atomic execution, publication source-version updates,
and the remaining legacy swap freeze. Part 10J remains the independent Phase 10 completion review.
