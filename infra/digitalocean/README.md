# DigitalOcean shared-development infrastructure

This module describes the persistent `workloop-clinic-dev` environment. It accepts synthetic
identities, rows, and files only. Provisioning is off by default, and a disabled plan contains no
resource or data-source operation.

Parts 14B and 14C validate this configuration without an API token and without contacting
DigitalOcean. Do not apply it before Part 14G records and receives approval for the exact target
manifest.

## Fixed resources

The module names the existing `workloop-clinic-dev` project and the existing `fra1-default` VPC.
It looks up the VPC by ID `b8b6d17b-eae4-47de-b2b5-9d10baabdd2d` and checks its name, region,
CIDR, and default status. Terraform must not create, import, rename, or manage that VPC.

An approved plan contains these project members:

- the `workloop-clinic-dev` App Platform app in `fra`;
- the `workloop-clinic-dev-db` PostgreSQL 16 cluster in `fra1`, with one
  `db-s-1vcpu-1gb` node and fixed 10 GiB storage;
- the `workloop` and `keycloak` databases;
- the private, versioned `workloop-clinic-dev-634213f9` Space; and
- seven app components named `database-migrate`, `api`, `keycloak`, `web`, `expiry`,
  `file-scanner`, and `storage-reconciler`.

The API has one `apps-s-1vcpu-1gb-fixed` instance. Keycloak has one
`apps-s-1vcpu-2gb` instance. Each worker has one `apps-s-1vcpu-0.5gb` instance. The static site is
included at no fixed monthly charge. Migration and expiry job runtime remains a variable charge.
The static site disables deployment on push. The other six components use reviewed image digests,
so they have no branch source or mutable tag to watch.

The fixed estimate is USD 65.15 per month before tax and overages:

| Item | Monthly USD |
| --- | ---: |
| API | 10.00 |
| Keycloak | 25.00 |
| File scanner | 5.00 |
| Storage reconciler | 5.00 |
| PostgreSQL | 15.15 |
| Spaces Standard | 5.00 |
| Static site | 0.00 |

The architecture configuration ceiling is USD 70. The current owner cap is stricter: USD 15 total
usage. Because the fixed target is USD 65.15, every enabled plan fails until the architecture is
revised below the owner cap.
Deployment and scheduled-job runtime, tax, storage above the included allowance, and bandwidth
overages need named owners in the approved target manifest.

## Network, storage, and address rules

The database and app bind to the existing VPC. The database firewall accepts only the app ID. The
module has no public IP or CIDR database rule.

The Space uses a private ACL, versioning, `force_destroy = false`, and Terraform destruction
protection. It has no browser CORS rule. Component-specific object keys and secret routes belong to
Part 14C.

App Platform supplies the only public address and terminates TLS. The module declares no custom
domain. Frontend URLs use `APP_URL`, and the Keycloak realm permits only that exact origin and its
`/oidc/callback` path. The initial app stays in maintenance mode. Disabling maintenance requires a
separate recorded promotion approval.

The managed database includes provider-managed native backups. DigitalOcean controls their live
schedule and retention for this plan. Part 14G must record those provider settings, and Part 14F
must prove the portable backup and isolated restore rules. Provider version `2.100.0` rejects an
explicit disabled storage-autoscaling block during cluster creation because it sends a zero
threshold. The module omits that optional block, which leaves storage autoscaling disabled on
creation. Part 14G must verify the live disabled setting before traffic begins.

## Approval input

`shared-development.tfvars.example` is safe to validate as committed because provisioning is
false and `approval` is null. An enabled plan requires all 16 non-secret approval fields. They bind
the target manifest, dated approval, price review, retention review, state custody, credential
custody, five operator roles, backup custody, variable-charge ownership, and cleanup manifest.

The approval object contains names and record references, never a token, password, private key,
database URL, Spaces key, signed URL, or private object.

The separate `operator_access` object uses a solo-owner model. It requires one named operator, an
MFA-protected least-privilege routine account, a distinct MFA-protected emergency account, an
offline recovery-material custody reference, a dated recovery test, all five role hats, and a
separate review record. It remains null in the committed Terraform example. Missing or incomplete
operator data blocks an enabled plan. Part 14G must supply the exact person and safe references in
the approved target manifest. The repository does not invent them.

