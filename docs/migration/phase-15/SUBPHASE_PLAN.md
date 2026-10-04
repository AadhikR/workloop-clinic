# Phase 15 subphase plan

## Status and authorization

The project owner signed off Phase 14, including finding `P14H-F-001`, and started Part 15A on
2026-10-02. That instruction authorizes Parts 15A through 15H under
`docs/migration/PHASE_EXECUTION_WORKFLOW.md`. Each part runs in a separate Codex task. A part must
pass its focused checks, boundary-matched local gate, one push, and every routed GitHub job before
the next task starts automatically.

Phase 15 starts from commit `628aa5b6a75243fd049163b19b46a821904abdb3` on
`migration/fastapi-keycloak`. GitHub Migration foundation run `37003532541` passed. Alembic has one
head at `e8a1c3f5b7d9`. The branch was clean and synchronized at the 15A preflight.

On October 4, the owner authorized a complete historical portal restoration, including missing
backend features. `PORTAL_RESTORATION_EXECUTION.md` controls that continuation in Parts A through F.
Its bounded backend amendment supersedes the endpoint exclusion below for required historical
workflows. All data, infrastructure, identity-security, and preserved-resource boundaries remain.

## Phase boundary

Phase 15 replaces the public architecture-proof page with an integrated Workloop portal. The portal
uses the existing React views, API clients, OIDC session, FastAPI routes, role model, database, file
flows, and DigitalOcean deployment. It then proves the product, denial, accessibility, performance,
promotion, recovery, and rollback boundaries with synthetic data.

The phase does not add backend business capability to make a screen look complete. When an existing
API does not support an action, the portal omits the action or shows the stable unavailable state.
The API remains the authorization authority. A hidden control or guarded browser route does not prove
permission.

The following work stays outside Phase 15:

- real employee, patient, payroll, banking, biometric, identity, or document data;
- a new database table, column, RLS policy, grant, protected function, Keycloak role, or business
  endpoint unless a later part proves that the approved portal cannot work without it and records a
  separate fail-closed amendment inside this phase;
- a custom domain, automatic deployment, external email, SMS, push, analytics, or delivery service;
- a second cloud provider or a provider migration decision;
- a committed token, password, private key, connection string, signed URL, private object, or
  Terraform state;
- deletion or modification of the Phase 13 external archive or the protected local PostgreSQL
  volume; and
- live work outside the existing `workloop-clinic-dev` resources or the approved USD 15 Phase 15
  cap.

## Part plan

| Part | Scope | Required result | Rollback boundary |
| --- | --- | --- | --- |
| 15A | Portal contract, dependency inventory, routes, role ownership, file flows, gaps, golden cases, verifier, and workflow route | Every current client, approved browser route, file flow, gap, evidence class, and golden case has one later-part owner; the contract rejects invented endpoints and client-only authorization | Revert the 15A records, verifier, tests, package route, workflow route, and roadmap update |
| 15B | Shared shell and session routing | Replace the architecture-proof landing view with signed-out, loading, unavailable, forbidden, and signed-in shell states; resolve the server-derived role and selected branch before role navigation | Restore the 15A landing entry while leaving all domain clients and backend contracts unchanged |
| 15C | Administrator portal | Route the existing administrator views for organization, people, leave, attendance, roster, payroll, records, development, requests, and reports with selected-branch scope and stable failure states | Disable administrator portal routes and return administrators to the 15B shell |
| 15D | Manager portal | Route existing manager and self-service views for team, leave, time, expenses, development, and requests; deny every administrator-only gap | Disable manager routes and return managers to the 15B shell |
| 15E | Employee portal | Route existing self-service views for profile, leave, time, pay, records, development, and requests; deny every administration gap | Disable employee routes and return employees to the 15B shell |
| 15F | Cross-role local acceptance | Prove the integrated product, API denial, file flows, accessibility, production build, performance budgets, restart behavior, safe logs, and exact synthetic cleanup | Revert test and measurement controls only after preserving failure evidence; do not weaken a product or denial rule to make a gate pass |
| 15G | Reviewed DigitalOcean promotion and acceptance | Bind one reviewed release, promote it manually with automatic deployment off, then pass synthetic live role, file, denial, recovery, rollback, restart, log, and performance acceptance | Return to maintenance mode and the last compatible reviewed release; never delete a preserved resource as rollback |
| 15H | Independent review and complete phase gate | Trace all 15A records to current evidence, repeat the closing local and live checks, confirm exact cleanup and boundaries, record Phase 15 completion, and request owner signoff | Keep the last reviewed release and evidence; stop before another phase |

## Part 15A portal integration contract

15A records the current application rather than redesigning its business rules. The baseline has 34
React files and 31 API client modules. `src/App.jsx` still labels the page `Architecture proof`, and
`src/OrganizationPanel.jsx` renders most signed-in views in one long document. The OIDC bootstrap,
token check, account lookup, company and branch context, protected HTTP client, domain clients, and
role-aware components already exist.

The machine source is `integration-catalogue.json`. It records 52 inventory items, 31 client
contracts, 29 approved browser routes, six file flows, eight owned gaps, 42 golden cases, the exact
part and rollback order, one Alembic head, and the deployment boundary. The focused verifier checks
the catalogue against repository files, prose records, the Alembic index, package command, workflow
route, and roadmap.

