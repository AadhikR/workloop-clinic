# Phase 6G architecture proof runbook

## Status

Phase 6G completed successfully on 2026-09-09 and its billable DigitalOcean resources have been
destroyed. The owner confirmed a USD 20 prepayment and spend alert on 2026-09-08. The approved test
window was 48 hours, with an estimated cost of USD 3.94 before tax and overages. Phase 7 is not
authorized.

The local implementation and cloud definitions passed their complete local gate on 2026-09-08.
The cloud proof used Terraform state outside the repository at
`%LOCALAPPDATA%\Workloop\phase-6g\terraform.tfstate`. The state, backups, plans, and ignored variables
file were deleted after teardown was verified and the temporary credentials were revoked.

## Proof boundary

The test deploys only the React migration shell, the FastAPI health and current-account paths, one
production-mode Keycloak replica, one managed PostgreSQL cluster with separate databases and users,
and one private synthetic object in Spaces. It runs Alembic once through a pre-deploy job. It uses no
real identities, business data, SMTP, public object access, wildcard redirect, or wildcard CORS.

The app starts in maintenance mode. Public exposure remains blocked in Terraform until the Keycloak
administrator is forced to configure TOTP before console access. The owner must finish TOTP
enrollment and verify a second-factor login as soon as the proof is exposed.

## Cost control

The full-month resource rate is USD 55.15 before tax and overages, but that duration is not approved.
The 48-hour estimate is USD 3.94. Stop new work and request teardown approval at USD 15. Never exceed
USD 20. DigitalOcean prepayment and spend alerts do not prevent additional billing, so elapsed time
and the team billing page remain the controlling checks.

## Provisioning controls

1. In GitHub, confirm the DigitalOcean App Platform installation has access only to
   `AadhikR/workloop-clinic`.
2. In DigitalOcean, confirm `workloop-clinic-dev` exists and contains no unrelated resources.
3. Choose a UTC teardown deadline no more than 48 hours after the planned apply.
4. Create short-lived scoped DigitalOcean and Terraform Spaces credentials. Do not send them in chat.
5. Generate separate temporary passwords for the Keycloak bootstrap administrator and synthetic
   login. Do not send them in chat.
6. Review the Terraform plan with Codex and confirm it shows only the fixed sizes in the technical
   runbook.

The commands, state handling, MFA sequence, evidence list, and teardown procedure are in
[`infra/digitalocean/README.md`](../../../infra/digitalocean/README.md).

## Local gate

The local gate passed 374 backend tests, 78 frontend tests, lint, formatting, strict type checks,
dependency checks, both frontend builds, Terraform validation, and the Phase 6G static verifier.
Both production images built. A disposable production Keycloak test imported the cloud realm and
proved that the administrator TOTP helper rejects a fresh password-only login.

The complete stack gate used the separate `workloop-phase6g` Compose project and a fresh volume. It
passed the full migration history, schema, grant, RLS, function, concurrency, HTTP, Keycloak,
three-persona browser, and log-safety checks. After container recreation without rebuilding, the
database fingerprint remained `eeb158a9d2fcda117c6d603498d048b2`, both signing keys remained, and
the image identities and volume creation time were unchanged. The gate removed its synthetic rows,
users, containers, network, volume, and local images.

The existing `workloop-clinic` services stayed healthy throughout the gate. The
`workloop-clinic_postgres_data` volume kept its `2026-08-31T07:31:48Z` creation time.

## Live proof evidence

The live proof passed these checks on 2026-09-09:

- DigitalOcean deployment `1f090494-f5f4-458c-917e-8a1e1e05c7df` became active and healthy on commit
  `01260d99d03da156cabfbd5d1ef2341917acd1eb` for the API, Keycloak, migration job, and static site.
- The migration job reported that database ownership, schema, and the synthetic identity were ready.
- Keycloak required the configured second factor for a fresh administrator login. The synthetic
  browser login then resolved the fixed administrator application user and company through FastAPI.
- `/health` returned `{"status":"ok","database":"ok"}`, and `/api/v1/public/status` returned the
  expected public response. The OIDC issuer was the exact public Keycloak realm URL, and the login
  request used the exact `/oidc/callback` redirect.
- CORS returned the allow-origin header only for the exact application origin. An unrelated origin
  was rejected with HTTP 403.
- The managed PostgreSQL cluster remained at 1 GB RAM, 1 vCPU, 10 GiB disk, PostgreSQL 16 in FRA1.
  Its network-access list contained only the Phase 6G application, and the cluster remained attached
  to the proof VPC.
- The browser created and read a 35-byte private object, read it again after the full component
  rebuild, deleted it, and confirmed it was absent. DigitalOcean then showed the Space at zero items
  and zero bytes, with file listing restricted to access-key users.
- The original local `workloop-clinic_postgres_data` volume still had creation time
  `2026-08-31T07:31:48Z`.
- DigitalOcean's account-level billing view reported USD 0.22 total September usage and a USD 0.00
  estimated balance after credits. The page was last updated at 2026-09-09 07:39 GMT+4, so this is
  not a phase-only or real-time charge figure.

## Teardown evidence

The owner approved teardown on 2026-09-09. The reviewed destroy plan contained 14 exact delete
actions, with no create or update actions. Terraform removed the app, database cluster, databases,
users, firewall, Space, bucket-scoped application key, project assignment, and local guard.

DigitalOcean refused to delete the proof VPC because the first VPC created in FRA1 had automatically
become that region's default. The VPC had zero members, and the Phase 6G project was already empty.
Creating a replacement would still leave one regional default VPC, so the owner approved retaining
the empty, non-billable network. It was renamed `fra1-default` and detached from Phase 6G state.

The final checks confirmed that:

- Terraform state and the `workloop-clinic-dev` DigitalOcean project were empty.
- The former App Platform hostname no longer resolved, and the former Space endpoint returned HTTP
  404.
- The temporary DigitalOcean API token and full-access Terraform Spaces key were revoked. Terraform
  had already deleted the bucket-scoped application key.
- The external Terraform state, its backups, both saved plans, and the ignored `phase6g.auto.tfvars`
  file were permanently deleted.
- DigitalOcean's final available billing view still reported USD 0.22 in account-level September
  usage and a USD 0.00 estimated balance after credits. The dashboard was last updated at 2026-09-09
  07:39 GMT+4, so it was not a phase-only or real-time charge figure.
- The original `workloop-clinic_postgres_data` volume retained its
  `2026-08-31T07:31:48Z` creation time. No teardown command targeted the existing local containers or
  volume.

## Completion rule

The deployed browser login, protected account call, managed database, private object persistence,
controlled migration, component redeploy, restart persistence, exact security boundary, cost
evidence, teardown evidence, GitHub checks, and owner signoff all passed. Phase 6G is complete. Stop
before Phase 7.
