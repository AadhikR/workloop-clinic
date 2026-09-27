# Part 14F recovery runbook

## Scope

This runbook restores synthetic shared-development data into isolated targets. It never restores over
the shared environment. Keep maintenance enabled, application writes blocked, and worker processing
disabled until every comparison and the full synthetic journey pass.

Part 14F does not create cloud resources. The managed PostgreSQL backup schedule, retention, and
point-in-time restore remain a live Part 14G dependency. Record that dependency as
`pending-14g-provider-live`; do not turn a local rehearsal into provider evidence.

## Custody and schedule

The backup custodian owns native backup records, encrypted portable database exports, private object
versions, and recovery evidence. The release reviewer owns retained release artifacts. Portable
database exports keep seven daily and four weekly copies. Deleted object versions remain available
for 30 days. Keep current and prior compatible releases for 90 days and sanitized recovery evidence
for 365 days.

Encrypt both logical database exports before they reach durable storage. Keep the encryption key in
the owner-approved secret store and outside command arguments, logs, repository files, Terraform
state, and application settings. Record only its eight-character key ID. Back up the Keycloak
database and the digest of its signing-key IDs together. Never export signing private keys as
separate evidence.

The private-object manifest records version count, object count, total bytes, an opaque key digest,
and a content digest. Restricted custody keeps the version IDs and encrypted object bodies outside
Git. The repository record contains totals and digests only.

## Backup

1. Verify the reviewed release manifest, exact commit, artifact digests, and Alembic head.
2. Confirm the source is synthetic-only and the backup identity has no write permission.
3. Export `workloop` and `keycloak` through `scripts/phase-14f-database-recovery.sh export`. The helper
   streams each logical export into authenticated encryption, so it does not create a plaintext dump.
4. Record the Keycloak signing-key ID digest, identity counts, row counts, object version and byte
   totals, opaque key digest, content digest, scanner state, and reconciliation state.
5. Retain the matching release manifest, application specification, configuration names, and
   frontend, backend, Keycloak, dependency, Terraform, and schema digests. Keep the protected
   configuration values in the security custodian's encrypted store. Retain only the digest of the
   canonical names and values as evidence.

A missing export, digest, custodian, schedule, or matching release blocks the rehearsal.

## Isolated restore

1. Enable maintenance and stop expiry, scanner, and reconciliation claims on the source.
2. Resolve the exact target names from `infra/digitalocean/recovery-contract.json`. Reject any target
   that differs. Do not use `workloop-clinic_postgres_data`.
3. Create fresh isolated targets with no public network exposure. Restore `workloop`, then
   `keycloak`, with `scripts/phase-14f-database-recovery.sh restore`.
4. Restore private object versions into the named empty bucket. Abort if the target contains an
   object or version.
5. Load only the release manifest that matches the backup. Keep application writes and workers
   disabled. Restore its protected configuration from the security custodian's encrypted store.
   Compare the configuration-value digest before starting the API. A new storage signing key,
   object-key HMAC key, cursor key, idempotency recovery key, or malware result key is a mismatch.
6. Compare every required item in the recovery contract. Any mismatch leaves the target blocked.
7. Verify Keycloak readiness, issuer discovery, JWKS, signing-key continuity, authentication,
   authorization denials, private file upload and download, scanner and reconciliation processing,
   and the administrator, manager, and employee browser journeys.

The local rehearsal may enable writes only inside the isolated target after all comparisons pass.
It must restore the blocked state before rollback and cleanup. Shared promotion still waits for the
Part 14G provider-native evidence.

## Rollback rehearsal

Name the requested prior release. The helper rejects an implicit choice, a mutable artifact, an
unreviewed release, or a different Alembic head. Keep the current schema. Automatic downgrade is
forbidden. Redeploy Keycloak, API, web, scanner, reconciler, and expiry from the chosen compatible
manifest, then repeat health, authentication, authorization, object, worker, and reconciliation
checks before maintenance can end.

## Evidence and cleanup

Retain a sanitized record and its SHA-256 digest before cleanup. The record may contain timestamps,
operators, release IDs, target names, counts, byte totals, safe key suffixes, statuses, and digests.
It must not contain credentials, connection strings, object keys, filenames, signed URLs, private
keys, object bytes, document contents, or raw database rows.

Compare each target with the exact allowlist in the recovery record. Remove only those targets.
Repeat the cleanup check to prove it is idempotent. Stop if a target resolves to the protected local
volume, the Phase 13 archive, `workloop-clinic-dev`, `fra1-default`, or any name not in the record.
