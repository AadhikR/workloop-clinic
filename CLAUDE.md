# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Development
npm run dev          # Start Vite dev server (localhost:5173)
npm run build        # Standard Vite build
npm run build:dist   # Single-file bundle for offline distribution (vite.singlefile.config.js + fix-dist.js)
npm run lint         # ESLint
npm run preview      # Preview the production build
```

No test suite exists in this project.

## Environment

Create `sif-app/.env` with:
```
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

## Architecture

**Workloop** is a UAE HR/payroll SaaS. It generates **SIF files** (Salary Information File — UAE WPS/MOL bank format) and manages employees, payroll, leave, and attendance. There are two completely separate UIs sharing one Supabase project.

### Dual-portal structure

| Portal | Entry point | Who uses it |
|--------|-------------|-------------|
| Admin (HR) | `App.jsx` → `AppShell` | Company owner/HR; `profile.role === 'admin'` |
| Employee self-service | `App.jsx` → `EmployeeShell` | Linked employees; `profile.role === 'employee'` |

`App.jsx` renders either `AppShell` or `EmployeeShell` based on `profile.role` from `AuthContext`. Both shells use a fixed floating sidebar island (solid `#08122e`, `border-radius: 22px`, `top/left/bottom: var(--sidebar-gap)`) with an animated sliding pill for the active nav item driven by `useLayoutEffect` + `getBoundingClientRect`.

### Auth flow

`AuthContext.jsx` manages four auth actions:

- **`createCompany`** — Admin sign-up; detects existing accounts via `identities.length === 0` (Supabase silently returns the existing user on duplicate sign-up).
- **`signInAsAdmin`** — Verifies a `companies` row exists (via RLS); writes `user_profiles`.
- **`signUpAsEmployee`** — Employee first-time registration; calls `link_employee_account()` RPC to match `auth.email()` → `employees.work_email`, then upserts `user_profiles`.
- **`signInAsEmployee`** — Checks for existing `user_profiles` row first (idempotent re-login); falls back to `link_employee_account()` only on first login.

### Data layer

All DB access goes through utility modules — components never call `supabase` directly except for RPCs and auth operations in `AuthContext`.

| File | Scope |
|------|-------|
| `utils/storage.js` | Admin CRUD: companies, employees, payroll runs/entries, payslip record creation |
| `utils/profileStorage.js` | Role resolution (`user_profiles`), employee self-service data (own record, own payslips, own company) |
| `utils/leaveStorage.js` | Leave types, requests, balances, public holidays |
| `utils/attendanceStorage.js` | Attendance records, clock events, shifts, regularisation |

**Shape converters**: `storage.js` has `dbToXxx` / `xxxToDb` functions that translate between snake_case DB columns and camelCase JS objects. All components consume camelCase objects.

**Column repurpose**: `payroll_entries.du_cost` stores `leaveDeduction` (per-employee leave deduction in a payroll run) — there was no schema migration; this column was repurposed in-place.

### Supabase schema (key tables)

- `companies` — one row per admin user (`user_id = auth.uid()`)
- `employees` — all employees for a company; `auth_user_id` set when employee links their account; `user_id` = the admin's UUID
- `user_profiles` — `role` ('admin'|'employee'), `company_user_id`, `employee_id`; RLS restricts each user to their own row
- `payroll_runs` + `payroll_entries` — payroll run header + one row per employee
- `payslips` — snapshot of each employee's pay per period; created when admin downloads SIF (`createPayslipRecords`)
- `leave_types`, `leave_requests`, `leave_balances`, `public_holidays`
- `clock_events` — raw clock-in/out events; `user_id` = admin's UUID (even for self-service entries via RPC)
- `attendance_records` — derived daily record; unique on `(user_id, employee_id, date)`
- `employee_job_history` — audit log of salary/title/department/status changes; written on every employee save

### RLS model

**Admin tables** (`companies`, `employees`, `payroll_*`, `payslips`, `leave_*`, `clock_events`, `attendance_records`, `employee_job_history`) are scoped `user_id = auth.uid()` for admin reads/writes.

**Employee self-service** crosses the RLS boundary via `SECURITY DEFINER` RPCs and dedicated SELECT policies:

