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

`App.jsx` renders either `AppShell` or `EmployeeShell` based on `profile.role` from `AuthContext`. Both shells use a fixed floating sidebar island (dark navy, `rgba(8,18,46,0.92)`, `border-radius: 22px`, `top/left/bottom: var(--sidebar-gap)`) with an animated sliding pill for the active nav item driven by `useLayoutEffect` + `getBoundingClientRect`.

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
| `utils/attendanceStorage.js` | Attendance records |

**Shape converters**: `storage.js` has `dbToXxx` / `xxxToDb` functions that translate between snake_case DB columns and camelCase JS objects. All components consume camelCase objects.

**Column repurpose**: `payroll_entries.du_cost` stores `leaveDeduction` (per-employee leave deduction in a payroll run) — there was no schema migration; this column was repurposed in-place.

### Supabase schema (key tables)

- `companies` — one row per admin user (`user_id = auth.uid()`)
- `employees` — all employees for a company; `auth_user_id` set when employee links their account
- `user_profiles` — `role` ('admin'|'employee'), `company_user_id`, `employee_id`; RLS restricts each user to their own row
- `payroll_runs` + `payroll_entries` — payroll run header + one row per employee
- `payslips` — snapshot of each employee's pay per period; created when admin downloads SIF (`createPayslipRecords`)
- `leave_types`, `leave_requests`, `leave_balances`, `public_holidays`
- `attendance_records`
- `employee_job_history` — audit log of salary/title/department changes

**RLS**: All tables are scoped by `user_id = auth.uid()` for admin access. Employee self-service uses a `SECURITY DEFINER` RPC `link_employee_account()` to write across the RLS boundary, plus separate RLS policies on `employees` (`auth_user_id = auth.uid()`) and `payslips` (`employee_id = linked employee`).

### Business logic utilities

- **`utils/sifGenerator.js`** — Generates the UAE WPS SIF file format (SCR header + EDR per employee). Amounts are integer AED (not fils). Filename format: `{MOL_ID}{YYMMDD}{seq}.sif`.
- **`utils/payslipGenerator.js`** — jsPDF payslip PDF. `generatePayslipPDF(company, emp, run, entry)` returns a jsPDF doc; `downloadPayslip(...)` calls `.save()`. Always use `downloadPayslip` from components, not `generatePayslipPDF`.
- **`utils/leaveEngine.js`** — UAE Federal Labour Law No. 33 of 2021 leave rules: entitlement calculation, day counting (working vs calendar), validation with errors/warnings.
- **`utils/gratuityCalculator.js`** — End-of-service gratuity per UAE law.
- **`utils/attendanceEngine.js`** — Attendance status constants and computation.
- **`utils/uaeValidators.js`** — UAE-specific field validation + date/currency formatters.

### Styling

Single CSS file: `src/index.css`. Design system is Apple Glass morphism:
- Body background: `#EEF2F7` with subtle blue/cyan radial gradients
- `--glass-bg: rgba(241,245,249,0.62)` (slate-100 tinted, not pure white)
- `--glass-border: rgba(100,116,139,0.16)`
- `--primary: #2563EB`, `--accent: #06B6D4`
- Sidebar: `rgba(8,18,46,0.92)` + `backdrop-filter: saturate(160%) blur(40px)`
- `--sidebar-gap: 12px` controls the floating island spacing on all sides
- Nav pill: `linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)` with spring animation (`cubic-bezier(0.34, 1.3, 0.64, 1)`)

Admin shell uses `.page-header` / `.page-body` / `.card` classes. Employee portal uses `.emp-page-header` / `.emp-page-body` / `.emp-card` parallels.
