# Phase 4E synthetic fixture manifest

## Status

First increment landed on 2026-09-03: the identity and organization spine plus
the load-bearing golden financial cases, seeded and validated against the
migrated database. Status-coverage rows for every leave, attendance, document,
incident, appraisal, training, and asset state are the next increment, so this is
not yet the full one-to-one match of the Phase 0 catalogue that the 4E completion
gate needs.

The seed lives in `backend/app/db/seed/` and is the executable manifest itself:
`fixtures.py` holds every row with its deterministic id and complete values,
`constants.py` holds the fixed clock and the id rules, and `runner.py` applies,
validates, and cleans. It is not part of the Alembic upgrade path.

## Determinism

Every value is fixed. The seed never reads the machine clock and never generates
a random id, so a run on any machine produces byte-identical rows.

- Fixed clock: `2026-08-27` (`docs/migration/phase-0/SYNTHETIC_TEST_DATA.md`).
- Explicit ids: the tenant branch, identity, advance, and payroll-run ids Phase 0
  pins by hand.
- Derived ids: everything else uses `uuid5` over namespace
  `00000000-0000-5000-8000-000000000001` and the canonical name
  `workloop/<table>/<tenant>/<branch>/<actor>/<scenario>`.
- Identifiers: MOL id, IBAN, Emirates ID, visa, passport, labour card, and phone
  follow Phase 0's exact per-sequence formulas. Every value is fictional and
  fails a real-world lookup. H-DXB-002 (sequence 2) produces MOL
  `90000000000002`, IBAN `AE000000000000000000002`, and Emirates ID
  `784-1990-0000000-2`, matching the Phase 0 example.

## Rows in this increment

79 rows across 14 tables, seeded in foreign-key-safe order.

| Table | Rows | Contents |
|---|---:|---|
| companies | 2 | Horizon Clinics, Cedar Medical Group |
| branches | 4 | Horizon Dubai and Abu Dhabi; Cedar Sharjah and DHCC |
| app_users | 15 | 2 admins and 13 employee-linked identities, all active |
| employees | 15 | 13 active or probation (incl. 4 managers) and 2 terminated |
| user_profiles | 15 | 2 admin (no employee) and 13 linked profiles |
| departments | 6 | Horizon Dubai, Clinical over Nursing, Laboratory, Pharmacy |
| department_staffing_rules | 3 | Nursing morning and night, Clinical morning |
| shifts | 5 | Horizon Dubai M, A, N, F, S |
| payroll_runs | 4 | Horizon Dubai 2026-05 through 2026-08, every run and approval state |
| payroll_entries | 1 | The canonical payroll golden case |
| salary_advances | 6 | pending, active, active, settled, cancelled, cancelled |
| advance_repayments | 1 | The August 500 golden repayment, idempotent |
| expense_claims | 1 | The approved unpaid 350 golden claim |
| roster_assignments | 1 | The golden roster overtime row, planned 8, actual 12 |

## Identity model

Two tenants (companies), two branches each. Each branch is a `branches` row, not
a company row, so this is the Phase 4 target shape, not the legacy "company per
branch". Managers precede their reports in insert order so the composite
reporting-manager foreign key resolves.

Seeded `app_users` use a dedicated synthetic issuer, `https://seed.workloop.test`,
which is not the live Keycloak issuer. The application-user resolver only matches
its configured issuer, so no seeded row can ever resolve against a real token or
be misread as a live account. The Phase 3 synthetic-login verifier creates its
own rows and is untouched.

## Golden cases

- Canonical payroll: H-DXB-002 in the August draft run persists
  `leave_deduction = 400.00` and `variable_allowance = 5238.46`, with the exact
  additional-allowance and deduction JSON from Phase 0.
- Advance: advance `51000000-...-02` is active at amount 1500 with outstanding
  1000, reflecting the one seeded August repayment of 500. Replaying that
  repayment through `record_advance_repayment` with the persisted idempotency key
  returns `alreadyRecorded=true` and does not decrement the balance again.
- Roster overtime: H-DXB-002 has planned 8 and actual 12 hours on 2026-08-28,
  the four-hour overtime case.

## Retired legacy-only fixtures

Two Phase 0 scenarios cannot exist in the Phase 4 target schema and are dropped,
recorded here so the omission is deliberate, not an oversight:

- `H-LEG-001` and every `company_id IS NULL` employee. The target requires a
  company and a branch on every employee, so the legacy null-company branch
  behavior is gone by design.
- `storage.objects` rows. The target keeps file metadata in domain tables and has
  no storage table; object keys move to FastAPI in a later phase.

## Running it

```
docker compose --profile tools run --rm --entrypoint python migrate -m app.db.seed
docker compose --profile tools run --rm --entrypoint python migrate -m app.db.seed --validate-only
docker compose --profile tools run --rm --entrypoint python migrate -m app.db.seed --clean
```

The seed refuses to run as `workloop_runtime`. `scripts/verify-phase-4e-seed.sh`
runs the full apply, idempotent re-apply, revalidate, and clean cycle in CI.
`backend/tests/test_seed_fixtures.py` checks the manifest without a database:
determinism, no duplicate ids, real column names, manager ordering, the golden
values, the identifier formats, and the absence of real personal data.

## Remaining for the 4E gate

The next increments add the status-coverage rows the Phase 0 catalogue lists:
every leave, attendance, document, certification, notification, training, CME,
appraisal, asset, incident, contract, offboarding, and letter state, plus the
cross-tenant and cross-branch negative-control rows. The 4E completion gate, a
one-to-one match with the Phase 0 scenario catalogue, is met when those land.
