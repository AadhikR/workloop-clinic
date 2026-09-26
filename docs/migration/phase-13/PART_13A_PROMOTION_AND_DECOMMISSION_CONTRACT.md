# Part 13A promotion and decommission contract

## Contract status

This contract governs Parts 13B through 13H. It changes no runtime, package, build default, schema,
secret, cloud resource, or external service in Part 13A. If a later implementation choice conflicts
with this contract, the later part must choose the narrower fail-closed behavior and record the
reason before its gate.

## Canonical application promotion

Part 13B changes the ordinary frontend commands as one bounded promotion:

| Command or consumer | Required target after 13B |
| --- | --- |
| `npm run dev` | Migration application on `127.0.0.1:5174`, with strict port selection |
| `npm run build` | Migration application output in `dist-migration` |
| `npm run preview` | The settled migration output on `127.0.0.1:5174` |
| Frontend regression job | The same default build and output |
| DigitalOcean static component | The same promoted command and `dist-migration` output |
| Browser journey and backend origin | `http://127.0.0.1:5174` |

Part 13B may add `dev:legacy`, `build:legacy`, and `preview:legacy` as temporary rollback commands.
Their names must contain `legacy`. No environment value, missing file, failed migration build, or
runtime exception may select or fall back to the legacy application. CI and deployment must never
call a legacy command.

Part 13C moves the migration entry point, source, assets, tests, and configuration into the canonical
root paths. The canonical production output becomes `dist`. Part 13C then removes the frozen legacy
source, browser generators, Supabase client calls, legacy-only assets, temporary legacy commands,
dual-build isolation, and `dist-migration` path. The move and removal form one reviewable change so
the repository never has two unlabeled canonical applications.

## Public frontend configuration

After 13C, the only public frontend environment names are:

- `VITE_API_BASE_URL`
- `VITE_OIDC_AUTHORITY`
- `VITE_OIDC_CLIENT_ID`
- `VITE_OIDC_REDIRECT_URI`
- `VITE_OIDC_POST_LOGOUT_REDIRECT_URI`
- `VITE_OIDC_AUDIENCE`

