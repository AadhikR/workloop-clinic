# Phase 14 subphase plan

## Status and authorization

The project owner signed off Phase 13 and started Part 14A on 2026-09-27. That instruction
authorizes Parts 14A through 14H under `docs/migration/PHASE_EXECUTION_WORKFLOW.md`. Each part runs
in a separate Codex task. A part must pass its focused checks, boundary-matched local gate, push,
and routed GitHub jobs before the next part starts automatically.

Phase 14 starts from commit `9535d8a74dee109ee29c1d31ff9db81442b45770` on
`migration/fastapi-keycloak`. GitHub Migration foundation run `36318950588` passed. Alembic has one
head at `e8a1c3f5b7d9`. The branch is clean and synchronized. The protected
`workloop-clinic_postgres_data` volume remains present and must not be attached, modified, deleted,
or recreated.

The earlier Phase 6G proof resources are gone. Its empty non-billable `fra1-default` regional VPC
remains outside Terraform state. The `workloop-clinic-dev` project had no App Platform application
at the Phase 13 closing review. Part 14A must verify current external facts before relying on them.

## Phase boundary

Phase 14 turns the retired Phase 6G architecture proof into a repeatable shared development
deployment. It uses default App Platform addresses, synthetic identities and data, managed
PostgreSQL, private object storage, Keycloak, FastAPI, the React static site, explicit workers, and
reviewed release promotion. It adds cost controls, least privilege, monitoring, backups, restore
proof, rollback evidence, and operator ownership.

This phase does not deploy real clinic data or claim production readiness. Phase 15 is the planned
continuation for the integrated Workloop portal, final cross-system validation, recovery acceptance,
and release validation on DigitalOcean. Phase 15 has no approved subphase plan or standing
authorization yet. Phase 14 may prepare portable artifacts for that work, but it cannot weaken the
current DigitalOcean synthetic-only restriction.

The following work remains outside standing authorization:

- No real patient, employee, payroll, banking, biometric, identity, or document data.
- No custom domain, email, SMS, push delivery, external scheduler, or analytics service.
- No second cloud provider, provider-migration credential, or provider-migration decision.
- No live DigitalOcean apply, paid resource, persistent credential, or public exposure until 14G
  records the exact target, price, duration, owners, credential custody, and owner approval.
- No deletion or modification of the retained Phase 13 external archive.
- No committed Terraform state, plan, password, token, private key, secret value, signed URL, or
  private object.

## Part plan

| Part | Scope | Required result | Rollback boundary |
| --- | --- | --- | --- |
| 14A | Deployment inventory, operating contract, risk register, golden cases, and promotion design | Every service, identity, secret, network path, release artifact, backup, monitor, owner, cost, and external action has one disposition and one later-part owner | Revert 14A documents and verifier only |
| 14B | Reusable infrastructure and cost guardrails | Terraform describes the shared development project, network, database, private object store, application, fixed sizes, budget checks, and disabled-by-default apply without Phase 6G names or teardown assumptions | Revert the infrastructure definition while provisioning remains disabled |
| 14C | Identities, secrets, and administrative access | Migration, API, workers, Keycloak, object storage, and operators receive separate least-privilege identities with rotation and break-glass rules; no secret reaches React or Git | Revert identity wiring before any live credential exists; rotate or revoke any credential created later |
| 14D | Application and worker deployment | Pinned application artifacts, migrations, API, Keycloak, static site, expiry, scanner, and reconciliation components have health, maintenance, concurrency, and failure controls | Select the prior reviewed artifact set; never roll schema back without its exact safe path |
| 14E | Operations and observability | Safe logs, metrics, alerts, retention, dashboards, ownership, incident steps, and cost checks cover each component without leaking protected values | Revert configuration only after preserving required audit and incident evidence |
| 14F | Backup, restore, and rollback rehearsal | Application database, Keycloak database, private objects, signing-key continuity, and matching release artifacts restore into isolated targets and pass reconciliation before use | Delete only named restore targets; never restore over the shared environment or recreate an external archive |
| 14G | Shared-development provisioning and promotion | The exact approved DigitalOcean resources deploy in maintenance mode, pass the full synthetic gate and restart proof, then receive explicit release promotion with recorded cost and ownership | Return to maintenance mode and the last compatible reviewed artifacts; destroy resources only with exact approval and retained state |
| 14H | Independent review and complete Phase 14 gate | Every 14A inventory item and golden case has evidence; the shared environment, recovery proof, rollback, operations, cost, safe logs, and cleanup boundaries pass | Keep the last reviewed release and evidence; request Phase 14 signoff without starting Phase 15 |

## Part 14A deployment and operations contract

14A inventories the current Phase 6G Terraform, application components, runtime settings, database
roles, Keycloak configuration, object-storage access, workers, CI, release artifacts, monitoring,
backups, restore steps, costs, owners, and external prerequisites. It compares each item with the
current Phase 14 target and assigns one action and one owner.

The operating contract fixes the environment purpose, resource names, region, default App Platform
address policy, maintenance sequence, artifact identity, schema head, component health, worker
concurrency, secret custody, operator access, backup classes, recovery order, monitoring signals,
promotion evidence, rollback order, cost ceiling, and resource-retention decision. A machine-readable
catalogue and golden cases cover every later part.

14A performs read-only external discovery if authenticated access is available. It creates no cloud
resource, credential, secret, Terraform state, or production data.

## Part 14B reusable infrastructure and cost guardrails

