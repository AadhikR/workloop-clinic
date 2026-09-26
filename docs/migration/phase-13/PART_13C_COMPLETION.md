# Part 13C completion

Status: implementation and the required local gate passed on 2026-09-26. Part 13C is complete when
the routed GitHub jobs for the commit containing this record pass.

## Result

The promoted application is now the only frontend. Its 75 tracked source files moved from
`migration/src` to `src`, and the root `index.html` and `vite.config.js` now own the canonical entry
point. The ordinary development, build, and preview commands use that root configuration, produce
`dist`, and keep the fixed local origin at `http://127.0.0.1:5174`. DigitalOcean consumes the same
command and output directory.

The frozen 96-file legacy source tree, seven public assets, 26 legacy freeze tests, legacy browser
generators, single-file build path, and dual-build isolation controls were removed. The repository
also dropped five direct packages used only by those paths. Active tests and workflow checks now
reference the canonical source and retained server-owned implementations. Historical cutover
records were not rewritten.

`PART_13C_REMOVAL_INVENTORY.json` pins the baseline commit, tracked path counts, and SHA-256 path
digests for each broad removal. The Part 13 catalogue records closure of `P13-SRC-001` through
`P13-SRC-005`, `P13-SVC-001` through `P13-SVC-003`, `P13-SVC-005`, golden cases `13A-GC-006`
through `13A-GC-008` and `13A-GC-010`, and the six Phase 12 entries retained for Phase 13.

Part 13D still owns `@supabase/supabase-js`, its transitive lockfile packages, and the Supabase
environment examples. They remain present but are not imported into the production graph.
The Alembic head remains `e8a1c3f5b7d9`.

## Verification

Focused development checks passed:

- 6 Part 13C tests covering the removal inventory, one canonical tree, commands, deployment
  mapping, production modules and bytes, package boundaries, and catalogue closure;
- the Part 13B promotion and canonical build tests;
- every affected Phase 8, 9, 11, and 12 static verifier; and
- `git diff --check`.

The final frontend gate passed all 246 unit tests and built the 91-module production graph. The
bundle contains OIDC support and no legacy-source or Supabase module. The existing chunk-size
warning remains informational.

The isolated `workloop-phase13c-gate` stack then:

- built the backend image once and started fresh PostgreSQL, FastAPI, Keycloak, and synthetic object
  storage services;
- applied migrations twice, confirmed head `e8a1c3f5b7d9`, and found no pending operation;
- passed the HTTP origin and authentication checks;
- recorded database, signing-key, stored-object, and scanner state;
- restarted existing images without rebuilding and matched every recorded value;
- passed authentication after restart without another configuration pass;
- passed the complete administrator, manager, and employee browser journey; and
- removed all synthetic application and Keycloak users and passed the final log-safety check.

## Resource boundary

Verification used synthetic local data and one named disposable Compose project. After the gate,
the `workloop-phase13c-gate` containers, network, and three volumes were removed. The protected
`workloop-clinic_postgres_data` volume remained present and was never attached, modified, deleted,
or recreated.

Part 13C did not access Supabase, production data, cloud resources, secret stores, paid services, or
external credentials. It did not run the Part 13F clean no-network gate.

## Rollback and continuation

Rollback restores the legacy source tree and build controls before changing ordinary command
selection. It must not remove the preserved Part 13D package and environment boundary.

After every routed GitHub job passes and the branch is clean and synchronized, Part 13D must run in
a new Codex task. Part 13D removes the Supabase package graph and active environment and
configuration inputs. It must not start the Part 13E historical-material cleanup or the Part 13F
no-network proof.
