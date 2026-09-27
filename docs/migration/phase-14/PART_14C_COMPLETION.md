# Part 14C completion

## Result

Part 14C established separate database, object-storage, runtime-secret, and operator boundaries for
the shared-development deployment. The local gate passed on 2026-09-27. Provisioning remains
disabled, no provider credential was supplied, and no DigitalOcean resource, route, state, or
secret was created.

The work closes golden cases `14A-GC-007` through `14A-GC-012`. It keeps the Phase 14A catalogue
unchanged and retains Alembic head `e8a1c3f5b7d9`.

## Identity and privilege boundary

Terraform now declares separate managed PostgreSQL users for migrations, API runtime, expiry,
file scanning, storage reconciliation, and Keycloak. The database bootstrap requires `NOINHERIT`
and rejects superuser, database creation, role creation, replication, or RLS bypass rights. It
removes database, schema, table, sequence, and function privileges from `PUBLIC`, then grants only
the explicit connection and Alembic-owned application privileges.

`btree_gist` needs execute rights on its extension functions for exclusion constraints to work.
Bootstrap therefore identifies only functions owned by that extension, removes their default
`PUBLIC` execute grant, and grants execute to the five application roles. Keycloak remains confined
to its separate database. The runtime proof found no role memberships and denied cross-role access.

Four bucket-scoped Spaces keys separate the API, scanner, reconciler, and future object-backup
process. The API and reconciler use the provider's `readwrite` grant. The scanner and backup use
`read`. No component receives account-wide `fullaccess`, and the migration, expiry, and Keycloak
components receive no object key.

## Secret routes and administrative access

App Platform routes encrypted runtime values only to their owning component. The migration job
alone receives the two temporary administrative database URLs. The API alone receives its shared
signing and idempotency keys. The scanner receives its malware-result signing key, and Keycloak
receives only its database value. The static site receives exactly six public `VITE_` settings and
no protected value. Terraform outputs contain identity names and readiness state, never credential
material.

The cloud realm imports no user or password. The administrator arming script requires a distinct
permanent administrator, its exact master-realm role, and an OTP credential before removing the
bootstrap account. A fresh password-only bootstrap login must then fail. Terraform has no
bootstrap-administrator or synthetic-user password input.

The access contract requires named primary and backup operators, separate account references, and
confirmed MFA for infrastructure, security, application, incident, and release-review roles. An
enabled plan fails before a provider call when this record or the encrypted runtime-secret input is
absent. Rotation allows at most 24 hours of overlap and requires verification, old-value denial,
and rollback. Break-glass access lasts at most one hour, with one separately approved one-hour
extension.

## Focused evidence

The Part 14C verifier passed all eight tests. Its mutation cases reject merged database identities,
over-broad object keys, a frontend secret route, retained bootstrap access, an incomplete rotation
record, and missing operator or MFA custody. The combined Part 14B and 14C slice passed 20 tests.

The cloud-deployment backend slice passed 15 tests after the final bootstrap repair. Ruff lint and
format checks passed the affected files. Pinned Pyright 1.1.411 then checked the complete backend
with zero findings. The repository guard, retained Phase 14A contract checks, and phase workflow
tests also passed.

Terraform 1.16.1 formatted and validated the module with DigitalOcean provider 2.100.0. The default
disabled plan reported no changes. An authorized synthetic plan without the operator and secret
records failed input validation before a provider call. Static inspection found no account-wide
Spaces key, plaintext runtime route, secret output, bootstrap value, or extra frontend setting.

## Boundary-matched local gate

The frontend gate passed 308 unit tests and built the 91-module production graph. The existing
chunk-size warning remained informational. Backend quality passed 673 tests with six unchanged
SQLAlchemy relationship warnings, lint and formatting across 531 files, the complete type check,
and the dependency check.

Compose project `workloop-phase14c-gate` used fresh synthetic credentials and three disposable
volumes. It started PostgreSQL, FastAPI, Keycloak, and private S3, applied migrations twice, and
configured Keycloak twice. Service health, authentication, scanner and expiry database access,
private storage, exact role attributes, explicit grants, cross-role denials, and safe logs passed.

The first integration attempt exposed two verifier defects: the host wrapper had been invoked from
a container without the Docker client, and PostgreSQL extension functions still carried their
default `PUBLIC` execute grant. The wrapper and grant hardening were corrected with focused checks.
The one permitted fresh-stack rerun passed the complete database proof.

The restart check recorded the database fingerprint, Keycloak signing-key IDs, local object state,
private S3 object state, and scanner state. It recreated the existing images without rebuilding.
Every recorded value matched, authentication passed without another Keycloak configuration run,
and the administrator, manager, and employee browser journeys passed.

Final checks found zero application users, zero users in the `workloop-dev` realm, and no protected
value in service logs. Cleanup verified and removed only:

- `workloop-phase14c-gate_postgres_data`
- `workloop-phase14c-gate_storage_data`
- `workloop-phase14c-gate_phase11b_s3_data`

The two temporary offline type-check volumes were also removed. `workloop-clinic_postgres_data` was
checked by name only and remains present. It was never attached, mounted, modified, deleted, or
recreated. The retained Phase 13 archive, `workloop-clinic-dev`, and `fra1-default` were not
inspected or changed.

## Rollback

Before provisioning, rollback is a repository revert of the Part 14C identity, secret-routing,
bootstrap, verifier, and documentation changes. It needs no provider action.

After a later approved apply, enable maintenance mode and stop workers before changing a route.
Restore the last verified credential only to its owning component, prove service recovery, revoke
the failed replacement, and record the denial result. Resource destruction still needs fresh
approval for exact names and retained external state. Never delete the existing project, default
VPC, Phase 13 archive, or protected local volume.

## Next part

Part 14D starts only after this commit and every routed GitHub job pass, and the branch is clean and
synchronized. It owns immutable application artifacts, digest-pinned deployment inputs, migration
release ordering, expiry invocation controls, and its assigned golden cases. It must not provision
the shared environment or implement Part 14E observability.
