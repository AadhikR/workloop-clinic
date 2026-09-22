# Part 11B scanner runbook

## Boundary

The file scanner is a separate worker with the `workloop_file_scanner` login. It can select and
update `file_security_scans` under the scheduled-job context. It has no grant on business tables,
`audit_events`, or `storage_operations`. The protected audit function is the only scanner path into
the audit log.

The tracked scanner is deterministic and test-only. It reports `infected` only for the synthetic
marker in `app.storage.malware.SYNTHETIC_MALWARE_MARKER`. Production scanning stays disabled until
the owner approves a provider, credentials, cost, data location, alert route, and operator contract.

## Start and inspect

Generate local credentials with `scripts/new-local-postgres-env.ps1`. Start the worker through the
`file-scanner` Compose service. Set `FILE_SCANNER_ONCE=1` for one maintenance and claim cycle.

Inspect queue state through a migration-role database session. Use only scan UUID, entity type,
status, attempt count, scanner definition, safe error code, and timestamps. Do not copy object keys,
filenames, digests, employee IDs, signed URLs, or file content into tickets or logs.

## State and retry handling

- `pending` is unavailable for download and ready for the first claim.
- `claimed` holds a 15-minute lease. An expired lease can be reclaimed below attempt eight.
- `clean` permits signing for 30 days only when object metadata and scanner definition still match.
- `infected` stays unavailable. Replacement requires a new approved upload and object.
- `failed` retries after 1 minute, 5 minutes, 15 minutes, 1 hour, 6 hours, 24 hours, and 72 hours.
  Attempt eight is terminal.

Provider absence records `object_missing`; metadata mismatch records `integrity_error`; provider
failure records `provider_error`; scanner failure records `scanner_error`; and an expired eighth
lease records `retry_exhausted`. Each code is safe for operational output.

## Manual requeue

Manual requeue is allowed only for a failed scan at attempt one through seven. Use the scanner role,
set the exact company and branch context, and call `requeue_file_security_scan(scan_id)`. The
function makes the row immediately due without resetting its attempt count or error code and writes
`storage_manual_requeue` through the protected audit path. A terminal, clean, infected, claimed,
pending, or wrong-scope row returns false or is denied.

Do not edit retry timestamps, attempt counts, status, or audit rows directly. Investigate and fix the
provider or scanner cause before requeueing. A requeue that fails again continues the normal retry
schedule.

## Verification

Run `scripts/verify-phase-11b-database.py` in the isolated Compose network. It proves fail-closed
downloads, clean and infected results, concurrent claims, every retry delay, expired leases,
terminalization, manual requeue, restricted grants, RLS, audit metadata, and cleanup.
