# Part 14A completion

Status: Part 14A is complete when the routed GitHub jobs for the commit containing this record pass.
The implementation and boundary-matched local gate passed on 2026-09-27.

## Result

Part 14A created the Phase 14 deployment catalogue, inventory, operations contract, external-fact
record, golden cases, focused validator, and eight mutation tests. The catalogue has 57 unique
inventory items. Each item has one allowed action, one owner from 14B through 14H, at least one valid
evidence class, and a concrete evidence target. The 38 golden cases cover every later part. The
phase rollback list is the exact reverse part order.

The operations contract fixes the synthetic-only environment, resource names, FRA1 placement,
provider default address, maintenance sequence, artifact identity, schema head, health rules, worker
concurrency, secret custody, operator access, backup classes, recovery order, monitoring signals,
promotion evidence, rollback order, cost ceiling, and retention decision.

The smallest fail-closed choices are:

- reuse the existing empty `fra1-default` VPC by read-only lookup and keep it outside Terraform
  state;
- use only the App Platform default address;
- disable automatic deployment and bind releases to immutable digests;
- run one scanner and one reconciler instance with one-row claims;
- keep maintenance enabled until security, recovery, restart, and synthetic journey evidence passes;
- stop before apply when fixed monthly cost exceeds USD 70 or a variable charge has no owner; and
- move a lapsed shared environment to maintenance instead of deleting it automatically.

## External discovery

Authenticated read-only discovery found an empty `workloop-clinic-dev` project, no App Platform
application, no managed database, no Spaces bucket, and no resource alert. The retained
`fra1-default` VPC remains the FRA1 default and has no member, NAT gateway, peering, or partner
attachment. The USD 20 monthly spend alert remains active at 75 and 100 percent.

The September billing page reported USD 0.95 of historical service use, fully offset by credit, and
USD 20 of remaining prepayment. Those numbers are account-level, updated daily, and do not prove a
live Phase 14 resource. Official DigitalOcean pages confirmed Frankfurt availability and the price
inputs used for the USD 65.15 fixed monthly estimate.

GitHub Migration foundation run `36320345154` was readable and successful for the baseline commit.
The exact DigitalOcean GitHub App installation scope and the names of primary and backup operators
remain unknown. Part 14G must resolve both before any paid apply. No credential was requested or
recorded.

## Verification

Focused checks passed:

- the Part 14A validator reported 57 inventory items, 38 golden cases, 12 external facts, and seven
  later-part owners;
- all eight mutation tests passed, including duplicate ID, missing owner, invalid action, invalid
  evidence class, rollback order, cost arithmetic, external-fact status, prose coverage, and schema
  head failures; and
- focused ESLint and `git diff --check` passed.

The boundary-matched local gate also passed the permanent repository guard across 1,015 files and
the Phase 13H independent review across all 50 dependencies and 42 golden cases. Alembic remains at
one head, `e8a1c3f5b7d9`, with the pinned index digest unchanged.

No local full-stack gate ran. Part 14A changes contracts and a validator only. It does not alter a
runtime, schema, authentication configuration, Compose file, or Terraform definition. GitHub may
still route broader jobs because the permanent workflow treats verifier paths conservatively. The
successful workflow URL belongs in the 14B handoff and task report so this record does not need a
second documentation-only commit.

## Resource and data boundary

Part 14A used repository state, synthetic fixtures, public documentation, and authenticated
read-only provider pages. It did not create or change a project, VPC, application, component,
database, object, bucket, key, token, alert, billing setting, credential, Terraform state, plan, or
backup. It accessed no real clinic data and changed no Phase 13 archive resource.

The local `workloop-clinic_postgres_data` volume remains present. Part 14A did not attach, mount,
inspect, modify, delete, or recreate it. No container was running during the final preflight.

## Rollback and continuation

Part 14A rollback removes only its five records, machine catalogue, validator, and focused test. It
does not change application, database, authentication, Terraform, provider, or external state.

After the routed GitHub jobs pass and the branch is clean and synchronized, Part 14B runs in a new
Codex task. It replaces the Phase 6G proof Terraform with disabled-by-default shared-development
infrastructure and cost guards. It must not apply a plan, create a credential, or provision a paid
resource.
