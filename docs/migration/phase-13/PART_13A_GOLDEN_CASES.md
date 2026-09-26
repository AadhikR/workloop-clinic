# Part 13A golden cases

## Use

These cases are fixed acceptance inputs for Parts 13B through 13H. The machine-readable copies live
in `docs/migration/phase-13/dependency-catalogue.json`. A later part may add narrower cases, but it
must not weaken, renumber, or silently drop these cases.

## Cases

| ID | Owner | Area | Expectation |
| --- | --- | --- | --- |
| `13A-GC-001` | 13B | default command | npm run dev starts only the migration application on the fixed migration port. |
| `13A-GC-002` | 13B | default command | npm run build builds only the migration application. |
| `13A-GC-003` | 13B | default command | npm run preview serves only the promoted migration output. |
| `13A-GC-004` | 13B | CI | The ordinary CI frontend build consumes the promoted application and its declared output. |
| `13A-GC-005` | 13B | deployment | The DigitalOcean static component consumes the same promoted command and output as CI. |
| `13A-GC-006` | 13C | Auth | No canonical source imports or calls Supabase Auth, including auth-state listeners. |
| `13A-GC-007` | 13C | tables | No canonical source uses Supabase table or PostgREST calls. |
| `13A-GC-008` | 13C | RPC | No canonical source uses Supabase RPC calls. |
| `13A-GC-009` | 13D | Realtime | No direct, transitive, bundled, or configured Supabase Realtime dependency remains. |
| `13A-GC-010` | 13C | Storage | No canonical source uses Supabase Storage calls or bucket URLs. |
| `13A-GC-011` | 13F | absent environment | The clean setup passes with all Supabase variables absent. |
| `13A-GC-012` | 13F | hostile environment | A hostile VITE_SUPABASE_URL value cannot change the build or cause a lookup or request. |
| `13A-GC-013` | 13F | hostile environment | A hostile VITE_SUPABASE_ANON_KEY value cannot enter output or runtime state. |
| `13A-GC-014` | 13F | hostile environment | A hostile SUPABASE_SERVICE_ROLE_KEY value cannot enter a process that does not own it. |
| `13A-GC-015` | 13E | direct import | The repository guard rejects a direct @supabase package import in active code. |
| `13A-GC-016` | 13E | transitive import | The repository guard and module scan reject transitive, dynamic, aliased, and dead-code Supabase imports. |
| `13A-GC-017` | 13F | DNS | Any Supabase DNS lookup attempt fails the no-network proof even when resolution fails. |
| `13A-GC-018` | 13F | HTTP | Any Supabase HTTP or HTTPS request attempt fails the no-network proof before response handling. |
| `13A-GC-019` | 13F | WebSocket | Any Supabase WebSocket or Realtime connection attempt fails the no-network proof. |
| `13A-GC-020` | 13F | database and storage network | Any Supabase PostgreSQL or object-storage connection attempt fails the no-network proof. |
| `13A-GC-021` | 13E | historical file | A needed historical SQL or migration record remains outside active paths with an explicit history label. |
| `13A-GC-022` | 13E | historical file | An unlabeled Supabase file outside the approved historical allowlist fails the repository guard. |
| `13A-GC-023` | 13E | current documentation | Current setup and architecture instructions cannot direct a reader to Supabase runtime setup. |
| `13A-GC-024` | 13G | GitHub secrets | Read-only discovery records exact GitHub store and entry names without values. |
| `13A-GC-025` | 13G | DigitalOcean secrets | Read-only discovery records exact DigitalOcean app and entry names without values. |
| `13A-GC-026` | 13G | secret discovery | Missing access or unresolved secret names blocks deletion and produces no guessed target. |
| `13A-GC-027` | 13G | backup | The encrypted export manifest records location, owner, object counts, byte counts, and SHA-256 digests outside Git. |
| `13A-GC-028` | 13G | restore | An isolated restore reproduces schema, row counts, Auth metadata counts, object counts, and recorded digests. |
| `13A-GC-029` | 13G | retention | No destructive action occurs before the thirty-day minimum retention deadline. |
| `13A-GC-030` | 13G | retention | A deadline is set only after a successful restore and cannot be shortened. |
| `13A-GC-031` | 13G | approval | Phase authorization alone does not authorize an external deletion or revocation. |
| `13A-GC-032` | 13G | approval | Approval for one key, secret, bucket, object set, or project does not authorize any other target. |
| `13A-GC-033` | 13G | approval | Wildcard, inferred, ambiguous, or stale approval is denied. |
| `13A-GC-034` | 13B | rollback | The temporary legacy rollback command is explicit and never selected by environment or fallback. |
| `13A-GC-035` | 13F | rollback | Repository rollback follows 13F, 13E, 13D, 13C, then 13B without mixing active runtimes. |
| `13A-GC-036` | 13G | rollback | External deletion has no automatic rollback and never recreates a project. |
| `13A-GC-037` | 13E | schema | The Alembic head remains e8a1c3f5b7d9 and 13A creates no schema revision. |
| `13A-GC-038` | 13E | coverage | Every tracked file containing a Supabase marker matches exactly one coverage group. |
| `13A-GC-039` | 13E | coverage | Every other tracked file is counted as inspected and reference-free. |
| `13A-GC-040` | 13F | preserved resource | The workloop-clinic_postgres_data volume is never attached, modified, deleted, or recreated. |
| `13A-GC-041` | 13F | clean install | A fresh locked dependency install and production build pass without a Supabase account or package. |
| `13A-GC-042` | 13F | clean setup | The disposable setup has no Supabase credential, host mapping, bucket, project access, or network exception. |

## Fixed fixtures and denial rules

Hostile environment tests use reserved invalid hostnames and sentinel values that cannot be mistaken
for a credential. A hostile value is present in the process environment but must not be read, copied
to output, logged, resolved, or requested.

Import tests cover static imports, dynamic imports, package subpaths, aliased paths, a transitive
fixture, and code that a bundler could otherwise discard. Network tests record attempts before name
resolution or response handling, so a blocked connection still fails.

Historical-file tests need one allowed labeled record, one unlabeled copy in an unapproved path, and
one current instruction that tries to configure the retired service. The first passes. The other two
fail.

Approval tests use separate targets for a key, a GitHub secret, a DigitalOcean secret, a bucket and
object set, and the project. Approval for one fixture never unlocks the others. The destructive
adapter remains disabled until every prerequisite in the promotion and decommission contract passes.
