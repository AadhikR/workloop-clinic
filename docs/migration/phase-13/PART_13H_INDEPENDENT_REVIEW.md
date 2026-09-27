# Part 13H independent review

## Review method

This review starts from the repository and settled manifests at commit
`60dcd7257e824669566f933603ff257461839fe3`. Earlier completion records supply context, but they do
not count as independent proof. The review follows each catalogue entry and golden case to current
source, tests, build configuration, workflow checks, or a digest-bound external record.

The repository evidence is enough to decide whether the retained Supabase project has an active
Workloop dependency. No new external inspection was needed. Part 13H did not contact or change the
project, its Auth data, database, keys, buckets, objects, or encrypted export.

## Findings and closure

The review found one bookkeeping gap. `dependency-catalogue.json` had no 13B closure object even
though the 13B completion record, tests, source, and deployment configuration proved all six 13B
dependencies and six golden cases. Part 13H added that missing closure from current evidence. It did
not change runtime behavior.

No active-runtime, package, source, document, history-label, clean-setup, network, retention,
rollback, log-safety, or cleanup defect was found. The focused verifier now rejects omitted or
duplicate trace rows, missing owner closures, active retired-provider markers, a changed 13G manifest
binding, a second Alembic head, or removal of a required closing-gate layer.

## Dependency trace

