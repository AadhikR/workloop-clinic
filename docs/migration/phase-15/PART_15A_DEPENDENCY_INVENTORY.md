# Part 15A dependency inventory

## Scope

This inventory records the portal baseline at commit
`628aa5b6a75243fd049163b19b46a821904abdb3`. The machine source is
`docs/migration/phase-15/integration-catalogue.json`. Each row has one later-part owner. The machine
record carries the full current-state text, action, evidence classes, and evidence targets.

Part 15A does not claim that a browser component grants access. The role column for a client states
which portal may call it. FastAPI still decides whether a particular request is allowed.

## Portal inventory

| ID | Item | Action | Owner |
| --- | --- | --- | --- |
| `P15-SHL-001` | Authenticated application shell | replace architecture proof | 15B |
| `P15-SHL-002` | Browser route table and role home selection | replace architecture proof | 15B |
| `P15-SHL-003` | OIDC bootstrap, callback, renewal, expiry, and logout | retain protected contract | 15B |
| `P15-SHL-004` | Server-derived account and role | retain protected contract | 15B |
| `P15-SHL-005` | Company and branch context | route existing view | 15B |
| `P15-SHL-006` | Role-specific navigation and unavailable states | replace architecture proof | 15B |
| `P15-SHL-007` | Notifications and task centre | route existing view | 15B |
| `P15-SHL-008` | Dashboard entry and safe error presentation | route existing view | 15B |
| `P15-SHL-009` | Architecture storage proof controls | deny unavailable gap | 15B |
| `P15-ADM-001` | Organization and branch administration | route existing view | 15C |
| `P15-ADM-002` | Departments and staffing rules | route existing view | 15C |
| `P15-ADM-003` | Employee administration and lifecycle | route existing view | 15C |
| `P15-ADM-004` | Leave configuration, balances, requests, and approvals | route existing view | 15C |
| `P15-ADM-005` | Attendance setup and ingestion | route existing view | 15C |
| `P15-ADM-006` | Attendance calculation, exceptions, audit, and period close | route existing view | 15C |
| `P15-ADM-007` | Roster drafting, validation, publication, actual hours, and swaps | route existing view | 15C |
| `P15-ADM-008` | Payroll, payslip administration, WPS, SIF, and Nafis | route existing view | 15C |
| `P15-ADM-009` | Expenses and advances administration | route existing view | 15C |
| `P15-ADM-010` | Documents, insurance, contracts, and offboarding | route existing view | 15C |
| `P15-ADM-011` | Assets, training, certifications, CME, appraisals, and incidents | route existing view | 15C |
| `P15-ADM-012` | Reports, exports, downloads, notifications, tasks, and dashboards | route existing view | 15C |
| `P15-MGR-001` | Manager home, notifications, tasks, and self dashboard | route existing view | 15D |
| `P15-MGR-002` | Own profile and direct-report directory | route existing view | 15D |
| `P15-MGR-003` | Leave self-service and direct-report approvals | route existing view | 15D |
| `P15-MGR-004` | Personal attendance and schedule | route existing view | 15D |
| `P15-MGR-005` | Expense review and personal expense submission | route existing view | 15D |
| `P15-MGR-006` | Direct-report appraisals, training, and certifications | route existing view | 15D |
| `P15-MGR-007` | Manager-unavailable administrator operations | deny unavailable gap | 15D |
| `P15-EMP-001` | Employee home, notifications, tasks, and self dashboard | route existing view | 15E |
| `P15-EMP-002` | Profile and contact self-service | route existing view | 15E |
| `P15-EMP-003` | Leave balances, requests, cancellation, calendar, and attachments | route existing view | 15E |
| `P15-EMP-004` | Attendance correction and history | route existing view | 15E |
| `P15-EMP-005` | Schedule, colleagues, and shift swaps | route existing view | 15E |
| `P15-EMP-006` | Payslips, expenses, and advances | route existing view | 15E |
| `P15-EMP-007` | Documents, insurance, assets, training, certifications, and CME | route existing view | 15E |
| `P15-EMP-008` | Appraisals and letter requests | route existing view | 15E |
| `P15-FIL-001` | Leave attachment upload and download | retain protected contract | 15F |
| `P15-FIL-002` | Employee document upload, verification, download, and delete | retain protected contract | 15F |
| `P15-FIL-003` | Expense receipt upload and download | retain protected contract | 15F |
| `P15-FIL-004` | Training and certification evidence | retain protected contract | 15F |
| `P15-FIL-005` | CSV, SIF, report, payslip, letter, settlement, and ZIP delivery | retain protected contract | 15F |
| `P15-FIL-006` | Cross-role and cross-branch file denial | prove integrated behavior | 15F |
| `P15-VAL-001` | Cross-role product journey and denial matrix | prove integrated behavior | 15F |
| `P15-VAL-002` | Keyboard, focus, landmarks, names, status, contrast, and reduced-motion proof | prove integrated behavior | 15F |
| `P15-VAL-003` | Local production-build and route performance budget | prove integrated behavior | 15F |
| `P15-VAL-004` | Reviewed DigitalOcean portal promotion | promote reviewed release | 15G |
| `P15-VAL-005` | Synthetic live role, file, denial, and log acceptance | promote reviewed release | 15G |
| `P15-VAL-006` | Integrated portal recovery, rollback, and restart acceptance | promote reviewed release | 15G |
| `P15-VAL-007` | Live DigitalOcean performance acceptance | promote reviewed release | 15G |
| `P15-VAL-008` | Independent inventory and golden-case trace | review independently | 15H |
| `P15-VAL-009` | Schema, security, credential, data, provider, and preserved-resource boundary | review independently | 15H |
| `P15-VAL-010` | Whole Phase 15 completion and owner signoff | review independently | 15H |

