# Phase 7E completion record

## Status

The project owner authorized Phase 7E on 2026-09-11. Department and staffing-rule implementation,
cutover evidence, and the complete local gate are finished. The required GitHub result remains the
final Phase 7E check and will be reported in the task handoff.

Phase 7F has not started and remains unauthorized.

## Department boundary

FastAPI now provides branch-scoped department list, create, update, and guarded-delete operations.
Only an admin with a verified selected branch may use them. The list supports the approved search,
parent, head, sorting, and cursor rules. Responses contain only the Phase 7A projection.

Create and update validate exact names, same-branch parents and heads, active head eligibility,
cycles, and the 20-level hierarchy limit under a locked branch hierarchy. Updates and deletes compare
the complete prior mutable snapshot. Missing or inaccessible references return the generic not-found
response, while stale snapshots and visible department conflicts use their stable Phase 6 errors.

A rename locks matching employees and staffing rules in deterministic order. It updates their labels
in the same transaction and appends one `department_change` history row for every affected employee.
The existing Phase 7C idempotency record now carries the selected branch for this admin workflow, so
an identical replay returns the committed department without repeating label or history changes.

Delete returns 204 only when no child, employee label, department head, staffing rule, retained audit,
or database reference uses the department. Every rejected operation rolls back without partial data.

## Staffing-rule boundary

FastAPI now provides branch-scoped staffing-rule list, create, update, and delete operations for
admins. The list implements the approved department, category, effective-date, sort, null-last, and
cursor behavior. Create is insert-only and returns a safe conflict for the existing branch,
department, and category key. It never acts as an upsert.

Mutations require an existing selected-branch department, an approved category, a nonnegative integer
minimum, and a valid date range. Update and delete compare the complete prior mutable snapshot under a
row lock. Phase 7E does not evaluate rosters or staffing compliance.

## Migration UI and cutover

The migration build now uses strict FastAPI adapters for departments and staffing rules. Admins can
view the hierarchy, choose eligible department heads, edit department details, and create, edit, or
delete staffing rules. The adapters reject missing, extra, snake_case, and malformed response fields.
They bind every request to the verified selected branch and load paginated data without accepting
duplicate rows or cursors.

The migration import graph contains no legacy source or Supabase dependency. The legacy
`departmentStorage` and `staffingStorage` paths remain available only to the separate legacy build and
are frozen for these cutover units. Both records name `migration-fastapi` as the sole read and write
authority. Department and staffing rollback remain independent until an authorized Phase 7F employee
writer begins to depend on them.

## Verification

Focused checks passed for exact schemas, strict query parsing, branch and tenant scope, role denial,
inactive and unlinked accounts, wildcard search, stable pagination, null-last dates, hierarchy locks,
cycles, depth, snapshots, deletion guards, staffing validation, duplicate creation, rename atomicity,
and idempotent replay. The Phase 7E verifier returned state digest
`b11a8f30f2c6ee84a361ece4d993d67c506a402b84c04df8350c5ea2f2b78e23`.

The settled complete local gate passed after one clean rerun:

- 427 backend tests, Ruff lint and formatting, strict Pyright, and the locked dependency check;
- 109 frontend tests, the legacy and migration production builds, and isolation across 449 legacy
  modules and 34 migration modules;
- repeatable migration at the unchanged single Alembic head `7d4a9c2e6b10` without replaying the
  historical chain;
- schema, trigger, seed, repository, RLS, grant, protected-function, concurrency, security, and
  PostgreSQL ownership checks;
- Phase 7B, 7C, and 7D regression verifiers plus the Phase 7E department and staffing verifier;
- Phase 6 HTTP, Keycloak-to-FastAPI authentication, and the complete admin, manager, and employee
  browser journey, including department and staffing UI mutations; and
- service log safety and complete synthetic-data cleanup.

The final gate used Compose project `workloop-phase7e-final` on PostgreSQL port 15432, API port 18000,
and Keycloak ports 18080 and 19000. It used a fresh temporary PostgreSQL volume and applied migrations
twice. The Phase 7B fingerprint remained
`4a0731e2e75bb0a0e534227af6500ebe64dc2ed9ad19ffe0fb8d315311fc18e3`. The Phase 7C fingerprint
remained `dd5e4f94ae8c89f41e738b8fe29f80f1e9a975bf49626f377ebd594fb9e68b55`. The Phase 7D digest
remained `6c56844915ac08f120947e5a7744675dbce008ef966fd8141b55f113db0fd05e`.

The gate recreated the containers without rebuilding or removing the temporary data volume. The
database catalogue fingerprint remained `1b703ceacf8b11604027646ec2ae6efc`, both Keycloak signing key
IDs remained unchanged, and the three image IDs matched. Context isolation, authentication, and the
full browser journey passed after restart without another Keycloak configuration pass. All synthetic
Workloop rows and Keycloak users returned to zero.

## Resource boundary

Verification used local synthetic data only. It accessed no production data, cloud resource, paid
service, or persistent external credential. After recording evidence, the gate removed its
containers, network, generated credentials, and temporary PostgreSQL volume.

The protected `workloop-clinic_postgres_data` volume was not attached, upgraded, recreated, seeded,
or deleted. It remains present. The retained empty FRA1 default VPC was not changed.

## Stop condition

Phase 7E closes when the pushed commit containing this record passes the path-routed `Migration
foundation` workflow. Stop before Phase 7F and require separate project-owner authorization.
