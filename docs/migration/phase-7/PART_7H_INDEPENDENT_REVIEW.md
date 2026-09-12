# Phase 7H independent review

## Review status

The project owner authorized Phase 7H on 2026-09-12. The independent read-only pass is complete.
The implementation pass recorded the findings below before starting a correction.

The review starts from branch `migration/fastapi-keycloak` at commit
`6981086bd5fb12f57d44cfac71284b2cdd8ab1ce`. The working tree was clean and synchronized with
`origin/migration/fastapi-keycloak` before this record was created.

## Reviewer boundary

A separate Codex reviewer inspected direct excerpts from the Phase 7 contract, legacy employee
storage, legacy freeze tests, later-phase callers, and the implementation pass's verified inventory
and cutover results. The reviewer did not edit repository files or start containers. The
implementation pass separately inspected the complete contract, code, migrations, tests, freezes,
cutover declarations, and evidence files.

The review covers:

- every stable dependency ID in `PART_7A_DOMAIN_CONTRACT.md`;
- authorization, tenant and branch scope, transaction ownership, optimistic locking, idempotency,
  audit coverage, error disclosure, protected functions, and rollback ordering;
- the seven completed cutover records and their implementation evidence; and
- the absence of a Supabase path for cut-over Phase 7 features in the migration build.

The reviewer must call out any finding that would change an approved product rule, schema design,
role, grant, protected-function contract, phase boundary, rollback decision, or Alembic history.
Such a finding stops implementation for project-owner review.

## Findings

### Finding 1: an exported legacy employee hard delete remains active

- Severity: High
- Evidence: `PART_7A_DOMAIN_CONTRACT.md:32`, `PART_7A_DOMAIN_CONTRACT.md:55`,
  `PART_7A_DOMAIN_CONTRACT.md:81`, `src/utils/storage.js:156`,
  `tests/phase-7f-legacy-freeze.test.js:5`, and `tests/phase-7g-legacy-freeze.test.js:5`
- Finding: The approved contract excludes employee hard deletion and inventories `deleteEmployee`
  as a legacy writer. The export still sends a Supabase `DELETE`, while the other Phase 7 employee
  writers fail before reaching Supabase. No existing freeze test covers this export.
- Disposition: Accepted. Preserve the export as a deterministic hard-fail guard and add it to the
  employee administration freeze test. This enforces the approved rule without changing a schema,
  role, grant, protected function, rollback decision, phase boundary, or Alembic history.
- State: Resolved in `src/utils/storage.js` and
  `tests/phase-7f-legacy-freeze.test.js`. The focused freeze test and the updated employee
  administration cutover validation pass.

### Finding 2: retained later-phase screens call shared functions frozen by Phase 7

- Severity: Medium
- Evidence: `PART_7A_DOMAIN_CONTRACT.md:28`, `PART_7A_DOMAIN_CONTRACT.md:98`,
  `SUBPHASE_PLAN.md:88`, `src/components/EmployeeModal.jsx:300`,
  `src/components/EmployeeModal.jsx:309`, `src/components/EmployeeModal.jsx:337`,
  `src/components/EmployeeModal.jsx:345`, `src/components/ClinicalDashboard.jsx:116`,
  `src/components/ClinicalDashboard.jsx:119`, `src/components/IncidentManager.jsx:222`,
  `src/components/Reports.jsx:939`, and `src/components/RosterManager.jsx:243`
- Finding: The retained legacy graph still contains Phase 11 contract handlers and later-phase
  department or staffing consumers. Some of those callers now reach Phase 7 freeze guards. In the
  contract flow, a legacy contract row can be written before the frozen employee writer rejects the
  current-field update.
- Disposition: Closed as an explicit later-phase limitation. The migration build does not import the
  legacy graph, and these callers are not supported Phase 7 paths. Phase 11 owns a replacement for
  the contract transaction before that feature cuts over. The later owning phases must replace
  department and staffing consumers before claiming those features in the migration build. Repairing
  those workflows in Phase 7H would cross the approved boundary, so this phase makes no such change.
- State: Accounted for with an explicit later-phase owner. No Phase 7H correction is authorized.

## Dependency accounting

The Phase 7A contract contains 24 stable dependency IDs. The seven declarations contain the same
24-ID union, every former `planned-*` locator names existing implementation files, and no
`synthetic://` locator remains.

