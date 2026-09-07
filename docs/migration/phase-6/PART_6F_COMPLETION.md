# Phase 6F completion record

## Status

The project owner authorized Phase 6F on 2026-09-07. The independent review, corrections, and
complete local gate are finished. The path-routed GitHub result and explicit project-owner signoff
remain required to close Phase 6F.

Phase 6G has not started.

## Review result

The independent reviewer recorded six findings in
[`PART_6F_INDEPENDENT_REVIEW.md`](PART_6F_INDEPENDENT_REVIEW.md). The primary implementation pass
resolved all six, and the reviewer confirmed that no finding or regression remains.

The corrections connect strict duplicate-key parsing to routed request bodies without surrendering
validation order to FastAPI, preserve the documented request schema, cancel in-flight work when the
client disconnects, separate every approved user and company rate-limit ceiling, and enforce the
canonical cutover JSON schema before the existing semantic checks.

No Phase 6A contract decision changed. No business route, legacy screen, schema revision, RLS policy,
grant, database function, Keycloak realm setting, or cutover authority changed.

## Verification

Focused checks passed during correction work:

- 61 backend HTTP, sample-route, and rate-limit tests passed after the initial corrections;
- the final 19-test HTTP boundary set covered invalid duplicate precedence, protected-route
  authentication precedence, OpenAPI request-body output, and transaction cleanup after disconnect;
- all 23 cutover record tests passed, including the four new canonical-schema cases; and
- Ruff checks and strict Pyright passed on the affected backend files after the last review change.

The final code-quality gate passed with 355 backend tests, Ruff lint and formatting, strict Pyright,
and `pip check`. It also passed 76 frontend unit tests, both production builds, the frontend
isolation verifier, the canonical cutover template validation, and `git diff --check`. The isolation
verifier scanned 449 legacy modules and 23 migration modules.

The complete full-stack gate used the separate `workloop-phase6f` Compose project with PostgreSQL on
port 15432, FastAPI on port 18000, Keycloak on ports 18080 and 19000, the migration frontend on port
5174, and a fresh temporary volume. It built the Phase 6F backend image once, applied the migration
twice, confirmed the single Alembic head `2c4d6e8f0a1b`, found no model drift, and confirmed
`current_user = session_user = workloop_migration`.

Keycloak was configured once. The Phase 6B HTTP verifier, the Keycloak-to-FastAPI protocol verifier,
and the three-persona browser gate passed before restart. The browser gate covered admin, manager,
and employee authentication, the public and protected sample routes, renewal, restoration,
disabled-account handling, logout, rejected state and nonce values, approved token destinations, and
durable-storage absence.

Before restart, the database fingerprint was `eeb158a9d2fcda117c6d603498d048b2`. The realm exposed two
key IDs, including one RS256 signing key. The gate recreated the isolated containers without
rebuilding. The database fingerprint, both key IDs, all three image identities, and the volume
creation time remained unchanged. The HTTP, protocol, and three-persona browser checks passed again
without reconfiguring Keycloak.

Both log scans found no credential, token, generated secret, identity subject, or account-query leak.
The browser verifier returned all synthetic Workloop rows and Keycloak users to zero. The gate then
removed the isolated containers, network, volume, image, and temporary Compose override.

Historical migration, deep RLS, grant, and database-function checks were not repeated because Phase
6F changes no database boundary.

## Resource and rollback boundary

The existing `workloop-clinic` PostgreSQL, FastAPI, and Keycloak services remain healthy. The running
backend still uses image `sha256:67e0810e4d1ec265d1bf470036c4b5072700218a07888ef1c0e6ad1e5b8c562f`.
The `workloop-clinic_postgres_data` volume still has its `2026-08-31T07:31:48Z` creation time. Phase
6F did not restart, rebuild, attach, upgrade, recreate, or delete that stack or volume.

Verification used local synthetic identities only. It accessed no Supabase account, production data,
SMTP service, paid service, or cloud resource.

Rollback removes the strict request-body dependency and its OpenAPI helper, disconnect monitoring,
the split authenticated rate-limit classes, canonical-schema validation, focused regressions, and
the two Phase 6F records. It requires no schema, data, Keycloak, or legacy-build rollback.

## Stop condition

After the implementation commit passes the path-routed GitHub workflow, Phase 6F still requires the
project owner's explicit signoff on the reviewed Phase 6A through Phase 6F baseline. Stop before
Phase 6G and request separate authorization after that signoff.