## Identities and secret routes

Terraform declares six database users: `workloop_migration`, `workloop_runtime`,
`workloop_expiry_processing`, `workloop_file_scanner`, `workloop_storage_reconciler`, and
`keycloak`. The bootstrap sets every role to `NOINHERIT`, removes broad database and schema grants,
and removes `PUBLIC` default privileges. Alembic grants the application roles only their required
tables, columns, sequences, and functions.

Four Spaces keys have exact bucket scope. The API and storage reconciler receive `readwrite`. The
file scanner and object-backup process receive `read`. The provider does not support a narrower
verb matrix, so the configuration rejects account-wide `fullaccess`. Live 14G verification must
prove the allowed and denied operations.

App Platform database bindings route each URL only to its component. Spaces key pairs follow the
same rule. The API receives its application signing values, and the scanner receives its malware
result signing value. The Keycloak service receives only its runtime database credential. Bootstrap
administrator settings are absent from Terraform and must be removed after the first-start process.

The web build has exactly six public settings: API base URL, OIDC authority, client ID, callback,
post-logout callback, and audience. It receives no encrypted setting. Terraform outputs contain
only resource identifiers, identity names, the cost result, and readiness flags. They never contain
credentials or private connection values.

`runtime_secrets` is sensitive and null in the committed example. Part 14G must supply its values
from restricted owner-controlled custody. Terraform state will contain provider-generated database
passwords and Spaces keys after an approved apply, so the state rules below are mandatory.

The full operator, rotation, revocation, bootstrap removal, break-glass, and evidence rules are in
`docs/migration/phase-14/PART_14C_ACCESS_CONTROL.md`.

## Release manifest and component order

`release-manifest.schema.json` defines the release record. The committed
`release-manifest.example.json` cannot deploy because `deployable` is false. A deployable copy must
record one full Git commit, the backend and Keycloak image coordinates and digests, the frontend
tree and root digests, all three dependency lock digests, the Terraform digest, the app spec
contract digest, and Alembic head `e8a1c3f5b7d9`. The target approval must name the same release ID.

Create a release record only from a clean reviewed commit and already-published image digests. The
manifest helper refuses to overwrite its output file. It also validates the current frontend,
dependency lock, Terraform, and app spec bytes before the record can be used. Keep the resulting
manifest with the release evidence outside Terraform state.

Terraform uses the backend image digest for migration, API, expiry, scanner, and reconciler. It
uses the separate Keycloak image digest for Keycloak. The web component builds only the manifest's
full commit and fails its build unless `dist` and `index.html` match the recorded digests.
Automatic branch deployment stays disabled. A branch name, mutable tag, provider label, or rebuild
with different bytes cannot satisfy the release contract.

App Platform runs `database-migrate` as the sole pre-deploy job. It checks the manifest head,
applies Alembic, requires exactly one row at `e8a1c3f5b7d9`, and reports whether the schema was
already current. A failed or incompatible migration blocks the deployment. Maintenance remains on,
expiry refuses to run, and the two workers refuse claims until the release promotion record passes.

Promotion also requires a nonempty `expiry_scopes` list. One manual expiry invocation processes
every listed company and optional branch under the expiry database identity and one advisory lock
per scope and business date. If no date is supplied for a controlled replay, the command uses the
current `Asia/Dubai` date. App Platform does not schedule this job; the named operator must start
the daily invocation and retain its safe completion record. The scanner and reconciler promotion
gate does not depend on the expiry scope list.

Both workers use one instance, one-row claims, 15-minute leases, eight attempts, and the fixed retry
delays in `app-spec.contract.json`. App Platform gives each worker 120 seconds to terminate. The
worker stops claiming immediately, waits up to 105 seconds for its current claim, and then releases
that claim with a bounded retry if it is still running.

## State custody

