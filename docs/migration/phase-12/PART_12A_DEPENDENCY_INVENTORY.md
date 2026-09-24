# Part 12A dependency inventory

## Scope and counting rule

This catalogue covers the remaining notification, task, dashboard, report, expiry, CSV, PDF, ZIP,
SIF, letter, print, preview, and download boundary. A row represents one migration dependency, not
one source line. Each row has one implementation owner. Indirect callers are separate when they
control authorization, source selection, or output delivery.

Phase 12 reads the authoritative APIs and immutable snapshots from Phases 7 through 11. It does not
rebuild source-domain state, repair old rows, or write back a calculated value. Phase 13 owns the
removal of the retained legacy modules after all Phase 12 cutovers pass.

## Notifications and expiry

| ID | Legacy or current dependency | Contract risk | Owner |
| --- | --- | --- | --- |
| `P12-NOT-01` | `src/components/NotificationBell.jsx` | Polls list and count separately, treats read errors as empty state, and routes by legacy entity labels. | 12B |
| `P12-NOT-02` | `getNotifications` and `getUnreadCount` in `src/utils/notificationStorage.js` | Direct Supabase reads have no stable cursor and can disagree between calls. | 12B |
| `P12-NOT-03` | `markNotificationRead` and `markAllNotificationsRead` | Browser timestamps and direct updates bypass the HTTP error and audit contract. | 12B |
| `P12-NOT-04` | `createNotification` and `createNotifications` | Caller supplies recipient, text, entity type, and entity ID. The migration build must use allowlisted producers. | 12B |
| `P12-NOT-05` | `generateExpiryNotifications` | Browser time, browser-loaded rows, and Dashboard visits decide production. | 12B |
| `P12-NOT-06` | Employee document, visa, passport, Emirates ID, labour card, and clinical licence expiry sources | Thresholds differ by source and must use a trusted Dubai business date. | 12B |
| `P12-NOT-07` | Certification, employee insurance, and policy renewal sources | Legacy logic accepts owner-wide inputs and repairs branch scope in memory. | 12B |
| `P12-NOT-08` | Probation and limited-contract expiry sources | The source is Phase 7 employee state. Notification production cannot mutate employment or contract state. | 12B |
| `P12-NOT-09` | Leave decision, payslip issue, and roster publication producers | Existing `create_workflow_notification(text,text)` already derives recipient and content for approved types. | 12B |
| `P12-NOT-10` | `notifications` table, recipient RLS, unread index, and five-part dedup key | Human reads stay recipient-only and branch-aware. Producers cannot gain general table insert rights. | 12B |
| `P12-NOT-11` | `workloop_expiry_processing` login and source-column grants | Explicit execution must preserve the fixed actor, company, branch, business date, and audit label. | 12B |
| `P12-NOT-12` | Expiry policies in `e96f7a1b4c53`, `0a18c3d6e75f`, and `2c4d6e8f0a1b` | The eight approved types and source-linked insert policy are the security baseline. | 12B |
| `P12-NOT-13` | Admin, manager, and employee shells | All three embed the bell. A role-specific shell is not an authorization check. | 12B |
| `P12-NOT-14` | Supabase event dispatch and 60-second polling | Migration refresh may use explicit invalidation or bounded polling. Supabase Realtime removal belongs to Phase 13. | 13 |

## Task aggregation

