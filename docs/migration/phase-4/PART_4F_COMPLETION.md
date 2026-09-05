# Phase 4F completion record

## Status

The independent review and complete local Phase 4F gate passed on 2026-09-06. The review found no
defect in the approved Phase 4C schema or corrected Phase 4D behavior. It found four verification
gaps. All four are fixed and passed focused checks.

The commit containing this record must still pass the existing GitHub workflow. The task handoff
records that post-commit result, so this file does not require a second documentation-only commit.
Phase 4 remains in progress until the project owner signs off. Phase 5 has not started.

## Independent review

An independent GPT-5.6 reviewer inspected the Phase 4C migrations and models, all corrected Phase
4D revisions through `d307b9c1f25e`, and the verification scripts. The reviewer made no edits and
did not run the complete gate.

The review counted 54 target tables and 189 foreign keys. It found no missing composite branch
foreign key, unscoped branch-owned employee reference, cascading delete, timestamp without time
zone, or dependency on an `auth` or `storage` schema. The three business functions match the
approved transaction rules. Their corrected search paths, ownership path, PUBLIC revokes,
protected-table revokes, and downgrade order also match the approved design.

## Findings and dispositions

| Finding | Severity | Disposition |
|---|---|---|
| The source scan named only selected `auth` and `storage` objects and one Supabase role. | Medium | Confirmed verification gap. The static tests and seed verifier now reject every `auth.*` and `storage.*` reference, the known Supabase service roles, and browser roles used as database identifiers. The scan includes migrations, models, functions, and seed code. |
| The function-security verifier did not pin the exact function set, owner, namespace, or definer mode. Successful behavior ran as the superuser. | Medium | Confirmed verification gap. The verifier now requires exactly four public functions owned by `workloop_migration`, requires the three business functions to use `SECURITY DEFINER`, requires the trigger helper to remain invoker mode, and checks every pinned search path. All three business functions now complete a successful path as `workloop_runtime`. |
| The repayment and shift-swap tests did not cover several branches claimed by their completion record. | Medium | Confirmed verification gap. Focused cases now cover repayment payroll conflict, payroll scope, scale, range, and outstanding balance. Shift swaps now cover disabled, non-admin, and wrong-company actors, missing assignments, same-day and destination conflicts, one-way coverage, two-way swaps, and stale requests. |
| Effective privilege checks did not reject unexpected table ACL recipients or PUBLIC table grants. | Low | Confirmed verification gap. The grant verifier now expands table and function ACLs, rejects PUBLIC and unexpected recipients, rejects runtime grant options, and proves the runtime cannot create objects in `public`. |

No finding required a schema decision, a boundary change, or more migration scope. No Alembic
revision, table, column, constraint, function body, trigger, grant, seed row, API route, or
authentication behavior changed.

## Focused checks

The review fixes passed before the complete gate:

- 46 focused static tests in `test_phase4_schema.py` and `test_seed_fixtures.py`.
- Ruff on both changed test modules.
- Shell syntax checks for every changed verifier.
- The changed grant, function-security, function-behavior, and Phase 4F live-database verifiers on
  isolated Compose project `workloop-phase4f-review-20260906`.

That review project used a fresh PostgreSQL 17.11 volume with no host port. Its volume was removed
after the focused checks. The preserved PostgreSQL 16 project remained running throughout.

## Complete local gate

The one complete local gate used isolated Compose project `workloop-phase4f-20260906` and a new
named volume. The database started empty on PostgreSQL 17.11 and Alembic upgraded it to
`d307b9c1f25e` without a manual SQL step.

The repository checks passed:

- Backend Pytest passed 124 tests. Ruff, Ruff formatting, Pyright, and the dependency check passed.
- The locked frontend install completed. All 32 unit tests and four migration-build isolation tests
  passed. The legacy and migration production builds passed.
- Compose validation passed against the PostgreSQL 17.11 digest in `docker-compose.yml`.

The database checks passed:

- A repeated head upgrade was a no-op. Downgrade to base and upgrade back to head passed.
- Every Phase 4C domain revision and every Phase 4D revision downgraded to its parent and upgraded
  again. Alembic `current` and `heads` returned `d307b9c1f25e`; `alembic check` found no drift.
- The 54-table schema, composite tenant and branch constraints, exact runtime grants, ACL
  recipients, 19 triggers, function behavior, temporary-table shadowing defense, and shift-swap
  concurrency checks passed.
- The seed applied all 334 rows across 48 tables. A second application changed nothing and retained
  fingerprint `0c8093dcab9bf142c01e046cf80723e527da00c3db7a08a32a685a600ba658f9`.
  `workloop_runtime` could not run the seed. Cleanup removed all 334 rows and left every identity
  root empty.
- The live database contained no `auth` or `storage` schema, Supabase role, RLS policy, or retained
  function reference to a Supabase database object. Every public relation, enum, and function had
  the approved migration ownership. The runtime role had no elevated attribute or role membership.

Authentication and restart checks also passed. FastAPI and Keycloak were healthy, the protocol and
browser authentication verifiers passed before and after container and network replacement, and
Keycloak signing keys persisted. The final database held 54 target tables plus `alembic_version`,
two Keycloak realms, no temporary Workloop identity row, and no temporary Keycloak user. Service
log checks found no credential or token value.

The isolated project and its volume were removed after the gate. The same preserved PostgreSQL 16
container then restarted on `workloop-clinic_postgres_data` and returned healthy. PostgreSQL 17 was
never attached to that volume.

## Remaining limits

- Phase 4 still needs project-owner sign-off after the final GitHub workflow passes.
- Phase 4 has no RLS policy or application authorization. Phase 5 owns those controls and remains
  unauthorized.
- No API route, Keycloak provisioning, cloud resource, SMTP setting, object-storage adapter, real
  data, or legacy data converter was added.
- Local Keycloak still uses its approved development-only HTTP and `start-dev` setup. Existing npm
  advisories remain separate work.

No paid resource or new secret was created.
