# Part 12C completion

Status: implementation and local gate complete. The routed GitHub gate must pass before Part 12D
starts.

## Result

Part 12C adds `GET /api/v1/tasks` and the migration task screen. The server owns one fixed category
registry for administrators, managers, and employees. Each entry fixes the category code, label,
navigation code, urgency rule, completeness rule, category order, entity type, and stable task ID
prefix. Empty categories remain in the response. A failed required source remains present with
`status: failed` and `errorCode: task_source_unavailable`; the route returns HTTP 503 with the full
catalogue and the safe error envelope.

Scope comes only from the authenticated principal and verified request context. Administrators use
the selected branch, managers use current direct reports, and employees use self. The route accepts
no employee ID. Category, urgency, limit, and integrity-protected cursor filters bind to the caller,
role, company, branch, and normalized filter set.

The service orders tasks by server category order, urgency rank, source business date with missing
dates last, source creation time with missing timestamps last, and stable task ID. Task IDs identify
summaries and do not authorize a source read or mutation. Navigation objects contain fixed screen
codes only.

The repository reads the existing Phase 8 through Phase 11 projections. It uses
`document_type`, `period`, and `emirates_id_expiry`; it does not read the retired `doc_type`, payroll
month and year, or `eid_expiry` fields. No schema revision was needed, so Alembic head remains
`c3e5a7b9d1f6`.

The migration task client rejects unknown response fields and malformed IDs, dates, timestamps,
urgency values, navigation objects, category states, and failure codes. The screen renders explicit
empty and unavailable categories, supports category and urgency filters, and paginates through the
FastAPI route. The migrated path contains no Supabase or retained task-storage import.

## Gate evidence

- All 629 backend tests passed. Complete Ruff lint and formatting passed. Strict Pyright checks
  passed for every changed Python file, and the locked environment reported no broken requirements.
- All 268 frontend tests passed. Focused ESLint for every changed migration file passed. The legacy
  and migration production builds passed. The existing migration chunk-size warning is unchanged.
- Thirteen focused backend service and HTTP tests cover fixed role catalogues, explicit empty and
  failed categories, safe 503 delivery, derived branch and self scope, stable pagination, cursor
  binding, filter denial, and category completeness.
- Three focused migration client tests cover the exact safe response, approved filters, role-derived
  headers, navigation shape, shell wiring, and absence of Supabase and retained task storage.
- `scripts/verify-phase-12c-boundary.py` passed and confirms current source column names, no Part 12C
  migration revision, principal-derived scope, failure handling, and migration-only task wiring.
- `scripts/verify-phase-12c-database.py` executed all 28 role-category query combinations against a
  fresh database at Alembic head `c3e5a7b9d1f6`.
- Routed GitHub evidence: pending the first push from this completion record.

## Resource boundary

Verification used only synthetic identifiers and a disposable local PostgreSQL environment. The
`workloop-phase12c-dev` containers, network, and volumes were removed after the query verifier
passed. The protected `workloop-clinic_postgres_data` volume was not attached, modified, deleted, or
recreated.

No production provider, credential, cloud resource, paid service, production data, real employee
record, patient record, payroll record, or banking record was used.

## Rollback and remaining legacy boundary

Rollback removes the migration task screen from the shell and disables `GET /api/v1/tasks` before
restoring the legacy task aggregator. Part 12C writes no source-domain data, so rollback leaves every
Phase 8 through Phase 11 row unchanged.

`src/utils/taskStorage.js` and `src/components/TasksPanel.jsx` remain only as the Phase 13 rollback
boundary. The migration build does not import either file. Phase 13 owns their removal with the rest
of Supabase.

After every routed Migration foundation job passes and the branch is clean and synchronized, Part
12D starts automatically in a new Codex task in the same saved project and local checkout. Part 12D
implements dashboards only; it does not begin reports or output work.
