# Part 10A dependency inventory

## Scope and method

This inventory reconciles the Phase 0 catalogues with the repository at commit
`40a3548b598651b57c7db28ddd08fd2e4565dc93`. It covers every attendance, shift, roster,
biometric, staffing, employee, payroll, task, notification, dashboard, report, and export path.
The migration application must not call Supabase for any item assigned to Parts 10B through 10I.

## Legacy modules and callers

| ID | Source | Contract or caller | Owner and disposition |
| --- | --- | --- | --- |
| `ATT-JS-01` | `src/utils/attendanceStorage.js` | `getAttendanceSettings`, `saveAttendanceSettings` | 10B replaces both; freeze legacy reads and writes after configuration cutover. |
| `ATT-JS-02` | `src/utils/attendanceStorage.js` | `getShifts`, `saveShift`, `deleteShift` | 10B replaces the administrator catalogue and safe staff projection; freeze writers after 10B. |
| `ATT-JS-03` | `src/utils/attendanceStorage.js` | `getShiftForEmployee`, `assignShift` | 10B replaces both with effective-dated, nonoverlapping history. |
| `ATT-JS-04` | `src/utils/attendanceStorage.js` | `getClockEvents`, `recordClockEvent`, `recordManualClockEvent` | 10C replaces event reads and append-only manual writes. |
| `ATT-JS-05` | `src/utils/attendanceStorage.js` | `getAttendanceRecords`, `upsertAttendanceRecord`, `computeAndSaveAttendance` | 10D replaces browser calculation and record persistence. |
| `ATT-JS-06` | `src/utils/attendanceStorage.js` | `getAttendancePeriod`, `getAttendancePeriods`, `closeAttendancePeriod` | 10F replaces the non-atomic close and period reads. |
| `ATT-JS-07` | `src/utils/attendanceStorage.js` | `getRegularisationRequests`, submit, approve, reject, and audit helpers | 10E replaces exception workflows and unchecked audit inserts. |
| `ATT-JS-08` | `src/utils/attendanceStorage.js` | `getAttendancePayrollData` | 10F replaces it with the Phase 9 closed projection. |
| `ATT-JS-09` | `src/utils/attendanceStorage.js` | `getOvertimeFromRoster` | 10H replaces it with the published roster projection. |
| `ATT-JS-10` | `src/utils/attendanceStorage.js` | Roster list, save, delete, and publish helpers | 10G owns drafts; 10H owns publication and actual-hours evidence. |
| `ATT-JS-11` | `src/utils/attendanceStorage.js` | Swap list, decision, personal roster, colleague, and request helpers | 10H owns personal schedules and colleague selection; 10I owns swap commands. |
| `ATT-JS-12` | `src/utils/attendanceEngine.js` | Status, expected-hours, overtime, absence, consecutive-absence, payroll-summary, and working-day calculations | 10A fixes the rules; 10D ports daily calculation; 10F owns closed aggregation. Browser use becomes display-only. |
| `ATT-JS-13` | `src/utils/biometricStorage.js` | Mapping CRUD, CSV parsing, minute deduplication, and bulk event inserts | 10C replaces database access and server-validates bounded normalized rows. Local parsing may remain presentation-only. |
| `ATT-JS-14` | `src/utils/staffingStorage.js` | Staffing-rule CRUD | Phase 7 is authoritative. 10G consumes its FastAPI projection and never writes these rules. |
| `ATT-UI-01` | `src/components/AttendanceManager.jsx` | Settings, shifts, manual events, calculation, exception decisions, close, reports, and export | 10B through 10F replace the matching tabs. Phase 12 owns reports and CSV output. |
| `ATT-UI-02` | `src/components/BiometricImport.jsx` | Mapping editor, CSV preview, and import result | 10C replaces it. No device polling or vendor call is retained. |
| `ATT-UI-03` | `src/components/RosterManager.jsx` | Shift templates, drafts, leave conflicts, staffing, overrides, publication, export, and swap decisions | 10B, 10G, 10H, and 10I replace runtime paths. Phase 12 owns export and notifications. |
| `ATT-UI-04` | `src/components/employee/EmpAttendance.jsx` | Personal calculated records, raw-event fallback, and regularisation RPC | 10D owns reads and 10E owns requests. The direct Supabase fallback is frozen with 10D. |
| `ATT-UI-05` | `src/components/employee/EmpSchedule.jsx` | Published schedule, colleague list, and swap request | 10H owns reads and 10I owns requests. |
| `ATT-UI-06` | `src/components/employee/EmpHome.jsx` | Personal today summary | 10D consumes the personal attendance projection. |
| `ATT-UI-07` | `src/components/EmployeeModal.jsx` | Active shift catalogue | 10B supplies the safe active-shift projection; assignment writes stay in the migration controls. |
| `ATT-UI-08` | `src/components/ClinicalDashboard.jsx` | Attendance, roster coverage, and staffing gaps | Phase 12 replaces the dashboard consumer after 10D and 10H expose source projections. |
| `ATT-UI-09` | `src/components/Reports.jsx` | Attendance and roster reports and exports | Phase 12 owns replacement. It may consume only named Phase 10 projections. |
| `ATT-UI-10` | `src/components/PayrollEditor.jsx` | Browser attendance summary and roster overtime | Frozen by Phase 9E. Phase 9 consumes only the internal 10F and 10H projections. |
| `ATT-UI-11` | `src/components/DepartmentManager.jsx` | Staffing-rule administration | Completed Phase 7 migration boundary; 10G reads it. |
| `ATT-UI-12` | `src/components/NotificationBell.jsx` and shells | Roster and attendance notifications | Phase 12 owns producers and presentation. Phase 10 writes no notification row. |
| `ATT-UI-13` | `src/components/TasksPanel.jsx` | Pending regularisation and swap task aggregation | Phase 12 owns replacement. Phase 10 supplies safe workflow projections only. |