| ID | Legacy or current dependency | Contract risk | Owner |
| --- | --- | --- | --- |
| `P12-TSK-01` | `src/components/TasksPanel.jsx` | Shared renderer trusts missing categories and role strings supplied by its caller. | 12C |
| `P12-TSK-02` | `getAdminTasks` in `src/utils/taskStorage.js` | Two nested `Promise.allSettled` groups silently remove failed categories. | 12C |
| `P12-TSK-03` | Admin leave, expense, advance, request, document, certification, regularisation, swap, and payroll approval queries | Stale columns and mixed statuses make partial success look complete. | 12C |
| `P12-TSK-04` | Admin employee identity and profile expiry checks | Legacy code receives employee rows from the caller and calculates expiry locally. | 12C |
| `P12-TSK-05` | Admin certification expiry query | It reads expiry rows directly and joins employee names through PostgREST. | 12C |
| `P12-TSK-06` | Admin employment-contract expiry query | Phase 11 contract history is authoritative. The task service may only summarize it. | 12C |
| `P12-TSK-07` | Admin offboarding checklist and nested task query | Phase 11 checklist state and incomplete tasks remain authoritative. | 12C |
| `P12-TSK-08` | Admin appraisal query | Phase 11 appraisal status is authoritative and must stay branch-scoped. | 12C |
| `P12-TSK-09` | `getManagerTasks` | Manager aggregation mixes two RPCs and direct tables without a completeness signal. | 12C |
| `P12-TSK-10` | `manager_get_leave_queue` | Replace with the Phase 8 direct-report or delegated approval projection. | 12C |
| `P12-TSK-11` | `manager_get_expense_queue` | Replace with the Phase 9 manager queue projection. | 12C |
| `P12-TSK-12` | Manager appraisals and certifications | Replace with Phase 11 direct-report projections. | 12C |
| `P12-TSK-13` | `getEmployeeTasks` employee lookup by Supabase auth ID | Keycloak identity mapping and self scope come from the application principal. | 12C |
| `P12-TSK-14` | Employee certification, document, leave, advance, expense, request, and missing-clock-out queries | Replace with self projections from Phases 8 through 11. | 12C |
| `P12-TSK-15` | `daysUntil`, urgency, labels, category names, and navigation entities | Freeze business-date rules and return stable machine codes separate from display text. | 12C |
| `P12-TSK-16` | Task response shape | Every requested category must return `ok`, `empty`, or `failed`; omission is forbidden. | 12C |
| `P12-TSK-17` | Direct Supabase queries and RPCs in `taskStorage.js` | Freeze at cutover, retain for rollback, then remove with the rest of Supabase. | 13 |

## Dashboards

| ID | Legacy or current dependency | Contract risk | Owner |
| --- | --- | --- | --- |
| `P12-DSH-01` | `src/components/Dashboard.jsx` load orchestration | Eight owner-wide requests, two follow-up requests, and swallowed errors produce an inconsistent snapshot. | 12D |
| `P12-DSH-02` | Admin setup, headcount, payroll, pending letter, and pending appraisal cards | Counts must come from one branch-scoped server snapshot with an `asOf` value. | 12D |
| `P12-DSH-03` | Payroll trend and recent-run calculations | Use finalized Phase 9 money and ordering, not `payrollCalculator.js`. | 12D |
| `P12-DSH-04` | WPS deadline card | Use trusted Dubai business date, company salary day, and Phase 9 WPS state. | 12D |
| `P12-DSH-05` | Emiratization and Nafis card | Use the Phase 9 stored Nafis snapshot. The browser does not reinterpret quota policy. | 12D |
| `P12-DSH-06` | Probation, contract, document, certification, licence, and insurance cards | Share the Phase 12 expiry policy and authoritative Phase 7 and 11 source projections. | 12D |
| `P12-DSH-07` | `src/components/ClinicalDashboard.jsx` load orchestration | Owner-wide reads and in-memory employee filters are not authorization. | 12D |
| `P12-DSH-08` | Clinical credential compliance and expiry pipeline | Phase 11 verified-document projections determine status. Rejected or quarantined evidence is excluded. | 12D |
| `P12-DSH-09` | Roster coverage, on-duty, leave, attendance, and staffing gap cards | Use published Phase 10 roster, calculated attendance, approved leave, and staffing validation. | 12D |
| `P12-DSH-10` | Joiner, birthday, probation, and department cards | Use Phase 7 employee and department projections with a trusted date. | 12D |
| `P12-DSH-11` | `src/components/employee/EmpHome.jsx` | Self summary must use self projections for leave, latest payslip, today's attendance, and current assets. | 12D |
| `P12-DSH-12` | Legacy dashboard storage modules and local calculators | Freeze after migration dashboard cutover and remove only with Supabase promotion. | 13 |

## Reports