| Dependency ID | Current disposition and evidence |
| --- | --- |
| `legacy-auth-company-profile` | Retained in `src/context/AuthContext.jsx` for legacy authentication and later identity provisioning. Phase 7 organization writes are frozen separately. |
| `legacy-company-storage` | Phase 7 organization writers in `src/utils/storage.js` fail closed. Legacy readers remain for the legacy graph. |
| `legacy-company-context` | Retained in `src/context/CompanyContext.jsx`. The migration organization context uses its own FastAPI adapter and branch selection. |
| `legacy-profile-storage` | Portal-role access fails closed in `src/utils/profileStorage.js`. Other legacy self and later-phase readers remain assigned to their owning phases. |
| `legacy-employee-storage` | Phase 7 employee writers, including hard deletion, fail closed in `src/utils/storage.js`. Later-phase readers remain in the legacy graph. |
| `legacy-csv-converter` | Retained only in the legacy graph. The migration build uses `migration/src/employeeCsv.js` and create-only server validation. |
| `legacy-department-storage` | `src/utils/departmentStorage.js` fails closed for reads and writes after the department cutover. Later consumers are covered by Finding 2. |
| `legacy-staffing-storage` | `src/utils/staffingStorage.js` fails closed for reads and writes after the staffing cutover. Later consumers are covered by Finding 2. |
| `legacy-employee-joined-readers` | Retained for later appraisal, asset, attendance, expense, leave, task, and training phases. They are absent from the migration graph. |
| `legacy-phase7-consumers` | Phase 7 migration consumers have replacements under `migration/src`. Retained legacy later-phase consumers are assigned to their later owners. |
| `legacy-schema-contracts` | Retained as source evidence only. Target runtime schema authority is Alembic and PostgreSQL. |
| `target-domain-models` | Implemented in `backend/app/models/identity.py` and `backend/app/models/people.py`. |
| `target-scope-foundation` | Implemented under `backend/app/auth`, `backend/app/repositories/scoped.py`, and `backend/app/services/execution.py`. |
| `target-schema-foundation` | Implemented in `backend/alembic/versions` with one expected head at `8f6b2d1a4c70`. Runtime proof remains part of the final gate. |
| `target-http-client` | Implemented in `migration/src/http.js`. |
| `target-build-isolation` | Implemented in `migration/vite-isolation.js` and `scripts/frontend-build-isolation.mjs`. The focused pass found 449 legacy modules and 36 migration modules with no migration Supabase path. |
| `planned-organization-reader` | Replaced by the organization API, service, repository, schemas, migration adapters, context, chooser, and panel named in `organization-context.json`. |
| `planned-organization-writer` | Replaced by the organization and idempotency implementation named in `organization-administration.json`. |
| `planned-employee-reader` | Replaced by the employee API stack, reporting-manager migration, migration adapter, directory, and panel named in `employee-directory.json`. |
| `planned-department-writer` | Replaced by the department API stack and migration settings components named in `departments.json`. |
| `planned-staffing-writer` | Replaced by the shared department API stack and migration settings components named in `staffing-rules.json`. |
| `planned-employee-writer` | Replaced by the employee API stack, migration adapter, CSV parser, and employee directory named in `employee-administration.json`. |
| `planned-lifecycle-writer` | Replaced by the employee API stack, migration adapter, and employee directory named in `employee-lifecycle.json`. |
| `synthetic-identity-map` | Retained in `tests/fixtures/phase-6d/synthetic-users.json` for local proof only. |

## Cutover accounting

Structural validation passes for all seven records. The focused Phase 7H boundary test also proves
the exact 24-ID union, seven expected feature IDs, real replacement locators, completed states, one
writable system, opposite-system freezes, and the required rollback step order.

| Cutover unit | Read authority | Write authority | Writable system | Review disposition |
| --- | --- | --- | --- | --- |
| Organization context | Migration FastAPI | Legacy Supabase | Legacy Supabase | Valid read-only cutover. Later organization administration owns the migrated writes. |
| Organization administration | Migration FastAPI | Migration FastAPI | Migration FastAPI | Valid. Rollback freezes migration writes before restoring legacy writes. |
| Employee directory | Migration FastAPI | Legacy Supabase | Legacy Supabase | Valid read-only cutover. Later employee administration and lifecycle records own migrated writes. |
| Departments | Migration FastAPI | Migration FastAPI | Migration FastAPI | Valid. Rollback precedes dependent employee writer rollback. |
| Staffing rules | Migration FastAPI | Migration FastAPI | Migration FastAPI | Valid. Rollback observes the dependent employee boundary. |
| Employee administration | Migration FastAPI | Migration FastAPI | Migration FastAPI | Valid after Finding 1 closes the remaining legacy hard-delete path. |
| Employee lifecycle | Migration FastAPI | Migration FastAPI | Migration FastAPI | Valid. Rollback keeps committed history and audit evidence. |

The implementation pass refreshed all seven synthetic evidence files after the complete gate. The
business verifiers, database boundaries, authentication checks, restart persistence comparison,
complete browser journey, cleanup checks, and service log checks passed.

## Final reviewer confirmation

The independent reviewer confirmed Finding 1 as a blocking Phase 7H defect and Finding 2 as a
later-phase limitation that Phase 7H must document rather than repair. The reviewer found no reason
for a schema, role, grant, protected-function, rollback, phase-boundary, or Alembic amendment.

The independent review of direct excerpts did not run database, authentication, browser, rollback,
or deployment checks. The implementation pass ran those checks in the isolated Phase 7H stack and
recorded the results in `PART_7H_COMPLETION.md` and the seven cutover evidence files.
