# Phase 0 Baseline and Inventory

## Status

**Completed on 2026-08-27.**

Phase 0 records the current application before backend migration begins. It does not fix baseline defects or change runtime behavior.

## Completion Gate

The Phase 0 gate requires every visible portal feature to have an owner phase and the current build and test state to be recorded.

The gate passes because:

- Shared, admin, manager, and employee features are mapped to migration phases.
- Supabase Auth, table, RPC, and Storage dependencies are inventoried.
- The SQL files, missing schema objects, policies, functions, and ordering risks are inventoried.
- Frontend request, response, converter, status, and calculation contracts are recorded.
- The synthetic-data specification defines two tenants, fixed identities, a fixed clock, scenario coverage, golden outcomes, and a deterministic ID rule. Phase 4 owns the executable row manifest and seed implementation.
- Architecture defaults and operational ownership are recorded below.
- Passing and failing baseline commands are recorded without changing the existing implementation.

## Artifacts

| Artifact | Purpose |
|---|---|
| [`SUPABASE_DEPENDENCY_INVENTORY.md`](SUPABASE_DEPENDENCY_INVENTORY.md) | Every Supabase-dependent module, operation, table, RPC, bucket, converter, and ambiguous contract found under `src/` |
| [`SQL_SCHEMA_INVENTORY.md`](SQL_SCHEMA_INVENTORY.md) | Root and numbered SQL order, tables, functions, triggers, RLS, grants, Supabase coupling, missing definitions, and Alembic implications |
| [`FEATURE_AND_CONTRACT_MATRIX.md`](FEATURE_AND_CONTRACT_MATRIX.md) | Portal features, workflows, permissions, business rules, data shapes, statuses, and migration ownership |
| [`SYNTHETIC_TEST_DATA.md`](SYNTHETIC_TEST_DATA.md) | Deterministic organizations, users, records, files, financial cases, and cross-tenant tests |
| This file | Command baseline, decisions, ownership, known defects, and Phase 0 conclusion |

## Command Baseline

Commands were run from the repository root on 2026-08-27.

| Command | Result | Evidence |
|---|---|---|
| `npm.cmd run test:unit` | Pass | 14 tests passed; 0 failed; Node test runner completed normally |
| `npm.cmd run build` | Pass with warning | Vite 8.0.10 transformed 2,062 modules and completed in 3.92 seconds |
| `npm.cmd run lint` | Fail | ESLint reported 123 problems: 114 errors and 9 warnings |
| `npm.cmd test` | Fail | Playwright discovered the Node utility tests, which passed, then exited with `Error: No tests found` because no Playwright specifications are present |

### Unit-Test Coverage Present

The 14 passing unit tests cover selected report calculations and custom-request validation:

- Empty headcount export.
- Approved leave usage.
- Attendance classifications.
- Overtime hours and cost.
- Document expiry and deduplication.
- Salary movement.
- Turnover date handling.
- WPS classifications.
- 2026 Emiratization tiers.
- End-of-service liability.
- Persisted leave balances.
- Request-kind normalization.
- Custom-request required fields.
- Custom-request database length limits.

They do not cover authentication, RLS, storage, portal workflows, PostgreSQL functions, or browser behavior.

### Build Warning

The standard production build succeeds. Vite warns that at least one minified chunk exceeds 500 kB. The main generated JavaScript chunk was approximately 522 kB. This is a baseline performance warning, not a migration blocker.

### Lint Failure Categories

The current lint failure predates FastAPI migration work. Representative categories include:

- State updates triggered synchronously from React effects.
- Functions referenced before declaration under React hook/compiler analysis.
- Missing hook dependencies.
- Unused imports, variables, assignments, and ESLint directives.
- Empty catch blocks.
- Context or utility exports that conflict with the Fast Refresh rule.
- Manual memoization that the React compiler cannot preserve.

The migration must not report these as new regressions. New backend and migration-build files must pass their own lint and test checks. Existing frontend lint debt should be fixed in a separate tracked effort or reduced deliberately as each touched module migrates.

## Inventory Summary

| Item | Recorded count |
|---|---:|
| Modules importing or creating the Supabase client | 24 |
| Direct `supabase.from(...)` entry points observed | At least 77 |
| Direct `supabase.rpc(...)` call sites observed | At least 32 |
| Direct Supabase Auth references observed | At least 28 |
| Direct Supabase Storage references observed | At least 13 |
| Effective application tables | 52 |
| Frontend-referenced RPC names | 27 |
| Storage buckets | 2 |
| Root-level SQL scripts | 12 |
| Numbered SQL scripts | 50 |

