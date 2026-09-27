# Part 14B completion

## Result

Part 14B replaced the temporary infrastructure definition with a reusable shared-development
module. The local gate passed on 2026-09-27. Provisioning remains disabled, no provider credential
was supplied, and no DigitalOcean resource, route, state, or secret was created.

The module closes `P14-INF-001` through `P14-INF-010` and golden cases `14A-GC-001` through
`14A-GC-006`. It keeps the Phase 14A catalogue unchanged and retains Alembic head
`e8a1c3f5b7d9`.

## Infrastructure boundary

Terraform now declares the exact project, app, PostgreSQL cluster, two databases, private Space,
and seven application components from the 14A contract. All provider data sources and resources
have a zero count unless provisioning and the complete approval record are present.

The module looks up `fra1-default` by ID `b8b6d17b-eae4-47de-b2b5-9d10baabdd2d`. Before any
resource can proceed, it checks the network name, region, CIDR, and default status. It contains no
VPC resource or import instruction. The app and database use that VPC, and the database firewall
accepts only the app ID.

The Space has a private ACL, versioning, forced deletion disabled, and Terraform destruction
protection. It has no browser CORS rule. The database has one fixed 1 GiB node, fixed 10 GiB
storage, disabled storage autoscaling, and a declared maintenance window. DigitalOcean owns the
native backup schedule for this plan. Part 14G must record the live schedule and retention, and
Part 14F owns portable backup and restore proof.

The API, Keycloak, two workers, migration job, expiry job, and static site have fixed instance
counts and sizes. Deployment on push is false for every source component. The app has no custom
domain and starts in maintenance mode. Only the provider-managed address appears in API and OIDC
settings.

## Decisions

Part 14B declares component shells without database users, object keys, or runtime secrets. Part
14C owns those identities and routes. This avoids carrying the shared Phase 6G database and object
credentials into the persistent design.

The expiry component uses an untriggered App Platform job declaration. Part 14B does not invent an
external scheduler or run it after deploy. Part 14D owns the reviewed invocation and overlap
controls.

The database receives provider tags for environment, data class, Terraform ownership, and operator
role. The app receives the same non-secret ownership values as app-level settings. Spaces has no
tag field in the pinned provider, so its exact name and project assignment are the ownership
controls. The focused verifier requires all three project assignments.

The approval object has 16 non-secret fields. They identify the target manifest, dated approval,
price and retention reviews, state and credential custodians, five operator roles, backup and
variable-charge owners, and cleanup manifest. An enabled plan with any missing field fails input
validation before a provider call. The configuration also requires a separate release-promotion
approval before maintenance mode can be disabled.

Disabled outputs are null. This matters because fixed informational outputs alone would produce an
output-only state change. With null outputs, the disabled plan reports no changes and cannot create
a state record.

Terraform keeps the local backend declaration. Live state must reside in restricted,
owner-controlled storage outside Git. The module accepts only a safe state-path reference. It has
no credential variable or secret output.

## Cost guard

The fixed monthly estimate is USD 65.15:

| Item | Monthly USD |
| --- | ---: |
| API | 10.00 |
| Keycloak | 25.00 |
| File scanner | 5.00 |
| Storage reconciler | 5.00 |
| PostgreSQL | 15.15 |
| Spaces Standard | 5.00 |
| Static site | 0.00 |

The ceiling is USD 70. The verifier rejects missing or unknown line items, size or count drift,
autoscaling, a changed ceiling, and a calculated total other than USD 65.15. Deployment and expiry
job runtime, tax, storage overage, and bandwidth remain variable charges with required owners.

## Focused evidence

The Part 14B verifier passed all 12 tests. Its mutation cases reject a resource in a disabled plan,
name drift, a managed replacement VPC, public or destructive storage, custom or wildcard addresses,
cost drift, autoscaling, automatic deployment, public database sources, secret outputs, missing
ownership labels, and incomplete approval input.

The retained 14A contract verifier passed with 57 inventory items, 38 golden cases, 12 external
facts, and seven later-part owners. The affected workflow, phase-execution, and promotion regression
slice passed 37 tests.

Terraform 1.16.1 formatted and validated the module with DigitalOcean provider 2.100.0. The
isolated verifier copied source and the cached provider into a temporary directory, used disposable
local state, and passed two credential-free plans:

- the default disabled plan reported no changes; and
- `provisioning_authorized = true` with no approval object failed before a provider call.

The repository guard passed with 1,018 files inspected, 238 classified, and 780 reference-free.
The obsolete Phase 6G verifier and variables example were removed. The 14A verifier now checks the
shared database name instead of the retired proof name.

## Boundary-matched local gate

The frontend gate passed 300 unit tests and built the 91-module production graph. The existing
chunk-size warning remained informational. A fresh locked install built twice with matching output
digests and no forbidden environment input.

Backend quality passed 673 tests with six unchanged SQLAlchemy relationship warnings. Ruff lint
and formatting passed 531 files. Pinned Pyright reported zero findings, and the locked environment
had no broken requirements.

Compose project `workloop-phase14b-gate` used fresh synthetic credentials and three disposable
volumes. It built the API image once, started PostgreSQL, FastAPI, Keycloak, and private S3, applied
migrations twice, and configured Keycloak twice. Service health, authentication, the realm count,
and initial safe logs passed.

The restart check recorded the database fingerprint, Keycloak signing-key IDs, local object state,
private S3 object state, and scanner state. It recreated the existing images without rebuilding.
Every recorded value matched, authentication passed without another Keycloak configuration run,
and the administrator, manager, and employee browser journeys passed.

The final checks found no synthetic application or Keycloak users and no secret in service logs.
Cleanup checked the exact Compose project label and exact three-volume set before removing:

- `workloop-phase14b-gate_postgres_data`
- `workloop-phase14b-gate_storage_data`
- `workloop-phase14b-gate_phase11b_s3_data`

`workloop-clinic_postgres_data` was checked by name only. It was never attached, mounted, modified,
deleted, or recreated. The retained Phase 13 archive, `workloop-clinic-dev`, and `fra1-default` were
not inspected or changed.

## Rollback

Before provisioning, rollback is a repository revert of the Part 14B infrastructure, verifier,
tests, and documentation. It needs no provider action. Do not restore the Phase 6G Terraform.

After a later approved apply, rollback starts with maintenance mode and stopped workers. Resource
destruction needs fresh approval for exact names and retained external state. Never delete the
existing project, default VPC, Phase 13 archive, or protected local volume.

## Next part

Part 14C starts only after this commit and every routed GitHub job pass, and the branch is clean and
synchronized. It owns separate database roles, object permissions, runtime secret routes,
bootstrap removal, rotation, revocation, operator access, and its assigned golden cases. It must
not apply the infrastructure or implement Part 14D deployment behavior.
