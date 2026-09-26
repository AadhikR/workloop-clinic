# Part 13B completion

Status: implementation and the required local gate passed on 2026-09-26. Part 13B is complete when
the routed GitHub jobs for the commit containing this record pass.

## Result

Part 13B promoted the migration frontend without moving either source tree. `npm run dev`,
`npm run build`, and `npm run preview` now select `migration/vite.migration.config.js` directly.
The production output remains `dist-migration` until Part 13C moves the promoted application into
the canonical source and output paths.

The retained rollback path is one explicit `build:legacy` command. The ordinary commands contain no
environment switch, conditional, or fallback. CI already used `npm run build`; DigitalOcean now
uses that same command and consumes `dist-migration`. Neither consumer calls the rollback command.

The migration environment example now uses `/oidc/callback`. This matches the application route,
both Keycloak realm definitions, the browser journey, and the DigitalOcean build input. The fixed
local origin remains `http://127.0.0.1:5174` in Vite, the backend allowlist, generated local
configuration, authentication tests, and the browser journey.

These changes close catalogue entries `P13-BLD-001` through `P13-BLD-006` and golden cases
`13A-GC-001` through `13A-GC-005` plus `13A-GC-034`. The Alembic head remains
`e8a1c3f5b7d9`.

## Verification

Focused checks passed:

- 4 Part 13B promotion tests covering command selection, CI and deployment inputs, the public
  environment allowlist, fixed ports, browser and backend origin agreement, rollback isolation, and
  production graph and byte equality;
- 4 migration-build tests covering direct and transitive import rejection, production output, SPA
  startup, and strict port 5174 behavior; and
- the dual-build isolation check, with 435 legacy modules and 91 migration modules kept separate.

The frontend gate passed all 302 unit tests and the promoted production build. The migration bundle
contains OIDC support and no legacy-source or Supabase module. The existing chunk-size warning is
unchanged. The promoted preview command served the migration SPA on `127.0.0.1:5174`.

The isolated `workloop-phase13b-gate` stack then:

- built the backend image once and started fresh PostgreSQL, FastAPI, Keycloak, and synthetic object
  storage services;
- applied migrations twice and confirmed one Alembic head with no pending operation;
- passed the HTTP origin check and two Keycloak configuration passes;
- recorded database, signing-key, stored-object, and scanner state;
- restarted the existing images without rebuilding and matched every recorded value;
- passed authentication after restart without another configuration pass; and
- passed the complete administrator, manager, and employee browser journey and removed all
  synthetic application and Keycloak users.

`git diff --check` passed. The successful GitHub workflow URL belongs in the Part 13C handoff after
the routed jobs finish.

## Resource boundary

Verification used synthetic local data and one named disposable Compose project. After the gate,
the `workloop-phase13b-gate` containers, network, and three volumes were removed. The protected
`workloop-clinic_postgres_data` volume remained present and was never attached, modified, deleted,
or recreated.

Part 13B did not access Supabase, production data, cloud resources, secret stores, paid services, or
external credentials. It did not run the Part 13F clean no-network gate.

## Rollback and continuation

Rollback restores the previous ordinary command mapping and the DigitalOcean migration-specific
build command. It leaves both source trees, the package graph, environment examples other than the
corrected callback path, database state, and external services unchanged.

After the routed GitHub jobs pass and the branch is clean and synchronized, Part 13C must run in a
new Codex task. Part 13C moves the promoted frontend into the canonical paths and removes the frozen
legacy source. It must not remove the Supabase package or active environment examples, which belong
to Part 13D.