## Tables, functions, and external boundaries

| ID | Dependency | Current issue | Owner and disposition |
| --- | --- | --- | --- |
| `ATT-DB-01` | `attendance_settings` | Branch-scoped row and secret exist; bounds and day partition are incomplete. | 10B amends constraints and owns service access. |
| `ATT-DB-02` | `shifts` | Catalogue exists; retained-use editing rules are not encoded. | 10B adds validation and guarded service behavior. |
| `ATT-DB-03` | `shift_assignments` | No overlap constraint or mutable-row timestamp exists. | 10B adds both and owns effective-date precedence. |
| `ATT-DB-04` | `clock_events` | Method set excludes legacy `BIOMETRIC_API`; durable import identity and fingerprint are absent. | 10C normalizes the legacy name to `BIOMETRIC` and adds append-only provenance. |
| `ATT-DB-05` | `biometric_mappings` | Mapping rows exist without batch provenance. | 10C retains the table and adds only required ingestion entities. |
| `ATT-DB-06` | `attendance_records` | Derived rows lack a source snapshot, version, correction version, and closed snapshot identity. | 10D through 10F add versioned derivation and closure. |
| `ATT-DB-07` | `regularisation_requests` | Workflow state exists, but correction evidence and concurrent decision version are incomplete. | 10E adds required evidence and locking fields. |
| `ATT-DB-08` | `attendance_periods` | Close state exists without durable source version or amendment history. | 10F adds immutable close versions and append-only amendments. |
| `ATT-DB-09` | `attendance_audit_log` | Legacy domain audit exists; action constraints and structured source identity are incomplete. | 10E and 10F append exact actions. General audit remains protected. |
| `ATT-DB-10` | `roster_assignments` | Row publication boolean cannot represent a month publication or immutable version. | 10G keeps draft rows; 10H adds a month publication entity and version membership. |
| `ATT-DB-11` | `shift_swap_requests` | Protected approval exists, but it does not update a publication source version. | 10I replaces the function under the approved version contract. |
| `ATT-DB-12` | `department_staffing_rules` | Phase 7 source is effective-dated and branch-scoped. | Read-only 10G input. |
| `ATT-DB-13` | `leave_requests`, `public_holidays`, leave settings | Phase 8 owns approved leave, holidays, and Ramadan dates. | Read-only 10D, 10G, and 10H inputs. |
| `ATT-DB-14` | Employees, salary, employment, department, and branch settings | Phase 7 owns eligibility, scope, salary, and feature flags. | Read-only Phase 10 inputs. |
| `ATT-DB-15` | `compliance_overrides` | Existing `roster_publish` type can retain immutable exceptions. | 10G uses it through a narrowed roster rule-code contract. |
| `ATT-RPC-01` | `employee_submit_regularisation` | Browser-facing Supabase RPC. | 10E replaces it with FastAPI and freezes the caller. |
| `ATT-RPC-02` | `employee_record_clock_event` | Legacy self-clock RPC has ambiguous ownership. | Removed from migration scope; no portal clock command is allowed. |
| `ATT-RPC-03` | `employee_get_my_roster` | Legacy RPC has a direct-query fallback with different semantics. | 10H replaces both paths with one FastAPI projection. |
| `ATT-RPC-04` | `employee_get_colleagues` | Legacy selector is broader than a swap needs. | 10H replaces it with an eligible same-branch selector. |
| `ATT-RPC-05` | `employee_request_shift_swap` | Legacy request RPC. | 10I replaces it. |
| `ATT-RPC-06` | `admin_execute_shift_swap` | Retained and hardened, but publication versioning is absent. | Retain behind the runtime role until 10I replaces its exact definition. |
| `ATT-EXT-01` | Biometric CSV bytes | Local synthetic input only; no archive or external vendor is authorized. | 10C accepts bounded request bytes. Phase 11 owns common production storage. |
| `ATT-EXT-02` | Payroll attendance projection | Phase 9E currently fails closed. | 10F implements the internal repository projection. |
| `ATT-EXT-03` | Payroll roster projection | Phase 9E currently fails closed. | 10H implements the internal repository projection. |
| `ATT-EXT-04` | Reports, CSV, PDF, dashboard, tasks, and notifications | Later consumers are still legacy. | Phase 12 owns replacement; Phase 10 exposes safe source reads only. |
| `ATT-EXT-05` | Supabase client and final legacy removal | Required only by retained legacy screens. | Phase 13 removes it after every cutover. |

## Freeze order

The eight cutover units are configuration; event ingestion; attendance calculation; exceptions;
period close and projection; roster drafting; roster publication and projection; and shift swaps.
Each unit freezes the matching legacy writer before enabling its migration writer. Rollback reverses
that order. A legacy fallback never runs inside a migration flow, and no unit permits dual writes.
