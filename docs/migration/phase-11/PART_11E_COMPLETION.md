# Part 11E completion

Status: complete.

## Result

Part 11E moves appraisal cycles, generated employee reviews, fixed weighted sections, manager
ratings, administrator review and calibration, and clinical incident handling to FastAPI and the
migration frontend. The server owns eligibility, section templates, weighted totals, actors,
timestamps, workflow state, branch scope, and optimistic locking. It retains closed cycles,
calibrated appraisals, and every incident report.

Appraisals use the five approved sections and calculate weighted ratings with decimal half-up
rounding. Managers can rate direct reports but cannot read or change unrelated employees. Employees
receive the approved self-history projection without a self-rating command. Clinical incidents keep
descriptions, people, causes, actions, and notes out of audit metadata and unrelated role projections.
Incident hard delete remains unsupported.

Alembic revision `a1c3e5f7b9d4` follows `f0b2c4d6e8a3`. It adds the Phase 11E constraints, optimistic
locks, workflow guards, policies, protected audit actions, and retained-history rules. The appraisal
and clinical-incident cutover records name the migration API as the sole read and write authority.
The matching legacy storage paths now fail closed.

## Gate evidence

- All 592 backend tests, Ruff lint and formatting, strict Pyright checks, and dependency checks
  passed. Focused Phase 11E and compatibility reruns covered 48 backend tests.
- All 238 frontend tests and both production builds passed. Five focused frontend tests covered the
  new projections and the legacy freeze.
- A fresh isolated database applied the migration chain twice, completed the downgrade and upgrade
  round trip, restored the exact Phase 11D predecessor, and reported no Alembic drift.
- Historical schema, RLS, grant, trigger, protected-function, audit, security-control, and database
  checks passed through Phase 11E. The standard 334-row seed also applied, validated, and cleaned up
  after the Phase 11E verifier.
- Focused checks covered cycle create, edit, activate, generate, close, guarded draft deletion,
  eligibility, replay, concurrent generation, the five fixed sections, weighted rounding, employee
  self scope, manager direct-report scope, review, calibration, stale updates, and retained history.
- Incident checks covered create, list, detail, ordinary update, investigation, corrective action,
  closure evidence, branch-scoped employee references, stale and concurrent closure, audit
  redaction, generic errors, retained history, forced rollback, and cleanup.
- Existing images restarted without rebuilding. Database fingerprints, Keycloak signing keys,
  service health, browser authentication, cleanup, and log-safety checks passed after restart.
- GitHub Migration foundation run `35859385540` passed classification, backend quality, frontend
  regression, full-stack smoke, and the deep database-boundary step on commit
  `2b4dc6cbf0637e02b5cd47e967f9ba0a833c1fb0`.

## Source state

The implementation began in commit `4139fe3`. Commits `f84e402`, `df469c9`, `0bc17d0`, `b4aa7a6`,
`93c349c`, `5b2c292`, `56ebce2`, and `2b4dc6c` tightened model metadata, test stability, historical
compatibility, deep-change routing, and verifier cleanup before the passing GitHub run.

## Resource boundary

Verification used synthetic local rows in disposable containers, networks, and volumes. The
protected `workloop-clinic_postgres_data` volume was not attached, modified, deleted, or recreated.
The Phase 11E disposable environment and its synthetic rows were removed after the evidence was
recorded.

No production provider, credential, cloud resource, paid service, production data, or real employee
or patient record was approved or used. Notifications, tasks, dashboards, reports, aggregates, and
exports remain outside Part 11E.

## Rollback and next step

Disable migration incident mutations before restoring any legacy incident path. For appraisals,
disable calibration, review, rating, and cycle writers in that order before restoring legacy paths.
Preserve closed cycles, appraisals, section ratings, incident reports, investigation history,
corrective actions, actors, and timestamps. Never reopen or delete retained evidence during a
technical rollback.

Part 11F is next under the project owner's sequential authorization.
