# Part 13D completion

Status: implementation and the required local gate passed on 2026-09-26. Part 13D is complete when
the routed GitHub jobs for the commit containing this record pass.

## Result

The frontend manifest and lockfile no longer contain `@supabase/supabase-js` or any transitive
`@supabase/*` package. A clean locked install produced an installed dependency tree with no
Supabase package or package directory.

The active environment examples no longer contain `VITE_SUPABASE_URL`,
`VITE_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, a Supabase URL, or a credential-shaped
Supabase value. The frontend example now contains only the six public FastAPI and OIDC inputs. The
browser-test example keeps blank fields for synthetic local identities and carries no external
service configuration. CI, Compose, infrastructure, Vite configuration, and the local environment
generator had no matching active input and remain unchanged.

The focused Part 13D verifier checks the manifest, lockfile, active configuration paths, production
module IDs, emitted bytes, hostile sentinel values, catalogue closure, and Alembic head. The Part
13C verifier now checks its recorded handoff boundary without requiring the removed package or
environment values to remain installed.

The catalogue closes `P13-SVC-004`, `P13-PKG-001`, `P13-PKG-002`, `P13-ENV-001`,
`P13-ENV-002`, `P13-ENV-003`, and golden case `13A-GC-009`. Alembic still has one head at
`e8a1c3f5b7d9`.

## Decision

Part 13D removes the package and inputs without a replacement alias, dummy client, optional flag,
or fallback. The dedicated verifier is the only new test that injects the three forbidden names.
It uses reserved hostile values solely to prove they cannot enter the production graph or emitted
bytes. This is the smallest fail-closed change that proves the 13D boundary while leaving the
broader historical and test-reference classification to Part 13E.

## Verification

Focused and regression checks passed:

- a clean `npm ci --ignore-scripts` install and an installed-tree check with no `@supabase`
  package;
- 4 Part 13D tests covering packages, configuration, production output, catalogue closure, and the
  fixed schema head;
- 57 focused authentication, API, private-file, output, environment, build, and boundary tests;
- all 250 frontend unit tests and the canonical 91-module production build; and
- `git diff --check`.

The isolated `workloop-phase13d-gate` stack then:

- built the backend image once and started fresh PostgreSQL, FastAPI, Keycloak, and synthetic object
  storage services;
- applied migrations twice and confirmed head `e8a1c3f5b7d9`;
- passed the HTTP origin, authentication, and initial log-safety checks;
- recorded the database fingerprint, Keycloak signing keys, synthetic object, S3 object, and scanner
  state;
- restarted the existing images without rebuilding and matched every recorded value;
- passed authentication after restart without another configuration pass;
- passed the complete administrator, manager, and employee browser journey; and
- removed all synthetic application and Keycloak users and passed the final log-safety check.

## Resource boundary

Verification used synthetic local data and one named disposable Compose project. After the gate,
the `workloop-phase13d-gate` containers, network, and three volumes were removed. The protected
`workloop-clinic_postgres_data` volume remained present and was never attached, modified, deleted,
or recreated.

Part 13D did not contact Supabase, inspect an external project, access a cloud secret store, change
a paid service, use production data, rewrite Alembic history, clean historical SQL or current
architecture documents, or run the Part 13F no-network proof.

## Rollback and continuation

Rollback restores the package and active configuration boundary only from the Part 13C commit. It
must not enable a Supabase runtime alongside the promoted application.

After every routed GitHub job passes and the branch is clean and synchronized, Part 13E must run in
a new Codex task. Part 13E labels historical material, updates current documents and tests, and adds
the permanent repository guard. It must not run the Part 13F clean setup or no-network proof.
