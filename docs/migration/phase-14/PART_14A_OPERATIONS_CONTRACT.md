# Part 14A operations contract

## Purpose and boundary

The DigitalOcean environment is persistent shared development for synthetic identities, rows, and
files only. It may run the complete Workloop application so engineers can test deployments,
recovery, rollback, and operations. It is not a production environment and cannot hold real patient,
employee, payroll, banking, biometric, identity, or document data.

Phase 14 excludes custom domains, email, SMS, push delivery, an external scheduler, analytics, Azure,
and any change to the retained Phase 13 external archive. The protected local
`workloop-clinic_postgres_data` volume must not be attached, mounted, modified, deleted, or
recreated.

## Fixed environment

The existing DigitalOcean project is `workloop-clinic-dev`. The app name is
`workloop-clinic-dev`. App Platform uses region `fra`; provider resources use `fra1`. Terraform
looks up the existing `fra1-default` VPC by its verified identity and leaves it outside Terraform
state. It must not create a replacement VPC or import the default VPC into Phase 14 state.

The managed cluster is `workloop-clinic-dev-db`. It contains `workloop` and `keycloak`. The private
bucket is `workloop-clinic-dev-634213f9`. Part 14G must fail before apply if any name is unavailable,
already belongs to an unrelated resource, or no longer resolves to the approved account and project.

The application uses only the provider-managed App Platform default address. A custom domain is not
authorized. The provider terminates TLS. CORS, OIDC issuer, redirect, logout, and web origins must
name that exact default address. Wildcards fail validation.

## Components and release identity

The app has seven components:

| Component | Type | Instances | Contract |
| --- | --- | --- | --- |
| `database-migrate` | pre-deploy job | one | Bootstrap roles, run Alembic, and exit only at one head, `e8a1c3f5b7d9`. |
| `api` | service | one | Serve FastAPI on port 8000 and pass the database-backed health check. |
| `keycloak` | service | one | Serve the `workloop-dev` realm and internal management health on port 9000. |
| `web` | static site | one | Serve the reviewed `dist` bytes and no secret build value. |
| `expiry` | scheduled job | one invocation | Process every approved synthetic scope once per business date. |
| `file-scanner` | worker | one | Claim and scan one object at a time. |
| `storage-reconciler` | worker | one | Claim and reconcile one object operation at a time. |

Each release manifest records the full Git commit, backend image digest, Keycloak image digest,
frontend output digest, dependency lock digests, Terraform digest, App Platform spec digest, and
Alembic head. Automatic branch deployment is disabled. Mutable tags, an unrecorded rebuild, a branch
name alone, or a provider label alone cannot identify a release.

## Maintenance and promotion sequence

Maintenance mode starts enabled for the first deploy and every incompatible update. Operators use
this order:

1. Confirm the exact target manifest, owner approval, cost, state path, and short-lived credentials.
2. Create or update only the approved project assignments, database, bucket, application, and scoped
   identities.
3. Run `database-migrate` and prove that the exact head exists. A second run must report no pending
   change.
4. Start Keycloak, remove bootstrap access, require administrator MFA, and record signing-key
   identifiers without key material.
5. Start API and web. Start the workers with processing disabled until their secret routes, health,
   leases, and safe logs pass.
6. Prove backups, isolated recovery, restart persistence, and the synthetic administrator, manager,
   and employee journeys.
7. Record the release reviewer and owner promotion approval. Enable worker processing, then disable
   maintenance mode.

A failed step leaves maintenance enabled and workers stopped. It never selects an older artifact or
destroys a resource automatically.

## Health and worker rules

`database-migrate` exits zero only when one head equals `e8a1c3f5b7d9`. `api` must return HTTP 200
from `/health` with `status` and `database` both `ok` within five seconds. Keycloak must return HTTP
200 from `/management/health/ready` on internal port 9000, after which issuer discovery and JWKS must
work through `/auth`. The web root must return HTTP 200 and match the release digest.

The expiry job records its business date and tenant scope, exits zero, and uses one database advisory
lock for each company, branch scope, and business date. Scanner and reconciler each run one instance.
Each loop claims one row, holds a 15-minute lease, makes at most eight attempts, and uses delays of
1, 5, 15, 60, 360, 1,440, and 4,320 minutes. An idle loop waits five seconds. A sanitized heartbeat
or completed claim must be no older than two minutes.

Termination stops new claims. A worker finishes its current claim or releases it before the App
Platform termination window ends. A stale lease is recoverable without a duplicate successful
mutation.

## Identities, secrets, and access

Database login roles remain separate: `workloop_migration`, `workloop_runtime`,
`workloop_expiry_processing`, `workloop_file_scanner`, `workloop_storage_reconciler`, and
`keycloak`. Part 14C proves explicit grants, `NOINHERIT` where defined, denied cross-role operations,
and the absence of broad `PUBLIC` or default privileges.

The API, scanner, reconciler, and backup process receive separate bucket permissions. The web build
receives only the six public API and OIDC settings. It never receives a password, token, connection
string, object secret, HMAC key, signing key, or signed URL.

Runtime secrets live in encrypted App Platform settings and route only to the component that owns
them. Bootstrap values are short lived and removed or revoked after setup. Terraform state is
encrypted in owner-controlled storage outside Git. Git contains no state, plan, backup, token,
password, private key, signed URL, or private object.

Five operator roles must have a named primary, named backup, least-privilege account, and MFA before
apply: infrastructure custodian, security custodian, application operator, incident operator, and
release reviewer. Routine work uses provider and application controls. Direct database, container,
or Keycloak administrator access is break-glass access with a reason, start time, expiry, and review.

