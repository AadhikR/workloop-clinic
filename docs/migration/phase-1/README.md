# Phase 1 DigitalOcean Access and Cost Controls

## Status

**Completed on 2026-08-27 with one accepted deferral.**

The spend alert is deferred by the project owner. It must be created or explicitly reconsidered before Phase 6A creates the first billable DigitalOcean resources.

## Purpose

Phase 1 establishes account access, source-control visibility, region and branch decisions, cost expectations, resource ownership, and a secret inventory. It does not deploy the application or create a database, Keycloak service, Space, VPC, or API token.

## Confirmed Account Capabilities

The project owner reported that the DigitalOcean team creation menu exposes the required categories:

| Required capability | Confirmed evidence |
|---|---|
| App Platform | `App Platform` creation option is visible |
| Managed PostgreSQL | `Managed Database` creation option is visible |
| Spaces | `Spaces Object Storage` creation option is visible |
| Networking | `VPC`, `Firewall`, `Load Balancer`, and related options are visible |
| Alerts | `Resource Alert` creation option is visible; spend alert is handled separately under Billing |
| API access | `API Key` creation option is visible; no key was created |
| Project organization | Empty project `workloop-clinic-dev` was created successfully |

Visibility demonstrates practical creation access for Phase 1 planning. Each service wizard must still be checked before provisioning because product plans, quotas, and billing permissions can differ.

## GitHub Integration

| Item | Result |
|---|---|
| Repository | `AadhikR/workloop-clinic` |
| Visibility to DigitalOcean | Confirmed by project owner |
| App created | No |
| Deployment started | No |
| Repository installation scope | Intended to be this repository only; verify in GitHub application settings before Phase 6A |
| Stable reference branch | `main` |
| Migration branch | `migration/fastapi-keycloak` |
| Remote branch | `origin/migration/fastapi-keycloak` |

The migration branch was created from commit `416931c` and pushed to GitHub. It tracks the remote migration branch. `main` remains the current Supabase reference implementation.

No separate repository or fork is required. The two branches preserve a common history while allowing the migration build to diverge safely.

## DigitalOcean Project

| Setting | Decision |
|---|---|
| Project name | `workloop-clinic-dev` |
| Purpose | Synthetic-data development for the FastAPI and Keycloak migration |
| Environment | Development |
| Current attached resources | None reported |
| Real data allowed | No |
| Default App Platform address | Accepted for future development deployment |

An empty project is an organizational container. It does not run code or create normal infrastructure charges by itself.

## Region Decision

**Selected region: Frankfurt, Germany (`fra1`).**

DigitalOcean's regional availability documentation, last updated 2026-08-10, lists no UAE region. Frankfurt was selected because the required development services have full availability there:

- Dynamic App Platform
- Static App Platform
- Managed PostgreSQL
- Spaces Standard Storage
- VPC networking

The DigitalOcean environment remains synthetic-data-only. Frankfurt does not satisfy a future requirement to keep regulated clinic data in the UAE. The production system must move to the separately approved Azure UAE architecture before real clinics or records are introduced.

Official reference: `https://docs.digitalocean.com/platform/regional-availability/`

## Cost Estimate

This estimate uses public DigitalOcean prices reviewed on 2026-08-27. Actual prices, taxes, transfer, and selected plans must be rechecked immediately before provisioning.

| Component | Preliminary development size | Approximate monthly cost |
|---|---:|---:|
| React static site | App Platform free static tier | USD 0 |
| FastAPI | Shared fixed, 1 vCPU and 1 GiB | USD 10 |
| Keycloak | Shared, 1 vCPU and 2 GiB | USD 25 |
| Managed PostgreSQL | Basic, 1 vCPU and 1 GiB | USD 15.15 |
| Spaces | Base plan | USD 5 |
| Expected base total | Before tax, SMTP, overages, or resizing | **USD 55.15/month** |

Keycloak memory must be measured during Phase 6A. A smaller plan may be unstable, while a larger plan increases cost. Managed PostgreSQL is preferred over the USD 7 App Platform development database because the latter is not backed up by default, cannot create the separate Workloop and Keycloak databases required by the plan, and is deleted with its app.

Planning guardrail:

```text
Monthly budget: USD 100
Suggested thresholds: 50%, 75%, 100%
Scope: total team spend while the team has no unrelated resources
```

Official references:

- `https://www.digitalocean.com/pricing/app-platform`
- `https://www.digitalocean.com/pricing/managed-databases`
- `https://www.digitalocean.com/pricing/spaces-object-storage`
- `https://docs.digitalocean.com/platform/billing/spend-alerts/`

## Accepted Cost-Control Deferral

The project owner could not access the spend-alert interface and chose to defer this task.

