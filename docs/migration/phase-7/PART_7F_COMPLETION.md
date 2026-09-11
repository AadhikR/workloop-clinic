# Phase 7F completion record

## Status

The project owner authorized Phase 7F on 2026-09-11. Employee onboarding, ordinary editing, CSV
import, cutover evidence, and the complete local gate are finished. The required GitHub result
remains the final Phase 7F check and will be reported in the task handoff.

Phase 7G has not started and remains unauthorized.

## Employee mutation boundary

FastAPI now provides administrator-only employee creation, ordinary editing, and create-only CSV
import. Every operation derives company, selected branch, actor, identifiers, and timestamps on the
server. Department and reporting-manager references are locked and validated in the same
transaction. A reporting manager must be an active or probationary employee in the selected branch;
the employee's portal role is not used as manager eligibility.

Creation and import normalize work email addresses by trimming and lowercasing them, then enforce a
nonempty company-wide unique value. They do not use employee number or MOL ID as identity and do not
upsert existing employees. Creation and import require Phase 7C idempotency keys. An identical replay
returns the committed response, while a changed payload with the same key returns the stable
idempotency conflict.

Ordinary editing requires `expectedUpdatedAt` and accepts only the fields assigned to Phase 7F by the
Phase 7A contract. A stale version returns `state_conflict`. Branch transfer, hard deletion,
lifecycle status changes, salary workflows, job-history changes, portal-role changes, Keycloak
provisioning, documents, insurance, contracts, and shifts remain outside this part.

The import route accepts at most 500 rows and a declared request size of at most 1 MiB. Each row uses
the exact `rowNumber`, `empNo`, `name`, `molId`, `bankName`, `bankRoutingCode`, `iban`, `basicSalary`,
and `allowance` contract. All rows commit in one transaction or none commit. Row diagnostics use
stable request-field locations and do not expose tenant data.

Phase 7A decision D3 reserves employee audit events for manager and portal-role changes. Phase 7F
ordinary create, edit, and import operations therefore append no audit event or job-history row.
Those privileged workflows remain assigned to Phase 7G.

## Migration UI and cutover

The migration employee directory now includes an administrator create form, ordinary edit form, and
CSV preview and import flow. Papa Parse runs only for browser preview. The server repeats all
validation and owns the batch transaction. The adapters reject missing, extra, snake_case, and
malformed fields, and every request is bound to the verified selected branch.

The migration import graph contains no legacy source or Supabase dependency. The legacy
`saveEmployee` and `saveEmployees` functions fail before reaching Supabase. The employee
administration cutover record names `migration-fastapi` as the sole read and write authority and
records the order required to restore the legacy writer safely.

## Verification

Focused checks covered exact request and response schemas, role denial, inactive and unlinked
accounts, tenant and branch scope, same-branch department and manager validation, manager status,
normalized email uniqueness, stale edits, idempotent creation and import replay, changed-payload
conflicts, the 500-row and 1 MiB limits, deterministic row diagnostics, and batch rollback. The Phase
7F verifier returned state digest
`055e65fbf6b5509f52fdc6d0f1f08f3125c674a8b3c7736c5c56bfb5c276ed34`.

The settled complete local gate passed:

- 429 backend tests, Ruff lint and formatting, strict Pyright, and the locked dependency check;
- 114 frontend tests, the legacy and migration production builds, and isolation across 449 legacy
  modules and 36 migration modules;
- repeatable migration at the unchanged single Alembic head `7d4a9c2e6b10`, with no pending
  operations;
- schema, migration round-trip, trigger, seed, context, RLS, grant, security, and PostgreSQL
  ownership checks;
- Phase 7B, 7C, 7D, and 7E regression verifiers plus the Phase 7F employee verifier;
- Phase 6 HTTP, Keycloak-to-FastAPI authentication, and the complete admin, manager, and employee
  browser journey, including create, edit, CSV preview, and atomic import; and
- service log safety and complete synthetic-data cleanup.

The final gate used Compose project `workloop-phase7f-final` on PostgreSQL port 25432, API port
28000, and Keycloak ports 28080 and 29000. It used a fresh temporary PostgreSQL volume and applied
migrations twice. The Phase 7B fingerprint remained
`4a0731e2e75bb0a0e534227af6500ebe64dc2ed9ad19ffe0fb8d315311fc18e3`, the Phase 7C fingerprint
remained `dd5e4f94ae8c89f41e738b8fe29f80f1e9a975bf49626f377ebd594fb9e68b55`, the Phase 7D digest
remained `6c56844915ac08f120947e5a7744675dbce008ef966fd8141b55f113db0fd05e`, and the Phase 7E digest
remained `b11a8f30f2c6ee84a361ece4d993d67c506a402b84c04df8350c5ea2f2b78e23`.

The gate recreated the containers without rebuilding or removing the temporary data volume. The
database catalogue fingerprint remained `1b703ceacf8b11604027646ec2ae6efc`, both Keycloak signing key
IDs remained unchanged, and the PostgreSQL, backend, and Keycloak image IDs matched. Context
isolation, authentication, and the full browser journey passed after restart without another
Keycloak configuration pass. All synthetic Workloop rows and Keycloak users returned to zero.

## Resource boundary

Verification used local synthetic data only. It accessed no production data, cloud resource, paid
service, or persistent external credential. After recording evidence, the gate removed its
containers, network, generated credentials, quality container, and temporary PostgreSQL volume.

The protected `workloop-clinic_postgres_data` volume was not attached, upgraded, recreated, seeded,
or deleted. It remains present. The retained empty FRA1 default VPC was not changed.

## Stop condition

Phase 7F closes when the pushed commit containing this record passes the path-routed `Migration
foundation` workflow. Stop before Phase 7G and require separate project-owner authorization.