Counts describe the checked-in source and are navigation aids. One fluent Supabase entry point may contain several filters, joins, or mutations, and one RPC may have several call sites.

## Critical Baseline Findings

These findings are existing conditions. They must be addressed or preserved deliberately, but are not defects introduced by migration.

| Finding | Migration consequence |
|---|---|
| The checked-in SQL is not a complete fresh-install chain | Build a clean Alembic baseline from contracts and intended final structure rather than replaying files blindly |
| The original project supplied the previously missing `user_profiles`, `employees.auth_user_id`, and employee Auth mapping SQL | Use it as historical contract evidence, but reconstruct identity explicitly with `app_users` and Keycloak issuer/subject mapping rather than copying Supabase Auth coupling |
| One called RPC definition remains missing | Specify new FastAPI behavior for `manager_get_leave_queue` from its task and manager-leave contracts |
| Recovered self-service SQL contains historical defects and overloads | Apply the later clock-event fix, resolve the old and warning-aware leave overloads, and review all recovered authorization before the Alembic baseline |
| SQL migrations have missing numbers and unclear root ordering | Treat old SQL as historical evidence, not the new migration runner |
| Several timestamp triggers and RLS policies overlap | Choose one canonical trigger and authorization design in Alembic |
| Several security-definer functions have weak ownership checks or broad execution | Do not copy them unchanged; reimplement authorization in FastAPI and reviewed SQL functions |
| Branch scoping is incomplete across feature tables | Define explicit tenant and branch ownership in the new schema and permission matrix |
| Admin, employee, and manager code use mixed camelCase and snake_case objects | Preserve documented API contracts or convert screens deliberately with contract tests |
| Task aggregation references stale column names | Treat empty task categories as a known baseline risk and implement explicit API contracts |
| Several writes use multiple non-atomic browser calls | Replace them with FastAPI transactions or reconciled object-storage workflows |
| Current payroll approval has no separation-of-duties role | Preserve current behavior initially, then make any policy change an explicit product decision |
| Unknown profile roles fall through to the admin shell | The migration build must require an explicit recognized role and deny unknown roles |
| No database Realtime subscription exists | Polling and explicit refresh are sufficient for migration parity |

## Architecture Decisions

These defaults apply unless a later dated decision-log entry replaces them.

| Topic | Phase 0 decision | Reason |
|---|---|---|
| Infrastructure as code | Terraform | Supports DigitalOcean now and Azure later; keeps reviewed infrastructure in source control |
| PostgreSQL version | PostgreSQL 16 | Mature version with broad DigitalOcean and Azure PostgreSQL compatibility; verify availability before provisioning |
| Application identity | Application-owned UUID plus text `identity_issuer` and `identity_subject` | Prevents Keycloak identifiers from becoming business-table foreign keys and supports a future issuer change |
| Authentication | Keycloak OIDC Authorization Code flow with PKCE S256 | Avoids custom password handling and remains host-portable |
| Application roles | Store admin, manager, employee, company, and employee links in Workloop PostgreSQL | Keycloak proves identity; FastAPI and Workloop data determine business permissions |
| API authorization | FastAPI is the primary authorization boundary | Every query and workflow passes through the API after migration |
| Database authorization | Retain standard PostgreSQL RLS as defense in depth for tenant and employee-owned records | Protects sensitive rows if an application query misses a scope; requires transaction-local context and pool-isolation tests |
| API field names | Return existing camelCase frontend shapes using explicit Pydantic aliases; migrate current raw snake_case employee consumers in the same release as their endpoint | Minimizes React changes without preserving two employee contracts indefinitely |
| Database field names | Keep PostgreSQL columns in snake_case | Matches PostgreSQL and Python conventions while separating storage from API contracts |
| Status values | Preserve exact existing values and casing during initial migration | Prevents hidden behavior changes across modules that currently use different casing conventions |
| Branch model | Preserve the current branch-as-company-row behavior initially | Avoids combining a backend migration with an organization-model redesign; revisit before Azure production |
| SQL functions | Keep only reviewed set-based or atomic operations that are clearer and safer in PostgreSQL | Move Auth-dependent orchestration and permission decisions to FastAPI services |
| File upload | Stream through FastAPI using server-generated object keys | Allows authorization, byte inspection, size checks, and predictable metadata state before availability |
| File download | FastAPI authorizes, then returns a short-lived signed URL | Keeps files private without forcing FastAPI to serve every download byte |
| Storage portability | Provider-neutral interface with DigitalOcean Spaces adapter | Allows Azure Blob replacement without rewriting business services |
| Exports | Keep current browser PDF, CSV, ZIP, and SIF generation initially; source data comes from scoped APIs | Preserves behavior while removing direct database access; move large exports server-side only when measured |
| Scheduled jobs | Add none during parity migration | Current behavior uses polling, explicit refreshes, and user-triggered generation; add a scheduler only for a defined requirement |
| Migration coexistence | Separate legacy Supabase and Keycloak migration builds | A Keycloak token cannot authorize existing Supabase RLS or RPCs; mixed sessions are prohibited |
| Data synchronization | One-way deterministic synthetic refresh only | Avoids dual-write conflicts; migrated slices have one authoritative backend |

