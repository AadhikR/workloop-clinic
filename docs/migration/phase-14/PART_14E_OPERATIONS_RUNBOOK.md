# Part 14E operations runbook

## Scope

This runbook covers the persistent shared-development environment and synthetic data. The signal
contract is `infra/digitalocean/operations-signals.json`. The provider fixture is
`infra/digitalocean/operations-alerts.json`. Provider mutation is disabled and no external alert
vendor is configured. Part 14G may activate only the reviewed provider controls after it records
the live resource IDs and named operators.

The application operator owns routine service and worker response. The security custodian owns
authentication, authorization, signing-key, and access-change response. The infrastructure
custodian owns database capacity, object growth, and billing review. The backup custodian owns
backup completion. The release reviewer owns deployment drift and cost-plan acceptance. The
incident operator coordinates critical incidents. Part 14G must replace role names with named
primary and backup people before apply.

## Daily operation

Review the operator console at the start of the Dubai business day. Confirm frontend, API, and
Keycloak probes; database capacity, connections, locks, and backup state; private-object count,
bytes, versioning, and access; expiry completion; worker heartbeats and queue age; deployment
identity; and current spend and forecast. Record only timestamps, counts, sizes, digests, release
IDs, safe resource IDs, safe key suffixes, and approved error codes.

A heartbeat older than 120 seconds is critical. A queue item older than 15 minutes is a warning.
Every recovered expired lease needs a single-mutation check. Three retries for one item or ten in
15 minutes pause new related work. Attempt eight opens an incident. Expiry must have one successful
record for every approved scope and business date by 02:00 Asia/Dubai.

The reviewed fixed plan and forecast must remain at or below USD 70. A value above USD 70 blocks
new work and provider mutation. The existing USD 20 account alert is an early warning. It is not a
spending cap.

## Safe evidence capture

Export candidate records to restricted temporary storage outside Git. Run the evidence helper with
an input and a new output path. The helper accepts only the contract's safe scalar fields and will
not overwrite a file. Inspect the sanitized evidence, compute its SHA-256 digest, move it to the
owner-controlled incident store, then remove the temporary input through the approved local cleanup
procedure.

Reject any record containing a token, password, connection string, private key, object secret,
signed URL, document content, object bytes, request body, email address, filename, or full object
key. Do not paste provider pages or application logs into an incident record. Store a sanitized
record reference and digest instead. Application and worker logs remain for 30 days. Security,
administrator, release, incident, backup, restore, and rollback records remain for 365 days.

## Incident sequence

1. The incident operator creates a record from `incident-record.example.json`, sets `template` to
   false, and records the incident ID, open time, severity, summary code, and named operators.
2. A named application operator enables maintenance and records the timestamp. Stop expiry,
   scanner, and reconciler processing. Do not clear leases or delete queued work.
3. The incident operator sends each owner notification through the existing owner-controlled
   channel and records the time, sender, owner role, and safe record reference. The repository does
   not deliver messages.
4. Capture sanitized evidence. Record its timestamp, named operator, restricted-store reference,
   and digest. Keep databases, private objects, current logs, and release artifacts unchanged.
5. The release reviewer selects the prior reviewed release that matches the current Alembic head.
   Record the selection time, operator, release ID, head, and reason. Never choose a mutable tag or
   perform an automatic schema downgrade.
6. A named operator redeploys the reviewed artifacts in the contract order. Keep maintenance on
   and workers stopped while checking database health, Keycloak readiness and key IDs, API health,
   frontend digest, private objects, and reconciliation state.
7. Record recovery start and verification times, the named operator, and the result. Resume workers
   only after their leases and queues pass. Record the maintenance-disable time only after the
   synthetic authentication and authorization checks pass.

If recovery fails, maintenance stays enabled and the record remains open. Part 14E does not run a
restore. Part 14F owns isolated restore and recovery rehearsal.

## Access and retention review

Every 30 days, the security custodian checks the named primary and backup for each operator role,
MFA state, break-glass records, credential rotation due dates, provider access, and alert ownership.
An absent owner, expired review, disabled MFA, unknown key-ID change, or broader object scope blocks
new work. The reviewer records names, roles, timestamps, and safe account references, never a
credential.

Retention expiry removes only records that have passed their contractual period and have no legal,
security, incident, rollback, or recovery hold. Never delete current incident evidence during
configuration rollback. Reverting 14E removes repository configuration only after the incident
operator confirms required evidence remains in owner-controlled storage.
