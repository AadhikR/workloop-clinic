# Part 10C completion

Status: complete.

## Result

Part 10C makes FastAPI the sole writer for manual and biometric clock events. Administrators can
list selected-branch events, record manual events with a reason, manage branch-scoped badge
mappings, and import bounded normalized biometric candidates. Employees can read only their own
events. The migration client uses explicit Dubai time for manual entry and validates exact
camelCase projections.

Alembic revision `b7d9e1f3a5c6` adds append-only import batches and row outcomes, scoped event
provenance, deterministic fingerprints, minute-level duplicate protection, tenant-safe foreign
keys, RLS policies, runtime grants, protected audit actions, and replay-resource support. Concurrent
imports serialize by batch fingerprint, repeated content returns its durable first result, and
conflicting event inserts become duplicate outcomes instead of transaction failures.

Legacy manual clock-event, biometric-mapping, and biometric-import writers fail closed. The
`attendance-event-ingestion` cutover is complete, with `migration-fastapi` as its only read and
write authority.

## Gate evidence

The final tree passed the database-sensitive local gate in the isolated
`workloop-phase10c-gate` stack:

- Ruff lint and formatting, Pyright, dependency checks, and all 518 backend tests;
- all 190 frontend unit tests, changed-file ESLint, the legacy production build, and the migration
  production build;
- repeatable migration, exact predecessor rollback and replay, the focused Phase 10C catalogue
  verifier, and the cutover validator;
- direct PostgreSQL checks for administrator, employee, and denied-role scope; manual, duplicate,
  unknown-badge, mapping, import, durable replay, pagination, provenance, audit, RLS, grant, and
  append-only behavior;
- backend and identity health, Keycloak and FastAPI authentication, database and storage/signing
  persistence across an image-preserving restart, the full browser-authentication journey, and a
  final service-log secret scan; and
- idempotent synthetic-data cleanup.

The routed GitHub result is reported in the task handoff after the single push. This pre-push record
does not contain a pending workflow URL.

## Resource boundary

Verification used synthetic local data. The protected volume `workloop-clinic_postgres_data` was
not attached, modified, deleted, or recreated. Its creation timestamp remained
`2026-08-31T07:31:48Z` before and after the gate. The temporary Phase 10C containers, network,
storage volume, PostgreSQL volume, and generated local credentials were removed after evidence was
recorded.

## Writing review

The repository-required `.opencode/skill/unslop/SKILL.md` was absent. New prose received a manual
review for direct language, concrete claims, sentence-case headings, and consistent terms.

## Stop condition

Part 10D is the next authorized task. It may add server-owned attendance calculation and the
approved administrator and personal reads. Corrections, period close, rosters, swaps, and Phase 11
remain outside the 10D task boundary.
