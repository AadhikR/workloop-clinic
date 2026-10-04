# Portal restoration progress

## How to read this record

The reference is `a3b72a22924d1b56b5603ee8e0069ddecee65f43`. Use the inventory for source paths
and current clients. The owner authorized missing backend features as well as UI restoration.

"A implemented" means this task changed and tested the listed work. It does not certify complete
historical parity. The remaining work below is required before Part F can close the phase.
"Pending" means the assigned part has not yet compared that view. No other view inherits a pass
from the shared stylesheet.

## Module-by-module comparison

| Portal | Module | Assigned part | Comparison and current result |
| --- | --- | --- | --- |
| Admin | Dashboard | D | D restores the setup checklist, scoped server cards and warning links, Emiratization compliance, and paged payroll cost tables and charts. |
| Admin | Clinical dashboard | D, F | D restores scoped credential cards, staffing compliance, and document expiry tables. Card details show confirmed counts and work-area links. F must restore employee drill-downs through D-01. |
| Admin | Company settings | B, D, F | B restores grouped employer, payroll, jurisdiction, module, insurance-policy, and WPS reference areas. It adds validated logo upload, preview, replacement, and removal, while keeping biometric integration excluded. D implements and proves the atomic routing-code cascade in B-01. F must publish its backend and migration before final promotion. |
| Admin | Employees | B, C, F | B restores active, expiry, and terminated summaries; the employee table; a broad tabbed modal; job history; lifecycle controls; and selected-employee documents, insurance, contracts, offboarding, and settlement access. A new idempotent profile command saves ordinary, title, department, manager, and salary changes in one transaction. C adds the current effective default shift and versioned replacement to Job and contract. F owns the large-branch expiry reader and database proof in B-03 and B-04. |
| Admin | Departments | A, C, F | A restores separate department, hierarchy, and staffing views with named hierarchy, employee search, expand/collapse, and guarded dialogs. C now reads the selected branch and hides staffing navigation and controls unless that branch enables staffing rules. F checks card density and row-level delete placement. |
| Admin | Requests | B, F | B restores Pending, Completed, Rejected, and All filters across letter and custom requests. Printable source and PDF controls now appear only for completed standard letters. F owns populated database and rendered-output proof in B-04. |
| Admin | Payroll | D, F | D preserves the accepted salary review and adds atomic routing change and complete run traversal. WPS and Nafis retain confirmed state and inputs on failure. SIF previews separate employee and control records and download server bytes. F owns final live promotion. |
| Admin | Advances | D, F | D restores shared request and decision dialogs and complete collection traversal. F owns protected historical cancellation in D-02. |
| Admin | Expenses | D, F | D restores shared request and decision dialogs, complete collection traversal, and protected attached-receipt viewing. F owns recoverable historical removal in D-02. |
| Admin | Leave | C | C restores Overview, Requests, Calendar, Balances, and Settings work areas around the current scoped clients. Request decisions, policy, holidays, balance work, and delegations remain server-authoritative. |
| Admin | Attendance | C | C restores Dashboard, Manual Entry, Records, Absences, Overtime, Corrections, Periods, and Settings work areas. Biometric mapping and import controls remain excluded. |
| Admin | Assets | A, F | Old register/history tabs and custody forms replaced by an inline editor with identifier prompts. A restores summaries, register columns, named assign/return dialogs, history, status filters, and confirmations. New server history and dated custody support added. Actor labels and self-history pagination remain in F. |
| Admin | Training | A, E, F | Old Training/Certifications/CME work areas replaced by simultaneous forms requiring a selected employee. A restores tabs, per-tab summaries, employee selection inside creation dialogs, completion/rejection dialogs, certification edit, and branch CME tracking. Status transitions, complete collection pagination, and contributing CME records remain. |
| Admin | Appraisals | A, F | Old Cycles/Reviews tables and review dialog replaced by stacked cycles and rating prompts. A restores those views, cycle selection, review summaries, section detail and rating dialogs, calibration, confirmation, and closed-cycle read-only controls. Admin section rating and retained review removal need an authority amendment. Department/job metadata and final dialog layout remain. |
| Admin | Roster | C | C restores Shift Templates, Monthly Roster, and Swap Requests. The monthly grid keeps validation, exact-version publication, actual-hours, overtime, and swap operations on current clients. |
| Admin | Incidents | A, F | Old summaries, filters, nine-column register, people/time fields, and report dialog replaced by a permanent form and terse actions. A restores these UI areas and investigation/corrective-action dialogs. Historical deletion has no current audited server operation. Retained removal and final edit layout remain in F. |
| Admin | Reports | D | D restores family selection, named supported filters, 13 report tables and charts, authoritative totals, pagination, and protected CSV/PDF output with retained failure state. |
| Admin | Tasks | D | D restores grouped, collapsible server task cards, urgency, manual and timed refresh, and role-correct links. Notifications page the inbox and confirm read writes before updating. |
| Manager | Home | E | Pending |
| Manager | Leave queue | E | Pending |
| Manager | Expense queue | E | Pending |
| Manager | Appraisals | E | Shared A dialogs changed. Own records cannot show rating controls. Historical manager-specific comparison and populated proof pending. |
| Manager | Leave | E | Pending |
| Manager | Schedule | E | Pending |
| Manager | Attendance | E | Pending |
| Manager | Payslips | E | Pending |
| Manager | Advances | E | Pending |
| Manager | Expenses | E | Pending |
| Manager | Training | E | Shared A tabs/forms changed. Completion is limited to selected direct reports. Historical team/personal comparison and populated proof pending. |
| Manager | Documents | B, E | B keeps document and insurance components in selected employee context. E still owns the complete manager-specific historical comparison and direct-report restrictions. |
| Manager | Requests | B, E | B fixes own completed-letter output for managers and prevents custom requests from entering the standard-letter renderer. E still owns the complete manager workspace comparison. |
| Manager | Profile | E | A corrected UAE mobile validation in the shared contact editor. Full historical profile comparison remains pending. |
| Manager | Tasks | D, E | D proves grouped tasks, manager queue links, and notification read/failure behavior. E owns the complete personal workspace comparison. |
| Employee | Home | E | Pending |
| Employee | Leave | E | Pending |
| Employee | Schedule | E | Pending |
| Employee | Attendance | E | Pending |
| Employee | Payslips | E | Pending |
| Employee | Advances | E | Pending |
| Employee | Expenses | E | Pending |
| Employee | Training | E | Shared A forms changed. No employee verification or completion authority added. Historical personal workflow and required self-completion contract pending. |
| Employee | Appraisals | E | Shared A result dialog changed. Remains read-only. Historical personal comparison and populated proof pending. |
| Employee | Documents | B, E | B preserves the shared protected-file components and selected-record integration. E still owns the personal documents and insurance layout comparison. |
| Employee | Requests | B, E | B restores the shared letter/custom request split and limits output to completed standard letters. E still owns the complete personal workspace comparison. |
| Employee | Profile | E | A corrected UAE mobile validation in the contact editor. Full historical profile comparison remains pending. |
| Employee | Tasks | D, E | D proves personal grouped tasks, links, and notification read/failure behavior. E owns the complete personal workspace comparison. |

