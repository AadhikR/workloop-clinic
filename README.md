# Workloop — UAE Payroll & HRMS

A lightweight, UAE-compliant HR and payroll web application built with React + Vite + Supabase.

---

## Features

### Payroll Module
- Monthly payroll runs with bulk salary processing for all active employees
- Basic salary + housing allowance + transport allowance + configurable allowances per employee
- Deductions management (loans, penalties, absences — itemised with labels)
- WPS / SIF file generation — produces a valid `.sif` file per the MOHRE/Central Bank spec
- PDF payslip generation per employee (jsPDF) — includes earnings breakdown, deductions, net pay
- Payroll history log with audit trail (who ran it, when, total disbursed)
- Auto-save on every change (800ms debounce)

### UAE WPS / SIF Compliance
- EDR (Employee Detail Record) + SCR (Salary Control Record) format
- MOL Employer ID, agent bank code, employee IBAN, salary month/year
- Basic pay + variable pay fields in integer AED
- Filename format: `{MOL_ID}{YYMMDD}{HHMMSS}.sif`
- MOHRE-compliant salary structure: basic + housing + transport = total package

### Employee Records Module
- Full UAE HR profile per employee
- Document expiry tracking: Visa, Passport, Emirates ID, Labour Card
- Colour-coded expiry warnings: red (< 30 days), amber (30–60 days), green (60–90 days)
- Job history log — timestamped audit trail of title/department/salary changes
- CSV import/export

### UAE-Specific Features
- Gratuity / EOSB accrual calculator (UAE Labour Law Art. 51):
  - < 1 year: no gratuity
  - 1–5 years: 21 days basic salary per year
  - > 5 years: 30 days per year beyond 5 (capped at 2 years total basic)
- End-of-service settlement screen: EOSB + pro-rata final salary + advance deductions
- WPS 30-day deadline tracker (UAE Labour Law Art. 56 compliance warning)
- Emirates ID validation (784-YYYY-XXXXXXX-X format)
- UAE IBAN validation (AE + 21 digits = 23 chars)
- Free Zone vs Mainland flag (per company and per employee)

### Settings / Company Profile
- Company name, MOL Employer ID, agent bank code
- Default salary payment day (for WPS deadline tracking)
- Company logo URL (for payslips)
- Free zone or mainland flag

---

## Tech Stack

- **Frontend**: React 19 + Vite
- **Database**: Supabase (PostgreSQL + Row Level Security)
- **Auth**: Supabase Auth
- **PDF**: jsPDF
- **CSV**: PapaParse
- **Icons**: Lucide React

---

## Setup

### 1. Clone and install

```bash
npm install
```

### 2. Configure Supabase

Copy `.env.example` to `.env` and fill in your Supabase project URL and anon key:

```
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

### 3. Run the database schema

In your Supabase project → SQL Editor → New Query, paste and run the contents of `supabase_schema.sql`.

This creates all tables with RLS policies and migration blocks (safe to run on existing databases).

### 4. Start development server

```bash
npm run dev
```

### 5. Build for production

```bash
npm run build
```

Or build as a single self-contained HTML file:

```bash
npm run build:dist
```

---

## Database Schema

| Table | Description |
|-------|-------------|
| `companies` | One row per user — MOL ID, bank routing, payroll settings |
| `employees` | Full UAE HR profile — personal, job, salary, compliance fields |
| `employee_job_history` | Immutable audit log of job/salary changes |
| `payroll_runs` | One row per payroll run — period, payment date, status, audit trail |
| `payroll_entries` | One row per employee per run — salary breakdown, allowances, deductions |

---

## UAE Compliance Notes

- **WPS (Wage Protection System)**: Salary files must be submitted via your bank's WPS portal. This app generates the `.sif` file in the correct format.
- **Gratuity**: Calculated per Federal Decree-Law No. 33 of 2021 (new UAE Labour Law). Both resignation and termination receive full gratuity after 1 year.
- **Article 56**: Employers must pay salaries within 30 days of the due date. The dashboard shows a warning if the previous month's payroll has not been processed.
- **Emirates ID**: Format validated as 784-YYYY-XXXXXXX-X (15 digits starting with 784).
- **IBAN**: Validated as AE + 21 digits (23 characters total).
- **Date display**: All dates shown in DD/MM/YYYY format (UAE standard).
- **Currency**: All amounts displayed as AED with comma-separated thousands.