## Client and backend contract inventory

The marker column lists the existing path families that the client source contains. It is an
allowlist for integration, not permission to synthesize another path under the same prefix.

| ID | Client | Roles | Existing path markers | Owner |
| --- | --- | --- | --- | --- |
| `P15-API-001` | `src/organizationApi.js` | admin, manager, employee | company, employer, branches | 15B |
| `P15-API-002` | `src/sampleApi.js` | admin, manager, employee | public status, account, architecture proof | 15B |
| `P15-API-003` | `src/notificationApi.js` | admin, manager, employee | notifications | 15B |
| `P15-API-004` | `src/taskApi.js` | admin, manager, employee | tasks | 15B |
| `P15-API-005` | `src/dashboardApi.js` | admin, manager, employee | dashboards | 15B |
| `P15-API-006` | `src/departmentApi.js` | admin | departments, staffing rules | 15C |
| `P15-API-007` | `src/employeeApi.js` | admin, manager, employee | employees, imports, job history | 15C |
| `P15-API-008` | `src/leaveConfigurationApi.js` | admin | settings, types, holidays | 15C |
| `P15-API-009` | `src/leaveBalanceApi.js` | admin, manager, employee | balances, calendars | 15C |
| `P15-API-010` | `src/leaveRequestApi.js` | admin, manager, employee | requests | 15C |
| `P15-API-011` | `src/leaveApprovalApi.js` | admin, manager | approvals, delegations | 15C |
| `P15-API-012` | `src/leaveAttachmentApi.js` | admin, manager, employee | attachment submissions, attachments | 15C |
| `P15-API-013` | `src/attendanceConfigurationApi.js` | admin | settings, shifts, assignments | 15C |
| `P15-API-014` | `src/attendanceIngestionApi.js` | admin | clock events, mappings, imports | 15C |
| `P15-API-015` | `src/attendanceCalculationApi.js` | admin, manager, employee | records, self, calculations | 15C |
| `P15-API-016` | `src/attendanceExceptionsApi.js` | admin, manager, employee | regularisations, audit | 15C |
| `P15-API-017` | `src/attendancePeriodsApi.js` | admin | periods | 15C |
| `P15-API-018` | `src/rosterApi.js` | admin, manager, employee | months, schedules | 15C |
| `P15-API-019` | `src/shiftSwapApi.js` | admin, manager, employee | shift swaps | 15C |
| `P15-API-020` | `src/payrollApi.js` | admin, employee | payroll runs, self payslips | 15C |
| `P15-API-021` | `src/wpsNafisApi.js` | admin | payroll WPS and SIF, Nafis | 15C |
| `P15-API-022` | `src/expenseApi.js` | admin, manager, employee | expenses and receipts | 15C |
| `P15-API-023` | `src/advanceApi.js` | admin, manager, employee | advances | 15C |
| `P15-API-024` | `src/recordsBenefitsApi.js` | admin, manager, employee | documents, insurance, contracts | 15C |
| `P15-API-025` | `src/developmentAssetsApi.js` | admin, manager, employee | assets, training, certifications, CME | 15C |
| `P15-API-026` | `src/appraisalsIncidentsApi.js` | admin, manager, employee | appraisal cycles, appraisals, incidents | 15C |
| `P15-API-027` | `src/letterRequestsApi.js` | admin, manager, employee | requests | 15C |
| `P15-API-028` | `src/offboardingApi.js` | admin | offboarding | 15C |
| `P15-API-029` | `src/reportApi.js` | admin | reports | 15C |
| `P15-API-030` | `src/outputApi.js` | admin | exports | 15C |
| `P15-API-031` | `src/renderedOutputApi.js` | admin, employee | reports, payslips, requests, offboarding | 15C |