## Backend additions in A

| Operation | Implemented contract |
| --- | --- |
| `GET /api/v1/assets/assignments` | Admin-selected branch, company/branch equality on employee and asset joins, named employees, optional asset filter, dated UUID keyset pagination. Managers and employees denied before execution. |
| Asset inventory pagination | Server emits an actual next cursor and `hasMore`. Admin register follows every page and rejects repeated cursors. Existing self projection stays unchanged. |
| Asset handover and return dates | Optional request dates default to the server's business date. Reject future dates, returns before handover, and backdated assignments overlapping retained custody. Existing row locks, versions, idempotency, audit, and active-employee scope remain. |
| `PATCH /api/v1/certifications/{id}` | Immutable employee ownership, authorized admin/self/direct-report scope, row lock, expected version, and audit. Edits return a certificate to pending review and clear the previous decision. Staff cannot edit a verified certificate. Evidence is neither exposed nor replaced. |
| `GET /api/v1/cme/summary` | Admin-selected branch and year, employee keyset pagination, authoritative target/completed/in-progress/gap values and requirement versions. Completed totals require passed training and the same evidence scan predicate as the existing self summary. |

## Backend additions in B

| Operation | Implemented contract |
| --- | --- |
| `POST /api/v1/employees/{employeeId}/profile-save` | Admin-selected branch, required idempotency key, locked employee and manager relationships, expected employee version, eligible acyclic manager, existing department, and one database update. Changed title, department, and salary snapshots append job history. A manager change appends the existing allowlisted audit event. Lifecycle state remains in its named commands. |
| Completed request source and PDF authorization | Managers now use the same self-scoped branch derivation as employees. The request service rejects custom requests before producing standard-letter source data. The UI exposes source, print, and download only for completed standard letters. |
| Branch logo payload | Branch create and update requests accept the restored bounded image data payload. The browser accepts PNG, JPEG, or WebP files up to 64 KB and retains the existing expected-version branch update. No database revision was required because the retained column is text. |

