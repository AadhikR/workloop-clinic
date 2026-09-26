# Part 13E completion

Status: implementation and the required local gate passed on 2026-09-26. Part 13E is complete when
the routed GitHub jobs for the commit containing this record pass.

## Result

Part 13E closes `P13-HIS-001` through `P13-HIS-003`, `P13-DOC-001` through `P13-DOC-004`,
`P13-TST-001`, `P13-TST-002`, `P13-GRD-001`, and `P13-DB-001`. It also closes golden cases
`13A-GC-015`, `13A-GC-016`, `13A-GC-021` through `13A-GC-023`, and `13A-GC-037` through
`13A-GC-039`.

The former root Supabase SQL and `sql/` chain now live under
`docs/history/legacy-supabase-sql/`. The directory label states that the files are historical and
must not run or deploy. The label preserves the old root and numbered-chain locations without
changing SQL contents. No active bootstrap, migration, test-fixture, build, or deployment path reads
them.

`backend/HISTORICAL_SOURCE_TERMS.md` labels the two append-only Alembic revisions and two backend
tests that retain source-system terms. `docs/migration/HISTORICAL_RECORDS.md` labels Phase 0 through
Phase 12 records as evidence of earlier repository states. Phase 13 records remain current migration
evidence.

The retired feature-list generator was removed. Its generated PDF moved unchanged to
`docs/history/legacy-feature-list/` beside a history label. The allowlist pins the PDF to its original
indexed SHA-256 digest, `4c3599a71f412d3472af48cf9289734a978b0c2f6134306025a31a2ed38381cc`.

The root setup, architecture, contributor, roadmap, checklist, remaining-test, backend, deployment,
and recovery documents now describe one runtime: React, Keycloak, FastAPI, portable PostgreSQL, and
private object storage. They contain no Supabase setup or operating instruction.

## Repository guard

`scripts/verify-phase-13e-repository-guard.mjs` inspects every tracked or unignored file. Its
machine-readable policy is `scripts/phase-13e-retired-runtime-allowlist.json`. The policy uses exact
repository-relative paths only. It has no prefix, regular-expression, or wildcard exception.

The guard rejects an unclassified case-insensitive marker and concealed concatenated package names.
This covers packages, direct and transitive graph entries, static and dynamic imports, aliases,
dead-code imports, environment inputs, endpoints, service calls, bootstrap SQL, copied public assets,
and unlabeled historical files. Historical groups must include a label containing the fixed "do not
run or deploy" sentence. Stale, duplicate, missing, absolute, parent-relative, or digest-mismatched
allowlist entries fail.

Focused fixtures prove rejection of direct, transitive, dynamic, aliased, dead-code, configuration,
endpoint, bootstrap, copied-asset, concealed-name, and unlabeled-history cases. Positive fixtures
prove the labeled-history and inert-sentinel paths. The guard also proves that every inspected file
is either classified once or counted as reference-free.

The always-routed `Classify and validate changes` job runs `npm run guard:repository` before any
path-dependent job. A workflow change cannot bypass the guard by selecting a narrower route.

## Decision

The allowlist records exact files instead of directory classes. This is the smallest fail-closed
choice. Adding a new historical or negative-test file requires an explicit policy review, so moving
active code into a broadly exempt directory cannot silence the guard.

The generator was retired rather than rewritten. `FEATURES_ROADMAP.md` now owns current feature and
release planning, while the digest-pinned PDF keeps the old product record. Maintaining another
generator would create a second current feature inventory with no runtime need.

The SQL moved as historical material, but its contents and the append-only Alembic chain did not
change. Alembic still has one head at `e8a1c3f5b7d9`.

## Focused and application verification

The following checks passed before the final local gate:

- 47 Phase 13, workflow-classifier, and phase-execution tests;
- the permanent repository guard, with every file accounted for exactly once;
- all 262 frontend unit tests;
- the canonical 91-module production build and emitted-byte scan;
- the Part 13 catalogue closure and fixed Alembic-head checks; and
- `git diff --check`.

## Final local gate

The named `workloop-phase13e-gate` stack:

- built the backend image once and started fresh PostgreSQL, FastAPI, Keycloak, and synthetic private
  object-storage services;
- applied Alembic twice and confirmed head `e8a1c3f5b7d9`;
- passed repository, API health, Keycloak readiness, authentication, and initial log-safety checks;
- recorded database fingerprint, Keycloak signing keys, local object, S3 object, and scanner state;
- restarted the existing images without rebuilding and matched every recorded value;
- passed authentication after restart without another configuration pass;
- passed the complete administrator, manager, and employee browser journey;
- removed the synthetic application and identity fixtures and passed final log safety; and
- removed its four containers, network, and three confirmed volumes.

The protected `workloop-clinic_postgres_data` volume remained present. The gate did not attach,
mount, modify, delete, or recreate it.

## Resource boundary

Work used synthetic local data only. Part 13E did not contact Supabase or access a cloud project,
secret store, paid service, production credential, or production resource. It did not run the Part
13F no-network proof, rewrite an Alembic revision, or change the schema head.

## Rollback and continuation

Rollback reverts the documentation, guard, allowlist, history relocation, and workflow route. It
must not restore a runtime package, environment input, client, alias, shim, or fallback.

After every routed GitHub job passes and the branch is clean and synchronized, Part 13F must run in
a new Codex task. Part 13F owns the fresh locked setup and no-network proof. It must not be
implemented in this task.
