# Workloop — UAE Payroll & HRMS

A UAE-compliant HR and payroll web app built with React + Vite + Supabase. Started as a WPS/SIF payroll generator and extended into a full clinic / small-hospital HRMS (Workloop Clinic).

Three portals share one codebase:

- **Admin (HR)** — company owner or HR manager. Full data access.
- **Manager** — direct-report managers with a scoped view (their team's leave, expenses, appraisals, training, roster).
- **Employee** — self-service portal: profile, payslips, leave, attendance, advances, expenses, documents, training, appraisals, letter requests, tasks.

---

## Features

### Payroll
- Monthly payroll runs with bulk salary processing.
- Basic + housing + transport + configurable allowances per employee; itemised deductions.
- **WPS / SIF file generation** (MOHRE / Central Bank format) — CRLF line endings, integer AED, filename `{MOL_ID}{YYMMDD}{HHMMSS}.sif`.
- Multi-step approval: `draft → pending_approval → approved → generated`.
- PDF payslips per employee (jsPDF).
- One-click "Apply to Payroll" for advance repayments, approved expenses, and roster-calculated overtime.
- Compliance-override gate (with mandatory reason) if any employee has an expired professional licence, Emirates ID, or visa.

### Employees
- Full UAE profile: personal, job, salary, bank, UAE compliance (visa/passport/EID/labour card + expiries).
- Colour-coded document expiry badges (red / amber / green + 90-day amber for clinical credentials).
- Job history: append-only audit log of title, department, salary, and status changes.
- Multi-company / multi-branch — each admin can manage several `companies` rows.
- CSV bulk import with per-row IBAN / MOL ID format warnings surfaced in the import banner (non-fatal).

### Leave (UAE Labour Law Nos. 33/2021, MR 43/2022, Cabinet Res. 1/2022)
- Types seeded from law: Annual, Sick (tiered pay), Maternity, Paternity, Bereavement, Hajj, Study, Nursing, Unpaid.
- Probation-aware eligibility per type.
- Half-day requests, attachment upload, sick-leave tier calculator, encashment on offboarding.
- Multi-level approval: `Pending → ManagerApproved → Approved` (HR final).
- Overlap detection — an employee can't submit a request covering days that already fall inside a pending or approved request.
- Balance display rounded to whole days (accrual math stays exact under the hood).

### Attendance & Roster
- Employee clock-in / clock-out (SECURITY DEFINER RPC), late / grace-window aware.
- Manual clock-event entry for HR; regularisation requests with validation on approve (clock-out after clock-in, within 24 h, on the requested date).
- Shift templates and monthly duty roster grid, publish gate, shift-swap approvals.
- **Biometric CSV import** — upload device punches, map badge → employee, preview matched vs unmatched.
- Auto-calculated overtime from roster planned-vs-actual hours (Art. 19, 1.25× hourly).

### Expenses & Advances
- Employee submits expense claim (with receipt URL); manager pre-approval → HR approval → paid; approved-unpaid claims auto-surface in the next payroll's Reimbursements panel with a one-click Apply button.
- Advances: HR-created (starts `active`) or employee-requested (starts `pending`). Employees can withdraw their own pending requests. Approved advances show the "MMM YYYY → MMM YYYY" repayment window; monthly deduction auto-surfaces in payroll with a one-click Apply button.

### Documents & Letters
- Upload / verify: Visa, Passport, EID, Labour Card, Clinical (DHA / DOH / MOH / BLS / ACLS / PALS / NRP / CME), General.
- DHA / DOH / MOH licence uploads require a licence number (3–30 alphanumeric).
- Letter requests: Salary Certificate (bank / embassy / personal), NOC, Experience Letter, Employment Certificate, Salary Transfer. HR prepares; employee prints from the portal.

### Training & CME
- Admin, manager, and employee can all log training records with hours.
- `is_cme` flag on training records — surfaces as an "Is CME?" checkbox in EmpTraining / ManagerTraining forms and aggregates on the Clinical Dashboard.
- Certification self-service (BLS / ACLS / DHA licence renewals) starts as `pending_review`; HR verifies.
- Annual CME requirement targets per employee.

### Appraisals
- Cycle-based reviews; HR assigns staff, managers rate direct reports, calibration by HR.
- Manager sub-view toggle: "Team Appraisals" (interactive rating) vs "My Appraisals" (read-only).

### Emiratization / Nafis (2026 rules)
- Sector selector with pre-filled quota targets (Cabinet Resolution 27/2023).
- Tiered logic: **< 20 skilled staff** → "Nafis not mandatory" banner shown, quota alert suppressed. **20 – 49** in a priority sector → fixed minimum of 2 Emirati staff. **50+** → percentage-based target.
- Monthly fine: **AED 9,000 per unfilled Emirati slot** (updated 2026 rate).
- Feature can be turned off entirely in Company Settings for clinics where Nafis isn't in scope.

### Clinical Dashboard
- Live compliance: expiring visas / passports / EIDs / licences.
- Roster staffing gaps and licence status dots per row.
- Pending leave, incident reports, CME progress.

### Feature toggles (per company / branch)
Turn modules on / off in Company Settings → Modules & Features. All default **on** so existing installs behave the same:

| Toggle | What it hides when off |
|---|---|
| Emiratization / Nafis | Dashboard panel, quota alert, Reports tab |
| Roster Staffing Rules | DepartmentManager tab, RosterManager publish-gate override |
| Biometric Punch-In Import | Biometric Import tab under Attendance |

### Reports
Eight tabs: Payroll history, Leave, Attendance, Salary, Turnover, Nafis, Staffing, Certifications. All filterable by date range and department.

### Notifications
Dashboard bell with dedup on `(recipient, type, entity_id)`. Auto-generated for expiring visas / passports / EIDs / licences (30 / 14 d), insurance renewal (60 d), probation end, contract renewal, certification expiry.

### Cross-cutting validation
Every write path runs through `src/utils/uaeValidators.js`:

- IBAN (AE + 21 digits), Emirates ID (784-YYYY-XXXXXXX-X), MOL ID (10–15 digits).
- UAE phone (`+971` / `971` / `0` prefix + 9 digits), email (RFC-lite).
- Date range, past-date, future-date, amount with min / max ceiling, bank routing code (9 digits), rejection reason (≥ 10 chars, matches SIF override standard), UAE visa, passport, and a `clampNumber` for `onChange` clamping of bounded inputs.
- CSV import returns a per-row `errors[]` for admin review — bad IBAN / MOL rows still import but surface a warning.

---

## Tech Stack

- **Frontend**: React 19 + Vite
- **Database**: Supabase (Postgres + Row Level Security)
- **Auth**: Supabase Auth (email + password)
- **PDF**: jsPDF
- **CSV**: PapaParse
- **Icons**: Lucide React
- **Tests**: Playwright (E2E, headless Chromium)

---

## Setup

### 1. Install

```bash
npm install
```

### 2. Configure Supabase

Copy `.env.example` to `.env`:

```
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

### 3. Apply the database schema

In Supabase → SQL Editor, run every file in `sql/` in numerical order. The migrations are idempotent — safe to re-run on an existing database.

The most recent migrations you should not skip:

- `047_cme_tracking.sql` — `cme_requirements` table + `training_records.is_cme` flag.
- `048_incident_reports.sql` — clinical incident reporting.
- **`049_feature_toggles.sql`** — per-company `enable_nafis` / `enable_staffing_rules` / `enable_biometric_import` columns + `employee_cancel_advance(UUID)` RPC for the employee-side pending-advance withdrawal.
- **`050_advance_repayment_scheduling.sql`** — month-specific advance staging, repayment start month, and idempotent payroll repayment recording.
- **`051_employee_request_actions.sql`** — fixes employee pending-advance withdrawal and adds ownership-checked deletion for pending/rejected employee expense claims.

### 4. Create the storage bucket

In Supabase → Storage, create a **private** bucket named `employee-documents`. All document uploads (leave attachments, employee docs) go through it.

### 5. Run

```bash
npm run dev            # Vite dev server on http://localhost:5173
npm run build          # Standard production build
npm run build:dist     # Single self-contained HTML bundle (offline distribution)
npm run lint           # ESLint
npm test               # Full Playwright suite (headless, dev server auto-starts)
npm run test:ui        # Playwright UI mode for debugging
```

Run a single spec:

```bash
npx playwright test leave           # any spec name in tests/
npx playwright test employees
npx playwright test payroll
npx playwright test attendance
npx playwright test clinical-credentials
```

See `CLAUDE.md` → *Commands* for the full list of feature-specific spec commands.

---

## Documentation

- **[CLAUDE.md](CLAUDE.md)** — architecture, RLS model, migration notes, behavioural patterns, known bug patterns. Read this before writing code.
- **[CLAUDE_TESTING.md](CLAUDE_TESTING.md)** — Playwright test-writing patterns and selector gotchas.
- **[MANUAL_TEST_CHECKLIST.md](MANUAL_TEST_CHECKLIST.md)** — 13-day structured manual QA plan across all portals.
- **[FEATURES_ROADMAP.md](FEATURES_ROADMAP.md)** — original 22-feature roadmap.
- **[Workloop_Clinic_HRMS_Feature_List.pdf](Workloop_Clinic_HRMS_Feature_List.pdf)** — clinic extension features 1.1 – 7.2.

---

## UAE Compliance Notes

- **WPS (Wage Protection System)** — SIF files use CRLF line endings, integer AED amounts, and MOHRE-compliant EDR / SCR structure.
- **Gratuity** — Federal Decree-Law 33/2021: 21 days basic/year for years 1–5, 30 days/year thereafter, capped at 2 years of basic.
- **Article 56** — Salaries must be paid within 30 days of due date; Dashboard shows a Late warning if the previous month hasn't been generated.
- **Emiratization** — Cabinet Resolution 27/2023 + 2026 amendments (see Feature list above). Fine: AED 9,000 per unfilled skilled slot per month.
- **Emirates ID** — validated as `784-YYYY-XXXXXXX-X` (15 digits starting with 784).
- **IBAN** — validated as `AE` + 21 digits (23 chars total).
- **Bank routing code** — validated as 9 numeric digits (SCR line in SIF).
- **Nafis / Nafis wage** — from 1 Jan 2026 the minimum wage for UAE nationals is **AED 6,000/month**; Emiratis below that don't count toward quota. Existing employers had until 30 June 2026 to bring salaries in line.
- **Date display** — DD/MM/YYYY throughout via `formatDateUAE()`.
- **Currency** — AED with comma-separated thousands.