## Required follow-up work

| ID | Owner | Dependency and required result |
| --- | --- | --- |
| A-01 | E, F | Training currently has creation, planned-record edit, and admin/direct-report completion. Restore start/cancel transitions and historical personal completion with protected server commands. Self-entered results must not grant verified CME credit. Verify ownership, direct-report changes, versions, audit, and failure states. |
| A-02 | F | Admin section rating conflicts with the manager-only `appraisal_section_rated` audit authority. Add a scoped, versioned admin operation and an append-only authority amendment. Keep closed cycles locked and deny staff outside current direct-report ownership. |
| A-03 | F | Appraisal and incident removal lacks the required current operation and retained authority. Implement recoverable archival/removal with audit, versions, idempotent replay, and tenant/branch scope. Preserve closed records. Do not revive historical unaudited hard deletion. |
| A-04 | F | Training, certification, appraisal, incident, and self-asset collections still cap results. Complete server pagination and client traversal across these shared read families before certifying totals or large-population parity. A's new history, inventory, and branch CME readers already page. |
| A-05 | F | Asset history needs a readable assigned-by label. Resolve it through an approved application identity projection, not a UUID presented as a person's name. Do not expose identity-provider subjects or private profiles. |
| A-06 | F | C binds the staffing tab to the selected branch's `enableStaffingRules` setting and proves enabled and disabled browser states. F must repeat this with final populated roster coverage and publication evidence. |
| A-07 | F | Final visual comparison must check department card/table choice, staffing delete action placement, appraisal employee department/job metadata and complete review editor, CME contributing-record detail and top action placement, incident retained-edit layout, and every dark/mobile/failure state. |
| A-08 | F | Backend changes are not deployed by a frontend rebuild. Publish reviewed backend artifacts through the existing provider procedure before promoting the final UI. Keep accepted payroll release `e42808894b1c1a66c5e42738bbf9fa0cb46c538e` live until Part F. |
| B-01 | D, F | Restore the historical routing-code cascade as one idempotent server command, not a branch update followed by client fan-out. Lock the branch and every affected draft payroll run, verify the branch version and each draft source/version, update the branch default and only draft runs in the selected branch, reject approved or paid runs, append allowlisted audit events, and return the changed run identifiers and versions. D integrates it with payroll. D proves concurrency, rollback, audit, replay, and denial behavior against disposable PostgreSQL. F must apply revision `f1a3c5e7b9d2` and publish the backend before final promotion. |
| B-02 | F | C shows the effective default shift in Job and contract and replaces it through `POST /api/v1/shift-assignments` with the freshly read assignment identifier and version. C did not add unassignment: the current model has no branch default to fall back to, so clearing would leave an ambiguous schedule. F verifies the final editor and roster interaction. |
| B-03 | F | The restored expiry summary combines fixed employee dates with uploaded document expiry records through current scoped readers. Add a paged or aggregate admin-selected-branch expiry projection before certifying large-branch parity, so the summary does not require one document request per employee. The result must expose employee identity, source type, expiry date, and status without document numbers, storage paths, hashes, or signed URLs. |
| B-04 | F | Run the composite profile command, custom-request output denial, manager self-letter output, logo update, and selected-employee child readers against the disposable PostgreSQL and object-storage environment. Prove one-transaction rollback, stale versions, manager cycles, audit rows, replay, branch denial, protected output, and browser failure retention. Publish the reviewed backend artifact only in F. |
| B-05 | F | Final visual comparison must cover populated employer settings, logo states, every employee modal tab, fixed and uploaded expiry warnings, long job histories, empty and populated child tabs, offboarding and settlement states, all request filters, dark mode, mobile scrolling, keyboard focus, and failed saves. |

