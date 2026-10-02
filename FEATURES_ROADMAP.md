# Workloop Clinic roadmap

## Current product boundary

The current application uses one React frontend, one FastAPI API, Keycloak, portable PostgreSQL, and
private object storage. The three portals share that runtime and differ by API-enforced role and
scope. DigitalOcean is the only active hosting target. Moving to another provider requires a new
owner decision and a separate plan.

## Implemented areas

| Area | Current capability |
| --- | --- |
| Organization | Companies, branches, settings, departments, staffing rules, and role-scoped context |
| Employees | Directory, administration, lifecycle, job history, CSV input, and self-service profile |
| Leave | Configuration, balances, requests, attachments, manager review, and final approval |
| Attendance | Clock events, calculation, exceptions, period close, configuration, and biometric input |
| Roster | Drafts, publication, schedules, staffing checks, and shift swaps |
| Payroll | Runs, approvals, payslips, WPS, Nafis snapshots, expenses, and advances |
| Documents | Private employee documents, contracts, insurance, letters, and offboarding evidence |
| Development | Training, certifications, CME, appraisals, assets, and clinical incidents |
| Work management | Notifications, tasks, dashboards, reports, exports, and rendered output |
| Security | OIDC authentication, scoped API authorization, separate database roles, and safe logs |

## Active release work

Phases 13 and 14 are complete. The approved stack runs on DigitalOcean with synthetic data,
managed secrets, private networking, backups, health checks, retained logs, and recovery evidence.

Phase 15 is active. It replaces the architecture-proof page with the integrated Workloop portal,
then runs the product, denial, accessibility, performance, promotion, recovery, and independent
review gates on DigitalOcean. The canonical plan is
`docs/migration/phase-15/SUBPHASE_PLAN.md`.

Phase 15 reuses the current backend contracts. A missing UI capability stays unavailable instead of
creating an unplanned business endpoint or widening a role. DigitalOcean remains the only active
provider.

The canonical phase plan is under `docs/migration/`. A feature is complete only when its API,
permissions, persistence, frontend, regression tests, restart behavior, and recovery boundary pass.

## Later product work

The following items remain outside the current migration scope and need separate approval:

- Arabic and right-to-left interface support
- Production email delivery and message templates
- Provider-backed malware scanning operations
- Maps and geofenced attendance
- DEWS and GPSSA contribution workflows
- Production analytics, alerting, and service-level objectives

## Product decision rules

- Add a feature only through the current API and identity model.
- Keep tenant, branch, manager, and employee scope fail-closed.
- Prefer portable PostgreSQL and S3-compatible contracts over provider-specific application code.
- Store private files outside Git and expose them only through scoped backend operations.
- Record legal and payroll rules with their effective date, source, and test cases.

## Historical feature material

The retired generated PDF is stored under `docs/history/legacy-feature-list/` with a clear history
label. It does not define current setup, architecture, or planned implementation.
