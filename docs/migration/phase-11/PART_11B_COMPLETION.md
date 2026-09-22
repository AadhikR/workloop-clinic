# Part 11B completion

Status: implementation and local gate complete; awaiting the routed GitHub result.

## Result

Part 11B adds one private-file safety boundary for leave attachments and expense receipts without
changing their Phase 8 or Phase 9 business permissions. Upload completion creates a pending scan in
the same database transaction as metadata and durable upload success. Download signing fails closed
until the linked row has a current clean result for the exact object metadata and scanner definition.

Alembic revision `d8f0a2c4e6b1` follows `c6e8a1b3d927`. It adds the scan queue, same-scope links,
restricted scanner role, forced RLS, transition guard, protected scan audit, audited manual requeue,
and protected recovery audit actions. The scanner worker reserves attempts, uses the approved retry
schedule, terminalizes attempt eight, and emits safe identifiers and error codes only.

The storage layer now enforces the approved PDF, PNG, JPEG, 10 MiB, digest, private-cache, and
conditional-create contract. Encrypted AES-256-GCM snapshots authenticate a canonical manifest and
restore objects only after metadata, digest, count, and scan-binding checks. A failed restore removes
its partial writes. The disposable local S3 target proves privacy, signing, backup, restore, restart,
and recovery-key rotation.

## Gate evidence

- All 573 backend tests, Ruff lint and formatting, Pyright, and dependency checks passed.
- All 226 frontend unit tests and the legacy and migration production builds passed.
- A fresh isolated database applied the empty-schema chain and the Phase 11B migration twice.
- The exact `c6e8a1b3d927` predecessor rollback and `d8f0a2c4e6b1` replay passed.
- Deep checks covered scanner grants, RLS, transition guards, fail-closed signing, clean and infected
  results, claim concurrency, all retry delays, terminalization, manual requeue, and safe audit data.
- The local S3 checks covered private listing, conditional create, signing, encrypted snapshot,
  tamper rejection, exact restore, cleanup, key rotation, and the 15-minute local objective.
- Existing images restarted without rebuilding. Database state, Keycloak signing keys, synthetic
  storage, an S3 object, and clean scan state persisted. Authentication and service health passed.

The routed GitHub result is reported in the task handoff after the final push. This file does not
store a workflow URL.

## Resource boundary

Verification used synthetic local rows and files. The SeaweedFS container and its buckets were
disposable local targets. The protected `workloop-clinic_postgres_data` volume was not attached,
modified, deleted, or recreated. The isolated gate containers, network, credentials, synthetic data,
buckets, and temporary volumes were removed after the evidence was recorded.

No production provider, scanner, bucket, retention rule, backup schedule, RPO, RTO, restore owner,
credential, cloud resource, paid service, production data, or real employee file was approved or
used. Production storage remains disabled at this policy stop.

## Rollback and next step

Disable migration provider and scanner writes before restoring a legacy writer. Preserve domain
metadata, object state, scan history, audit evidence, and durable operations. Restore reads only
after one authorized storage writer exists and retained state reconciles. The common adapter rolls
back last after every Phase 8, 9, and 11 consumer has another approved path.

Part 11C is next under the project owner's sequential authorization after the routed GitHub checks
for this commit pass.
