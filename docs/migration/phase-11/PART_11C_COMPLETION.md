# Part 11C completion

Status: complete.

## Result

Part 11C moves employee documents, insurance, and employment-contract history to FastAPI and the
migration frontend. Employee document access now uses server-derived scope, private object metadata,
current clean scan results, retained verified evidence, guarded pending or rejected cleanup, and
separate administrator and employee-self permissions. Insurance policies, employee coverage, and
dependants use selected-branch administration, exact decimal fields, locked replacements, guarded
deletion, and a redacted self projection. Employment contracts use append-only `new`, `renewed`,
`converted`, and `not_renewed` events with idempotency, expected-state checks, and synchronized
employee contract fields.

Alembic revision `e9a1b3d5f7c2` follows `d8f0a2c4e6b1`. It adds optimistic locks and constraints,
replaces the employee-document policies needed for self submission and cleanup, protects the new
audit actions, extends replay kinds, and preserves the earlier audit-function chain. The cutover
records assign the migration API as the sole read and write authority for all three domains and
freeze the matching legacy paths.

## Gate evidence

- All 580 backend tests, Ruff lint and formatting, targeted Pyright checks, and dependency checks
  passed.
- All 230 frontend unit tests and the legacy and migration production builds passed.
- A fresh isolated database applied the migration chain and repeated the Phase 11C migration.
- Alembic current-state validation, the exact `d8f0a2c4e6b1` predecessor, rollback, replay, and the
  Phase 11C database verifier passed.
- Historical schema, trigger, RLS, grant, protected-function, and domain round-trip checks passed
  through the consolidated database boundary.
- Focused checks covered administrator, employee-self, branch, tenant, redaction, file validation,
  clean-scan release, review, rejection, retained evidence, cleanup, insurance decimals and dates,
  coverage replacement, dependant scope, contract transitions, stale state, replay, concurrency,
  audit, and rollback.
- Existing images restarted without rebuilding. Database state, Keycloak signing keys, storage
  state, scan bindings, durable operations, service health, and cleanup checks passed.
- GitHub Migration foundation run `35820870386` passed classification, backend quality, frontend
  regression, migration history, database boundaries, service safety, persistence, restart, and
  cleanup checks.

## Resource boundary

Verification used synthetic local rows and files in disposable containers, networks, and volumes.
The protected `workloop-clinic_postgres_data` volume was not attached, modified, deleted, or
recreated. Every Phase 11C verification container, network, credential, synthetic row, file, and
temporary volume was removed after the evidence was recorded.

No production provider, bucket, scanner, credential, cloud resource, paid service, production data,
or real employee file was approved or used. Notifications, tasks, dashboards, reports, and generated
files remain outside Part 11C.

## Rollback and next step

Disable migration document upload and signing before restoring a legacy document path. Preserve
verified metadata, review history, object state, and cleanup operations. Disable insurance and
contract mutations before restoring their legacy writers, and preserve current coverage,
dependants, contract events, job history, and synchronized employee fields. Never delete retained
evidence to simplify rollback.

Part 11D is next under the project owner's sequential authorization.
