# Phase 13 subphase plan

## Status and authorization

The project owner signed off Phase 12 and started Part 13A on 2026-09-26. That instruction
authorizes Parts 13A through 13H under `docs/migration/PHASE_EXECUTION_WORKFLOW.md`. Each part runs
in a separate Codex task. A part must pass its focused checks, boundary-matched local gate, push,
and routed GitHub jobs before the next part starts automatically.

Phase 13 starts from commit `71ee41636ab3f06f62b8d2d3cd0580675c251d5f` on
`migration/fastapi-keycloak`. GitHub Migration foundation run `36222327809` passed. Alembic has one
head at `e8a1c3f5b7d9`. The protected `workloop-clinic_postgres_data` volume remains present and must
not be attached, modified, deleted, or recreated.

## Phase boundary

Phase 13 makes the Keycloak, FastAPI, portable PostgreSQL, and private object-storage application
the only active Workloop runtime. It promotes the migration frontend to the default application,
removes the retained legacy frontend and Supabase runtime package, removes active Supabase
configuration, proves a clean setup without Supabase credentials or network access, and updates
current setup, architecture, deployment, and recovery instructions.

The phase distinguishes active runtime material from historical evidence. Historical SQL and
migration records may retain the word `Supabase` when they explain the source system or a past
cutover. They must live outside active build, deployment, database-bootstrap, and test-fixture paths
and carry an explicit historical label. Tests may use inert forbidden-value sentinels to prove that
the application rejects or ignores Supabase configuration.

The following work is outside the standing authorization:

- No production or real clinic data, employee record, patient record, payroll record, or banking
  record.
- No paid resource, new cloud service, production credential, or Azure work.
- No Phase 14 DigitalOcean hardening or release promotion.
- No deletion of the external Supabase project, bucket, object, key, GitHub secret, or DigitalOcean
  secret until the owner approves the exact targets after retention and restore evidence exists.
- No committed export, credential, secret value, private object, Auth password, or personal data.

## Part plan

| Part | Scope | Required result | Rollback boundary |
| --- | --- | --- | --- |
| 13A | Dependency inventory, promotion contract, retention rules, golden cases, and decommission design | Every active, historical, test-only, configuration, secret-store, and external Supabase dependency has one disposition and one owner | Revert 13A documents and verifier only |
| 13B | Default application promotion | Default development, build, preview, Compose, and CI entry points use the migration frontend; legacy stays available only as an explicit rollback build | Restore the previous default commands and deployment entry point while leaving both source trees intact |
| 13C | Canonical frontend and legacy removal | The promoted frontend occupies the canonical source and output paths; retained legacy components, utilities, generators, auth, and build isolation are removed | Revert the source-tree move and restore the frozen legacy tree before changing dependencies |
| 13D | Supabase package, environment, and active configuration removal | No active source, package, lockfile, environment example, CI, Compose, infrastructure, or bootstrap path requires Supabase | Restore only from the 13C boundary; never mix restored Supabase runtime with the promoted application |
| 13E | Historical SQL, tests, docs, and repository guardrails | Historical material is labeled and isolated; current docs and tests describe one runtime; automated scans reject new active Supabase dependencies | Revert documentation and guardrails without restoring runtime dependencies |
| 13F | Clean setup and no-network proof | A fresh disposable setup builds and passes the full application gate with no Supabase URL, key, account, bucket, DNS lookup, or request | Return to the 13E commit; preserve test evidence and do not alter external services |
| 13G | Retention proof and external decommission | Approved encrypted exports and object hashes are verified outside Git, then specifically approved keys, secrets, buckets, and the Supabase project are revoked or deleted | Stop before each destructive action unless the owner has approved its exact target; external deletion has no repository rollback |
| 13H | Independent review and complete Phase 13 gate | Repository, clean setup, network capture, secret-store evidence, retention evidence, and external state prove no Supabase runtime dependency | Restore the promoted application from source control; never recreate an external project as an automatic rollback |

## Part 13A dependency and decommission contract

13A creates a repository-wide inventory that covers source imports, transitive packages, environment
names, build commands, outputs, tests, CI, Compose, infrastructure, SQL, documentation, GitHub and
DigitalOcean secret names, Supabase Auth, tables, RPCs, Realtime, Storage, and the external project.
Each item receives one classification: remove, replace, retain as inert test proof, retain as labeled
history, inspect externally, or destroy only after explicit approval.

The promotion contract fixes the canonical entry point, source tree, build output, public environment
allowlist, rollback sequence, clean-install test, no-network test, retention evidence, and external
approval gate. Golden cases cover default commands, all five Supabase service classes, missing and
hostile Supabase environment values, direct and transitive imports, DNS and HTTP attempts, historical
files, secret-store names, backup verification, and destructive-action denial.

13A adds no runtime route, frontend behavior, migration revision, cloud resource, secret, export, or
external service change.

## Part 13B default application promotion