Every client record also names its current backend source in the machine catalogue. Part 15A found
no portal need for a new backend route. Dynamic identifiers and commands remain constrained by each
client's current functions and the backend operation.

## Browser route inventory

| ID | Path | Allowed role | Result | Owner |
| --- | --- | --- | --- | --- |
| `P15-ROUTE-001` | `/` | public or signed in | sign-in state or role home redirect | 15B |
| `P15-ROUTE-002` | `/oidc/callback` | public callback | consume once, clear state, select role home | 15B |
| `P15-ROUTE-003` | `/forbidden` | signed in | safe role denial | 15B |
| `P15-ROUTE-004` | `/unavailable` | signed in | safe unsupported-capability result | 15B |
| `P15-ROUTE-005` | `/admin` | admin | home, notifications, tasks, dashboards | 15C |
| `P15-ROUTE-006` | `/admin/organization` | admin | company, branches, departments, staffing | 15C |
| `P15-ROUTE-007` | `/admin/people` | admin | directory, lifecycle, history, CSV, portal roles | 15C |
| `P15-ROUTE-008` | `/admin/leave` | admin | configuration, balances, requests, approvals | 15C |
| `P15-ROUTE-009` | `/admin/attendance` | admin | setup, ingestion, calculation, exceptions, close | 15C |
| `P15-ROUTE-010` | `/admin/roster` | admin | roster and shift swaps | 15C |
| `P15-ROUTE-011` | `/admin/payroll` | admin | payroll, expenses, advances, WPS, SIF, Nafis | 15C |
| `P15-ROUTE-012` | `/admin/records` | admin | documents, insurance, contracts, letters, offboarding | 15C |
| `P15-ROUTE-013` | `/admin/development` | admin | assets, training, certification, CME, appraisal, incidents | 15C |
| `P15-ROUTE-014` | `/admin/reports` | admin | reports and authorized output | 15C |
| `P15-ROUTE-015` | `/manager` | manager | home, notifications, tasks, dashboard | 15D |
| `P15-ROUTE-016` | `/manager/team` | manager | own profile and direct reports | 15D |
| `P15-ROUTE-017` | `/manager/leave` | manager | self leave and approval queue | 15D |
| `P15-ROUTE-018` | `/manager/time` | manager | attendance, schedule, colleagues, swaps | 15D |
| `P15-ROUTE-019` | `/manager/expenses` | manager | self claims and manager decisions | 15D |
| `P15-ROUTE-020` | `/manager/development` | manager | self and direct-report development and appraisal | 15D |
| `P15-ROUTE-021` | `/manager/requests` | manager | supported self advances, records, benefits, letters | 15D |
| `P15-ROUTE-022` | `/employee` | employee | home, notifications, tasks, dashboard | 15E |
| `P15-ROUTE-023` | `/employee/profile` | employee | profile and contact fields | 15E |
| `P15-ROUTE-024` | `/employee/leave` | employee | balances, calendar, requests, attachments | 15E |
| `P15-ROUTE-025` | `/employee/time` | employee | attendance, schedule, colleagues, swaps | 15E |
| `P15-ROUTE-026` | `/employee/pay` | employee | payslips, expenses, receipts, advances | 15E |
| `P15-ROUTE-027` | `/employee/records` | employee | documents, insurance, assigned assets | 15E |
| `P15-ROUTE-028` | `/employee/development` | employee | training, certifications, CME, appraisal | 15E |
| `P15-ROUTE-029` | `/employee/requests` | employee | letter and custom requests | 15E |

