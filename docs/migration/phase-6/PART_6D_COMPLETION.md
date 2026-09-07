# Phase 6D completion record

## Status

The project owner authorized Phase 6D on 2026-09-07. The implementation and local gate are complete.
The required GitHub result remains the final phase check and will be reported in the task handoff.

Phase 6D adds cutover controls only. Every business screen still reads and writes through legacy
Supabase. The migration build still has no business screen, business endpoint, or business write
path. Phase 6E has not started.

## Cutover record and validator

`cutover-record.schema.json` defines the reusable record format. `cutover-record.template.json` is a
complete synthetic declaration for a sample employee-directory slice. It remains in preparation
status with legacy Supabase as the reader and sole writer.

The record requires:

- a stable feature ID and a Phase 0 inventory source;
- exact agreement between required and declared dependency IDs;
- one reader, one writer, and a single-item writable-system list;
- read and write freeze conditions, release conditions, and verification commands;
- an ordered rollback plan that freezes migration writes, restores legacy writes and reads, and
  verifies authority and data;
- a tracked synthetic refresh source, exact command, source digest, execution time, evidence file,
  evidence digest, matching record counts, and a maximum evidence age;
- a complete one-to-one map from required legacy Supabase UUIDs to application-owned UUIDs; and
- ordered status history for preparation, active cutover, completion, and rollback.

`scripts/cutover-record-validator.mjs` checks the record structure and its cross-field rules. It
hashes the tracked source and evidence files, compares the evidence to the declared feature, command,
source, and timestamp, and rejects evidence outside the declared age limit. The validator accepts
synthetic declarations only.

The sample refresh command and its evidence are test fixtures. Phase 6D did not run a refresh or add
a refresh tool.

## Negative fixtures

The fixture set rejects a missing dependency, an omitted reader or writer, ambiguous authority, two
writable systems, incomplete read or write freezes, a partial rollback, missing refresh provenance,
missing or altered evidence, stale evidence, an incomplete identity map, and status that disagrees
with its history. Extra focused cases reject duplicate application-owned IDs and an invalid status
transition.

## Build isolation

`vite.legacy-isolation.js` blocks the legacy build from importing `oidc-client-ts`, `keycloak-js`, or
anything under `migration/`. The legacy Vite configuration now exposes only
`VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.

The migration build keeps its existing guard against legacy `src/` and `@supabase/*` imports. Its
six-name public configuration allowlist is unchanged.

`scripts/frontend-build-isolation.mjs` builds and scans both production graphs. It requires the
legacy graph to contain Supabase and exclude migration authentication and client modules. It requires
the migration graph to contain OIDC and exclude legacy source and Supabase modules. Opposite-build
configuration sentinels must also be absent from each compiled output.

## Verification

Focused checks passed before the final gate:

- 18 cutover tests covering the complete declaration and every required rejection;
- two build-isolation tests, including real production graph scans with 449 legacy modules and 21
  migration modules; and
- direct validation of the canonical synthetic template.

The settled local gate passed with:

- syntax checks for both new command-line validators;
- direct validation of `cutover-record.template.json`;
- `npm run test:unit`, with all 68 tests passing;
- `npm run build`;
- `npm run build:migration`; and
- `git diff --check`.

The change affects frontend build configuration, Node validators, tests, fixtures, and documentation.
It does not cross a backend, database, Keycloak, Compose, or shared-infrastructure boundary, so the
verification workflow does not require a local full-stack, migration-history, RLS, database-function,
or authentication gate. The path-routed GitHub workflow must run its frontend checks.

## Resource and rollback boundary

The existing `workloop-clinic` stack and its `workloop-clinic_postgres_data` volume were not read,
restarted, rebuilt, attached, upgraded, recreated, or deleted. Verification used tracked synthetic
fixtures. It accessed no Supabase account, real identity mapping, production data, SMTP service, paid
service, or cloud resource.

Rollback removes the record schema, template, fixtures, validators, tests, and legacy Vite isolation
plugin, then restores the previous legacy Vite configuration. No database, authentication, runtime,
or data rollback is needed.

## Stop condition

Phase 6D closes when the implementation commit passes the required path-routed GitHub workflow. Stop
before Phase 6E and request separate project-owner authorization.