15A changes no React runtime, backend route, schema, RLS policy, grant, Keycloak state, live setting,
credential, or cloud resource.

## Part 15B shared shell and session routing

15B replaces proof-first rendering with one shell. The shell must settle authentication and
`/api/v1/account/me` before choosing a role home. Administrators may select only a branch returned by
the API. Managers and employees receive the one server-scoped branch and no chooser.

The shell owns the common signed-out, loading, account-unavailable, service-unavailable,
session-expired, forbidden, unavailable, and not-found behavior. It also owns notifications, tasks,
dashboard entry, navigation landmarks, focus movement after navigation, and logout. It removes the
architecture storage proof from the product portal without removing the Phase 14 backend proof route.

15B does not move domain views into finished role portals. It creates the stable route and session
contract that 15C through 15E fill.

## Part 15C administrator portal

15C assigns the existing administrator components to the ten `/admin` routes in the catalogue. It
preserves selected-branch headers, idempotency keys, optimistic timestamps and versions, exact money
strings, server output, file authorization, and current empty, conflict, and denial responses.

The part may split large view files or load route groups on demand when tests prove unchanged API
behavior. It must not invent a bulk action, dashboard calculation, report, endpoint, or manager
permission. Existing administrator functionality that has no safe route state stays unavailable and
is recorded as such.

## Part 15D manager portal

15D exposes only manager and self contracts already implemented by the API. The manager can see the
own profile, direct reports, delegated or reporting-scope leave queue, manager expense queue,
personal time and schedule, direct-report development and appraisals, and existing self requests.

Payroll administration, WPS, organization settings, employee lifecycle, attendance administration,
roster drafting, branch records administration, clinical incident administration, reports, and
offboarding stay unavailable. A component branch that hides a button is not sufficient. Direct route
and API denial must pass.

## Part 15E employee portal

15E exposes only self contracts already implemented by the API. It covers profile contact fields,
leave, attendance correction and history, schedule and swaps, payslips, expenses, receipts, advances,
documents, insurance, assigned assets, training, certifications, CME, appraisals, and letter
requests.

The portal must not accept an employee, company, or branch identifier as proof of scope. Another
employee's identifier must fail at the API even when a user edits a URL or request in the browser.

## Part 15F local acceptance

15F runs one route-oriented journey for each role and covers every file class. It tests cross-role,
cross-company, cross-branch, cross-manager, and cross-employee denial at the backend boundary. It
also checks keyboard order, focus, landmarks, accessible names, status updates, dialogs, contrast,
zoom, reduced motion, and error recovery.

The part records budgets for the locked production build, initial route transfer, later route
transfer, interaction response, and API timing under a named local profile. A budget must use a
measured number and a reproducible command. Vague claims such as "fast enough" do not pass.

The final local gate uses a fresh disposable environment because Phase 15 changes shared frontend
and workflow controls. It preserves `workloop-clinic_postgres_data` and removes only the named
disposable environment and synthetic fixtures.

## Part 15G DigitalOcean promotion and acceptance

15G starts with a read-only provider preflight. It confirms the existing project, network,
application, component set, backups, automatic-deployment setting, current release, monthly usage,
and available cap. It binds the reviewed commit and all release artifacts before a manual promotion.

The integrated portal then passes the three role journeys, file flows, denial matrix, safe logs,
restart, rollback, recovery, and performance thresholds on the provider-managed App Platform default
address. The work uses only synthetic fixtures and removes them by exact identifier. It creates no
new paid resource and stays within the existing USD 15 Phase 15 cap.

## Part 15H independent review

15H checks every catalogue record against current source, tests, local evidence, GitHub results,
release identity, provider state, recovery evidence, performance measurements, and cleanup records.
It verifies that no client-only authorization claim, invented API, real record, committed credential,
custom domain, automatic deployment, external delivery service, second provider, or preserved
resource change entered the phase.

The last part runs the complete phase-closing gate, records the phase result, and asks the owner for
one signoff. It does not create or start another phase.

## Shared verification and source control

Every part follows `docs/migration/VERIFICATION_WORKFLOW.md`. Focused checks run while one unit is
changing. One boundary-matched local gate runs after the part settles. Each part commits and pushes
once, waits for all routed Migration foundation jobs, confirms a clean synchronized branch, and then
starts the next task automatically.

Workflow-control, authentication, Compose, database, migration, or shared-infrastructure changes are
full-stack sensitive. A documentation-only follow-up after a passing code gate uses changed-file
validation only and does not repeat that gate.

## Resource and data boundary

Use synthetic identities, rows, and files only. DigitalOcean is the only active provider. Use the
existing `workloop-clinic-dev` project, `fra1-default` network, application, database, bucket, and
components. Automatic deployment remains disabled. Use only the provider-managed App Platform
default address.

Preserve the Phase 13 external archive and `workloop-clinic_postgres_data`. Do not attach, mount,
modify, delete, or recreate the protected local volume. Before cleanup, resolve the exact synthetic
fixtures or disposable environment created by the current part. Never use a broad delete as phase
cleanup.
