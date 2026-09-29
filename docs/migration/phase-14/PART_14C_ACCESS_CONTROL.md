# Part 14C access control

## Scope

This contract governs the shared-development identities before Part 14G can run an enabled plan.
It creates no credential and authorizes no provider change. All values remain absent from the
committed example. An enabled plan fails until the approved target manifest supplies the required
operator and secret inputs.

The application database has five login roles: `workloop_migration`, `workloop_runtime`,
`workloop_expiry_processing`, `workloop_file_scanner`, and
`workloop_storage_reconciler`. Keycloak has the separate `keycloak` login role. Every role uses
`NOINHERIT`, has no superuser, database creation, role creation, replication, or RLS bypass right,
and receives an explicit database connection grant. The database and `public` schema grant nothing
to `PUBLIC`. Default privileges also grant nothing to `PUBLIC` on tables, sequences, or functions.
Alembic remains the source of table, column, sequence, function, and RLS grants.

The API, file scanner, storage reconciler, and object backup each receive a separate Spaces key.
The API and reconciler need bucket-scoped `readwrite`. The scanner and backup need bucket-scoped
`read`. DigitalOcean offers bucket-level `read`, `readwrite`, and account-wide `fullaccess` grants.
It does not offer narrower verb combinations. `fullaccess` is forbidden. The migration and expiry
jobs and Keycloak receive no object key because they perform no object action.

## Secret routes

App Platform stores runtime secrets as encrypted `RUN_TIME` settings. Each database URL goes only
to its named component. The two temporary `doadmin` URLs go only to `database-migrate`. Spaces key
pairs go only to the API, scanner, or reconciler that owns the matching key. The object-backup key
has no application route in Part 14C. Part 14F will define its backup process.

The API alone receives storage signing, attachment-key HMAC, cursor signing, and idempotency
recovery values. The scanner alone receives its malware result signing key. Keycloak receives its
database password. Terraform has no bootstrap administrator input and no synthetic-user password
input. The React build receives exactly six public `VITE_` values and no encrypted setting.

Provider-generated database passwords and Spaces key pairs exist in Terraform state after an
approved apply. The state custodian must keep that state encrypted outside Git and restrict it to
the infrastructure and security custodians. Terraform outputs expose identity names only. They do
not expose a password, access key, secret key, URL, token, private key, or signed URL.

## Bootstrap removal and administrator MFA

Part 14G may add Keycloak bootstrap settings outside Terraform for the first start only. The
bootstrap name must differ from the permanent administrator. Before public promotion, an operator
must create the permanent administrator, grant its exact master-realm administrator role, complete
OTP enrollment, and run `keycloak/cloud/arm-admin-totp.sh`.

The script verifies an OTP credential and the administrator role before it deletes the bootstrap
administrator. It then proves that a fresh password-only bootstrap login fails. The operator must
remove both bootstrap settings from App Platform, redeploy Keycloak, and repeat that denial check.
Maintenance mode stays enabled if any step fails. A password-only login by the permanent
administrator is not acceptable evidence. The final check must include its MFA challenge.

## Operator records

The approved 14G target manifest uses a solo operator model. It records one named person who holds
all five role hats:

- infrastructure custodian;
- security custodian;
- application operator;
- incident operator; and
- release reviewer.

The operator record includes one least-privilege routine account reference with MFA, a distinct
emergency account reference with MFA, an offline recovery-material custody reference, and the date
recovery was last tested. The emergency account is a recovery path for the same person, not a fake
backup operator, and it is not used for routine work. The release record must use a separate review
record from the execution record and state which role hat applied to each action. This is procedural
self-review, not independent review; evidence must not claim otherwise. Terraform keeps
`operator_access` null in the committed example and refuses an enabled plan until the complete solo
operator and recovery record passes validation. No placeholder name, shared routine account, or
claimed future MFA enrollment passes the gate.

## Rotation

The credential owner opens a rotation record before creating a replacement. The record names the
credential class, owning component, solo operator, active role hat, start time, verification
method, rollback point, and planned revocation time. It contains no value or connection string.

Create the replacement with the same or narrower rights. Route it only to the owning component,
restart that component, and verify its database or object operations. The old and new values may
overlap only while that verification runs. The maximum overlap is 24 hours. Revoke the old value
as soon as verification passes, then prove the old value fails. If verification fails, restore the
prior route, verify service recovery, revoke the unused replacement, and record the rollback.

Database and Spaces credentials rotate independently. Shared application signing keys use their
existing bounded previous-key format when one exists. A key with no supported overlap format needs
a maintenance window and an exact rollback point. Rotation never adds a second component owner.

## Revocation

Revoke a credential at once when it leaks, its custodian loses access, its owner changes, or its
scope no longer matches this contract. Enable maintenance mode before revoking an API, Keycloak,
database migration, or shared signing credential. Stop the affected worker before revoking a
worker credential. Record the credential name, safe suffix when available, reason, operator,
time, affected component, and denial result.

After revocation, issue a narrower replacement only when the component still needs access. Verify
the new path and prove the revoked path fails. A failed denial check keeps maintenance enabled and
starts the incident process. Do not delete a database, bucket, object, Terraform state, or retained
evidence as part of credential revocation.

## Break-glass access

Direct database, container, or Keycloak administrator access is break glass. Acting under the
incident-operator hat, the solo operator records a reason, exact target, start time, and expiry
before access. The maximum lifetime is one hour, with one recorded extension of at most one hour.
The distinct emergency account uses MFA, remains unused for routine work, and keeps its recovery
material offline and separate from the routine credential. The custody record stores only a safe
reference, never the recovery material. No shared standing administrator account is allowed.

At expiry, revoke the session or temporary credential, prove later use fails, and review every
action against provider and application audit records. Missing approval, missing MFA, an expired
window, or unavailable audit evidence blocks access. Emergency access never authorizes a schema
change, data export, or resource deletion outside the approved incident action.

## Safe evidence

Evidence may contain identity names, role names, resource identifiers, safe key suffixes,
timestamps, MFA status, denial results, and SHA-256 digests. It must not contain passwords, access
keys, secret keys, database URLs, tokens, private keys, signed URLs, OTP seeds, recovery codes,
Terraform state, private objects, document contents, or command output that embeds those values.

Capture the check name and result instead of raw environment or provider output. Redact a failed
command before attaching it. Store any restricted audit export outside Git under the named evidence
custodian. The repository keeps only the sanitized record reference and digest.

## Fail-closed decisions

DigitalOcean Spaces permissions are coarser than the application operation list. The plan uses the
narrowest bucket-scoped provider permission and rejects `fullaccess`. Live verification in 14G must
prove the expected allowed and denied actions. A mismatch stops before promotion.

The repository does not name the real solo operator. Guessing would turn an unresolved control into
false evidence, so the committed input remains null. Part 14G must supply the exact operator,
account, recovery, and role-hat references in the approved target manifest.

Bootstrap values do not belong in Terraform because they would remain in state and in the
application specification. Part 14G may add them for the first start through its restricted
operator process, then must remove them before promotion.
