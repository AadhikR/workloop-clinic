# Phase 7D completion record

## Status

The project owner authorized Phase 7D on 2026-09-10. During implementation, the employee self read
could not obtain its manager through the existing employee RLS policy. Work stopped at that schema
boundary. The owner then approved a narrow protected reporting-manager function. The implementation,
complete local gate, and required GitHub result are finished. Migration foundation run
[#75](https://github.com/AadhikR/workloop-clinic/actions/runs/34506565933) passed on 2026-09-10.

The project owner authorized Phase 7E separately on 2026-09-11.

## Employee read boundary

FastAPI now exposes the six approved employee reads:

- `GET /api/v1/employees`;
- `GET /api/v1/employees/{employeeId}`;
- `GET /api/v1/employees/self`;
- `GET /api/v1/employees/direct-reports`;
- `GET /api/v1/employees/{employeeId}/job-history`; and
- `GET /api/v1/employee-job-history`.

Admin list, detail, and job-history reads require a verified selected branch. Manager and employee
reads reject the branch header and derive scope from the linked employee in the authorized
transaction. Managers receive only their current one-level direct reports. They cannot supply a
manager ID or request a recursive team. Staff cannot read admin collections or job history.

The list, detail, self, direct-report, and job-history schemas match the Phase 7A field sets. Responses
use camelCase, the Phase 6 envelopes, a fresh correlation ID, and `Cache-Control: no-store`. Query
parsing rejects unknown or duplicate parameters. Search, filters, sort allowlists, stable UUID
tie-breakers, cursor binding, and nullable employment-date ordering run in PostgreSQL. Inaccessible
employee IDs return the same `resource_not_found` error as missing IDs.

No employee mutation, import, lifecycle transition, department operation, staffing operation,
portal-role read, or Keycloak provisioning operation was added.

## Reporting-manager schema amendment

Alembic revision `7d4a9c2e6b10`, based on `31d7b4c8e2f0`, adds
`public.current_employee_reporting_manager()`. It changes no table or RLS policy. The no-argument
function returns only `id`, `name`, and `job_title` for the current eligible employee's manager.

The function is stable and security-definer, has a pinned search path, and belongs to
`workloop_migration`. Public and scheduled-job execution are denied. Only `workloop_runtime` may
execute it. The function binds the database session to the existing identity resolver and checks the
human actor, business date, active account, profile, company, employee, branch, role, and current
employment eligibility before it reads the manager. Admin or context-free calls return no row.

## Migration consumer and cutover

The migration build now has strict adapters for every Phase 7D response and a single employee
directory consumer. Admins can search a branch, open an employee detail, and inspect employee and
branch job history. Managers and employees see their own profile. Managers also see their current
direct reports.

The adapters reject snake_case fields, missing fields, extra fields, malformed scalar values, and a
detail or history response for the wrong employee. Admin requests send the selected branch header.
Staff requests remain selector-free. The migration dependency graph contains no legacy source or
Supabase import.

The `phase7-employee-directory` cutover record now names the real backend, migration, and schema
files. Read authority is `migration-fastapi`. Legacy Supabase remains the only employee write
authority because Phase 7D has no writer. Rollback disconnects the migration readers together and
restores every list, detail, self, direct-report, and job-history consumer to the legacy reader. It
does not enable a second writer.

## Verification

Focused checks covered exact response fields, query rejection, role denial, branch and tenant scope,
literal wildcard search, cursor binding, stable pagination, null-last date ordering, job-history
ordering, inactive and terminated employees, disabled and unlinked accounts, and the protected
function's ownership, grants, definition, and context behavior. The Phase 7D synthetic verifier
returned state digest
`6c56844915ac08f120947e5a7744675dbce008ef966fd8141b55f113db0fd05e`.

The complete local gate passed after a clean rerun:

- 416 backend tests, Ruff lint and formatting, strict Pyright, and the locked dependency check;
- 96 frontend tests and both production builds;
- frontend isolation across 449 legacy modules and 32 migration modules;
- the complete historical Alembic downgrade and upgrade chain;
- schema, trigger, seed, repository, RLS, grant, protected-function, concurrency, and PostgreSQL
  ownership checks;
- Phase 7B and Phase 7C regression verifiers;
- Phase 6 HTTP, Keycloak-to-FastAPI authentication, and the full admin, manager, and employee browser
  journey; and
- service log safety and synthetic-data cleanup.

The final gate used Compose project `workloop-phase7d-final` on PostgreSQL port 25432, API port
28000, and Keycloak ports 28080 and 29000. It used a fresh temporary PostgreSQL volume, built the
backend image once, and applied migrations twice. Alembic reported one head at `7d4a9c2e6b10` and no
pending schema operations. The Phase 7B fingerprint remained
`4a0731e2e75bb0a0e534227af6500ebe64dc2ed9ad19ffe0fb8d315311fc18e3`. The Phase 7C fingerprint
remained `dd5e4f94ae8c89f41e738b8fe29f80f1e9a975bf49626f377ebd594fb9e68b55`.

The gate recreated the containers without rebuilding or deleting the temporary data volume. The
database catalogue fingerprint remained `1b703ceacf8b11604027646ec2ae6efc`, both Keycloak signing key
IDs remained unchanged, and the PostgreSQL, backend, and Keycloak image IDs matched. Context
isolation, authentication, and the full browser journey passed after restart without another
Keycloak configuration pass. All synthetic Workloop rows and Keycloak users returned to zero.

## Resource boundary

Verification used local synthetic data only. It accessed no production data, cloud resource, paid
service, or persistent external credential. After recording evidence, the gate removed its
containers, network, generated credentials, and temporary PostgreSQL volume.

The protected `workloop-clinic_postgres_data` volume was not attached, upgraded, recreated, seeded,
or deleted. It remains present. The retained empty FRA1 default VPC was not changed.

## Stop condition

Phase 7D is closed. Its path-routed `Migration foundation` workflow passed, and Phase 7E required
separate project-owner authorization before work began.