## File-flow inventory

| ID | Flow | Roles | Contract | Owner |
| --- | --- | --- | --- | --- |
| `P15-FLOW-001` | Leave attachments | admin, manager, employee | protected intent, upload, download, scan state, exact cleanup | 15F |
| `P15-FLOW-002` | Employee documents | admin, manager, employee | protected intent, upload, verify or reject, download, delete | 15F |
| `P15-FLOW-003` | Expense receipts | admin, manager, employee | protected intent, upload, authorized review download | 15F |
| `P15-FLOW-004` | Training and certification evidence | admin, manager, employee | protected upload, download, delete with self or report scope | 15F |
| `P15-FLOW-005` | CSV and SIF output | admin | backend-produced bytes and authorized download | 15F |
| `P15-FLOW-006` | PDF, letter, settlement, and ZIP output | admin, employee | backend-produced bytes, save or open, revoke object URL | 15F |

## Test coverage baseline

The baseline has 62 Node test files under `tests`, 76 backend test files under `backend/tests`, and
the synthetic browser verifier at `scripts/verify-phase-13f-browser.mjs`. The Phase 14H closing gate
ran 358 Node tests and 704 backend tests. It also ran the locked frontend build, full migration and
database controls, restart persistence, three role journeys, file journeys, exact cleanup, and safe
log checks.

The present unit coverage is strongest at the client and API boundary. It covers authentication,
HTTP behavior, organization, employees, leave, attendance, roster, payroll, expenses, advances,
records, development, requests, notifications, tasks, dashboards, reports, output, workflow routing,
and earlier phase contracts. The browser verifier covers the current one-page integration. It does
not prove the 29 portal routes, route focus, unavailable states, route transfer budgets, or live
portal performance. Those gaps belong to 15B through 15G.

## Known gaps

| ID | Gap | Disposition | Owner |
| --- | --- | --- | --- |
| `P15-GAP-001` | No portal router, role home, or route-level denial state | Build the shared shell from the server-derived account | 15B |
| `P15-GAP-002` | Administrator views are one long document | Place existing views in the approved administrator routes | 15C |
| `P15-GAP-003` | Manager views mix self-service with administrator omissions | Expose existing manager and self contracts; deny unsupported operations | 15D |
| `P15-GAP-004` | Employee views have no dedicated navigation | Expose only existing self-service contracts | 15E |
| `P15-GAP-005` | No route-oriented product, denial, accessibility, or performance gate | Add the local integrated acceptance gate | 15F |
| `P15-GAP-006` | DigitalOcean still serves the architecture proof | Promote one reviewed portal release manually | 15G |
| `P15-GAP-007` | No live portal recovery or performance acceptance | Run live restart, rollback, recovery, and performance proof | 15G |
| `P15-GAP-008` | No independent Phase 15 trace or verdict | Trace the full catalogue and request phase signoff | 15H |

## Schema and deployment boundary

Alembic remains at one head, `e8a1c3f5b7d9`, with the Phase 14 indexed digest unchanged. Part 15A
adds no schema, RLS, grant, protected function, Keycloak state, credential, runtime setting, or live
mutation.

DigitalOcean is the only provider. Preserve `workloop-clinic-dev`, `fra1-default`, the Phase 13
external archive, and `workloop-clinic_postgres_data`. Automatic deployment stays off. The default
App Platform address remains the only public address. Later live proof uses synthetic data and the
existing USD 15 cap.
