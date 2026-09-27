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
Every source component disables deployment on push.

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

The configuration ceiling is USD 70. An enabled plan fails when the estimate exceeds that value.
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
must prove the portable backup and isolated restore rules. Database storage autoscaling stays off
so a plan cannot exceed the cost calculation without review.

## Approval input

`shared-development.tfvars.example` is safe to validate as committed because provisioning is
false and `approval` is null. An enabled plan requires all 16 non-secret approval fields. They bind
the target manifest, dated approval, price review, retention review, state custody, credential
custody, five operator roles, backup custody, variable-charge ownership, and cleanup manifest.

The approval object contains names and record references, never a token, password, private key,
database URL, Spaces key, signed URL, or private object.

The separate `operator_access` object requires primary and backup names, distinct least-privilege
account references, and confirmed MFA for all five operator roles. It remains null in the committed
example. Missing or incomplete operator data blocks an enabled plan. Part 14G must supply exact
people and accounts in the approved target manifest. The repository does not invent them.

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

## Rollback boundary

While provisioning remains disabled, rollback means reverting the Part 14B and 14C source files and
their focused checks. It does not include a provider action. Once Part 14G creates shared resources,
rollback starts with maintenance mode and stopped workers. Rotate or revoke any created credential
before reverting its route. Resource destruction needs fresh approval for exact names and the
retained external state. Never delete `fra1-default`, the existing project, the Phase 13 archive,
or the protected local `workloop-clinic_postgres_data` volume.
