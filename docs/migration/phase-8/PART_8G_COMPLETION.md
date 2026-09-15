# Phase 8G completion

Status: independent review and local verification complete. The matching GitHub result is reported
in the task report after the single settled push. The project owner's standing Phase 8 signoff
applies when that workflow passes.

## Review result

- Traced all 42 Phase 8A dependency IDs to a migrated authority, a named Phase 9 through 12 owner,
  or a deliberately retained legacy dependency.
- Found no runtime defect or contract gap that requires a new leave policy, schema revision, role,
  grant, RLS policy, protected function, or phase-boundary decision.
- Corrected four stale cutover source digests. Configuration, balances and reads, attachments, and
  request submission now name the current Phase 8A domain contract digest and their refreshed
  evidence digests.
- Corrected the Phase 8A verifier so it accepts the valid completed approval-workflow cutover. The
  Phase 8G regression test separately requires all five cutovers to be complete.
- Confirmed one migration read and write authority per feature, no dual writes, the approved legacy
  freezes, no migration Supabase path, and the required reverse rollback order.

## Evidence

- The complete backend gate passed with 469 tests, Ruff lint and formatting, strict Pyright,
  dependency validation, and the FastAPI import check.
- The complete frontend gate passed with 145 tests, the isolated migration build, the main and
  single-file production builds, and targeted ESLint. The Phase 8G tests prove exact coverage of all
  42 inventory IDs, five valid completed cutovers, rollback order, and no Supabase reference under
  `migration/src`.
- The fresh `workloop-phase8g-01a0a616` PostgreSQL 17 environment applied the migration twice,
  replayed the empty-schema chain, finished at the single `e8f4c7b2a610` head with no pending
  operations, and restored `d1e5f8a2c904` with the same predecessor-function hash.
- The deep database gate passed the schema, historical migration, seed, repository authorization,
  transaction context, RLS, grant, protected-function, security, employee lifecycle, and Phase 8B
  through 8F verifiers. Seed application was repeatable and removed all 334 fixture rows.
- The stack restarted without rebuilding. Database fingerprint
  `13834286a55282f3f85e5d5b95164518`, both Keycloak signing-key IDs, the prepared private storage
  proof, its signing key, and the PostgreSQL, backend, and Keycloak image digests were unchanged.
- The post-restart authentication check passed after one focused retry for transient Keycloak
  credential readiness. The realm remained clean, and no code or persisted state changed between
  attempts.
- The complete post-restart browser journey passed for administrator, manager, delegate, and
  employee leave behavior, including attachments, submission, cancellation, queues, decisions,
  audit projection, and session checks.
- Cleanup left zero synthetic identity, organization, leave, idempotency, audit, or storage-operation
  rows, zero Keycloak test users, and zero storage objects. The task's containers, network, and two
  labeled volumes were removed.
- `workloop-clinic_postgres_data` was not attached, upgraded, seeded, recreated, or deleted.

## Cutover evidence

- Domain contract:
  `1193ba0007aa23ad5840cf404d96d0eb46e02603cbd320891ea7baa38c6d87c1`
- Configuration evidence:
  `41aaa7b1b6d1a81e877937379b51bbb2d48b90b8d4dbb9854d052f8b3b8305de`
- Balances and reads evidence:
  `58de0adda2829d591128a30989dd96d9aa9a29119d5c3ba0a6092c526da7af17`
- Attachment evidence:
  `4c32daf2f89667aa0edadd4b6b8578782a2dc6f0e58bdcb700185e88b158bef3`
- Request submission evidence:
  `40ed54397eca4e0a1df86125039321ba17265bf9211a5ae9d9aac7a3f528ab49`
- Approval workflow evidence:
  `9efd131413c9e7e9140cccb0cbcca6abf721e5d469bd03d36598a89abe162807`

Phase 9 remains unauthorized.
