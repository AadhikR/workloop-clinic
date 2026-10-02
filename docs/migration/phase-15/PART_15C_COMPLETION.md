# Part 15C completion

Status: Part 15C is complete when every routed GitHub job for the commit containing this record
passes. The implementation and boundary-matched local gate passed on 2026-10-02.

## Result

Part 15C replaced the ten administrator placeholders with the approved routes from
`P15-ROUTE-005` through `P15-ROUTE-014`. The administrator home keeps notifications, tasks, the
administrator dashboard, and the clinical dashboard. The other nine routes compose the existing
organization, people, leave, attendance, roster, payroll, records, development, and report views.

The route composer passes the same server-derived account, protected authentication client, and
API-returned selected branch to the existing views. Those views still own idempotency recovery,
optimistic timestamps and versions, exact money strings, conflict messages, server output, and
protected file delivery. Part 15C adds no request path or browser document generator.

## Fail-closed decisions

The shared shell still resolves the account and validates the administrator branch before it mounts
an administrator view. A stale, missing, inactive, or foreign stored branch returns to the chooser.
Cross-role navigation stops before company, branch, or domain requests run.

Manager and employee routes remain 15D and 15E placeholders. Part 15C exposes no administrator
operation that lacks an existing client and backend contract. Unsupported actions remain absent,
and each reused view keeps its current empty, conflict, denial, file, and failure behavior. Backend
authorization remains the permission boundary.

The administrator composer contains no transport, output construction, or authorization logic. It
only assigns existing views to routes. This keeps rollback small: disable the 15C route result and
return those paths to the 15B unavailable state.

## Focused verification

The focused route suite passed four administrator mapping, role-denial, server-output, and catalogue
evidence checks. Together with the eight 15B shell checks, it proves all ten administrator routes,
the unchanged manager and employee placeholders, browser history, focus movement, and safe route
states.

The headless 15C browser journey opened every administrator route directly. It confirmed the page
heading, selected-branch label, mounted route group, stable service failures, back navigation,
heading focus, logout, stale-branch cleanup, explicit branch selection, and cross-role denial with
no protected request. The updated 15B browser regression also passed.

The affected frontend regression suite passed 381 tests. It covers authentication, protected HTTP,
organization, employee lifecycle, leave, attendance, roster, payroll, WPS, Nafis, expenses,
advances, records, development, reports, output, notifications, tasks, dashboards, optimistic
conflicts, exact decimal strings, and protected file bytes. The existing backend scope and
authorization set passed 94 tests, so route visibility did not replace API denial.

## Boundary-matched local gate

The frontend gate passed 381 Node tests, focused ESLint on every changed JavaScript and JSX file,
and the locked production build. The build transformed 93 modules. The 15C and 15B browser checks,
the backend scope set, the Phase 15A contract verifier, the Phase 14H review, and the repository
guard also passed.

The only failed development checks were useful test failures. The first focused test expected the
new route files before they existed. The browser journey then found a missing account prop on the
WPS and Nafis view, which was corrected before the passing gate. The 15B browser check still expected
the People placeholder and was updated to assert the completed 15C route.

## Catalogue and unchanged boundaries

Catalogue evidence now names the 15C composer and checks for `P15-ADM-001` through
`P15-ADM-012`, `P15-ROUTE-005` through `P15-ROUTE-014`, and `15A-GC-007` through
`15A-GC-012`. No later-part record changed. The part sequence, owners, rollback order, 31 client
contracts, 29 routes, six file flows, eight gaps, and 42 golden cases remain intact.

Part 15C added no backend endpoint, role, schema revision, RLS policy, grant, protected function,
Keycloak change, credential, business document generator, or business capability. Alembic still has
one head at `e8a1c3f5b7d9`.

No live or paid resource was accessed or changed. The `workloop-clinic-dev` project,
`fra1-default` network, Phase 13 external archive, and `workloop-clinic_postgres_data` remain
preserved. The browser checks used synthetic in-memory values and created no persistent identity,
row, file, or cloud resource.

## Rollback and continuation

Part 15C rollback returns the administrator route results to unavailable and removes the route
composer, focused checks, catalogue evidence, and this record. It leaves the 15B shell, existing
domain views and clients, backend contracts, database, identity provider, and cloud state unchanged.

After every routed GitHub job passes and the branch is clean and synchronized, Part 15D runs in a
new Codex task. It replaces only the manager placeholders with the approved manager portal routes
and leaves employee placeholders unchanged.