## Monitoring and evidence retention

Part 14E assigns an owner, severity, threshold, response, retention period, and test method to each
of these signals:

- frontend availability;
- API availability, latency, failures, authorization denials, and rate limits;
- Keycloak readiness, login failures, and signing-key changes;
- PostgreSQL capacity, connections, locks, and backup state;
- private object growth, failures, versioning, and access changes;
- expiry completion;
- scanner and reconciler heartbeat, queue age, attempts, leases, and terminal failures;
- deployment and component state; and
- monthly spend and forecast.

Sanitized application and worker logs are kept for 30 days. Security, administrator, release,
incident, restore, and rollback records are kept for 365 days. Current and prior compatible release
artifacts stay available for at least 90 days. Evidence contains names, identifiers, timestamps,
counts, sizes, safe key suffixes, and digests. It excludes protected values and document contents.

## Backup classes and recovery

The environment has five backup classes:

| Class | Content | Minimum retention |
| --- | --- | --- |
| `DB-NATIVE` | Provider backups and point-in-time recovery for both databases | Verify the provider schedule and retention at 14G. |
| `DB-PORTABLE` | Encrypted logical exports of `workloop` and `keycloak` | Seven daily and four weekly copies. |
| `OBJECT-VERSIONS` | Private object versions and count, byte, key, and digest manifests | Keep deleted versions for 30 days. |
| `RELEASE` | Release manifest, app spec, configuration names, digests, and schema head | Keep current and prior compatible releases for 90 days. |
| `RECOVERY-EVIDENCE` | Sanitized restore and rollback records | Keep for 365 days. |

Recovery always uses isolated targets. Put the shared app in maintenance and stop workers first.
Create named recovery targets, restore both databases, restore private object versions, then deploy
the matching Keycloak artifact. Verify signing-key continuity before login tests. Deploy the matching
API and web with writes and workers disabled. Check the schema, identities, authorization, files,
reconciliation, and browser journeys. Enable isolated writes only for the rehearsal. Retain sanitized
evidence, then remove only the named recovery targets.

## Promotion evidence

Promotion needs all of the following in one record:

- the approved target manifest, current price inputs, and resource identifiers;
- named operators, MFA state, credential custody, and the dated owner approval;
- release, dependency, Terraform, app spec, frontend, image, and schema digests;
- exact database and object permission routes;
- component health, worker state, and safe-log results;
- native backup status and isolated restore proof;
- restart and redeploy persistence;
- synthetic administrator, manager, and employee journeys; and
- the last compatible rollback point.

Missing evidence keeps maintenance enabled. A passing provider deployment status alone is not a
promotion result.

## Rollback

Runtime rollback uses this order:

1. Enable maintenance mode.
2. Stop expiry, scanner, and reconciliation processing.
3. Select the prior reviewed artifact set that is compatible with the current schema.
4. Preserve databases, private objects, logs, and incident evidence. Never downgrade the schema
   automatically.
5. Redeploy Keycloak, API, web, scanner, reconciler, and expiry from that release manifest.
6. Verify health, authentication, authorization, objects, and reconciliation before resuming workers.
7. Disable maintenance only after the operator records the result.

Repository and part rollback follows 14H, 14G, 14F, 14E, 14D, 14C, 14B, then 14A. Cloud destruction
is separate. A rollback cannot delete or recreate the retained VPC, retained project, Phase 13
archive, or protected local volume.

## Cost and retention

The current fixed estimate is USD 65.15 per month before tax and overages. It covers the API,
Keycloak, two workers, PostgreSQL, Spaces, and the included static site. Migration and expiry jobs,
storage beyond 250 GiB, and excess bandwidth are variable.

The configuration ceiling is USD 70 per month. Part 14G stops before apply when the fixed plan exceeds
USD 70 or any variable charge lacks an owner. The existing USD 20 alert is an early warning, not a
spending cap. Part 14G must review the current price and alert state in the same target manifest that
receives owner approval.

Retain `workloop-clinic-dev` and `fra1-default`. After promotion, retain the approved app, database,
and bucket while a named owner completes a cost and access review every 30 days. If the review,
ownership, or cost evidence lapses, enable maintenance mode and stop workers. Do not destroy anything
automatically. Destruction needs fresh approval for exact named resources and retained Terraform
state.

## Risk register

| Risk | Fail-closed decision | Owner |
| --- | --- | --- |
| Price or product availability changes before apply | Refresh official prices and provider availability. Stop on any unresolved size or region. | 14G |
| The default VPC identity changes or gains unrelated members | Stop before plan. Do not create a replacement, import it, or move unrelated resources. | 14B, 14G |
| A global bucket name is unavailable | Stop and amend the reviewed target manifest before approval. Do not append a random value during apply. | 14B, 14G |
| Provider-generated secrets enter Terraform state | Keep encrypted state outside Git, restrict its custodians, and rotate exposed material. | 14C |
| Keycloak bootstrap access remains usable | Keep maintenance enabled and deny promotion until bootstrap removal and fresh MFA login pass. | 14C, 14G |
| A worker duplicates an object mutation | Use one instance, one-row claims, leases, idempotent transitions, and stale-lease tests. | 14D |
| Monitoring cannot retain the required safe evidence | Keep maintenance enabled until a repository-owned capture method passes without protected values. | 14E |
| Native backup retention is shorter than required | Use the portable encrypted backup class and stop promotion until its isolated restore passes. | 14F |
| An older artifact is incompatible with the current schema | Keep the current release in maintenance. Never select an automatic schema downgrade. | 14F, 14G |
| Named operators or exact approval are missing | Do not apply or promote. Record the unresolved item without guessing. | 14G |