This does not block local Phases 2–6 because they do not require DigitalOcean infrastructure. It becomes a hard checkpoint before Phase 6A.

Before any billable DigitalOcean resource is created:

1. Recheck current prices and the selected sizes.
2. Present the exact expected monthly total to the project owner.
3. Obtain explicit provisioning approval.
4. Ask a team owner or biller to create the spend alert if the project owner still lacks Billing access.
5. Record whether the alert exists and who receives it.

A spend alert sends notifications; it does not stop spending automatically.

## Resource Ownership and Deletion

| Responsibility | Primary owner | Backup or approval |
|---|---|---|
| DigitalOcean project | Project owner | DigitalOcean team owner |
| GitHub integration | Project owner | GitHub repository owner |
| Migration branch | Project owner | Repository owner or designated backup |
| Future App Platform components | Project owner | DigitalOcean team owner |
| Future managed PostgreSQL | Project owner | Database reviewer before real data |
| Future Spaces storage | Project owner | Security reviewer before real files |
| Billing and spend alert | DigitalOcean team owner or biller | Project owner monitors expected cost |
| Resource deletion | Project owner requests and approves | Team owner performs it if permission is restricted |

No resource containing data may be deleted based only on an AI instruction. The project owner must approve deletion after backups and rollback requirements are checked.

## Secret Inventory

No Phase 1 secret was created. This inventory records future secret names and locations without values.

| Secret or sensitive value | Created in | Local storage | DigitalOcean storage | GitHub storage | Never expose to React |
|---|---|---|---|---|---|
| `DIGITALOCEAN_TOKEN` | Infrastructure setup | Password manager or ignored local environment | Not required by app | GitHub Actions secret only if Terraform deployment is approved | Yes |
| `DATABASE_URL` | Managed PostgreSQL | Ignored backend `.env` | FastAPI encrypted secret | Never unless an approved migration job requires it | Yes |
| `MIGRATION_DATABASE_URL` | Managed PostgreSQL | Ignored migration environment | Single-run migration job secret | Approved migration secret only | Yes |
| `KEYCLOAK_DATABASE_URL` | Managed PostgreSQL | Ignored Keycloak environment | Keycloak encrypted secret | Never | Yes |
| `KC_BOOTSTRAP_ADMIN_PASSWORD` | Keycloak bootstrap | Password manager | Keycloak encrypted secret during bootstrap | Never | Yes |
| `KEYCLOAK_ADMIN_CLIENT_SECRET` | Keycloak confidential client | Password manager or ignored backend `.env` | FastAPI encrypted secret | Never | Yes |
| `SPACES_ACCESS_KEY` | Spaces | Password manager or ignored backend `.env` | FastAPI encrypted secret | Never | Yes |
| `SPACES_SECRET_KEY` | Spaces | Password manager or ignored backend `.env` | FastAPI encrypted secret | Never | Yes |
| `SMTP_PASSWORD` | Email provider | Password manager or ignored environment | Keycloak encrypted secret | Never | Yes |
| Terraform state | Terraform backend | Encrypted approved backend only | Approved remote state | Never commit local state | Contains secrets; treat as sensitive |

Public browser configuration such as the API base URL, Keycloak issuer URL, realm, and public client ID is not secret. It may use `VITE_` variables. Passwords, database addresses containing credentials, private keys, and administrative client secrets must never use `VITE_` variables.

## Branch Policy

- `main` remains the stable Supabase reference until final cutover.
- `migration/fastapi-keycloak` owns migration work.
- DigitalOcean development deployment will use the migration branch, not `main`.
- Pull requests should target the migration branch during the long-running rewrite unless a change is intentionally for the legacy application.
- Do not merge the migration branch into `main` until Phase 13 confirms that Supabase is no longer required.
- Do not force-push the migration branch.
- Protect `main` from accidental migration deployment.

## Resources Not Created

Phase 1 did not create:

- An App Platform application
- A FastAPI service
- A Keycloak service
- A managed database
- A Space or bucket
- A VPC
- A firewall or load balancer
- A DigitalOcean API token
- A custom domain
- Any user, password, or synthetic business record

## Completion Gate

The Phase 1 technical gate passes with the documented cost-control deferral:

- DigitalOcean can see the private GitHub repository.
- The required creation categories are visible to the team member.
- The empty development project exists.
- Frankfurt is the recorded development region.
- The migration branch exists locally and on GitHub.
- Preliminary costs and ownership are recorded.
- Future secrets and approved storage locations are recorded.
- No credential has been committed.
- No billable Workloop resource has been created.

The spend alert is the only deferred control. It is mandatory to resolve or explicitly waive again before Phase 6A provisioning.

## Next Phase

Phase 2 is the local backend and infrastructure foundation. It must not start until the project owner explicitly authorizes it.