## Backend additions in D

| Operation | Implemented contract |
| --- | --- |
| `GET/POST /api/v1/branches/{branchId}/payroll-routing` | Active human administrator, exact selected branch, complete draft set, branch and draft versions, source digests, branch and draft locks, one transaction, required idempotency key, allowlisted audit, and exact replay. Revision `f1a3c5e7b9d2` grants runtime execution only. Ordinary branch PATCH denies routing changes. |
| `POST /api/v1/expenses/{claimId}/receipt-download` | Authorize the claim in current self, direct-report, or selected-branch scope, locate its attachment, then reuse existing receipt ownership, scan, object hash, and signed-download checks. No storage data enters the claim projection. |

## D dependencies assigned to F

| ID | Owner | Dependency and required result |
| --- | --- | --- |
| D-01 | F | Clinical card counts use scan-aware documents and verified certifications. The broader document expiry report does not have the same eligibility rules or certification rows. Add a paged selected-branch employee projection for each clinical card, with sanitized employee identity, credential type, expiry, and status. Match the card predicate, preserve tenant/branch scope, and exclude storage identifiers and protected evidence. Reuse B-03 and A-04 shared read work. Replace count-only expansion with the historical employee drill-down and prove count/detail agreement. |
| D-02 | F | Current expense DELETE supports only pending, manager-rejected, or rejected claims outside payroll. Historical removal from the broader register and administrator advance cancellation need protected retained operations. Extend A-03 retained removal across financial workflows, with scoped authorization, expected versions, idempotency, audit, recoverable archival where appropriate, and atomic cancellation rules. Preserve receipts, repayment history, generated payroll, paid claims, and protected ledgers. Define which pending or unpaid states can be removed or cancelled. Do not restore unaudited hard deletion or local success. |

## A verification

Focused service tests cover scoped joins, role denial, branch requirements, cursor validation,
pagination, invalid and overlapping custody dates, scan-aware CME totals, certificate ownership,
immutable fields, locking, resubmission, and audit. Browser fixtures use synthetic records through
the production parsers. They verify register/history, named custody payloads, retained deletion
failure, reporting hierarchy/search/collapse, staffing edits, creation context, completion payloads,
failed certificate edits, CME targets, appraisal review, incident time/people/investigation, and
390-pixel page containment. Evidence is in `evidence/restoration-a`.

The final local gate passed 417 frontend tests, including the production build, and 720 backend
tests. Changed frontend files pass lint. Backend lint, formatting, types, and dependency checks
pass. The populated browser verifier passes after waiting for the navigation pill to settle.
Shared route accessibility and failed-contact-save recovery checks pass all 46 navigation routes.
The complete independent gate passed for code commit `195fc669a84482652e02d3f514a09e0f3486d4fb`,
including database history, permissions, authentication, restart journeys, performance, and cleanup.
This closes A's assigned gate, not the required C, E, and F dependencies listed above.
See `PORTAL_RESTORATION_A_COMPLETION.md` for the execution environment and evidence limits.

