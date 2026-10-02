# Part 15A portal integration contract

## Decision

Phase 15 will integrate the portal from the existing React views and FastAPI contracts. It will not
rewrite the product or add backend business capability to fill a browser gap. `integration-catalogue.json`
is the machine source for the part order, browser routes, client ownership, file flows, gaps, golden
cases, rollback order, schema head, and DigitalOcean boundary.

The current signed-in page is useful migration evidence but a poor product shell. It renders most
features in one document, mixes role concerns, and exposes the synthetic architecture storage proof
beside business views. The smallest safe change is a route-oriented shell that reuses the current
clients and components, then moves the three role portals in separate parts.

## Authority and scope

Backend server authorization remains authoritative. In this contract, client-side role checks are
presentation controls only. They decide which links and controls appear, but they never grant company, branch,
manager, employee, record, or file scope. Every protected action must still pass the existing API
token, account, role, branch, ownership, version, and business-state checks.

No new backend business capability is approved by this contract. A later part may reorganize React
code, add browser routes, add loading and denial views, or split route bundles. It may not invent an
endpoint, widen a role, bypass an API client, generate a server-owned business document in the
browser, or treat a hidden control as denial evidence.

When a named portal route reaches a gap, the part must choose one of two results:

- omit the control and keep the page useful with the supported operations; or
- show the stable unavailable state without a protected request.

Adding a speculative action is not an option.

## Current application boundary

The React entry is `src/main.jsx`, which renders `src/App.jsx`. The current browser entrypoints are
`/` and `/oidc/callback`; both enter the same application component. The authenticated branch of
`App` loads `OrganizationPanel`, which resolves `/api/v1/account/me`, creates company context, and
renders the current product components in one long document.

The frontend contains 34 JSX files, 31 `*Api.js` client modules, the shared protected HTTP client,
OIDC session code, CSV parsers, output delivery, idempotency recovery, and company-context state.
The exact 31 client modules and their existing endpoint markers are in the catalogue. The catalogue
does not claim that a client module grants its listed roles. The backend route and scope checks make
that decision.

## Session contract

The shell must settle these states before it displays protected navigation:

1. validate the six public API and OIDC settings;
2. complete an OIDC callback once or restore the in-memory user through the existing session state;
3. call `/api/v1/auth/token-check`;
4. call `/api/v1/account/me` and accept only `admin`, `manager`, or `employee`;
5. resolve company and branch context; and
6. choose the home route from the server-derived role.

The authorization-code flow, nonce, callback validation, memory-only user store, session storage for
OIDC state, silent renewal, account recheck, logout, and token-expiry cleanup remain unchanged unless
15B adds focused proof for a safer equivalent. Tokens must not move to local storage, React state,
the URL, logs, or committed files.

An invalid token signs the user out. An inactive or unmapped application account shows the account
unavailable state. A temporary API or identity outage shows service unavailable without displaying
stale protected content. A failed logout remains explicit until the browser session is cleared or
Keycloak confirms it.

## Route and navigation contract

The 29 route records in the catalogue are the approved browser paths. `/`, `/oidc/callback`,
`/forbidden`, and `/unavailable` belong to 15B. The administrator, manager, and employee route groups
belong to 15C, 15D, and 15E. A later part may use a small local router or a locked dependency, but it
must preserve direct navigation, browser back and forward behavior, callback cleanup, and a stable
not-found result.

The shell must provide one main landmark, a skip link, a visible current-page label, a predictable
heading order, and a sign-out action. Navigation moves focus to the page heading or main content.
Loading, success, error, denial, and destructive confirmation messages use suitable status or alert
semantics. A route change must not discard an unsaved form without a clear warning.

Route guards run only after account resolution. A mismatched role goes to `/forbidden`. A capability
that this phase intentionally does not expose goes to `/unavailable`. Unknown paths show a safe
not-found result. None of those pages includes record existence, identifiers, filenames, or branch
names from a denied request.

## Company and branch contract

Administrators may choose only a branch returned by `/api/v1/branches`. The selected branch stays in
session storage and is revalidated against the latest API response. A deleted, deactivated, missing,
or foreign branch clears the selection and returns to the chooser.

Managers and employees receive one safe employer and branch context from the API. Their portal does
not display a branch chooser and does not accept a stored administrator selection. The browser sends
`X-Workloop-Branch-ID` only for clients that already require an administrator branch or a supported
manager branch operation. The API rejects a missing, conflicting, or foreign value.

## API and mutation contract

Portal code must use `AuthenticationSession.request` through the existing client modules. Direct
`fetch` calls from a role view are prohibited. The shared client continues to enforce the approved
origin, protected access, method allowlist, timeout, correlation identifier, no-store behavior,
problem response parsing, and one renewal attempt.

Existing mutation rules remain intact:

- use an idempotency key where the current client and API require one;
- send expected timestamps, versions, source digests, or calculation versions where defined;
- keep server-derived company, branch, employee, status, total, and audit fields out of editable
  browser payloads;
- treat 403 and opaque 404 as authorization failures without guessing record existence;
- handle 409 as stale state or business conflict and reload before retry; and
- never retry a non-idempotent mutation after an unknown network result without the existing
  idempotency recovery contract.

The portal may improve labels and error messages, but it must preserve the safe error code meaning.
It must not print raw response bodies, tokens, connection details, signed URLs, object keys, or
private record fields.

## Role contract

### Administrator

