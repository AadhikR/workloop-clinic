# Phase 8E completion

Status: implementation and local verification complete. Phase 8F is not authorized.

## Delivered

- Added employee self-submission and administrator submission for staff in the selected branch.
  The server owns employee scope, business date, day count, approval level, warnings, and balance
  effects.
- Added policy-based auto-approval in the submission transaction. Protected audit and leave-domain
  audit rows distinguish that result from a human decision.
- Added employee cancellation for owned `Pending` requests and administrator cancellation for
  future `Approved` requests. Each cancellation reverses the matching balance effect under locks.
- Bound staged attachments to submitted requests and routed cancellation cleanup through the
  existing storage-operation outbox. A completed cleanup removes the private object and records its
  audit event.
- Added idempotency for both submission routes and both cancellation routes. Same-key retries replay
  the original response, while changed payloads fail without another mutation.
- Added forced row-level security and staff lock-only policies needed for server-side policy reads.
  The new Alembic head is `d1e5f8a2c904`, with an exact rollback to `a83d5e7c1b29`.
- Added employee and administrator forms and cancellation controls to the migration frontend. The
  legacy submission and cancellation functions now fail closed.
- Completed the request-submission cutover with `migration-fastapi` as the only read and write
  authority for this workflow.

## Evidence

- Implementation commit `bb19c5fa0965bd498bad9b150ccf3c4f4bf7ea0d` passed on branch
  `migration/fastapi-keycloak`.
- The complete backend suite passed with 465 tests. Ruff formatting and lint, strict Pyright,
  dependency validation, and the FastAPI import check also passed.
- The complete frontend suite passed with 138 tests. The migration build, main production build,
  legacy single-file build, targeted ESLint, API contract tests, and legacy freeze check passed.
- The isolated PostgreSQL 17 gate applied the migration twice, replayed an empty schema, proved the
  exact predecessor rollback, finished at the single expected head, and reported no pending Alembic
  operations.
- The deep database verifier covered self and administrator scope, server-derived fields,
  auto-approval, balance reservations and reversals, overlap checks, attachment binding, cleanup,
  idempotency conflicts, concurrency, row-level security, grants, and both audit stores.
- The clean stack restarted without rebuilding. Its database fingerprint remained
  `0ee6a179662e6244a64ba43c7e91b5de`; both Keycloak signing IDs and the private storage marker also
  remained unchanged. Keycloak and FastAPI authentication passed after restart.
- The final browser journey covered administrator auto-approval and cancellation, employee
  submission and cancellation, attached-request cancellation, object deletion, outbox completion,
  and cleanup audit evidence.
- All disposable Phase 8E containers, networks, database volumes, storage volumes, objects,
  credentials, and synthetic rows were removed after verification.
- `workloop-clinic_postgres_data` was not attached, upgraded, seeded, recreated, or deleted.
- The required GitHub result is recorded in the task report after the single phase push.