| Table | Employee policy |
|-------|----------------|
| `employees` | `auth_user_id = auth.uid()` |
| `payslips` | `employee_id` matched via linked employee |
| `leave_requests`, `leave_balances` | `employee_id` matched via linked employee |
| `clock_events` | `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())` |
| `attendance_records` | same pattern as clock_events |
| `employee_job_history` | INSERT `WITH CHECK (user_id = auth.uid())` |

### Employee self-service RPCs (SECURITY DEFINER)

These must exist in Supabase. All look up the caller's employee via `employees.auth_user_id = auth.uid()`.

| RPC | What it does |
|-----|-------------|
| `link_employee_account()` | Links employee email → auth user on first login |
| `employee_submit_leave_request(...)` | Validates + inserts leave request |
| `employee_cancel_leave_request(p_request_id)` | Cancels a pending request |
| `employee_record_clock_event(p_event_type, p_notes)` | Inserts clock event with admin's `user_id`; upserts `attendance_records` with computed hours |
| `employee_submit_regularisation(...)` | Submits an attendance correction request |

All RPCs require `GRANT EXECUTE ON FUNCTION <name> TO authenticated`.

### Key behavioral patterns

**Payroll locking**: `payroll_runs.status === 'generated'` → `isLocked = true` in `PayrollEditor`. All salary inputs, deduction fields, and action buttons are disabled. The lock banner is shown and the Submit/Save buttons are hidden.

**Soft-delete employees**: `archiveEmployee()` in `storage.js` sets `active = false, employment_status = 'Terminated'` — never hard-deletes.

**Auto job history**: `handleSaveEmployee` in `EmployeeManager` diffs `basicSalary`, `jobTitle`, `department`, `employmentStatus` before and after save, then calls `addJobHistoryEntry` for each changed field. This is wrapped in its own `try/catch` so a missing RLS policy silently warns instead of blocking the save.

**Leave balance fallback**: `EmpLeave` and `EmpHome` compute balances locally when the DB `leave_balances` table is empty (admin never opened the Leave module). Falls back first to DB leave types, then to `DEFAULT_LEAVE_TYPES` from `leaveEngine.js`. `calculateAnnualLeaveAccrual` from `leaveEngine.js` computes accrued days from hire date.

**Attendance clock optimistic update**: `EmpAttendance.clock()` applies a local state update *before* awaiting the RPC, so the Clock Out button enables immediately after Clock In. State is reverted only if both the RPC and the direct-insert fallback fail.

### Business logic utilities

- **`utils/sifGenerator.js`** — Generates the UAE WPS SIF file format (SCR header + EDR per employee). Amounts are integer AED (not fils). Filename format: `{MOL_ID}{YYMMDD}{seq}.sif`.
- **`utils/payslipGenerator.js`** — jsPDF payslip PDF. `generatePayslipPDF` is async (loads company logo). Always call `downloadPayslip(company, emp, run, entry)` from components, not `generatePayslipPDF` directly.
- **`utils/leaveEngine.js`** — UAE Federal Labour Law No. 33 of 2021 leave rules. Exports `DEFAULT_LEAVE_TYPES` (seed data), `calculateAnnualLeaveAccrual`, `countLeaveDays`, `validateLeaveRequest`.
- **`utils/gratuityCalculator.js`** — End-of-service gratuity per UAE law.
- **`utils/attendanceEngine.js`** — `ATTENDANCE_STATUS`, `STATUS_LABELS`, `STATUS_COLORS` constants + `deriveAttendanceStatus`.
- **`utils/uaeValidators.js`** — UAE-specific field validation (IBAN, Emirates ID, MOL ID) + formatters.

### Styling

Single CSS file: `src/index.css`. Solid-colour design system (glass/blur was removed):
- Body background: `#EEF2F7` with subtle blue/cyan radial gradients
- Cards/modals: `#ffffff`; form inputs: `#f8fafc`; table headers: `#e2e8f0`
- Sidebars: solid `#08122e` (no backdrop-filter)
- `--primary: #2563EB`, `--accent: #06B6D4`
- `--sidebar-gap: 12px` controls the floating island spacing on all sides
- Nav pill: `linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)` with spring animation (`cubic-bezier(0.34, 1.3, 0.64, 1)`)

Admin shell uses `.page-header` / `.page-body` / `.card` classes. Employee portal uses `.emp-page-header` / `.emp-page-body` / `.emp-card` parallels.
