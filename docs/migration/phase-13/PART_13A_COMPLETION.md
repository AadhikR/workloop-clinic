# Part 13A completion

Status: Part 13A is complete when the routed GitHub checks for the commit containing this record
pass. The implementation and required local gate passed on 2026-09-26.

## Result

Part 13A created the Phase 13 dependency catalogue, promotion and decommission contract, fixed
golden cases, and focused verifier. The catalogue has 50 unique dependencies. Every dependency has
one allowed disposition and one owner from 13B through 13G. Part 13H remains the independent reviewer
and owns no implementation entry.

The repository scan covered 1,097 tracked files at the starting commit. It found 260 text files with
a Supabase marker and classified each through a non-overlapping coverage rule. The tracked HRMS
feature-list PDF was outside the text scan, so it received a separate full-page inspection and a
pinned SHA-256 digest of its canonical indexed Git blob. The PDF contains historical Supabase Auth, Edge Function, RPC, and Storage
instructions and is assigned to 13E for labeling.

The contract fixes:

- default command, CI, deployment, source-path, output-path, port, and public environment promotion;
- removal of the direct client and six transitive packages;
- closure of Auth, table and PostgREST, RPC, Realtime, and Storage dependencies;
- the boundary between active material, inert negative proof, and labeled history;
- detection of DNS, HTTP, WebSocket, PostgreSQL, and object-storage attempts;
- encrypted export and isolated restore evidence;
- a 30-day minimum retention period that begins after a successful restore;
- exact fresh owner approval for each external key, secret entry, bucket and object set, and project;
  and
- reverse repository rollback with no automatic recreation after external deletion.

No repository evidence confirms the actual GitHub or DigitalOcean Supabase secret entries. The three
repository environment names are discovery candidates only. Part 13G must resolve exact store and
entry names read-only and stop before destruction if access, identity, evidence, retention, or exact
approval is missing.

## Verification

Focused checks passed:

- 8 Part 13A contract tests;
- 21 combined Part 13A, dual-build isolation, migration-build, and Phase 12 closing checks; and
- a complete render and text inspection of all 15 pages in the tracked feature-list PDF.

The final frontend-classified local gate passed:

- `npm run test:unit`: 298 tests passed;
- `npm run build`: the default production build passed; and
- the existing chunk-size warning remained unchanged.

The verifier confirmed one Alembic head at `e8a1c3f5b7d9` and no migration-file change from the Part
13A baseline. `git diff --check` passed. The GitHub workflow result belongs in the 13B handoff and
task report so this completion record does not require a second documentation-only commit.

## Resource boundary

Part 13A used repository state, synthetic fixtures, local builds, and read-only inspection. It did
not access or change Supabase, GitHub secret stores, DigitalOcean secret stores, cloud resources,
paid services, credentials, exports, private objects, or real records.

The `workloop-clinic_postgres_data` volume was not attached, inspected, modified, deleted, or
recreated. No Compose stack or database service was started because 13A changed no runtime, schema,
authentication, Compose, or infrastructure behavior.

## Rollback and continuation

Part 13A rollback removes only its five design and catalogue files plus the focused contract test.
It does not change application or external state.

After the routed GitHub jobs pass and the branch is clean and synchronized, Part 13B must run in a
new Codex task. It promotes the migration application to the default development, build, preview,
CI, and deployment entry points. It does not move or delete either source tree; Part 13C owns that
separate boundary.
