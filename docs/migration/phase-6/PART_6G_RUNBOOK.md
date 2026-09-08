# Phase 6G architecture proof runbook

## Status

Phase 6G is authorized as a small temporary architecture test with an absolute DigitalOcean ceiling
of USD 20. The owner confirmed a USD 20 prepayment and spend alert on 2026-09-08. No cloud resource
has been created from this work.

The local implementation and cloud definitions passed their complete local gate on 2026-09-08.
Billable provisioning remains blocked until the GitHub result, repository-only GitHub App scope,
isolated project state, temporary credentials, teardown deadline, and initial plan are verified.

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
The 72-hour estimate is USD 5.91. Stop and request teardown approval at USD 15. Never exceed USD 20.
DigitalOcean prepayment and spend alerts do not prevent additional billing, so elapsed time and the
team billing page remain the controlling checks.

## Owner tasks before provisioning

1. In GitHub, confirm the DigitalOcean App Platform installation has access only to
   `AadhikR/workloop-clinic`.
2. In DigitalOcean, confirm `workloop-clinic-dev` exists and contains no unrelated resources.
3. Choose a UTC teardown deadline no more than 72 hours after the planned apply.
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

## Completion rule

Phase 6G completes only after the deployed browser login, protected account call, managed database,
private object persistence, controlled migration, component redeploy, restart persistence, exact
security boundary, cost evidence, teardown evidence, GitHub checks, and owner signoff all pass. Stop
before Phase 7.