14B replaces the temporary Phase 6G shape with disabled-by-default shared-development Terraform.
It declares exact names, fixed sizes, private networking, managed PostgreSQL, private object storage,
the App Platform application, project assignments, database firewall, backup settings, and resource
labels. It removes proof-only deadlines, synthetic password injection, destructive bucket defaults,
and Phase 6G naming.

Static checks reject unbounded scaling, public databases or objects, wildcard sources, automatic
deployment, secret output, missing ownership labels, and an apply without every 14A approval input.
This part validates plans with provisioning disabled. It does not apply them.

## Part 14C identities, secrets, and administrative access

14C defines separate database roles for migrations, API runtime, expiry, scanner, reconciliation,
and Keycloak. It limits object-store keys by component and operation. It specifies App Platform
secret ownership, Keycloak bootstrap removal, required administrator MFA, operator access, rotation,
revocation, break-glass custody, and evidence that public frontend settings contain no secret.

Focused proof checks grants, connection ownership, secret routing, masked output, denied cross-role
operations, rotation overlap, and removal of bootstrap credentials. Live secrets remain deferred to
the approved 14G provisioning window.

## Part 14D application and worker deployment

14D deploys immutable reviewed artifacts for migrations, FastAPI, Keycloak, expiry, scanning,
reconciliation, and the static frontend. Every long-running component has a health or completion
contract, bounded retries, concurrency ownership, and a fail-closed maintenance response. The
migration job runs once before compatible application components become active.

Tests prove exact artifact references, one Alembic head, repeatable migration, startup order,
worker idempotence, stale-worker recovery, graceful shutdown, health failure, and rejection of an
incompatible release. Automatic branch deployment remains disabled.

## Part 14E operations and observability

14E defines provider and application signals for frontend availability, API latency and failures,
authorization denials, Keycloak readiness and signing-key changes, PostgreSQL capacity and locks,
object growth and failures, worker delay and retries, deployment state, backup completion, and cost.
It assigns an owner, severity, response, retention period, and test method to every signal.

The part adds safe-log verification, alert fixtures, operator runbooks, maintenance and incident
steps, and evidence capture that excludes tokens, passwords, connection strings, object keys,
signed URLs, and document contents. It does not add an external alerting vendor.

## Part 14F backup, restore, and rollback rehearsal

14F defines backup custody and schedules for the application database, Keycloak database, private
objects, configuration, signing-key identity, and reviewed release artifacts. It restores each data
class into exact isolated targets, then compares schema head, row and identity counts, object counts,
byte counts, digests, reconciliation state, and signing-key continuity.

The release rehearsal selects the matching frontend and backend artifacts, proves authentication,
authorization, files, workers, and browser journeys, and keeps restored writes disabled until every
check passes. Cleanup removes only the named restore targets after evidence is retained.

## Part 14G shared-development provisioning and promotion

14G starts with read-only account discovery and an exact target manifest. Before any apply, it must
record the current DigitalOcean project, regional network, resource list, plan sizes, monthly and
test-window estimates, budget and alert state, GitHub access, owners, credential custody, exposure
sequence, retention choice, and cleanup targets. A live apply requires owner approval for that exact
manifest and cost boundary.

The first apply stays in maintenance mode. It provisions only the approved resources, applies the
single schema head, configures Keycloak administration, and keeps public use blocked until health,
MFA, secrets, database, storage, workers, logs, and backups pass. The complete synthetic
administrator, manager, and employee journey runs before release promotion. Restart and redeploy
proof must preserve database, signing-key, object, scanner, and worker state.

The promoted shared environment remains synthetic-only. Its release record names commit, artifact
digests, schema head, resource IDs, configuration owners, monthly rate, backup result, rollback
point, and review time without storing a credential or private value.

## Part 14H independent review

14H traces every 14A inventory item and golden case against current source, Terraform, tests,
workflow, deployment evidence, provider state, operating records, backup and restore proof, release
artifacts, cost, logs, and owners. It verifies that no unapproved resource, secret, public path,
automatic deployment, real data, external archive change, or second-provider work entered Phase 14.

The closing gate runs the complete local proof and the routed GitHub gate. It checks the live shared
environment read-only where possible, repeats the agreed synthetic journey, validates recovery and
rollback evidence, records Phase 14 completion, and asks the project owner for one signoff. It does
not start Phase 15.

## Shared verification and source control

Each part follows `docs/migration/VERIFICATION_WORKFLOW.md`. Use focused checks while changing one
bounded unit, then run one boundary-matched local gate. Terraform, authentication, Compose,
deployment, worker, or shared-infrastructure changes require the complete frontend and full-stack
gate. Documentation-only completion edits use lightweight validation.

Every nonfinal part leaves a clean synchronized `migration/fastapi-keycloak` branch, generates the
next handoff from verified repository state, creates a new task in the same saved project and local
checkout, and starts it without another routine owner approval. The exact billable-resource approval
inside 14G is a resource boundary, not a part authorization gate.

## Resource and data boundary

Use synthetic identities, synthetic business rows, and synthetic files only. Keep all local work in
named disposable environments. Preserve `workloop-clinic_postgres_data` untouched. Keep Terraform
state, plans, backups, credentials, and private evidence outside Git in owner-controlled storage.

Before any external change, resolve the exact account, project, resource, region, cost, and owner.
Provision only the approved 14G manifest. Never target the retained Phase 13 archive. Cleanup and
rollback must verify exact resource identities, preserve required evidence, and avoid broad delete
commands.