## Operational Ownership

The project owner remains accountable even when AI writes implementation code. AI is a tool, not an operational owner.

| Responsibility | Development owner | Required reviewer or backup |
|---|---|---|
| Product scope and behavior acceptance | Project owner | None assigned |
| Repository and release approval | Project owner | DigitalOcean team owner where account permission is required |
| DigitalOcean resources and billing | Project owner | DigitalOcean team owner |
| Terraform changes | Project owner | AI-assisted review; independent review before Azure production |
| Keycloak realm and upgrades | Project owner | Independent identity/security reviewer before real users |
| Alembic migrations | Project owner | Independent database reviewer before real data |
| FastAPI and React releases | Project owner | Automated checks plus manual acceptance |
| Backup and recovery exercises | Project owner | DigitalOcean team owner during development; database reviewer before production |
| Supabase decommission approval | Project owner | Repository owner or designated backup |
| UAE production compliance | Project owner | Qualified UAE legal/privacy reviewer |
| Azure security and production handoff | Project owner | Independent Azure security specialist |

Named external reviewers are not required to begin development because DigitalOcean contains synthetic data only. They must be selected before the Azure production gate.

## Feature Ownership by Migration Phase

| Migration phase | Owned scope |
|---|---|
| Phase 3 | Keycloak identity, migration-build login, application-user mapping, and session behavior |
| Phase 4 | Canonical portable PostgreSQL and Alembic baseline for all recorded entities |
| Phase 5 | Cross-tenant, branch, manager, employee, and system authorization |
| Phase 6 | Shared HTTP client, API conventions, errors, tokens, and cutover rules |
| Phase 6A | Early DigitalOcean proof covering React, FastAPI, Keycloak, PostgreSQL, Spaces, and deployment migrations |
| Phase 7 | Companies, branches, departments, staffing rules, employees, job history, and portal role assignment |
| Phase 8 | Leave settings, types, holidays, requests, balances, approvals, delegates, attachments, and audit |
| Phase 9 | Payroll, entries, approval, payslips, WPS, SIF, advances, repayments, expenses, and financial audit |
| Phase 10 | Attendance, shifts, events, records, periods, corrections, biometric import, rosters, staffing gates, and swaps |
| Phase 11 | Documents, files, insurance, assets, training, certifications, CME, appraisals, incidents, contracts, requests, and offboarding |
| Phase 12 | Notifications, tasks, dashboards, reports, CSV, PDF, ZIP, and SIF output behavior |
| Phase 13 | Final migration-build promotion and complete Supabase runtime decommission |
| Phases 14–15 | DigitalOcean hardening, operations, full-system validation, recovery, and Azure handoff evidence |

Every visible feature in `FEATURE_AND_CONTRACT_MATRIX.md` belongs to one of these phases.

### Cross-Phase Ownership Boundaries

| Shared concern | Domain phase owns | Supporting phase owns |
|---|---|---|
| Leave attachments | Phase 8 owns leave metadata, permissions, and workflow behavior | Phase 11 owns the common object-storage adapter and recovery behavior |
| Expense receipts | Phase 9 owns claim metadata, permissions, and payroll integration | Phase 11 owns the common object-storage adapter and recovery behavior |
| SIF | Phase 9 owns payroll inputs, calculations, compliance, and authoritative values | Phase 12 owns browser file rendering and download parity |
| Employee response shape | Phase 7 changes raw snake_case employee consumers and the endpoint atomically | Phase 6 supplies shared camelCase API conventions and contract tests |

## Phase 0 Conclusion

The application can begin Phase 1 without modifying current runtime behavior. The next work is account and deployment preparation, not FastAPI feature implementation.

Phase 1 must confirm DigitalOcean permissions, connect the private GitHub repository, establish the development project and cost controls, select a compatible region, and record secret ownership. No real data may be introduced.
