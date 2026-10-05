# Portal UI and UX restoration review

## Reference and cause

The design reference is commit `a3b72a22924d1b56b5603ee8e0069ddecee65f43`. Its frontend tree matches
the final historical reference identified by the parity specification in `docs/history/legacy-feature-list`.

The previous restoration commit, `9f58cf4`, copied some visual tokens and recreated three financial
modules. It did not reproduce the populated payroll review workflow. Shared classes for form grids,
KPI labels and values, badges, and alerts were missing. Older generic rules also changed restored
controls. The payroll table had 14 headings and 15 cells per employee, which shifted every column
after Other Pay. The browser check rendered an unavailable payroll list and missed these defects.

## Implemented design decisions

| Area | Correction | Current service constraint |
| --- | --- | --- |
| Shared controls | Restore historical type, form grids, KPI values, status pills, semantic alerts, button variants, and keyboard focus in a scoped stylesheet | Existing service clients and role checks remain the source of data and permissions |
| Payroll review | Compact three-column metadata, Employees/Gross Earnings/Total Deductions/Net Payroll summaries, aligned salary table, employee search and status filters, validation review, and employee breakdown drawer | Salary snapshots and leave deductions are read-only. Editable variable pay has a separate column. Unsupported historical bank metadata and local payslip generation are omitted |
| Payroll changes | Show unsaved changes, prevent refresh or approval from ignoring edits, confirm discard, and normalize money before saving | Saving still submits the current preview, version, branch, and idempotency contract |
| Payroll validation | Translate readiness and negative-net codes into readable issues, deduplicate readiness messages, and link to the relevant module | Server validation still blocks approval. The UI does not override it |
| Employee directory | Employee table with named status, action toolbar, and create/import dialogs | Creation, imports, exports, and lifecycle actions use existing clients |
| Leave | Request dialog, separate Requests/Balances/Calendar views, named employees and leave types, separate approvals and settings | Request validation, attachment staging, and approval remain server operations |
| Attendance and roster | Separate records, entry, corrections, periods, settings, and shift-swap views | Tab names reflect the operations supported by current components |
| Records and benefits | Separate Documents/Insurance/Contracts tabs and a named employee selector | Employee choices come from the branch directory |
| Training and offboarding | Replace typed employee identifiers with authorized employee choices | Managers only receive their direct reports |
| Mobile | Contain wide payroll tables inside their card, collapse metadata fields, keep summaries readable, and prevent the administrator navigation pill from spanning every item | Administrator navigation stays accessible above the workspace. Employee and manager bottom navigation remains in place |

Visited module panels stay mounted when a user changes tabs, so tab switches preserve form drafts.
Dialogs support Escape, contain keyboard focus, lock background scrolling, and return focus to their
opening control. The active navigation pill is measured again after organization context finishes loading.

## Verification scope

The populated payroll fixture passes through the production response parsers. The browser verifier
checks table cell alignment, metadata layout, typography, readable issues, page containment,
employee search, filters, exclusions, recalculated totals, normalized save payloads, dirty-state
guards, validation, the breakdown drawer, mobile table scrolling, and adjustment-dialog containment.
The leave fixture checks request dialogs, calendar and balance views, settings separation, and retained
panel state. Existing manager and employee layout checks remain in the same verifier.

Evidence lives in `evidence/phase15g-payroll-review-desktop-final.png`,
`evidence/phase15g-payroll-review-mobile-viewport.png`, `evidence/phase15g-payroll-breakdown.png`, and
`evidence/phase15g-leave-workspace.png`.

These checks prove the changed workflows. They do not certify every historical module, every populated
state, or exact image equality across the whole application. Existing modules still need individual
comparisons for their dense detail views and dialogs. The original catalogue remains the route and
interaction inventory, not a claim of completed visual parity.

## Final restoration decisions in F

The final 46-view audit and focused A through F interaction proofs are in `evidence/restoration-f`.
`PORTAL_RESTORATION_PROGRESS.md` records each inherited dependency's current result.
`PORTAL_RESTORATION_F_WORKING_RECORD.md` records the complete bounded implementation decisions.

Administrator home now shows warning groups, the conditional setup checklist, five summary cards,
optional Nafis compliance, payroll trend, and recent runs. All aggregates use scoped server data.
Date, headcount, or run-count disagreement shows an unavailable state. Staff home restores today's
read-only status, two summary cards, optional expiry warnings, assets, and recent leave.

Insurance and contract editors use typed fields, current protected snapshots, and confirmation
dialogs. Failed identical retries retain their input and idempotency key. Contract printing uses
server-rendered PDF bytes and audit. Document rejection and removal retain a failed reason and reset
when the selected employee changes.

Administrator and manager appraisal review save all five canonical sections atomically. Archival
retains eligible appraisal, incident, and expense source rows. Pending advance cancellation retains
financial history. Complete pagination precedes every collection total. Clinical counts and details
share the same credential and published-roster predicates.

The audit contains populated desktop, light mobile, dark mobile, empty, loading, denied, and
unavailable captures. Focused interaction proofs add failed save, conflict, confirmation, retry,
and keyboard behavior. This evidence proves the restored supported workflows. It does not require
pixel equality or reinstate biometric controls, unaudited hard deletion, or browser-generated output.