| ID | Legacy or current dependency | Contract risk | Owner |
| --- | --- | --- | --- |
| `P12-RPT-01` | `src/components/Reports.jsx` and `src/utils/reportUtils.js` | Thirteen tabs fetch broad data and calculate rows in the browser. | 12E |
| `P12-RPT-02` | Headcount report | Phase 7 active employee projection supplies department, nationality, contract type, gender, and status. | 12E |
| `P12-RPT-03` | Payroll cost report | Phase 9 finalized runs and immutable entries supply exact decimal totals. | 12E |
| `P12-RPT-04` | Leave utilization report | Phase 8 approved requests supply counted days and leave types. | 12E |
| `P12-RPT-05` | Attendance summary report | Phase 10 calculated records supply the selected closed or open period. | 12E |
| `P12-RPT-06` | Overtime report | Phase 10 approved overtime amount and duration are authoritative. | 12E |
| `P12-RPT-07` | Document expiry report | Phase 7 identity dates and Phase 11 verified documents share the Phase 12 expiry policy. | 12E |
| `P12-RPT-08` | Salary movement report | Phase 7 job-history events supply old and new salary values and effective dates. | 12E |
| `P12-RPT-09` | Staff turnover report | Phase 7 employment start and termination dates supply joiners, leavers, and tenure. | 12E |
| `P12-RPT-10` | Staffing compliance report | Phase 10 published roster and validation results supply shortages and overrides. | 12E |
| `P12-RPT-11` | WPS compliance report | Phase 9 WPS run and entry state is authoritative. | 12E |
| `P12-RPT-12` | Emiratization report | Phase 9 Nafis snapshot is authoritative for a branch and period. | 12E |
| `P12-RPT-13` | EOS liability report | Phase 11 settlement policy and preview source replace `gratuityCalculator.js`; unsupported employees return an explicit reason. | 12E |
| `P12-RPT-14` | Leave balance report | Phase 8 persisted balances are authoritative. The report does not recalculate accrual. | 12E |
| `P12-RPT-15` | Expense, advance, asset, training, certification, incident, request, and appraisal report assignments | Add only reports named by the Phase 12 plan. Do not invent cross-domain analytics. | 12E |
| `P12-RPT-16` | Report filters and ordering | Server validates branch, date range, period, status, employee, department, format, limit, and cursor. | 12E |
| `P12-RPT-17` | Report response envelope | Return report ID, source version, `asOf`, canonical columns, rows, totals, and pagination metadata. | 12E |
| `P12-RPT-18` | Owner-wide legacy source calls followed by browser filtering | This behavior is denied in the migration build. | 12E |
| `P12-RPT-19` | Legacy report screen and calculation utilities | Freeze after report cutover and remove during migration-build promotion. | 13 |

## Generated files, previews, print, and downloads

| ID | Legacy or current dependency | Contract risk | Owner |
| --- | --- | --- | --- |
| `P12-OUT-01` | `exportCSV` in `src/utils/reportUtils.js` | PapaParse, browser object URLs, and caller-provided filenames do not provide deterministic delivery headers. | 12F |
| `P12-OUT-02` | Employee export and import template in `src/components/EmployeeManager.jsx` | CSV quoting, encoding, field order, and filename must be fixed. | 12F |
| `P12-OUT-03` | Leave balance export in `src/components/LeaveManager.jsx` | It uses browser-loaded balances and ad hoc CSV quoting. | 12F |
| `P12-OUT-04` | Attendance export in `src/components/AttendanceManager.jsx` | It emits LF rows from browser calculations. | 12F |
| `P12-OUT-05` | Roster export in `src/components/RosterManager.jsx` | It emits a UTF-8 BOM and CRLF from browser draft or publication state. | 12F |
| `P12-OUT-06` | Nafis CSV in `src/components/NafisReportModal.jsx` | Use the locked Phase 9 snapshot, fixed columns, and canonical filename. | 12F |
| `P12-OUT-07` | `generateSIF`, `generateCorrectedSIF`, `generateSIFFilename`, and `parseSIFPreview` in `src/utils/sifGenerator.js` | Server owns EDR and SCR bytes, ordering, integer-AED rounding, filename, and preview derivation. | 12F |
| `P12-OUT-08` | SIF download and corrected download in `src/components/PayrollEditor.jsx` | Browser-generated octet streams can diverge from the approved Phase 9 SIF input. | 12F |
| `P12-OUT-09` | SIF filename display in `src/components/PayrollList.jsx` and preview in `src/components/SIFPreviewModal.jsx` | Preview and final bytes must share one server renderer and source digest. | 12F |
| `P12-OUT-10` | `exportPDF` in `src/utils/reportUtils.js` | Generic jsPDF tables lose type information and are not byte-stable. | 12G |
| `P12-OUT-11` | `generatePayslipPDF`, single download, and bulk ZIP in `src/utils/payslipGenerator.js` | Browser recalculates immutable payroll amounts and ZIP metadata varies by run. | 12G |
| `P12-OUT-12` | Employee payslip download in `src/components/employee/EmpPayslips.jsx` | It must render only the caller's authorized immutable Phase 9 payslip snapshot. | 12G |
| `P12-OUT-13` | `src/utils/letterTemplates.js`, `src/utils/safePrint.js`, `src/components/LetterRequestsManager.jsx`, and `src/components/employee/EmpRequests.jsx` | Browser HTML uses wall-clock dates and references, then opens an unsupervised print window. | 12G |
| `P12-OUT-14` | Letter-request `print-source` projection | Phase 11 supplies completed request facts. Phase 12 renders bytes without changing request state. | 12G |
| `P12-OUT-15` | Offboarding NOC and experience letter print in `src/components/OffboardingModal.jsx` | Phase 11 `letter-source` is authoritative. | 12G |
| `P12-OUT-16` | Final settlement print in `src/components/EndOfServiceScreen.jsx` | Render the persisted Phase 11 settlement. Never rerun the legacy gratuity calculator. | 12G |
| `P12-OUT-17` | Employee detail print in `src/components/EmployeeModal.jsx` and leave calendar `window.print()` | Replace with named, authorized print projections or leave out if no approved business output exists. | 12G |
| `P12-OUT-18` | Browser generators, object URLs, and print helpers after cutover | Retain only for rollback until the complete migration build is promoted. | 13 |

