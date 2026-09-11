# Phase 7G completion record

## Status

The project owner authorized Phase 7G on 2026-09-11 and approved database amendment decisions
`7G-DB-D1` and `7G-DB-D2`. Employee lifecycle, job-history, self-contact, and portal-role workflows,
their cutover evidence, and the complete local gate are finished. GitHub Migration foundation run
`34640300429` passed for corrective commit `aed225913d74d4f341490dea86bf41a17574ded7` on 2026-09-11.

Phase 7H has not started and remains unauthorized.

## Workflow boundary

FastAPI now owns named administrator workflows for title, department, salary, status, manager,
probation confirmation, probation extension, probation termination, and archive changes. Protected
operations require idempotency keys and optimistic versions where the Phase 7A contract calls for
them. The server derives company, selected branch, actor, identifiers, and timestamps. It locks and
validates dependent employees, departments, profiles, and direct-report assignments in the same
transaction.

Manager demotion, termination, and archive operations reassign every direct report atomically or
leave all related state unchanged. Employee hard deletion and branch transfer remain unsupported.
Keycloak provisioning, documents, insurance, employment contracts, payroll, attendance, and shifts
remain outside Phase 7G.

The employee self-contact route accepts only phone, personal email, emergency-contact name, and
emergency-contact phone changes. It derives the employee from the trusted principal and rejects a
stale version. Portal-role reads and changes apply only to an eligible, active, already linked
`user_profiles` row. Only employee and manager roles are supported, and an administrator cannot
change their own role through this workflow.

## History, audit, and database amendment

Job-history rows are append-only and server-authored. Title, department, salary, and status
workflows append the approved history type in the same transaction as the employee change. The
probation and archive workflows use the existing `status_change` type instead of inventing another
history enum.

Alembic revision `8f6b2d1a4c70` implements the approved Phase 7G database amendment. It wraps the
protected audit function with the six approved employee actions, delegates every earlier action to
an exact private predecessor, and adds branch-scoped update policies for eligible portal-role
changes. Its downgrade restores the predecessor function and policy state exactly. The combined
predecessor-state hash matched before and after the downgrade round trip:
`ba257198f905a96014a8268ffd3da90197cdbc762e954ee69150860b3a9254db`.

## Migration UI and cutover

The migration employee directory now exposes the Phase 7G lifecycle controls and portal-role
round trip for administrators. Employee and manager views expose the restricted self-contact form.
The browser client validates exact camelCase projections and sends `PUT` only through the approved
HTTP method and CORS boundary.

Legacy archive, manual job-history, and portal-role functions fail before reaching Supabase. The
legacy employee screens no longer call those writers. The employee lifecycle cutover record names
`migration-fastapi` as the sole read and write authority and preserves the rollback order required
to avoid dual writes.

## Verification

Focused checks covered role and branch denial, foreign identifiers, stale versions, invalid state
transitions, manager cycles, complete report reassignment, idempotent replay, changed-payload
conflicts, inactive and unlinked portal profiles, self-role denial, protected audit calls, and
rollback after each failed transaction. The Phase 7G verifier recorded 39 protected-audit denial
cases and returned state digest
`3936a6ed48373e102be656033bab15924cb4dc16c363885a72ec07d5346f2740`.

The settled complete local gate passed:

- 432 backend tests, Ruff lint and formatting, strict Pyright, and the locked dependency check;
- 117 frontend tests, both production builds, and isolation across 449 legacy modules and 36
  migration modules;
- repeatable migration at the single Alembic head `8f6b2d1a4c70`, including an empty-schema replay,
  no pending operations, and the exact predecessor round trip;
- schema, migration round-trip, trigger, seed, repository, context, RLS, grant, function-security,
  audit, and PostgreSQL ownership checks;
- Phase 6 HTTP and CORS checks, Keycloak configuration idempotence, Keycloak-to-FastAPI
  authentication, and the complete administrator, manager, and employee browser journey; and
- restart persistence, service log safety, and complete synthetic-data cleanup.

The first pushed run exposed a revision-sensitive expectation in the shared Phase 5E verifier. The
corrective commit makes that verifier expect branch-scoped portal-role updates only while the Phase
7G policy is installed. The exact Phase 5F downgrade and upgrade chain passed locally after the
correction, as did the Phase 5E verifier at the Phase 7G head. GitHub run `34640300429` then passed
classification, backend quality, frontend regression, and the complete full-stack smoke job.

The final gate used Compose project `workloop-phase7g-final` on PostgreSQL port 25432, API port
28000, and Keycloak ports 28080 and 29000. It used a fresh temporary PostgreSQL volume, applied the
migrations twice, and proved the Phase 7G audit wrapper and exact predecessor. The database
catalogue fingerprint remained `3dcb949149dcb3078cd841a51bf9e6ff` across restart. Both Keycloak
signing key IDs and all three image IDs remained unchanged. The final images were:

- PostgreSQL: `sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0`;
- backend: `sha256:48283d2c28016e7a1f7d139b816119034a277c4105c7ff77dc730a81555fa7ad`;
  and
- Keycloak: `sha256:9d1f1b2b7261ff53c66cb1092dfcdc34a5fb77e81f9e6a6e75b8b6a795de8067`.

Context isolation, authentication, and the full browser journey passed after restart without
another Keycloak configuration pass. All synthetic Workloop rows and Keycloak users returned to
zero.

## Resource boundary

Verification used local synthetic data only. It accessed no production data, cloud resource, paid
service, or persistent external credential. After recording the gate result, the project removed
its containers, network, generated credentials, and temporary PostgreSQL volume.

The protected `workloop-clinic_postgres_data` volume was not attached, upgraded, recreated, seeded,
or deleted. It remains present. The retained empty FRA1 default VPC was not changed.

## Stop condition

Phase 7G is closed. Stop before Phase 7H and require separate project-owner authorization.