The module keeps the local backend boundary because this repository cannot choose the owner's
storage system. Live state must sit in restricted owner-controlled storage outside the repository.
The custodian must encrypt it, restrict access, retain it for exact rollback or destruction, and
record only a safe path reference in the approval object.

Never place a state file, plan, backup, provider token, Spaces key, password, or signed URL under
this directory. The repository ignores common Terraform working files, but ignore rules do not
replace restricted storage or access control.

## Disabled validation

Use the pinned Terraform image and provider cache. The verifier copies the Terraform source and
provider into a temporary directory, initializes a disposable local state path, validates the
module, and proves that the disabled plan has no changes. It also proves that an enabled plan with
missing approval, operator, or runtime-secret fields fails before a provider call.

```powershell
docker run --rm --volume "${PWD}/infra/digitalocean:/source:ro" --volume "${PWD}/scripts:/verification:ro" --entrypoint sh hashicorp/terraform:1.16.1 /verification/verify-phase-14b-terraform.sh /source
```

The plan must report no changes. Do not pass provider credentials during this check. Do not run
`apply` before the approved Part 14G window.

## Operations contract

`operations-signals.json` assigns one owner, severity, threshold, response, retention period, and
test method to each frontend, API, security, database, object, worker, deployment, backup, and cost
signal. `operations-alerts.json` maps those signals to provider or application sources. Provider
mutation and external delivery remain disabled. Part 14G must add exact live resource references
and the named solo operator before it can activate any provider control.

The API emits request duration, status, and denial or rate-limit conditions without paths, query
strings, headers, bodies, or identities. Workers emit heartbeat, queue-age, expired-lease, retry,
and terminal-failure events through the strict safe-field logger. Use the Part 14E evidence helper
and incident schema for operator records. The persistent procedure is in
`docs/migration/phase-14/PART_14E_OPERATIONS_RUNBOOK.md`.

The original USD 70 configuration ceiling remains an architecture check. The owner's stricter USD
15 total-usage cap blocks every enabled plan for the current USD 65.15 target. The existing USD 20
account alert is an early warning, not a spending cap.

## Part 14G live control

`phase-14g-target-manifest.example.json` fixes the approved target shape but cannot authorize work.
Its provider facts, solo-operator record, custody references, release identity, digest, and approval stay
empty. Keep the completed manifest outside Git. It must contain no credential or secret value.

Run the target check before asking for paid-resource approval:

```powershell
node scripts/phase-14g-control.mjs validate-target --target <restricted-target-manifest.json>
```

After the owner approves that exact digest and cost, `authorize-apply` checks the approval and the
30-minute authenticated preflight window. A successful check still leaves maintenance on and the
workers stopped. It does not call Terraform or change DigitalOcean.

The owner set a USD 15 total-usage cap for Part 14G and chose manual cleanup. The unchanged
architecture is USD 65.15 for a full billing month, while the conservative 72-hour base projection
is USD 6.99. The release images use a DigitalOcean Basic private registry in `fra1`; the run forecast
counts its full USD 5 monthly price. The approved plan is 48 hours, so the restricted manifest must
cover USD 4.66 of runtime resources, the registry, current accrued usage, and a positive tax and
variable-usage reserve without exceeding USD 15. The USD 20 account alert is only a notification;
no cleanup is automatic.

`phase-14g-live-record.example.json` lists every provisioning, backup, recovery, restart, redeploy,
journey, promotion, retention, and rollback fact required after apply. Fill its restricted copy from
safe evidence. Use `validate-live` before asking for release promotion, then use
`authorize-promotion` against the same target and live record. These checks validate records only.
The operator follows `docs/migration/phase-14/PART_14G_RUNBOOK.md` for every provider action.

## Rollback boundary

While provisioning remains disabled, rollback means reverting the Part 14B and 14C source files and
their focused checks. It does not include a provider action. Once Part 14G creates shared resources,
rollback starts with maintenance mode and stopped workers. Rotate or revoke any created credential
before reverting its route. Resource destruction needs fresh approval for exact names and the
retained external state. Never delete `fra1-default`, the existing project, the Phase 13 archive,
or the protected local `workloop-clinic_postgres_data` volume.