## Database and security objects

| ID | Object | Contract conclusion | Owner |
| --- | --- | --- | --- |
| `P12-DB-01` | `notifications` | Existing columns, five-part dedup key, unread index, and recipient FKs support 12B. | 12B |
| `P12-DB-02` | Notification recipient SELECT and `read_at` UPDATE policies | Reuse without widening. Admin still needs a verified branch context. | 12B |
| `P12-DB-03` | `create_workflow_notification(text,text)` | Reuse for leave decision, payslip issue, and roster publication only. | 12B |
| `P12-DB-04` | `workloop_expiry_processing` | Reuse as an explicit command login. Do not add a scheduler or share the credential with the web service. | 12B |
| `P12-DB-05` | Expiry source RLS and column grants | Existing employee, document, insurance, policy, certification, profile, account, company, and branch reads cover the eight approved sources. | 12B |
| `P12-DB-06` | Expiry notification INSERT policy and audit linkage | Reuse threshold-specific source checks and matching `expiry_notification_created` audit rows. | 12B |
| `P12-DB-07` | `audit_events` and `append_audit_event` | Current allowlists do not admit Phase 12 output-generation actions. Add a separate fixed-purpose writer. | 12G |
| `P12-DB-08` | Domain tables and source projections from Phases 7 through 11 | Reports, tasks, dashboards, and outputs receive read-only projections. No broad cross-table grant is added. | 12E |
| `P12-DB-09` | Output artifact persistence | No output-blob table is approved. Generate on demand, stream, audit metadata, and discard bytes. | 12G |

## Indirect callers and operational boundaries

| ID | Dependency | Contract conclusion | Owner |
| --- | --- | --- | --- |
| `P12-IND-01` | `src/App.jsx`, `ManagerShell.jsx`, and `EmployeeShell.jsx` | Navigation exposes Phase 12 screens but cannot grant authority. | 12D |
| `P12-IND-02` | `migration/src/http.js` | Reuse bearer token, request ID, problem response, and no-store conventions. | 12B |
| `P12-IND-03` | Existing migration API clients | Reuse validated query encoding and camelCase response conventions. | 12C |
| `P12-IND-04` | `CompanyContext` selected branch | Admin routes require a verified branch. Manager and employee routes derive branch from the principal. | 12D |
| `P12-IND-05` | API request logging | Log route, result, request ID, actor ID, and safe codes. Never log report rows or output bytes. | 12G |
| `P12-IND-06` | Existing middleware size and rate limits | Add tighter output concurrency and response-size limits without weakening global controls. | 12G |
| `P12-IND-07` | Phase 12 cutover records | Each consumer names one read authority, one output authority, the frozen path, and reverse rollback step. | 12G |
| `P12-IND-08` | Final Supabase removal and migration-build promotion | Phase 12 proves its boundary but does not remove the legacy client or promote the build. | 13 |

## Upstream assignment trace

Each row below appears once. The target catalogue IDs above provide the detailed implementation
owner. Combined assignments stay combined only when the upstream document described one shared
consumer.