13B makes the migration frontend the target of ordinary `dev`, `build`, and `preview` commands and
the output consumed by active local and CI workflows. It updates fixed ports, public environment
allowlists, browser journeys, and deployment-facing paths as one change. A clearly named legacy
rollback command may remain through 13B only. Default commands must never select the legacy app by
environment value or fall back after a migration-app failure.

Focused proof compares the promoted output with the last migration output, confirms OIDC and API
configuration, denies Supabase and legacy imports, verifies SPA startup, and runs the complete
three-role browser journey. Rollback restores the old command mapping without changing either app.

## Part 13C canonical frontend and legacy removal

13C moves the promoted application into the canonical source and output locations, then removes the
frozen legacy frontend, its Supabase auth context, storage clients, local calculators, browser file
generators, legacy-only components, and dual-build isolation. Tests and imports move with the
canonical source in the same commit. Historical cutover records remain immutable evidence.

Focused proof accounts for every deleted legacy path, rejects orphan imports and duplicate screens,
builds one production graph, and reruns the role, output, and browser journeys affected by the move.
This part does not remove the Supabase package or active environment examples; 13D owns that separate
dependency boundary.

## Part 13D runtime package and configuration removal

13D removes `@supabase/supabase-js` and its transitive lockfile packages. It removes Supabase public
environment names and values from active examples, CI, Compose, infrastructure, bootstrap scripts,
and deployment inputs. It also removes any active SQL or helper that still assumes Supabase Auth,
PostgREST, RPC, Realtime, or Storage.

Focused proof starts from a clean dependency install, scans the production module graph and bundled
bytes, checks active configuration keys, and runs authentication, API, file, and full-stack tests.
No replacement compatibility shim, dummy client, dead dynamic import, or optional Supabase flag is
allowed.

## Part 13E historical material and repository guardrails

13E classifies remaining Supabase references. It moves or labels SQL retained only for migration
history, removes obsolete setup and test instructions, and updates current architecture, deployment,
recovery, and contributor documentation. It preserves identifiers required to explain historical
cutovers or user mappings without treating them as runtime configuration.

A repository guard distinguishes forbidden active references from approved historical paths and
inert negative-test sentinels. CI runs that guard on every change. The guard rejects new Supabase
packages, imports, environment inputs, endpoints, service calls, bootstrap SQL, and unlabeled
historical files.

## Part 13F clean setup and no-network proof

13F creates a fresh disposable environment with no Supabase variables, credentials, host mapping,
account, or project access. It installs locked dependencies, builds the canonical frontend, starts
the complete local stack, applies migrations twice, and runs the full role and output journeys.
Network capture or an equivalent fail-closed harness must prove that no frontend, backend, worker,
test helper, or browser attempts Supabase DNS, HTTP, WebSocket, Postgres, or object-storage access.

The proof restarts existing images without rebuilding and compares database, signing-key, and stored
object state. It removes only its named disposable resources. It does not inspect or modify any
external Supabase resource.

## Part 13G retention and external decommission

13G begins with read-only discovery and a target manifest. It records the Supabase project, Auth
metadata, buckets, object counts and hashes, secret names, retention owner, encrypted export
location, restore check, and retention deadline without committing secrets or private data. The
project owner must then approve the exact destructive targets. Phase-level authorization alone does
not authorize revocation or deletion.

After that approval, 13G revokes the approved API keys, removes the named GitHub and DigitalOcean
secrets, deletes approved obsolete buckets and objects, and deletes the approved Supabase project.
It records non-secret receipts or hashes. If credentials, retention evidence, access, or approval are
missing, the task stops at the prepared manifest and reports the boundary.

## Part 13H independent review

13H independently traces every 13A inventory entry and golden case. It verifies the canonical build,
source and dependency scans, current documentation, historical-file labels, clean setup, no-network
capture, retention receipts, secret-store results, external project state, rollback order, safe logs,
and disposable cleanup.

The closing gate runs one complete local and routed full-stack proof. Part 13H records Phase 13
completion and asks the project owner for one signoff. It does not start Phase 14.

## Shared verification and source control

Each part follows `docs/migration/VERIFICATION_WORKFLOW.md`. Use focused checks while changing one
bounded unit, then run one boundary-matched local gate. Changes to the default build, CI, Compose,
authentication, dependency graph, or runtime configuration require the complete frontend and
full-stack gate. Documentation-only completion edits use lightweight validation.

Every nonfinal part leaves a clean synchronized `migration/fastapi-keycloak` branch, generates the
next handoff from verified repository state, creates a new task in the same saved project and local
checkout, and starts it without another owner approval. The separate destructive approval inside
13G applies only to the exact external targets. It does not interrupt routine execution of 13A
through 13F.

## Resource and data boundary

Use synthetic local data and named disposable services. Preserve `workloop-clinic_postgres_data`
untouched. Do not copy real data into the repository or a local fixture. Store any encrypted export
outside Git in project-controlled storage and record only its non-secret location, count, digest,
restore result, owner, and retention deadline. Verify exact local and external targets before cleanup.

Repository rollback proceeds in reverse order: no-network proof, repository guardrails, active
configuration removal, legacy source removal, then default-build promotion. External deletion is
irreversible and has no automatic rollback.
