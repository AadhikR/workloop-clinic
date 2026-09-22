# Part 11B storage recovery runbook

## Boundary

PostgreSQL metadata is the ownership source. Provider listing is diagnostic input only. The local S3
service and its buckets are disposable test resources. This runbook does not approve a production
bucket, retention period, backup location, schedule, RPO, RTO, credential, restore owner, external
scanner, cloud resource, or paid service.

The local objective is recovery from the latest completed encrypted snapshot in under 15 minutes.
It is a test assertion, not a production promise.

## Backup

1. Stop storage mutations for the scoped test fixture.
2. Read the authoritative object, scan, and durable-operation rows from PostgreSQL.
3. Fetch only the object keys named by those rows.
4. Build the canonical manifest and verify size, media type, SHA-256, record count, and scan binding.
5. Encrypt the manifest, metadata, and bodies with AES-256-GCM under the current recovery key ID.
6. Persist the encrypted payload in the approved disposable target.
7. Record `storage_backup_completed` with an operation UUID and `sha256:` manifest digest through
   `append_storage_recovery_audit`.

Never print the recovery key, provider credential, object key, filename, file digest, signed URL, or
employee ID. A partial snapshot is not complete and cannot be a restore source.

## Restore

1. Keep reads and writes disabled for the target.
2. Restore into an empty target with the recovery key named by the snapshot envelope.
3. Authenticate the AES-GCM envelope before accepting the document.
4. Verify the canonical manifest digest, object count, unique keys, metadata, object digest, scan
   binding, and durable-operation rows.
5. Roll back every object written by the attempt if any check or write fails.
6. Reconcile restored PostgreSQL references against the target. Do not infer ownership from listing.
7. Run the signed-download and scanner release checks before enabling reads.
8. Record `storage_restore_verified` with the operation UUID and manifest digest through the
   protected recovery audit function.

## Credential and key rotation

Install the new credential or recovery key before using it. Prove a new write and read, prove that a
snapshot encrypted with the previous approved key remains readable during the overlap, switch the
current key ID, and then revoke the old credential. Record `storage_credential_rotated` with an
operation UUID and no manifest digest. Do not print either value.

## Failure handling

A missing object, digest mismatch, metadata mismatch, unknown key ID, authentication failure,
duplicate key, nonempty restore target, or count mismatch stops recovery and leaves reads disabled.
Preserve database metadata, scan rows, operation rows, and the failed snapshot for investigation.
Use safe operation IDs and allowlisted error codes in logs.

## Local proof

`scripts/verify-phase-11b-storage.py` proves private listing, conditional create, five-minute signing,
encrypted backup, exact restore, tamper rejection, key rotation, cleanup, and the 15-minute local
objective against the disposable S3-compatible service. `scripts/verify-phase-11b-restart.py` proves
that an S3 object and clean scan state survive restart before removing its synthetic rows and bucket.