| Upstream assignment | Source | Phase 12 disposition |
| --- | --- | --- |
| `P0-NOTIFICATION-BELL` | Phase 0 feature matrix, Notification bell | 12B notification API and presentation |
| `P0-GENERATED-NOTIFICATIONS` | Phase 0 feature matrix, Generated notifications | 12B allowlisted producers |
| `P0-TASK-CENTER` | Phase 0 feature matrix, Task center | 12C role-specific aggregation |
| `P0-ADMIN-DASHBOARD` | Phase 0 feature matrix, Dashboard | 12D admin projection |
| `P0-CLINICAL-DASHBOARD` | Phase 0 feature matrix, Clinical dashboard | 12D clinical projection |
| `P0-REPORTS-EXPORTS` | Phase 0 feature matrix, Reports and exports | 12E reports, 12F CSV/SIF, 12G PDF |
| `P0-PAYSLIP-FILE` | Phase 0 file contract, Payslip | 12G PDF and ZIP |
| `P0-SIF-FILE` | Phase 0 file contract, SIF | 12F preview and bytes |
| `P0-REPORT-FILES` | Phase 0 file contract, Reports | 12F CSV and 12G PDF |
| `P0-TASK-ACCEPTANCE` | Phase 0 acceptance rule 7 | 12C complete-category proof |
| `phase8a-admin-leave-screen` | Phase 8 inventory | 12F leave-balance CSV only; Phase 8 owns the workflow |
| `phase8a-notification-producer` | Phase 8 inventory | 12B leave decision notification |
| `phase8a-balance-csv` | Phase 8 inventory | 12F CSV |
| `phase8a-notifications` | Phase 8 inventory | 12B delivery and inbox |
| `phase8a-tasks` | Phase 8 inventory | 12C aggregation |
| `phase8a-dashboards-reports` | Phase 8 inventory | 12D and 12E consumers, 12F and 12G bytes |
| `UI-01` | Phase 9 inventory | 12F SIF and 12G payslip controls only |
| `UI-09` | Phase 9 inventory | 12G self payslip PDF |
| `UI-10` | Phase 9 inventory | 12F SIF preview and corrected bytes |
| `UI-11` | Phase 9 inventory | 12F Nafis CSV |
| `UI-12` | Phase 9 inventory | 12D payroll summary |
| `UI-13` | Phase 9 inventory | 12E financial reports, 12F and 12G output |
| `UI-16` | Phase 9 inventory | 12C finance tasks |
| `JS-15` | Phase 9 inventory | 12F SIF renderer |
| `JS-17` | Phase 9 inventory | 12G payslip renderer |
| `JS-18` | Phase 9 inventory | 12E report rows, 12F and 12G output |
| `JS-19` | Phase 9 inventory | 12C task service |
| `JS-20` | Phase 9 inventory | 12B notifications |
| `EXT-04` | Phase 9 inventory | 12G payslip PDF and ZIP |
| `EXT-05` | Phase 9 inventory | 12F SIF bytes |
| `EXT-06` | Phase 9 inventory | 12E report data, 12F and 12G formats |
| `EXT-07` | Phase 9 inventory | 12C task aggregation |
| `EXT-08` | Phase 9 inventory | 12B workflow notifications |
| `ATT-UI-01` | Phase 10 inventory | 12E attendance report and 12F CSV |
| `ATT-UI-03` | Phase 10 inventory | 12F roster CSV and 12B publication notification |
| `ATT-UI-08` | Phase 10 inventory | 12D clinical dashboard |
| `ATT-UI-09` | Phase 10 inventory | 12E attendance and roster reports |
| `ATT-UI-12` | Phase 10 inventory | 12B roster and attendance notifications |
| `ATT-UI-13` | Phase 10 inventory | 12C regularisation and swap tasks |
| `ATT-EXT-04` | Phase 10 inventory | 12B through 12G shared consumer boundary |
| `P11-INS-02` | Phase 11 inventory | 12B policy renewal notification |
| `P11-AST-03` | Phase 11 inventory | 12D self asset summary |
| `P11-REQ-02` | Phase 11 inventory | 12G employee completed-letter output |
| `P11-REQ-03` | Phase 11 inventory | 12G administrator letter output |
| `P11-REQ-04` | Phase 11 inventory | 12G renderer and print delivery |
| `P11-OFF-02` | Phase 11 inventory | 12G NOC and experience letter |
| `P11-OFF-03` | Phase 11 inventory | 12G settlement print |
| `P11-OFF-05` | Phase 11 inventory | 12E EOS liability report |
| `P11-LTR-01` | Phase 11 inventory | 12D named dashboard projections |
| `P11-LTR-02` | Phase 11 inventory | 12C task aggregation |
| `P11-LTR-03` | Phase 11 inventory | 12B producers and presentation |
| `P11-LTR-04` | Phase 11 inventory | 12E reports, 12F CSV, and 12G rendered output |

## Rollback order

Rollback freezes new output generation first, then restores browser delivery in this order: 12G
rendered outputs and ZIP, 12F CSV and SIF, 12E reports, 12D dashboards, 12C tasks, and 12B
notifications. Preserve notification rows, read timestamps, audit events, source snapshots, and every
domain row. Do not restore a legacy writer while its migration writer remains enabled. Phase 13 may
remove the preserved modules only after the complete migration build passes.
