# Part 11F completion

Status: complete.

## Result

Part 11F moves employee and manager self-service letter and custom request submission, request
history, administrator decisions, and the completed-request print source to FastAPI and the migration
frontend. The server derives employee identity, branch scope, trusted employment snapshots, salary
snapshots, actors, timestamps, and workflow state. Employees and managers can read only their own
requests. Administrators use the selected branch queue and cannot distinguish out-of-scope records
from missing records.

The request contract supports the five approved letter types and bounded custom subjects and details.
Salary snapshots exist only for the three salary-bearing letter types and are not returned by ordinary
self, queue, or detail projections. The completed print source exposes only the approved trusted
fields. PDF rendering, arbitrary templates, and browser-download bytes remain outside Phase 11.

Alembic revision `b2d4f6a8c0e5` follows `a1c3e5f7b9d4`. It adds trusted snapshots, salary controls,
decision-state checks, protected audit actions, replay support, and the request update timestamp. The
letter-request cutover record names the migration API as the sole read and write authority. The
matching legacy storage and submission paths now fail closed.

## Gate evidence

- All 596 backend tests and all 245 frontend tests passed. Ruff lint and formatting passed, targeted
  strict Pyright checks reported no errors, and both production builds passed.
- Focused Phase 11F checks covered seven backend contract tests and six frontend and legacy-freeze
  tests. The historical seed compatibility correction passed 22 focused backend tests.
- A fresh isolated database applied the migration repeatedly, restored the exact Phase 11E
  predecessor, upgraded to the Phase 11F head, and reported no Alembic drift.
- The complete database-boundary sequence passed locally after the compatibility corrections. It
  covered historical schema round trips, the deterministic seed, transaction context, RLS, grants,
  protected functions, audit controls, security controls, and every database verifier through Phase
  11F.
- Request checks covered self submission and history, selected-branch administrator scope, canonical
  letter fields, custom fields, trusted snapshots, salary redaction, completion, rejection, stale
  state, replay, concurrent decisions, audit metadata, retained history, forced rollback, and
  cleanup.
- Existing images restarted without rebuilding. Database fingerprints, Keycloak signing keys, local
  object storage, scan state, authentication, the complete browser journey, synthetic cleanup, and
  log-safety checks passed after restart.
- GitHub Migration foundation run `35874371756` passed classification, backend quality, frontend
  regression, full-stack smoke, and the deep database-boundary step on commit
  `7294af05fbfd530d6922bf2059edf56a9f6136b9`.

## Source state

The implementation is recorded in commit `0bba46f`. Commit `ed5557c` preserved seed validation at
historical schemas, and commit `7294af0` updated the schema smoke fixture to the canonical
employment-confirmation letter type before the passing GitHub run.

## Resource boundary

Verification used synthetic local rows in disposable containers, networks, and volumes. The
protected `workloop-clinic_postgres_data` volume was not attached, modified, deleted, or recreated.
The Phase 11F verification environments, synthetic rows, and disposable volumes were removed after
the evidence was recorded.

No production provider, credential, cloud resource, paid service, production data, or real employee
or patient record was approved or used. PDF output, arbitrary templates, notifications, tasks,
dashboards, reports, aggregates, and exports remain outside Part 11F.

## Rollback and next step

Disable migration request decisions before submissions, then restore a legacy path only under the
cutover record. Preserve completed and rejected requests, trusted snapshots, actors, reasons, and
timestamps. Do not change a decided request during rollback.

Part 11G is next under the project owner's sequential authorization.
