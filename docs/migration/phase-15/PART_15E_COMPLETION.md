# Part 15E completion

Status: Part 15E is complete when every routed GitHub job for the commit containing this record
passes. The implementation and boundary-matched local gate passed on 2026-10-02.

## Result

Part 15E replaced the eight employee placeholders with the approved routes from `P15-ROUTE-022`
through `P15-ROUTE-029`. The employee home keeps notifications, assigned tasks, and the self
dashboard. The other routes compose the existing profile, leave, personal attendance and schedule,
pay, records, development, appraisal, letter, and custom request views.

The employee composer passes the server-derived account, protected authentication client, and
API-returned staff branch to those views. Existing role branches choose the self endpoints and omit
administrator branch headers. They retain idempotency keys, optimistic timestamps and versions,
exact money strings, protected file delivery, server-rendered output, and current empty, conflict,
denial, and failure responses.

The personal attendance view previously stayed on its loading message when one of its three reads
failed. Part 15E now clears those local results and renders the existing stable unavailable message.
The change adds no request, field, or permission.

## Fail-closed decisions

The profile route mounts the existing staff branch of the employee directory. It reads only
`/api/v1/employees/self`, exposes the approved contact fields, and never loads the administrator
directory or the manager direct-report list.

The employee leave, time, pay, records, and development routes use the current self contracts. They
do not accept an employee, company, or branch selector. Protected attachment, receipt, document,
evidence, payslip, appraisal, and request identifiers still pass through the existing clients and
backend ownership checks.

Administrator and manager queues stay out of the employee composer. Organization settings,
employee lifecycle, leave approval, attendance administration, roster drafting, payroll runs, WPS,
records administration, clinical incidents, reports, and offboarding are absent. Direct navigation
to an administrator or manager route returns the shared forbidden state before organization or
domain requests run. An unknown employee URL returns the generic not-found state without repeating
the supplied identifier.

Employees receive one branch from the staff organization response. The browser journey proved that
a stored administrator branch is cleared, no branch chooser appears, and employee domain requests
send no administrator branch header. Route visibility grants no permission.

## Focused verification

The route boundary suite passed four mapping, role-denial, client-boundary, and catalogue evidence
checks. The Phase 15A contract verifier still reports 52 inventory items, 31 client contracts, 29
routes, six file flows, eight owned gaps, 42 golden cases, and seven later-part owners. The Phase 14H
review and repository guard also passed.

The 15E browser journey opened every employee route directly. It confirmed headings, focus, staff
branch locking, expected self paths, the absence of branch headers and administration components,
the signed-in employee profile, stable request failures, browser back navigation, logout, cross-role
denial with no protected request, and safe handling of a URL containing another identifier. The 15B
shell, 15C administrator, and 15D manager browser checks also passed.

The affected backend regression set passed 327 tests. It covered tokens, authorization context and
dependencies, scope enforcement, HTTP boundaries, employees, leave, attachments, attendance,
rosters, shift swaps, payroll, expenses, advances, records, development, appraisals, requests,
output, notifications, tasks, and dashboards. Six existing SQLAlchemy relationship warnings remain
unchanged.

## Boundary-matched local gate

The frontend gate passed 389 Node tests, focused ESLint on every changed JavaScript and JSX file,
and the locked production build. The build transformed 99 modules. Its existing large-chunk warning
remains assigned to the measured performance work in Part 15F.

The test-first route check initially failed because the employee route files did not exist. The
first browser launch needed the approved Windows headless-browser permission. The journey then found
the personal attendance failure fallback described above. After that fix, all focused checks and the
single final gate passed. No product or denial rule changed to make a check pass.

## Catalogue and unchanged boundaries

Catalogue evidence now names the 15E composer and checks for `P15-EMP-001` through
`P15-EMP-008`, `P15-ROUTE-022` through `P15-ROUTE-029`, and `15A-GC-019` through
`15A-GC-024`. No later-part record changed. The part sequence, owners, rollback order, 31 client
contracts, 29 routes, six file flows, eight gaps, and 42 golden cases remain intact.

Part 15E added no backend endpoint, role, schema revision, RLS policy, grant, protected function,
Keycloak change, credential, browser authorization claim, business document generator, or business
capability. Alembic still has one recorded head at `e8a1c3f5b7d9`.

No live or paid resource was accessed or changed. The `workloop-clinic-dev` project,
`fra1-default` network, Phase 13 external archive, and `workloop-clinic_postgres_data` remain
preserved. The browser checks used synthetic in-memory values and created no persistent identity,
row, file, or cloud resource.

## Rollback and continuation

Part 15E rollback returns the employee route results to unavailable and removes the employee route
composer, focused checks, catalogue evidence, attendance failure fallback, and this record. It
leaves the 15B shell, administrator portal, manager portal, existing domain views and clients,
backend contracts, database, identity provider, and cloud state unchanged.

After every routed GitHub job passes and the branch is clean and synchronized, Part 15F runs in a
new Codex task. It owns cross-role local acceptance, complete file and denial proof, accessibility,
performance measurement, restart behavior, safe logs, and exact synthetic cleanup.
