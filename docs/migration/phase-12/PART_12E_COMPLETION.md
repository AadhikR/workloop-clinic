# Part 12E completion

Status: complete. The local gate and routed GitHub gate passed.

## Result

Part 12E adds the administrator-only `GET /api/v1/reports/{report_id}` route and the migration
report screen for the thirteen approved reports: headcount, payroll cost, leave utilization,
attendance summary, overtime, document expiry, salary movement, turnover, staffing compliance,
WPS compliance, Emiratization, EOS liability, and leave balance.

Each report reads the authoritative Phase 7 through Phase 11 source named by the Phase 12 contract.
The service applies company and selected-branch scope before reading, resolves employee and
department selectors inside that scope, rejects unknown filters, and limits inclusive date ranges to
366 days. Responses contain canonical columns, rows, full-filter totals, `asOf`, a stable source
version, and an encrypted cursor bound to the user, role, scope, report, filters, source version,
offset, and expiry. Decimal amounts are fixed-scale strings. Pagination cannot change the reported
totals.

The implementation keeps source-specific rules intact: payroll includes only generated and approved
runs and non-excluded entries; leave includes only final approved requests; staffing separates a
measured shortfall from its stored override; WPS and Nafis retain their source states; EOS uses
settlement policy `1.0.0` and returns an explicit unavailable reason instead of inventing a value;
and leave balance uses persisted balances. Reports are read-only, and a required-source failure
returns a safe HTTP 503 without partial results.

No schema revision was required. Alembic head remains `c3e5a7b9d1f6`.

## Gate evidence

- All 651 backend tests passed. Complete Ruff lint and formatting, strict Pyright, and the locked
  dependency check passed. The six focused report API and service tests cover role and branch scope,
  filter rejection, selector resolution, cursor binding, full-filter totals, EOS availability, and
  safe source failure.
- All 275 frontend unit tests passed. Focused ESLint passed for the changed migration files. Four
  report client tests cover the fixed catalogue, exact response parsing, scoped requests, and the
  absence of legacy or Supabase imports. The legacy and migration production builds passed; the
  existing migration chunk-size warning is unchanged.
- `scripts/verify-phase-12e-boundary.py` passed and confirms the fixed report catalogue,
  authoritative source predicates, read-only repository, encrypted pagination, and migration-only
  screen wiring.
- `scripts/verify-phase-12e-database.py` passed against a fresh PostgreSQL environment after Alembic
  head was applied twice. It prepared all thirteen report statements, exercised empty scoped reads,
  rejected out-of-scope selectors, and confirmed the source-table counts did not change.
- The fresh local full-stack gate passed backend health, the two migration applications, the
  boundary verifier, and the database no-write verifier.
- Code commits are `26145703e2c90cc661e2c0e7b301ed42e352ded0` and
  `fb96f7404d3f1330a1afb6392f56ec40ab30de30`. The first routed run passed frontend regression but
  exposed strict Linux type findings. The follow-up corrected those findings, repeated the complete
  backend gate, and passed routed Migration foundation run
  [36140072750](https://github.com/AadhikR/workloop-clinic/actions/runs/36140072750). Its classifier
  selected backend quality; frontend regression and full-stack smoke were skipped because the
  follow-up changed only backend type annotations and test typing.

## Resource boundary

Verification used synthetic records and disposable local PostgreSQL environments. The
`workloop-phase12e-dev`, `workloop-phase12e-gate`, and `workloop-phase12e-gate2` containers,
networks, and volumes were removed after verification. The protected
`workloop-clinic_postgres_data` volume was not attached, modified, deleted, or recreated.

No production provider, credential, cloud resource, paid service, production data, real employee
record, patient record, payroll record, or banking record was used.

## Rollback and remaining legacy boundary

Rollback removes the migration report screen from the organization shell and disables the Part 12E
route before restoring legacy report reads and browser calculations. Part 12E writes no source data,
so rollback must not change payroll, leave, attendance, roster, document, Nafis, settlement, or
employee records.

`src/components/Reports.jsx`, `src/utils/reportUtils.js`, and their broad legacy reads remain only
as the Phase 13 rollback boundary. Browser CSV, SIF, and PDF generation also remain disabled in the
migration report path.

After this documentation-only follow-up passes and the branch is clean and synchronized, Part 12F
starts automatically in a new Codex task in the same saved project and local checkout. Part 12F owns
deterministic CSV and SIF bytes, preview parity, delivery headers, protected output audit, and the
migration download controls. PDF and ZIP output remain in Part 12G.