The administrator portal owns the selected-branch views listed under `/admin`. It may expose current
organization, people, leave, attendance, roster, payroll, records, development, request, dashboard,
task, notification, report, export, and output operations. It may not claim cross-company access.
Any operation that lacks a current client and backend contract remains unavailable.

### Manager

The manager portal owns the existing manager and self contracts under `/manager`. Direct-report and
delegated queues come from the API. A manager cannot turn a direct-report identifier into general
employee administration. Administrator payroll, WPS, organization, lifecycle, attendance setup,
roster drafting, records administration, incident administration, report, and offboarding routes
remain unavailable.

### Employee

The employee portal owns the existing self contracts under `/employee`. It does not send an employee
identifier to establish ownership. Another employee's URL, request ID, file ID, payslip ID, or
appraisal ID must fail at the API.

## File and output contract

The six catalogue file flows cover leave attachments, employee documents, expense receipts,
training and certification evidence, CSV and SIF output, and rendered PDF, letter, settlement, and
ZIP output.

Uploads keep the current two-step submission intent where present. The browser validates only for a
useful early message. Backend type, size, scope, object state, and scanner rules remain decisive.
Failed or abandoned submissions must not become visible records.

Downloads use the current protected API operation. The browser may save returned bytes or open an
authorized PDF with `outputDelivery.js`. It must not persist private bytes, object keys, signed URLs,
or authorization headers. It must revoke temporary object URLs. CSV, SIF, PDF, letter, settlement,
and ZIP content stays server-generated.

File denial proof must cover cross-company, cross-branch, cross-manager, and cross-employee access.
A missing or denied file returns the existing opaque response and exposes no metadata.

## Accessibility contract

15F must test every route group at keyboard-only operation and 200 percent zoom. The acceptance set
covers skip navigation, landmarks, heading order, focus visibility, focus placement after route
changes, accessible names and descriptions, form errors, table headers, dialogs, live status,
destructive confirmations, color contrast, pointer target size, and reduced motion.

Automated checks can find missing names, roles, and some contrast errors. They do not replace the
manual keyboard, focus, zoom, and screen-reader spot checks recorded by 15F. A business action that
cannot be completed from the keyboard fails the part.

## Performance contract

15F must define and measure a named local acceptance profile against the locked production build.
The record must include initial compressed transfer, later route transfer, largest route bundle,
route-change interaction time, form feedback time, and representative API timing. It must state the
hardware or runner class, browser, network profile, sample count, percentile, and cold or warm cache.

The first budget must use the Phase 0 large-chunk warning as a baseline, not an excuse. Route splitting
is allowed when it does not duplicate sensitive state or weaken error handling. A later part may
tighten a budget after measurement. It may not relax one merely because the implementation missed it.

15G repeats the approved measurements on the DigitalOcean default address. Provider measurements
must separate frontend transfer and interaction time from API latency. A cached fast result does not
replace a cold-route sample.

## Local verification contract

15F uses a fresh disposable Compose project and synthetic fixtures. The complete local gate covers
the locked frontend install and build, frontend tests, backend tests and quality checks, migrations
twice, current schema and authorization controls, Keycloak configuration where affected, restart
persistence, the route-oriented three-role journey, file flows, denials, accessibility, performance,
safe logs, and exact cleanup.

The protected `workloop-clinic_postgres_data` volume must not be attached, mounted, inspected,
modified, deleted, or recreated. A failing gate keeps enough disposable evidence for diagnosis, then
cleanup names the exact project and volumes it removes.

## DigitalOcean contract

DigitalOcean remains the only active provider. Use the existing `workloop-clinic-dev` project,
`fra1-default` network, managed database, private object storage, application, and seven reviewed
components. Use only the provider-managed App Platform default address. Automatic deployment remains
disabled.

15G records a release identity that binds the reviewed commit, frontend build, public settings,
backend image, Keycloak image, app spec, Terraform, dependency locks, and Alembic head
`e8a1c3f5b7d9`. The record must distinguish the local frontend build, provider build, and delivered
root. That distinction preserves the lesson from `P14H-F-001`.

Live acceptance uses Synthetic identities, rows, and files only. It changes no resource count or
size and stays within the existing USD 15 Phase 15 cap. Promotion, rollback, restart, and recovery
records contain identifiers and digests, not credentials or private console output.

## Recovery and rollback contract

Portal rollback selects the last compatible reviewed frontend artifact while keeping the matching
backend, Keycloak, configuration, and schema contract. Never downgrade the schema automatically.
If compatibility is uncertain, enable maintenance mode and keep writes and workers disabled until
the matching release is verified.

Recovery acceptance restores into the exact isolated targets defined by the Phase 14 runbook. It
adds portal route, role, denial, file, and performance checks to the existing database, identity,
object, signing-key, worker, and reconciliation checks. Cleanup deletes only named recovery targets.

Rollback order is `15H`, `15G`, `15F`, `15E`, `15D`, `15C`, `15B`, then `15A`. Removing a portal
route never deletes its business data. Reverting a test or evidence file never substitutes for
reverting a faulty release.

## Preserved boundaries

Preserve `workloop-clinic-dev`, `fra1-default`, the Phase 13 external archive, and
`workloop-clinic_postgres_data`. Do not add real regulated data, a custom domain, automatic
deployment, an external delivery service, a second provider, or a committed credential.

The Phase 14 architecture proof backend route may remain for infrastructure verification, but it is
not a portal feature and must not appear in signed-in product navigation after 15B.