| ID | Canonical evidence | Review result |
| --- | --- | --- |
| `P13-BLD-001` | `package.json`; `tests/phase-13b-promotion.test.js` | `dev`, `build`, and `preview` select the canonical Vite application. |
| `P13-BLD-002` | `package.json`; `vite.config.js` | Migration-specific commands and configuration paths are gone. |
| `P13-BLD-003` | `index.html`; `vite.config.js`; `tests/phase-13c-canonical-frontend.test.js` | One root entry point uses port 5174 and output `dist`. |
| `P13-BLD-004` | `.github/workflows/migration-foundation.yml`; `infra/digitalocean/main.tf` | CI and deployment use `npm run build` and `dist`. |
| `P13-BLD-005` | `docker-compose.yml`; `backend/.env.example`; `scripts/new-local-postgres-env.ps1` | Backend and local configuration use the canonical frontend origin. |
| `P13-BLD-006` | `vite.config.js`; `.env.example` | The public environment allowlist contains only API and OIDC inputs. |
| `P13-SRC-001` | `src`; `tests/phase-13c-canonical-frontend.test.js` | The 75-file promoted source graph is the canonical frontend. |
| `P13-SRC-002` | `docs/migration/phase-13/PART_13C_REMOVAL_INVENTORY.json`; `tests/phase-13c-canonical-frontend.test.js` | The 96-file legacy graph is absent. |
| `P13-SRC-003` | `tests/phase-13c-canonical-frontend.test.js` | Dual-build isolation files and commands are absent. |
| `P13-SRC-004` | `docs/migration/phase-13/PART_13C_REMOVAL_INVENTORY.json`; `tests/phase-13c-canonical-frontend.test.js` | Legacy freeze tests are accounted for and removed. |
| `P13-SRC-005` | `docs/migration/phase-13/PART_13C_REMOVAL_INVENTORY.json`; `tests/phase-13c-canonical-frontend.test.js` | All six retained Phase 12 dependencies closed with their legacy consumers. |
| `P13-SVC-001` | `src`; `tests/phase-13c-canonical-frontend.test.js` | Canonical source contains no Supabase Auth client or listener. |
| `P13-SVC-002` | `src`; `tests/phase-13c-canonical-frontend.test.js` | Canonical source contains no table or PostgREST client call. |
| `P13-SVC-003` | `src`; `tests/phase-13c-canonical-frontend.test.js` | Canonical source contains none of the eight retired RPC calls. |
| `P13-SVC-004` | `package-lock.json`; `tests/phase-13d-runtime-removal.test.js` | No direct or transitive Realtime package remains. |
| `P13-SVC-005` | `src`; `tests/phase-13c-canonical-frontend.test.js` | Canonical source contains no retired bucket client or URL. |
| `P13-PKG-001` | `package.json`; `tests/phase-13d-runtime-removal.test.js` | The direct client package is absent. |
| `P13-PKG-002` | `package-lock.json`; `scripts/verify-phase-13f-clean-setup.mjs` | All six transitive packages are absent from the lockfile and clean install. |
| `P13-ENV-001` | `.env.example`; `.env.test.example`; `tests/phase-13d-runtime-removal.test.js` | Both public retired-provider variables are absent from active configuration. |
| `P13-ENV-002` | `.env.test.example`; `tests/phase-13d-runtime-removal.test.js` | The service-role variable is absent from active test configuration. |
| `P13-ENV-003` | `.env.example`; `.env.test.example`; `tests/phase-13d-runtime-removal.test.js` | No checked-in retired URL or credential-shaped example remains. |
| `P13-HIS-001` | `docs/history/legacy-supabase-sql/README.md`; repository guard | Historical SQL is isolated, labeled, and outside active inputs. |
| `P13-HIS-002` | `backend/HISTORICAL_SOURCE_TERMS.md`; repository guard | Append-only backend source terms are labeled and narrowly allowlisted. |
| `P13-HIS-003` | `docs/migration/HISTORICAL_RECORDS.md`; repository guard | Phase 0 through Phase 12 records carry one historical label. |
| `P13-DOC-001` | Current-document set; `scripts/verify-phase-13h-review.mjs` | Current setup and architecture documents contain no retired-runtime instruction. |
| `P13-DOC-002` | `docs/migration/phase-13`; repository guard | Current Phase 13 evidence is explicitly classified. |
| `P13-DOC-003` | `FEATURES_ROADMAP.md`; `tests/phase-13e-repository-guard.test.js` | The legacy generator is absent and the roadmap is canonical. |
| `P13-DOC-004` | `docs/history/legacy-feature-list/README.md`; digest-pinned PDF | The PDF is unchanged and labeled as history. |
| `P13-TST-001` | `tests/fixtures/phase-13e`; repository guard tests | Frontend markers remain only as inert negative proof. |
| `P13-TST-002` | `scripts/phase-13e-retired-runtime-allowlist.json`; repository guard tests | Verifier markers remain only in exact reviewed paths. |
| `P13-GRD-001` | `scripts/verify-phase-13e-repository-guard.mjs`; workflow | The exact-path repository guard runs for every change. |
| `P13-DB-001` | Alembic revision graph; `tests/phase-13h-review.test.js` | One head remains at `e8a1c3f5b7d9`. |
| `P13-NET-001` | `scripts/verify-phase-13f-clean-setup.mjs`; workflow | Fresh locked install, graph scan, and deterministic production builds remain routed. |
| `P13-NET-002` | `scripts/phase-13f-network-guard.mjs`; `tests/phase-13f-clean-setup.test.js` | DNS attempts fail before resolution. |
| `P13-NET-003` | Node, Python, and browser guards; Phase 13F tests | HTTP, WebSocket, PostgreSQL, and object-storage attempts fail before connection handling. |
| `P13-NET-004` | `docker-compose.phase13f.yml`; workflow | The named disposable stack runs without retired-provider access. |
| `P13-EXT-001` | `PART_13G_TARGET_MANIFEST.json`; 13G boundary verifier | The exact organization and project identity are resolved. |
| `P13-EXT-002` | `PART_13G_TARGET_MANIFEST.json`; digest-bound restore evidence | Auth counts are recorded without secret or personal values. |
| `P13-EXT-003` | `PART_13G_TARGET_MANIFEST.json`; digest-bound restore evidence | Database objects, counts, and RPC names are recorded and restored. |
| `P13-EXT-004` | `PART_13G_TARGET_MANIFEST.json`; storage metadata digests | Both buckets, counts, byte totals, and digests are recorded. |
| `P13-EXT-005` | `PART_13G_TARGET_MANIFEST.json` | Realtime settings and empty publication membership are recorded. |
| `P13-EXT-006` | `PART_13G_TARGET_MANIFEST.json` | Only safe API key identifiers are recorded. |
| `P13-EXT-007` | `PART_13G_TARGET_MANIFEST.json` | GitHub store names are resolved and contain no entries. |
| `P13-EXT-008` | `PART_13G_TARGET_MANIFEST.json` | The resolved DigitalOcean team has no App Platform applications. |
| `P13-DEL-001` | Retention decision; empty approval manifest | Keys and secret-store targets remain preserved and denied. |
| `P13-DEL-002` | Retention decision; storage manifests | Both buckets and their objects remain preserved and denied. |
| `P13-DEL-003` | Retention decision; exact project target | The project remains an archive and deletion is denied. |
| `P13-RET-001` | Export and restore sections of `PART_13G_TARGET_MANIFEST.json` | Encrypted artifact digests and matching isolated restore evidence are bound together. |
| `P13-RET-002` | Retention section of `PART_13G_TARGET_MANIFEST.json` | The passed restore starts the minimum, and the owner extends it indefinitely. |
| `P13-APR-001` | `scripts/verify-phase-13g-decommission.mjs`; 13G denial tests | Phase, partial, wildcard, stale, and absent approvals remain denied. |

