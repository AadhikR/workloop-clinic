# Part 11D completion

Status: complete.

## Result

Part 11D moves asset inventory, assignment history, training, certifications, certificate evidence,
and CME tracking to FastAPI and the migration frontend. Asset commands use selected-branch scope,
exact purchase costs, optimistic locks, guarded status changes, one open assignment, retained custody
history, and safe employee-self reads. Training supports administrator maintenance, employee
self-enrolment, and manager direct-report updates within the approved boundary. Certification
submissions use private evidence objects, current clean scan results, administrator review, rejection,
and retained verified evidence. CME totals are calculated from authoritative completed training; the
browser cannot persist an achieved total.

Alembic revision `f0b2c4d6e8a3` follows `e9a1b3d5f7c2`. It adds the Phase 11D constraints,
optimistic locks, policies, protected audit actions, direct-report locking function, and file-security
bindings. The asset and training cutover records assign the migration API as the sole read and write
authority and freeze the matching legacy storage paths.

## Gate evidence

- All 587 backend tests, Ruff lint and formatting, strict Pyright checks, and dependency checks
  passed.
- All 233 frontend tests and the legacy and migration production builds passed.
- A fresh isolated database applied the full migration chain twice and passed the empty-schema and
  exact Phase 11B, 11C, and 11D predecessor checks.
- Historical schema, trigger, RLS, grant, protected-function, lifecycle, and domain checks passed
  through the consolidated database boundary.
- Focused checks covered asset create, edit, status, assignment, return, history, guarded deletion,
  stale state, concurrent assignment, branch scope, self reads, training maintenance, employee
  enrolment, direct-report scope, certification evidence, clean-scan release, review, rejection,
  retained evidence, CME calculation, audit, cleanup, and forced rollback.
- Existing images restarted without rebuilding. Database fingerprints, Keycloak signing keys,
  synthetic storage, S3-compatible objects, scan state, service health, browser authentication,
  cleanup, and log-safety checks passed.
- GitHub Migration foundation run `35838026271` passed classification, backend quality, frontend
  regression, migration history, database boundaries, service safety, persistence, restart, browser
  authentication, and cleanup checks on commit `cb35168acf18676916760b4d4db474e6ea568c7f`.

## Resource boundary

Verification used synthetic local rows and files in disposable containers, networks, buckets, and
volumes. The protected `workloop-clinic_postgres_data` volume was not attached, modified, deleted, or
recreated. All Phase 11D verification containers, networks, credentials, synthetic rows, files,
buckets, and temporary volumes were removed after the evidence was recorded.

No production provider, bucket, scanner, credential, cloud resource, paid service, production data,
or real employee file was approved or used. Notifications, tasks, dashboards, reports, expiry jobs,
and generated files remain outside Part 11D.

## Rollback and next step

Disable migration certification uploads and review commands before training and CME writers. Disable
asset assignment and status writers before restoring legacy paths. Preserve verified certifications,
completed training, CME evidence, asset custody, assignment history, review history, object state,
and cleanup operations. Never delete retained evidence to simplify rollback.

Part 11E is next under the project owner's sequential authorization.
