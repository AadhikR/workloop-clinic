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
| Admin | Dashboard | D | Pending |
| Admin | Clinical dashboard | D | Pending |
| Admin | Company settings | B | Pending |
| Admin | Employees | B | Pending |
| Admin | Departments | A, C, F | Old department register, reporting-manager chart, and staffing views replaced by simultaneous editors. A restores separate views, named hierarchy, employee search, expand/collapse, and guarded dialogs. C must bind staffing visibility to the branch setting. F checks card density and row-level delete placement. |
| Admin | Requests | B | Pending |
| Admin | Payroll | D, F | Accepted populated review is preserved. D compares remaining output and compliance areas. |
| Admin | Advances | D | Pending |
| Admin | Expenses | D | Pending |
| Admin | Leave | C | Pending |
| Admin | Attendance | C | Pending |
| Admin | Assets | A, F | Old register/history tabs and custody forms replaced by an inline editor with identifier prompts. A restores summaries, register columns, named assign/return dialogs, history, status filters, and confirmations. New server history and dated custody support added. Actor labels and self-history pagination remain in F. |
| Admin | Training | A, E, F | Old Training/Certifications/CME work areas replaced by simultaneous forms requiring a selected employee. A restores tabs, per-tab summaries, employee selection inside creation dialogs, completion/rejection dialogs, certification edit, and branch CME tracking. Status transitions, complete collection pagination, and contributing CME records remain. |
| Admin | Appraisals | A, F | Old Cycles/Reviews tables and review dialog replaced by stacked cycles and rating prompts. A restores those views, cycle selection, review summaries, section detail and rating dialogs, calibration, confirmation, and closed-cycle read-only controls. Admin section rating and retained review removal need an authority amendment. Department/job metadata and final dialog layout remain. |
| Admin | Roster | C | Pending |
| Admin | Incidents | A, F | Old summaries, filters, nine-column register, people/time fields, and report dialog replaced by a permanent form and terse actions. A restores these UI areas and investigation/corrective-action dialogs. Historical deletion has no current audited server operation. Retained removal and final edit layout remain in F. |
| Admin | Reports | D | Pending |
| Admin | Tasks | D | Pending |
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
| Manager | Documents | B, E | Pending |
| Manager | Requests | B, E | Pending |
| Manager | Profile | E | Pending |
| Manager | Tasks | D, E | Pending |
| Employee | Home | E | Pending |
| Employee | Leave | E | Pending |
| Employee | Schedule | E | Pending |
| Employee | Attendance | E | Pending |
| Employee | Payslips | E | Pending |
| Employee | Advances | E | Pending |
| Employee | Expenses | E | Pending |
| Employee | Training | E | Shared A forms changed. No employee verification or completion authority added. Historical personal workflow and required self-completion contract pending. |
| Employee | Appraisals | E | Shared A result dialog changed. Remains read-only. Historical personal comparison and populated proof pending. |
| Employee | Documents | B, E | Pending |
| Employee | Requests | B, E | Pending |
| Employee | Profile | E | Pending |
| Employee | Tasks | D, E | Pending |

## Backend additions in A

| Operation | Implemented contract |
| --- | --- |
| `GET /api/v1/assets/assignments` | Admin-selected branch, company/branch equality on employee and asset joins, named employees, optional asset filter, dated UUID keyset pagination. Managers and employees denied before execution. |
| Asset inventory pagination | Server emits an actual next cursor and `hasMore`. Admin register follows every page and rejects repeated cursors. Existing self projection stays unchanged. |
| Asset handover and return dates | Optional request dates default to the server's business date. Reject future dates, returns before handover, and backdated assignments overlapping retained custody. Existing row locks, versions, idempotency, audit, and active-employee scope remain. |
| `PATCH /api/v1/certifications/{id}` | Immutable employee ownership, authorized admin/self/direct-report scope, row lock, expected version, and audit. Edits return a certificate to pending review and clear the previous decision. Staff cannot edit a verified certificate. Evidence is neither exposed nor replaced. |
| `GET /api/v1/cme/summary` | Admin-selected branch and year, employee keyset pagination, authoritative target/completed/in-progress/gap values and requirement versions. Completed totals require passed training and the same evidence scan predicate as the existing self summary. |

## Required follow-up work

| ID | Owner | Dependency and required result |
| --- | --- | --- |
| A-01 | E, F | Training currently has creation, planned-record edit, and admin/direct-report completion. Restore start/cancel transitions and historical personal completion with protected server commands. Self-entered results must not grant verified CME credit. Verify ownership, direct-report changes, versions, audit, and failure states. |
| A-02 | F | Admin section rating conflicts with the manager-only `appraisal_section_rated` audit authority. Add a scoped, versioned admin operation and an append-only authority amendment. Keep closed cycles locked and deny staff outside current direct-report ownership. |
| A-03 | F | Appraisal and incident removal lacks the required current operation and retained authority. Implement recoverable archival/removal with audit, versions, idempotent replay, and tenant/branch scope. Preserve closed records. Do not revive historical unaudited hard deletion. |
| A-04 | F | Training, certification, appraisal, incident, and self-asset collections still cap results. Complete server pagination and client traversal across these shared read families before certifying totals or large-population parity. A's new history, inventory, and branch CME readers already page. |
| A-05 | F | Asset history needs a readable assigned-by label. Resolve it through an approved application identity projection, not a UUID presented as a person's name. Do not expose identity-provider subjects or private profiles. |
| A-06 | C, F | Department staffing tab must respect the branch's enable setting. Prove enabled and disabled states alongside roster coverage/publication. |
| A-07 | F | Final visual comparison must check department card/table choice, staffing delete action placement, appraisal employee department/job metadata and complete review editor, CME contributing-record detail and top action placement, incident retained-edit layout, and every dark/mobile/failure state. |
| A-08 | F | Backend changes are not deployed by a frontend rebuild. Publish reviewed backend artifacts through the existing provider procedure before promoting the final UI. Keep accepted payroll release `e42808894b1c1a66c5e42738bbf9fa0cb46c538e` live until Part F. |

## A verification

Focused service tests cover scoped joins, role denial, branch requirements, cursor validation,
pagination, invalid and overlapping custody dates, scan-aware CME totals, certificate ownership,
immutable fields, locking, resubmission, and audit. Browser fixtures use synthetic records through
the production parsers. They verify register/history, named custody payloads, retained deletion
failure, reporting hierarchy/search/collapse, staffing edits, creation context, completion payloads,
failed certificate edits, CME targets, appraisal review, incident time/people/investigation, and
390-pixel page containment. Evidence is in `evidence/restoration-a`.

The final local gate passed 416 frontend tests, including the production build, and 720 backend
tests. Changed frontend files pass lint. Backend lint, formatting, types, and dependency checks
pass. The populated browser verifier passes after waiting for the navigation pill to settle.
See `PORTAL_RESTORATION_A_COMPLETION.md` for the execution environment and evidence limits.

These tests do not prove every backend transaction against PostgreSQL or every role-specific
historical layout. E and F own those remaining checks. No live resources, credentials, real records,
or preserved volumes changed. The required GitHub result travels in the next part's handoff.