## Golden-case proof map

| ID | Canonical proof | Result |
| --- | --- | --- |
| `13A-GC-001` | 13B promotion test; `package.json`; `vite.config.js` | Default development selects one app on strict port 5174. |
| `13A-GC-002` | 13B and 13C build tests | Default build produces only the canonical app. |
| `13A-GC-003` | 13B promotion test; `vite.config.js` | Default preview serves `dist` on strict port 5174. |
| `13A-GC-004` | Workflow frontend job | CI consumes the default canonical build. |
| `13A-GC-005` | `infra/digitalocean/main.tf`; 13B promotion test | Deployment uses the same command and output. |
| `13A-GC-006` | Source scan; 13C canonical test | No Auth client or listener remains. |
| `13A-GC-007` | Source scan; 13C canonical test | No table or PostgREST call remains. |
| `13A-GC-008` | Source scan; 13C canonical test | No retired RPC call remains. |
| `13A-GC-009` | Lockfile, installed-tree, module, and byte scans | No Realtime dependency remains. |
| `13A-GC-010` | Source scan; 13C canonical test | No Storage client or bucket URL remains. |
| `13A-GC-011` | 13F clean verifier | Absent hostile variables pass. |
| `13A-GC-012` | 13F deterministic hostile build and network guard | Hostile URL cannot affect output or network. |
| `13A-GC-013` | 13F emitted-byte comparison | Hostile anonymous-key sentinel cannot enter output or state. |
| `13A-GC-014` | 13F process environment proof | Hostile service-role sentinel cannot enter an unowned process. |
| `13A-GC-015` | Repository guard negative fixture | A direct package import fails. |
| `13A-GC-016` | Guard fixtures plus clean module scan | Transitive, dynamic, aliased, and dead-code imports fail. |
| `13A-GC-017` | Node and Python guard fixtures | A DNS attempt fails before resolution. |
| `13A-GC-018` | Node HTTP and HTTPS guard fixtures | A request fails before response handling. |
| `13A-GC-019` | Node and browser WebSocket guards | A Realtime connection attempt fails. |
| `13A-GC-020` | TCP, Python socket, and object-storage fixtures | Database and object-storage attempts fail. |
| `13A-GC-021` | History labels and exact allowlist | Needed historical records remain inert and labeled. |
| `13A-GC-022` | Unlabeled-history negative fixture | An unapproved historical copy fails. |
| `13A-GC-023` | Current-document scan | Current instructions cannot configure the retired runtime. |
| `13A-GC-024` | 13G GitHub discovery manifest | Exact store names appear without values. |
| `13A-GC-025` | 13G DigitalOcean discovery manifest | Exact team and application result appear without values. |
| `13A-GC-026` | 13G action evaluator tests | Missing discovery blocks deletion and creates no guessed target. |
| `13A-GC-027` | 13G export manifest and verifier | Location, owner, counts, bytes, and digests are recorded. |
| `13A-GC-028` | 13G restore comparison | Schema, counts, Auth metadata, and storage digests match. |
| `13A-GC-029` | 13G action evaluator | Destruction remains denied before the minimum deadline. |
| `13A-GC-030` | 13G retention validation | Retention starts after restore and cannot be shortened. |
| `13A-GC-031` | Empty approval manifest and denial tests | Phase authorization grants no destruction. |
| `13A-GC-032` | Exact-target action fixtures | One target approval never unlocks another. |
| `13A-GC-033` | Broad, partial, stale, and changed-target fixtures | Ambiguous approval fails closed. |
| `13A-GC-034` | 13B closure plus current command scan | The temporary rollback command was explicit and is now removed. |
| `13A-GC-035` | Promotion contract and 13H verifier | Rollback order remains 13F, 13E, 13D, 13C, then 13B. |
| `13A-GC-036` | 13G verifier source scan | No project recreation path exists. |
| `13A-GC-037` | Alembic graph scan | One head remains at `e8a1c3f5b7d9`. |
| `13A-GC-038` | Repository guard | Every marker-bearing file receives one exact classification. |
| `13A-GC-039` | Repository guard | Every other file is counted as reference-free. |
| `13A-GC-040` | Workflow cleanup rule; volume name inspection | The protected volume is never a cleanup target. |
| `13A-GC-041` | 13F clean verifier and workflow frontend job | Fresh install and production build pass without the retired package. |
| `13A-GC-042` | Phase 13F overlay, process guards, and browser wrapper | The disposable setup has no credential, mapping, account, or network exception. |

