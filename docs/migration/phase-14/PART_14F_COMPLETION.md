# Part 14F completion

## Result

Part 14F defines and rehearses encrypted portable backup, isolated restore, release rollback, and
exact cleanup for the shared-development design. It closes inventory items `P14-REC-001` through
`P14-REC-007` and golden cases `14A-GC-026` through `14A-GC-030`. Alembic remains at
`e8a1c3f5b7d9`.

The local recovery rehearsal passed. Provider-native backup proof does not exist because Part 14F
created no cloud resource and made no provider call. The contract records that dependency as
`pending-14g-provider-live` and keeps shared promotion blocked. Part 14G must verify the live
Workloop and Keycloak backup schedules, retention, and an isolated point-in-time restore.

## Backup and restore contract

The recovery contract assigns custody and retention to all five backup classes. Portable Workloop
and Keycloak exports use AES-256-GCM before storage and retain seven daily and four weekly copies.
Private object versions retain count, byte, opaque-key, content, and version evidence for 30 days.
Current and prior compatible releases remain available for 90 days. Sanitized recovery evidence
remains available for 365 days.

The database helper accepts only `workloop` or `keycloak`, binds each encrypted export to a release
ID and eight-character key ID, and streams dump bytes without a plaintext archive. Decryption fails
for a changed database, release, key, envelope, or ciphertext. The restore helper accepts only the
exact `workloop-phase14f-restore` project. Database ownership and grants remain in the archive and
the restored Part 14C least-privilege checks passed.

The object helper requires a fresh named target bucket. Its authenticated snapshot includes the
object body and private manifest. The retained repository evidence contains only counts, bytes, and
digests. It contains no object key, filename, body, signed URL, credential, or connection string.

## Write block and release rollback

The restore started PostgreSQL and private S3 first. The API and workers remained stopped until both
database snapshots, Alembic head, identity counts, row counts, per-table count digests, signing-key
ID digest, protected-configuration digest, and private-object evidence matched. The corrected
rehearsal proved why configuration belongs in recovery: a new storage-signing value invalidates
restored private delivery state. The runbook now requires the matching protected configuration from
the security custodian before the API can start.

Rollback requires an explicit prior release ID. The helper rejects the current release, an
unreviewed manifest, a mutable image reference, or a different schema head. The rehearsal selected
the prior reviewed manifest at `e8a1c3f5b7d9`. It never ran or proposed a schema downgrade.

## Focused evidence

The Part 14F contract passed eight tests covering the seven inventory items and five golden cases.
Mutation cases rejected plaintext exports, missing database and signing-key checks, incomplete
object manifests, early writes or workers, missing configuration continuity, implicit or
schema-incompatible rollback, broad cleanup, missing retained evidence, and a false provider-live
claim. Authenticated-encryption tests rejected a changed target and changed ciphertext.

Combined Part 14D through 14F contract coverage passed 35 tests. The full frontend unit suite passed
343 tests. The repository guard inspected 1,057 files. The frontend production build compiled 91
modules; its existing chunk-size warning remained informational. The focused JavaScript lint, shell
syntax, whitespace, Python format, and Python lint checks passed after one line-length repair.

## Boundary-matched local gate

The gate used `workloop-phase14f-source` and `workloop-phase14f-restore` with fresh ignored
credentials and no public network binding. It built the backend once, ran migrations twice,
configured Keycloak twice, and proved authentication. The source passed private S3 access,
authenticated object backup and restore, key rotation, workers, authorization denials, private-file
delivery, and the complete administrator, manager, and employee browser journey.

The gate encrypted both database exports and one nonempty private-object snapshot. The isolated
restore matched the source at Alembic head `e8a1c3f5b7d9`, Workloop identity counts `0:0:0:0:0`,
Workloop row count `2`, Keycloak identity count `1`, Keycloak row count `1597`, both per-table count
digests, the signing-key ID digest, and the protected-configuration digest. The object restore
matched one version, one object, 47 bytes, the opaque-key digest, and the content digest.

Only after those comparisons passed did the gate start the API. The restored target passed
authentication, the complete Part 14C database denial suite, private files, workers, and all three
browser journeys. Browser cleanup returned Workloop identities and rows to the restored baseline.
Keycloak row totals grew from `1597` to `1601` during the login journeys and to `1603` after the
post-restart authentication check. Those extra rows are ephemeral session records. The Keycloak
identity count stayed at `1`, the signing-key digest stayed unchanged, and the restart preserved the
Workloop counts, object bytes and digests, schema head, and backend image identity.

The first integrated attempt generated a new restore-side storage signing key and failed private
delivery. The contract and runbook now require configuration-value continuity. A later attempt mixed
the dedicated restart seed with the browser baseline, so the browser cleanup correctly refused a
zero-residual-data claim. The final gate kept the nonempty object fixture separate from the
browser-clean database backup. The complete journey and cleanup then passed.

The sanitized local evidence is
`docs/migration/phase-14/evidence/PART_14F_LOCAL_RECOVERY.json`, with SHA-256 digest
`bb85666f461e979b95b95fd128a841d16d49aebce83c3d5fd0468fdb2e6c885b` before this completion
record was added.

## Cleanup and preserved resources

The gate retained sanitized evidence before cleanup. It removed the exact restore object bucket
twice to prove idempotence, removed the exact source bucket, and removed only these disposable
volumes:

- `workloop-phase14f-source_postgres_data`
- `workloop-phase14f-source_storage_data`
- `workloop-phase14f-source_phase11b_s3_data`
- `workloop-phase14f-restore_postgres_data`
- `workloop-phase14f-restore_storage_data`
- `workloop-phase14f-restore_phase11b_s3_data`

All six names were absent after cleanup. `workloop-clinic_postgres_data` remained present and was
never attached, mounted, modified, deleted, or recreated. The Phase 13 archive,
`workloop-clinic-dev`, and `fra1-default` were not inspected or changed.

## Next part

Part 14G owns the exact shared-development target manifest, current price review, named operators,
credential custody, provider-live backup evidence, approved DigitalOcean provisioning, maintenance
deployment, complete synthetic promotion gate, and retained rollback point. It must keep promotion
blocked until the live backup dependency recorded here passes.
