# Workloop Clinic roadmap

## Current product boundary

The current application uses one React frontend, one FastAPI API, Keycloak, portable PostgreSQL, and
private object storage. The three portals share that runtime and differ by API-enforced role and
scope.

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

1. Finish Phase 13 repository, clean-setup, retention, external-state, and independent-review gates.
2. Deploy the approved stack to DigitalOcean with managed secrets, private networking, backups,
   health checks, log retention, and rollback evidence.
3. Run the final portal, security, recovery, and performance validation before release signoff.

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
- Azure production mapping after the DigitalOcean development and staging design is stable

## Product decision rules

- Add a feature only through the current API and identity model.
- Keep tenant, branch, manager, and employee scope fail-closed.
- Prefer portable PostgreSQL and S3-compatible contracts over provider-specific application code.
- Store private files outside Git and expose them only through scoped backend operations.
- Record legal and payroll rules with their effective date, source, and test cases.

## Historical feature material

The retired generated PDF is stored under `docs/history/legacy-feature-list/` with a clear history
label. It does not define current setup, architecture, or planned implementation.