Part 13D removes `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and
`SUPABASE_SERVICE_ROLE_KEY` from active source, examples, allowlists, CI, Compose, infrastructure,
bootstrap helpers, tests that no longer need them, and deployment inputs. It removes
`@supabase/supabase-js` and all `@supabase/*` transitive lockfile packages. No compatibility shim,
optional flag, dummy client, dead dynamic import, or build alias may retain them.

An absent forbidden variable must have no effect. A hostile value must also have no effect. Tests
must use reserved invalid hosts and unmistakable sentinel strings. They must not reuse a real project
reference or credential-shaped value.

## Five service classes

The canonical application must meet all five conditions:

| Service class | Required result |
| --- | --- |
| Auth | No Supabase session, login, logout, signup, password reset, token, or auth-state listener |
| Tables and PostgREST | No Supabase table query, REST endpoint, client chain, or generated URL |
| RPC | No Supabase function invocation or `/rest/v1/rpc` request |
| Realtime | No package, channel, subscription, WebSocket endpoint, or external publication dependency |
| Storage | No Supabase bucket client, signed URL, object endpoint, or browser upload path |

FastAPI, portable PostgreSQL, Keycloak, and the approved private object-storage adapters remain the
only active owners of those responsibilities.

## Active and historical material

Active paths include application source, package manifests, lockfiles, environment examples, build
configuration, CI, Compose, infrastructure, database bootstrap, current tests, and current setup,
architecture, deployment, recovery, and contributor instructions. These paths may mention Supabase
only inside an approved inert negative proof.

Historical material may retain a reference when every condition below holds:

- The file explains a past source system, migration decision, cutover, schema mapping, or rollback
  record.
- It lives outside active build, deployment, bootstrap, and fixture inputs.
- A nearby label says that the material is historical and not an instruction to run.
- The permanent repository guard lists the path or a narrow path class.
- Production source and built output cannot import or copy it.

Append-only Alembic revisions may retain source-system terms needed to explain an existing revision.
Part 13E must not rewrite revision history. Root Supabase SQL and the `sql/` directory are historical,
not active bootstrap inputs. Part 13E labels or relocates them without changing the database schema.
Alembic remains at one head, `e8a1c3f5b7d9`.

An inert negative proof may contain forbidden package names, environment names, hosts, service names,
or call strings only as fixture data or an assertion target. The guard must reject an executable
import, configuration input, network destination, copied build asset, or unlabeled file using the
same text.

## Clean install and no-network proof

Part 13F starts from a clean checkout or equivalent disposable copy and a clean dependency install.
No Supabase variable, credential, host mapping, account, bucket, or project access may be present.
It must:

1. Install locked dependencies and prove that no direct or transitive `@supabase/*` package exists.
2. Build the canonical production graph and scan module IDs and emitted bytes.
3. Start a named disposable stack, apply migrations twice, and run the approved role, API, file, and
   output journeys.
4. Detect DNS, TCP, TLS, HTTP, HTTPS, WebSocket, PostgreSQL, and object-storage attempts whose host,
   address, header, path, or protocol identifies Supabase.
5. Restart existing images without rebuilding and compare database, signing-key, and stored-object
   state.
6. Remove only the named disposable resources.

An attempted connection fails the proof even when it cannot resolve or connect. A network capture,
instrumented resolver and client harness, or equivalent fail-closed mechanism is acceptable only if
it covers the frontend build, browser, backend, command workers, test helpers, and restart journey.
Package-registry traffic needed for the clean install is outside the runtime network assertion. The
installed graph must still contain no Supabase package or tarball.

The proof must confirm that `workloop-clinic_postgres_data` exists only by safe name inspection when
needed. It must not attach, mount, modify, delete, or recreate that volume.

## Retention evidence

Part 13G begins with read-only discovery. It creates a target manifest outside any destructive
command path. The manifest records non-secret facts only:

- exact organization and project identifiers;
- Auth user and metadata counts, with no passwords or tokens;
- database schema objects, table row counts, RPC names, and export digest;
- Realtime publication and channel configuration;
- bucket names, object keys or safely escaped manifests, object counts, byte counts, and SHA-256
  digests;
- API key identifiers or safe suffixes, never values;
- exact GitHub repository, environment, and secret entry names;
- exact DigitalOcean app, component, and secret entry names;
- encrypted export location outside Git, custodian, encryption owner, and restore evidence; and
- retention start and deadline in UTC.

The export must cover the approved database, Auth metadata needed for audit or restoration, and
private objects. The restore runs in an isolated disposable target. It must reproduce the recorded
schema, row counts, Auth metadata counts, object counts, byte counts, and digests. A provider status
page, download success, or archive listing is not restore proof.

The minimum retention period is 30 calendar days. It starts only when the isolated restore passes.
The owner may extend the deadline. No task may shorten it. A failed or incomplete restore resets the
start condition rather than preserving an earlier deadline.

## Exact approval gate

Phase 13 authorization does not authorize external destruction. After the restore passes and the
retention deadline has elapsed, Part 13G must obtain fresh owner approval for each exact target class.
The request names:

- each API key identifier to revoke;
- each GitHub repository or environment and secret entry to delete;
- each DigitalOcean app or component and secret entry to delete;
- each bucket and its approved object set to delete; and
- the exact external project identifier to delete.

Approval for one target does not cover another. Wildcards, phrases such as "everything old",
inferred intent, old phase approval, and approval that predates the settled manifest are invalid.
Missing access, mismatched identifiers, new objects, changed counts, changed digests, failed restore,
unexpired retention, or uncertain owner identity stops destructive work.

Part 13G records non-secret receipts after each approved action. It must not print secret values,
private object contents, exports, passwords, access tokens, or personal data.

## Rollback

Before external destruction, repository rollback proceeds in this order:

1. Stop the 13F disposable proof and preserve its evidence.
2. Revert the 13E guard and documentation changes.
3. Restore the 13D package and configuration boundary only from the 13C commit.
4. Restore the 13C legacy tree before changing active commands.
5. Restore the 13B command mapping last.

Never enable a Supabase reader, writer, or session path while the promoted replacement remains the
active authority for the same behavior. A rollback cannot be selected automatically after a build or
runtime failure.

External deletion has no repository rollback. No task may recreate a deleted project, key, secret,
bucket, object, Auth user, or database as an automatic response. Recovery uses the verified encrypted
export only after a new owner-approved target and security decision.

## Part gates

Each part must close every catalogue entry it owns, run its focused checks, run one boundary-matched
local gate, push once, and pass every routed GitHub job. Part 13H traces every catalogue entry and
golden case. It also checks clean setup evidence, no-network evidence, secret-store discovery,
retention and restore evidence, exact approval receipts, external state, rollback order, and cleanup.
