# Phase 3H security, restart, and completion gate

## Status

**The local gate passed on 2026-09-01. Final GitHub confirmation is pending.**

Phase 3H reviews and tests the complete Phase 3 authentication foundation. It adds no account
lifecycle, authorization, business route, migrated feature, schema revision, persistent identity,
cloud resource, SMTP setting, or email delivery.

## Security corrections

The combined review found and corrected these issues:

- Concurrent `oidc-client-ts` user-loaded events and callback handling could send the same account
  check twice. Checks for one in-memory user object now share one request.
- An old account-check response could overwrite a newer expired, rejected, or renewed browser state.
  Account checks now use a session generation and ignore stale results.
- An old `401` cleanup could remove a newer in-memory user. A new user waits for in-flight removal,
  is stored again, and only then runs its FastAPI account check.
- JWT verification now rejects unsupported critical JOSE headers, detached-payload behavior, and RSA
  signing keys smaller than 2048 bits.
- The live realm verifier checks the complete expected client list, both mapper definitions, client
  protocols, refresh behavior, front-channel logout policy, registration policy, and RS256 token
  headers.
- Synthetic cleanup retries exact record removal, checks the whole Workloop realm and all four
  identity tables, and fails if a temporary Keycloak administrator session file remains.
- The migration browser tests now prove fresh 256-bit nonces, early callback URL removal, one account
  request per lifecycle event, failed-callback storage cleanup, logout-callback failure, and stale
  account-response handling.
- The migration output test checks the exact public-configuration boundary with injected secret and
  Supabase sentinels. The development server test checks its `no-referrer` response header.

## Local gate evidence

The locked local gate passed:

- 78 backend tests, Ruff lint and formatting, strict Pyright, and `pip check`.
- 32 Node tests: 14 legacy unit tests, 14 migration authentication tests, and four migration build
  isolation tests.
- The unchanged legacy production build and the isolated migration production build.
- Compose configuration, PostgreSQL, FastAPI, and Keycloak health checks.
- Repeated Alembic upgrade, the empty-schema downgrade boundary, `current`, `heads`, and `check` at
  `f41c9a7b23d1`.
- Live identity constraints, migration ownership, runtime read access, runtime write denial, and the
  running backend's `workloop_runtime` database identity.
- Repeated subject-mapper configuration and the complete Keycloak realm, client, PKCE, JWT, JWKS,
  refresh-rotation, application-user, and generic-failure checks.
- Temporary admin, manager, and employee browser flows covering login, callback, renewal, reload
  restoration, changed email, disabled account, logout, replay, wrong state, and wrong nonce.
- Zero Workloop realm users and zero `companies`, `employees`, `app_users`, and `user_profiles` rows
  after each verifier.
- Migration output and service logs scanned without printing secret values, tokens, database URLs,
  identity subjects, or account-query text.

The first Phase 3H browser run exposed duplicate FastAPI account requests. A later cleanup run failed
because retry logic treated deletion of an already absent user as an error. An expanded output regex
also matched protocol-library words rather than secret values. Focused fixes replaced those checks
with request-count, final-state, and injected-sentinel assertions. All corrected suites passed.

## Restart and persistence

The main Compose project recorded the `workloop-dev` JWKS key identifiers, ran `docker compose down`,
confirmed that `workloop-clinic_postgres_data` still existed, and rebuilt PostgreSQL, FastAPI, and
Keycloak. No volume was removed.

After restart:

- The JWKS key identifiers matched the pre-restart set.
- The realm, clients, subject mapper, and approved policy remained intact.
- FastAPI and Keycloak were healthy.
- Alembic remained at `f41c9a7b23d1` with no metadata drift.
- Database ownership and runtime read-only checks passed.
- Both live authentication verifiers passed again.
- Temporary identities and mappings were absent.
- Restarted service logs passed the sensitive-value scan.

## Independent review

An independent GPT-5.6 review covered the browser session, callback, nonce, renewal, logout, token
destination, JWT, JWKS, account state, CORS, database access, Keycloak policy, synthetic cleanup,
restart, build isolation, logs, and secret handling.

The review found three blocking groups: stale browser account-check races, unverified removal of
Keycloak administrator session files, and incomplete initial and restarted log scans. Two follow-up
passes found narrower asynchronous removal and CI shell-mode defects. The code, tests, cleanup, and
workflow were corrected after each pass. The final review returned no blocking findings.

## GitHub gate

The workflow now runs the migration build explicitly, verifies exact Alembic state and live database
permissions, checks the backend's runtime database identity, scans initial service logs, records
signing-key identifiers, recreates the complete stack without deleting its volume, repeats schema
and authentication checks, compares signing keys, verifies zero retained identities, and scans the
restarted logs. Shell verifiers run through `sh` so Git file mode does not control execution.

The Phase 3H implementation must be pushed and its final GitHub run must pass before this record and
the phase tracker can be marked complete.

## Unchanged boundaries

- The legacy `src/` graph, Supabase client, authentication, and session are unchanged.
- The migration build still rejects legacy `src/` and every `@supabase/*` import and exposes only the
  six approved public configuration names.
- Access, ID, and refresh tokens remain in memory. Session storage contains only temporary redirect
  transaction state.
- Callback parameters leave the URL before application modules load, and referrers remain disabled.
- FastAPI still requires approved RS256 access tokens and exactly one active issuer-and-subject
  mapping. Failures remain generic.
- CORS remains limited to `http://127.0.0.1:5174`, `GET`, and `Authorization`, without credentials.
- FastAPI retains read-only access to the identity schema at `f41c9a7b23d1`.
- The realm source remains sanitized and contains no users, credentials, secrets, SMTP settings, or
  signing keys.
- There is no role, tenant, company, employee, manager, or business authorization; provisioning API;
  runtime Keycloak Admin API access; business route; migrated business screen; DigitalOcean resource;
  SMTP configuration; or email delivery.

## Cost, secrets, and rollback

No external resource or ongoing cost was added. Existing ignored local environment files remain the
only storage for database and Keycloak administrator credentials. Browser and protocol test secrets
remain in process memory. The tests and evidence do not print their values.

Rollback is limited to the Phase 3H authentication hardening, tests, verifiers, workflow checks, and
this evidence. It must not delete the shared PostgreSQL volume, Keycloak realm, signing keys, or the
identity schema. A rollback must keep the earlier Phase 3G security fixes or restore commit
`bd9ecda` as one reviewed boundary.

## Completion gate

The local Phase 3 completion gate passes. Final completion still requires the pushed GitHub checks,
completion evidence with the run identifier, and a clean synchronized branch. Phase 4 remains
unauthorized.