## Closing-gate review

The canonical runtime is React, Keycloak, FastAPI, portable PostgreSQL, and private object storage.
The ordinary commands, Vite configuration, CI, and DigitalOcean configuration select that runtime.
The production source, package manifest, lockfile, module graph, emitted bytes, environment examples,
Compose inputs, infrastructure, and current documents contain no active Supabase dependency.

The closing workflow runs the exact-path repository guard, this independent verifier, a fresh locked
install, the canonical build, the complete unit suite, the disposable full stack, repeatable
migrations, one-head and pending-operation checks, process-level no-network guards, service health,
authentication, persisted-state comparison, the complete three-role browser journey, synthetic-data
cleanup, log-safety checks, and exact disposable-volume cleanup.

The rollback order remains fixed. Stop and preserve 13F proof first, revert 13E guardrails and docs,
restore 13D packages and configuration only from the 13C boundary, restore the 13C legacy tree, and
restore 13B command selection last. No rollback may enable two runtime authorities. External
deletion has no automatic rollback and remains outside Phase 13.

## Retained external project

The target manifest resolves organization `otqemcwkpkyhpncmxldm` and project
`dabphibgpamsfoxfhwmu`. Its verified encrypted export and isolated restore share the same evidence
digest. The approval manifest is bound to the settled target-manifest digest, has status `retained`,
and contains no approval.

The project is archive-only. Current source, packages, configuration, builds, tests, deployment, and
runtime network proof do not depend on it. Indefinite retention preserves the project, keys, Auth
records, database, Realtime settings, buckets, and objects. A future change requires new scope, a
fresh target manifest, and fresh exact approvals.

## Resource boundary

The review uses repository state, synthetic local data, and named disposable services. It does not
read private records or reveal credentials. `workloop-clinic_postgres_data` remains a protected name
only and is never attached, mounted, modified, deleted, or recreated. Cleanup may remove only the
verified Part 13H disposable project and its three named volumes.