These tests do not prove every backend transaction against PostgreSQL or every role-specific
historical layout. E and F own those remaining checks. No live resources, credentials, real records,
or preserved volumes changed. The required GitHub result travels in the next part's handoff.

## B verification

The final local gate passed 422 frontend tests and 724 backend tests. Changed frontend files pass
lint, and repository whitespace validation passes. Backend lint, formatting, dependency checks, and
changed-file type checks pass. The backend suite emitted the six existing SQLAlchemy relationship
warnings. The Node-only whole-tree type-check image cannot resolve boto packages used by unchanged
storage files, so that environment is not evidence of whole-tree type failure.

Four focused backend tests cover atomic profile history and audit writes, manager self-letter
scope, custom-request source denial, and OpenAPI registration. Eight focused frontend tests cover
the restored module wiring and output rules. The populated browser verifier covers grouped company
settings, the selected-employee editor, failed-save retention and retry, the combined profile
payload, request filters and output controls, manager print access, and 390-pixel containment. It
saves six desktop and mobile screenshots in `evidence/restoration-b`.

Shared route accessibility and recovery checks pass all 46 route groups. Local performance remains
inside the unchanged limits: 224,992 compressed initial bytes, no later-route transfer, a
206,154-byte largest route bundle, 101.8 ms route-change p95, 67.1 ms form-feedback p95, and
6.78 ms read-only health p95. The browser and API timing fixtures are local synthetic evidence, not
a populated production benchmark. The schema head remains `e8a1c3f5b7d9`.

These checks close B's local gate. They do not close B-01 through B-05 or publish the backend.
The independent GitHub gate and its commit binding are recorded in
`PORTAL_RESTORATION_B_COMPLETION.md` after the code commit passes.

## C verification

The final local gate passed 429 frontend tests and the production build. Every changed source and
verifier file passes lint, and repository whitespace validation passes. The schema head remains
`e8a1c3f5b7d9`. A focused backend boundary run passed 99 leave, attendance, roster, shift-swap,
and department tests with the six existing SQLAlchemy relationship warnings.

Seven focused source tests cover the restored work areas, removal of biometric controls, effective
shift concurrency fields, staffing visibility, and administrator route wiring. The Part C browser
fixture covers keyboard tab navigation; cross-tab leave refresh, requests, settings, and
delegations; failed manual
attendance writes; overtime; monthly roster edits, validation, publication, and swaps; both
staffing states; effective-shift failure retention and retry; and 390-pixel containment. Nine
desktop and mobile screenshots are in `evidence/restoration-c`.

The older full-stack browser verifier was updated to use the restored Requests and Settings tabs.
Its global cleanup assertion requires an otherwise empty database, so it was not accepted as a gate
against the preserved populated development volume. Its fixed synthetic identifiers were cleaned;
the isolated Part C fixture supplies the affected-route proof. The independent GitHub result will
be recorded in `PORTAL_RESTORATION_C_COMPLETION.md` after the code commit passes.

## D verification

The local gate passed 434 frontend tests and the production build, 732 backend tests, frontend and
backend lint, backend formatting, whole-tree types, and dependency checks. Seven focused backend
tests and four focused frontend tests cover the new contracts. Disposable PostgreSQL proof covers
the atomic routing operation, concurrent locks, stale sets and versions, approvals, rollback,
replay, audit, scope, and role denial. The complete affected historical chain and deep database
checks pass, including D's exact predecessor rollback.

The isolated stack proves persisted catalogue, signing keys, storage and scans across restart,
real role sign-in journeys, and synthetic cleanup. The D browser fixture exercises every current
report type, financial dialogs and output, receipt failures, routing retry, role-aware tasks,
notification failures, keyboard use, and 390-pixel containment. Fifteen screenshots and the
performance record are in `evidence/restoration-d`. Shared route and recovery checks pass all
46 views. Performance limits remain unchanged after deferred administrator module loading.
See `PORTAL_RESTORATION_D_COMPLETION.md` for measurements, environment, and evidence limits.
D does not certify D-01, D-02, or the other F dependencies, and does not deploy.