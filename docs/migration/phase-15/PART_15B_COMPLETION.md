# Part 15B completion

Status: Part 15B is complete when every routed GitHub job for the commit containing this record
passes. The implementation and boundary-matched local gate passed on 2026-10-02.

## Result

Part 15B replaced the architecture-proof entry with the shared Workloop portal shell. The shell now
settles public configuration, OIDC restoration or callback processing, token validation,
`/api/v1/account/me`, and company or branch context before it renders protected navigation.

The server account role selects `/admin`, `/manager`, or `/employee`. Administrators must choose a
branch returned by the API, and a stored selection is revalidated on every load. Managers and
employees receive the single branch that matches their server account and never see a branch
chooser. A mismatched or multiple staff branch response fails closed.

The shell owns signed-out, loading, account-unavailable, service-unavailable, session-expired,
logout-incomplete, forbidden, unavailable, and not-found states. It has one main landmark, a skip
link, current-page state, route-heading focus, browser history handling, sign-out, and common
notification, task, and dashboard entries. The architecture storage proof no longer appears in the
portal. Its backend route remains unchanged.

## Fail-closed decisions

Cross-role and unknown paths stop before company, branch, or domain components mount. A same-role
route assigned to 15C, 15D, or 15E returns the stable unavailable view until its owning part replaces
that placeholder. This keeps the API as the authorization authority and prevents a placeholder from
issuing a protected business request.

The existing Phase 13 canonical-source test had frozen the frontend at exactly 75 files. Part 15B
adds three canonical source modules, so the test now pins the original 75-file count and both
historical digests while allowing later canonical additions. It still rejects a restored legacy
tree, retired client source, or a second frontend path.

## Focused verification

The focused shell suite passed eight route, history, focus, account-error, staff-branch, catalogue,
and static-wiring tests. A headless Chromium check passed for current-page state, route-heading
focus, back navigation, cross-role denial without added API requests, stale administrator branch
cleanup, explicit branch choice, and staff branch locking.

Affected authentication, HTTP, organization, notification, task, and dashboard tests passed. The
OIDC checks cover callback consumption, callback replay, logout callbacks, renewal, expiry, token
storage, account failure states, and stale responses. The Phase 15A contract verifier still reports
52 inventory items, 31 client contracts, 29 routes, six file flows, eight gaps, and 42 golden cases.
The Phase 14H verifier still traces 57 inventory items and 38 golden cases with one Alembic head.

The unchanged backend authorization boundary passed 27 focused tests. Those tests confirm the
browser route guard did not replace API scope or role denial.

## Boundary-matched local gate

The corrected frontend gate passed 377 Node tests, focused ESLint on every changed JavaScript and
JSX file, and the locked production build. The build emitted one canonical graph with 36 transformed
modules. The focused browser and backend authorization checks also passed.

The first gate attempt exposed the Phase 13 exact-file-count freeze and a local ignored Python
environment that the repository-wide lint command tried to scan. The file-count check was corrected
as described above. The final gate used focused lint because the migration workflow defines the
frontend completion gate as unit tests plus the production build, and unrelated existing source and
fixture lint findings are outside 15B.

## Unchanged boundaries

Part 15B added no backend endpoint, role, schema revision, RLS policy, grant, protected function,
Keycloak change, credential, business document generator, or business capability. Alembic still has
one head at `e8a1c3f5b7d9`.

No live or paid resource was accessed or changed. The `workloop-clinic-dev` project, `fra1-default`
network, Phase 13 external archive, and `workloop-clinic_postgres_data` remain preserved. The work
used only local synthetic browser data and created no persistent application row or identity.

## Rollback and continuation

Part 15B rollback restores the 15A `App` entry and removes the shell, route, session-state, focused
test, browser harness, catalogue evidence, and this record. It does not change the backend storage
proof route, domain clients, database, identity provider, or cloud state.

After every routed GitHub job passes and the branch is clean and synchronized, Part 15C runs in a
new Codex task. It replaces only the administrator placeholders with the approved administrator
portal routes and leaves manager and employee placeholders unchanged.
