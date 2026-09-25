# Part 12D completion

Status: complete. The local gate and routed GitHub gate passed.

## Result

Part 12D adds `GET /api/v1/dashboards/admin`, `GET /api/v1/dashboards/clinical`, and
`GET /api/v1/dashboards/self`, with corresponding migration dashboard screens. Each response is one
internally consistent PostgreSQL statement snapshot with `asOf`, the trusted business date, a stable
`sourceVersion`, fixed cards, and server-owned drill codes. The routes reject unknown query
parameters and return no unrestricted source rows.

The admin dashboard derives active headcount, the latest finalized and approved payroll totals,
same-run WPS status, the latest stored Nafis ratio, and exact Part 12B expiry actions from the Phase
7 through Phase 9 authorities. Payroll amounts use fixed two-decimal strings. Company and branch
scope is applied before aggregation.

The clinical dashboard uses only the current published Phase 10 roster, its validated publication
state, current calculated attendance, and Phase 11 credential evidence that is verified and eligible
for download. Draft roster rows and rejected or unavailable credential files cannot contribute.

The self dashboard derives employee scope from the authenticated principal. It reads the employee's
current status, persisted leave balance, latest immutable payslip net amount, current calculated
attendance, current assets, and current published shift. It does not accept an employee ID.

Every dashboard is read-only. A required source failure returns a safe HTTP 503 without a partial
dashboard. No schema revision was needed: each dashboard repository query is one PostgreSQL
statement, and the existing Phase 7 through Phase 11 tables and projections are already the
authoritative sources. Alembic head remains `c3e5a7b9d1f6`.

## Gate evidence

- All 645 backend tests passed. Complete Ruff lint and formatting passed. Strict Pyright checks
  passed for every changed Python file, and the locked environment reported no broken requirements.
- All 271 frontend tests passed. Focused ESLint for every changed migration file passed. The legacy
  and migration production builds passed. The existing migration chunk-size warning is unchanged.
- Sixteen focused backend service and HTTP tests cover the fixed card catalogues, source authority,
  role and branch scope, fixed decimals, exact expiry policy, published-roster isolation,
  download-eligible credential evidence, self derivation, stable source versions, and safe 503
  behavior.
- Three focused migration client tests cover strict response validation, approved role routing,
  shell wiring, bounded drill navigation, and absence of Supabase reads.
- `scripts/verify-phase-12d-boundary.py` passed and confirms fixed route and card definitions,
  principal-derived self scope, pre-aggregation company and branch filters, read-only handling, and
  migration-only dashboard wiring.
- `scripts/verify-phase-12d-database.py` passed against fresh PostgreSQL environments after Alembic
  head was applied twice. It confirmed dashboard reads do not change notification, payroll, roster,
  version, or document counts.
- Routed GitHub evidence: Migration foundation run
  [36133847956](https://github.com/AadhikR/workloop-clinic/actions/runs/36133847956) passed change
  classification, backend quality, frontend regression, and full-stack smoke for commit
  `713eadb23fa2525210b54d460064031f9fc5bdf7`.

## Resource boundary

Verification used synthetic records and disposable local PostgreSQL environments. The
`workloop-phase12d-dev` and `workloop-phase12d-gate` containers, networks, and volumes were removed
after their checks passed. The protected `workloop-clinic_postgres_data` volume was not attached,
modified, deleted, or recreated.

No production provider, credential, cloud resource, paid service, production data, real employee
record, patient record, payroll record, or banking record was used.

## Rollback and remaining legacy boundary

Rollback removes the migration dashboard screens from the shell and disables the three Part 12D
routes before restoring legacy dashboard reads and calculations. Part 12D writes no source-domain
data, so rollback must not mutate or remove source snapshots, notifications, audit rows, payroll
runs, roster publications, or document evidence.

`src/components/Dashboard.jsx`, `src/components/ClinicalDashboard.jsx`,
`src/components/employee/EmpHome.jsx`, and their retained storage and calculation dependencies
remain only as the Phase 13 rollback boundary. Phase 13 owns their removal with the rest of
Supabase.

After the documentation-only follow-up passes and the branch is clean and synchronized, Part 12E
starts automatically in a new Codex task in the same saved project and local checkout. Part 12E
implements approved JSON reports only; CSV, SIF, PDF, and other output work remain in Parts 12F and
12G.
