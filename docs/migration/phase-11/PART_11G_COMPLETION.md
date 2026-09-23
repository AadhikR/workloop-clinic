# Part 11G completion

Status: complete.

## Result

Part 11G moves selected-branch offboarding checklist initialization, custom task creation, task
completion, visa-state transitions, final settlement, and offboarding completion to FastAPI and the
migration frontend. The server derives checklist provenance, actors, timestamps, upstream source
identities, calculated amounts, and employment history. Completion fails closed when a mandatory
task, open asset assignment, unsupported legal boundary, missing payroll source, stale input, or
negative net settlement remains.

The approved settlement policy covers foreign full-time employees in the UAE mainland private
sector under the traditional gratuity scheme. It uses inclusive paid calendar service, a 365-day
eligibility threshold, basic salary divided by 30, 21 gratuity days per year through five years,
30 days thereafter, and the statutory two-year basic-salary cap. It encashes the current annual
leave balance, includes unpaid net pay from the approved termination-month payslip, settles active
salary advances, and accepts manual notice and other adjustments only with reasons. Unsupported
nationality, jurisdiction, employment, or benefit-scheme combinations require manual review.

Alembic revision `c3e5a7b9d1f6` follows `b2d4f6a8c0e5`. It adds checklist provenance, immutable
versioned settlement policy, final settlements, protected source readers and commands, exact grants,
RLS, audit controls, and deterministic policy seeding. The offboarding cutover names the migration
API as the sole read and write authority. Matching legacy offboarding and gratuity paths now fail
closed.

## Gate evidence

- All 605 backend tests and all 248 frontend tests passed. Ruff lint and formatting, npm lint,
  targeted strict Pyright checks, dependency checks, and both production builds passed.
- Focused contract checks covered the Phase 11G API, legacy freeze, exact predecessor and head,
  golden cases, deterministic policy digest, immutable settlement evidence, stale inputs,
  concurrency, replay, forced rollback, audit, and cleanup.
- A fresh isolated database applied the migration repeatedly, restored the exact Phase 11F
  predecessor, upgraded to the Phase 11G head, and reported no Alembic drift.
- The complete database-boundary sequence passed locally. It covered historical schema round trips,
  deterministic seeds, transaction context, RLS, grants, protected functions, audit and security
  controls, and every database verifier through Phase 11G.
- Existing images restarted without rebuilding. Database fingerprints, Keycloak signing keys,
  synthetic storage, scan state, authentication, the complete browser journey, synthetic cleanup,
  and log-safety checks passed after restart.
- GitHub Migration foundation run `35900744230` passed classification, backend quality, frontend
  regression, full-stack smoke, the deep database-boundary sequence, restart preservation, service
  health, and cleanup on commit `a3c3ac553658fbf0c5b0113f45666f7b1ab3bd66`.

## Source state

The implementation is recorded in commit `1df955f8b53e310c971fcc78a1b5384e982f9496`. Commit
`a3c3ac553658fbf0c5b0113f45666f7b1ab3bd66` aligned the historical schema, RLS, grant, and protected
function gates with the additive Phase 11G boundary before the passing GitHub run.

## Resource boundary

Verification used synthetic local rows in disposable containers, networks, and volumes. The
protected `workloop-clinic_postgres_data` volume was not attached, modified, deleted, or recreated.
The Phase 11G verification environments, synthetic rows, and disposable volumes were removed after
the evidence was recorded.

No production provider, credential, cloud resource, paid service, production data, or real employee
or patient record was approved or used. The policy does not automate UAE-national pensions, free
zones, DIFC, ADGM, alternative savings schemes, or another unsupported legal boundary. Generated
letters, PDFs, notifications, tasks, dashboards, reports, aggregates, and exports remain outside
Part 11G.

## Rollback and next step

Disable migration completion and settlement before task and checklist mutations, then restore a
legacy path only under the cutover record. Preserve completed checklists, settlements, source
snapshots, employment history, repayments, asset history, actors, and audit. Never delete evidence
or reverse a completed offboarding as a technical rollback shortcut.

Part 11H is next under the project owner's sequential authorization.
