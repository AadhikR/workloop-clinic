# Phase 3A authentication design

## Status

**Completed and approved on 2026-08-31.**

Phase 3A fixes the names, URLs, browser session behavior, token rules, trust boundaries, and
account-lifecycle defaults that later Phase 3 parts must implement. It changes no runtime code,
database schema, Keycloak realm, user, password, or cloud resource.

## Current constraint

The legacy startup graph initializes Supabase before React renders:

```text
index.html
  -> src/main.jsx
  -> src/App.jsx
  -> src/context/AuthContext.jsx
  -> src/lib/supabase.js
  -> createClient(...)
```

`src/App.jsx` also reaches Supabase through `CompanyContext` and `src/utils/storage.js`. At least 23
modules import the Supabase client directly. Lazy-loading a new login component inside the legacy
application would not isolate authentication.

The migration frontend must therefore have a separate Vite root and module graph. Supabase stays
installed for the legacy build until final cutover.

## Approved identifiers

| Purpose | Value |
|---|---|
| Keycloak realm | `workloop-dev` |
| OIDC issuer | `http://127.0.0.1:8080/realms/workloop-dev` |
| Discovery document | `http://127.0.0.1:8080/realms/workloop-dev/.well-known/openid-configuration` |
| JWKS endpoint | `http://127.0.0.1:8080/realms/workloop-dev/protocol/openid-connect/certs` |
| Public React client | `workloop-migration-web` |
| FastAPI audience | `workloop-api` |
| Legacy frontend | `http://127.0.0.1:5173` |
| Migration frontend | `http://127.0.0.1:5174` |
| Login callback | `http://127.0.0.1:5174/auth/callback` |
| Post-logout destination | `http://127.0.0.1:5174/` |
| FastAPI | `http://127.0.0.1:8000` |

Use `127.0.0.1` consistently. Browsers treat `localhost` and `127.0.0.1` as different origins.
The local Vite servers must use fixed ports with `strictPort: true` so they fail instead of moving
to an unregistered callback port.

Cloud issuer, callback, logout, and origin URLs will be different. Add exact App Platform URLs only
when Phase 6A is authorized. Wildcards remain prohibited.

## Keycloak realm policy

| Setting | Proposed value |
|---|---|
| Realm enabled | Yes |
| Public registration | Disabled |
| Username editing | Disabled |
| Login with email | Enabled |
| Duplicate emails | Disabled |
| Remember me | Disabled |
| Verify email | Disabled until SMTP is approved |
| Password reset | Disabled until SMTP is approved |
| SSL requirement | `external` for local development |
| Default access-token signature | RS256 |
| Access-token lifetime | 5 minutes |
| SSO session idle timeout | 30 minutes |
| SSO session maximum | 8 hours |
| Refresh-token revocation | Enabled |
| Refresh-token maximum reuse | 0 |
| Offline access | Not requested by the React client |
| Brute-force detection | Enabled |
| Failed logins before temporary lockout | 5 |
| Initial wait after threshold | 60 seconds |
| Maximum temporary wait | 15 minutes |
| Failure-count reset window | 12 hours |
| Permanent lockout | Disabled for local development |

The current `workloop-local-admin` remains in Keycloak's `master` realm. It is not a Workloop user
and must never receive a Workloop business role. Its unique password remains local and ignored.

Keycloak supports administrator TOTP, but this design proposes a time-bound local deferral. The
administrator is reachable only through a loopback-bound development service with synthetic data.
TOTP or another approved MFA control becomes mandatory before Phase 6A exposes Keycloak in a
shared cloud environment. The project owner must approve this deferral.

## React client policy

The public React client will use:

- Authorization Code flow only.
- PKCE with `S256`, enforced by Keycloak.
- OIDC `state` and `nonce` validation through the selected library.
- Scopes `openid profile email` only.
- No client secret.
- No implicit flow.
- No Direct Access Grants.
- No service account.
- No wildcard redirect URI or web origin.
- No role, company, employee, manager, or payroll claims as authorization input.

The proposed browser library is `oidc-client-ts` 3.5.0 under the Apache-2.0 license. npm published
that version on 2026-03-13. It supports Authorization Code flow with PKCE, OIDC transaction state,
nonce handling, refresh tokens, and session events. Add and lock it only in the React-auth part.

## Browser storage and renewal

Access, ID, and refresh tokens will remain in memory. They must not be written to local storage,
session storage, IndexedDB, cookies created by Workloop, URLs, logs, or error reports.

The temporary authorization transaction state must survive the browser redirect. The OIDC library
may store only that short-lived state and PKCE verifier in session storage. It must remove them
after callback completion or failure.

While the page remains open, the client may renew with an in-memory refresh token. A full page
reload loses Workloop's token objects. The migration frontend will restore the session with a
top-level OIDC authorization request using `prompt=none` and the existing Keycloak SSO cookie. It
will not depend on a hidden iframe, persistent Workloop token storage, or third-party cookies.

If silent top-level restoration reports `login_required`, the frontend shows the signed-out state
rather than looping. Interactive login then requires a user action.

## Token trust boundary

FastAPI accepts only access tokens intended for `workloop-api`.

Required validation:

```text
signature
issuer
audience
expiry
not-before when present
subject
allowed algorithm RS256
signing key ID
token type where available
```

FastAPI rejects unsigned tokens, symmetric algorithms, ID tokens used as bearer access tokens,
unknown audiences, malformed claims, and algorithm choices supplied by the token. It refreshes
JWKS once for an unknown key ID, then fails closed.

Keycloak proves identity. PostgreSQL decides application status, role, company, employee link, and
manager scope. FastAPI ignores Keycloak realm and client roles for business authorization. Email
is display and invitation data, not an ownership key.

## Application identity and lifecycle

The permanent mapping is:

```text
issuer + subject
  -> app_users
  -> user_profiles
  -> role and company or employee links
```

Application-owned UUIDs remain the primary keys. The Keycloak subject is opaque text.

Provisioning states are:

```text
pending_identity
active
disabled
```

Every protected request checks the current Workloop application-user status. Disabling a Workloop
user blocks access even if an already-issued Keycloak token has not expired.

Initial synthetic provisioning may use a one-shot local administrative command. FastAPI's runtime
container must not receive the master administrator password. Automated provisioning later
requires a separate confidential client with minimum Admin API permissions, idempotent operations,
retry limits, compensation, and reconciliation.

## Frontend isolation design

The migration build will use this separate root:

```text
migration/
  index.html
  src/
    main.jsx
    App.jsx
    index.css
vite.migration.config.js
```

The legacy `index.html`, `src/main.jsx`, `src/App.jsx`, and default scripts remain unchanged. The
migration root will build to `dist-migration` and use strict port 5174.

A Vite pre-enforcement plugin will reject:

- Every module under the legacy root `src/`.
- `@supabase/supabase-js` and every `@supabase/*` package.
- `src/lib/supabase.js` directly or transitively.

The rule applies during development and production builds. CI will build both frontends without
Supabase environment variables, inspect the migration module graph, and scan its output for
Supabase package paths, configured hostnames, and auth-storage markers.

The migration build will use only public values with `VITE_` names:

```text
VITE_API_BASE_URL
VITE_OIDC_AUTHORITY
VITE_OIDC_CLIENT_ID
VITE_OIDC_REDIRECT_URI
VITE_OIDC_POST_LOGOUT_REDIRECT_URI
VITE_OIDC_AUDIENCE
```

Passwords, tokens, private keys, database URLs, and confidential client secrets remain forbidden
in all `VITE_` variables.

## Logging and errors

- React does not log tokens, callback URLs containing authorization codes, PKCE values, or user
  claims.
- FastAPI does not log authorization headers or token bodies.
- Authentication responses use stable 401 and 403 bodies without raw Keycloak, JWT, SQL, or Python
  errors.
- Keycloak event logging will be reviewed before shared deployment.
- Correlation IDs and general API error conventions remain Phase 6 work.

## Deferred items

- SMTP, email verification, and password-reset email delivery remain deferred until an email
  provider and sender domain are approved.
- Administrator MFA is deferred only for loopback local development and is mandatory before Phase
  6A cloud exposure.
- App Platform URLs are added only when cloud architecture proof begins.
- Rate limiting and production browser headers remain required before public use.
- Automated account provisioning with a confidential client is added only when its lifecycle is
  implemented and tested.

## Phase 3 parts

| Part | Scope | Status |
|---|---|---|
| 3A | Authentication design | Completed 2026-08-31 |
| 3B | Minimal identity database schema | Completed 2026-08-31; see [`IDENTITY_SCHEMA.md`](IDENTITY_SCHEMA.md) |
| 3C | Keycloak realm and public clients | Completed 2026-08-31; see [`KEYCLOAK_CONFIGURATION.md`](KEYCLOAK_CONFIGURATION.md) |
| 3D | FastAPI token validation | Completed 2026-08-31; see [`FASTAPI_TOKEN_VALIDATION.md`](FASTAPI_TOKEN_VALIDATION.md) |
| 3E | Application-user resolution | Completed 2026-08-31; see [`APPLICATION_USER_RESOLUTION.md`](APPLICATION_USER_RESOLUTION.md) |
| 3F | Separate React migration build | Completed 2026-08-31; see [`SEPARATE_REACT_MIGRATION_BUILD.md`](SEPARATE_REACT_MIGRATION_BUILD.md) |
| 3G | Synthetic login and account lifecycle | Completed 2026-09-01; see [`SYNTHETIC_LOGIN_AND_ACCOUNT_LIFECYCLE.md`](SYNTHETIC_LOGIN_AND_ACCOUNT_LIFECYCLE.md) |
| 3H | Security, restart, and completion gate | On hold |

## Approved project-owner decisions

The project owner approved:

- The identifiers and exact local URLs.
- `oidc-client-ts` 3.5.0 as the browser protocol library.
- Five-minute access tokens, 30-minute idle sessions, and eight-hour maximum sessions.
- In-memory tokens with session storage limited to temporary redirect state.
- Top-level `prompt=none` session restoration after page reload.
- Public registration, remember-me, Direct Access Grants, implicit flow, service accounts, and
  offline access disabled.
- SMTP, verification, and password-reset email delivery deferred.
- Local administrator MFA deferred until before Phase 6A.
- PostgreSQL as the only source of business roles and authorization scope.
- Physical migration-root isolation from every legacy `src/` and `@supabase/*` module.

## Completion gate

Phase 3A passes because:

- All local identifiers and URLs are fixed and use one canonical hostname.
- Browser flow, storage, renewal, callback, and logout behavior are explicit.
- Keycloak client capabilities and token lifetimes are fixed.
- FastAPI token checks and the PostgreSQL authorization boundary are fixed.
- The legacy and migration frontend module graphs have a testable isolation rule.
- SMTP and local administrator MFA have time-bound deferrals.
- No secret, realm, identity, schema, dependency, or runtime behavior changed.

Phase 3B completed on 2026-08-31. Its implementation and validation are recorded in
[`IDENTITY_SCHEMA.md`](IDENTITY_SCHEMA.md).

Phase 3C completed on 2026-08-31. Its implementation, protocol tests, and security review are
recorded in [`KEYCLOAK_CONFIGURATION.md`](KEYCLOAK_CONFIGURATION.md).

Phase 3D completed on 2026-08-31. Its bearer dependency, JWKS cache behavior, live token checks,
failure tests, and security review are recorded in
[`FASTAPI_TOKEN_VALIDATION.md`](FASTAPI_TOKEN_VALIDATION.md).

Phase 3E completed on 2026-08-31. Its issuer-and-subject lookup, account-state checks,
failure behavior, live tests, and independent security review are recorded in
[`APPLICATION_USER_RESOLUTION.md`](APPLICATION_USER_RESOLUTION.md).

Phase 3F completed on 2026-08-31. It adds the separate migration Vite root, fixed development port,
Supabase and legacy-source import isolation, public-configuration allowlist, and automated output
checks. GitHub Actions run 21 passed its frontend, backend, full-stack authentication, realm-upgrade,
and persistence checks. See
[`SEPARATE_REACT_MIGRATION_BUILD.md`](SEPARATE_REACT_MIGRATION_BUILD.md).

Phase 3G completed on 2026-09-01. It adds the approved browser login,
restoration, renewal, callback, logout, and account-state behavior plus temporary three-persona
browser tests. GitHub Actions run 24 passed the implementation and persistence gates. See
[`SYNTHETIC_LOGIN_AND_ACCOUNT_LIFECYCLE.md`](SYNTHETIC_LOGIN_AND_ACCOUNT_LIFECYCLE.md).

## Next model recommendation

Use **GPT-5.6** for Phase 3H because it is the final authentication security and restart gate. It
must review the combined realm, browser, token, application-user, persistence, and cleanup behavior.
Phase 3H remains on hold and requires separate project-owner authorization.

### Phase 3H handoff prompt

```text
Continue the Workloop Clinic migration with Phase 3H only: the authentication security, restart,
and completion gate.

Read AGENTS.md, DIGITALOCEAN_MIGRATION_PLAN.md, the Phase 2 foundation records, and every Phase 3
design and evidence document. Inspect the synchronized migration/fastapi-keycloak branch, both Vite
graphs, browser login lifecycle, FastAPI token and application-user boundaries, Keycloak realm,
Compose stack, Alembic state, tests, and GitHub checks.

Expected state: Phase 3A through Phase 3G are complete; temporary synthetic admin, manager, and
employee browser flows pass; no persistent Workloop user, provisioning API, role or tenant
authorization, business route, migrated business feature, cloud resource, SMTP, or email delivery
exists.

Do not begin without explicit Phase 3H authorization. When authorized, perform only the approved
combined security, restart, persistence, cleanup, and Phase 3 completion gate. Preserve the legacy
Supabase build, migration isolation, identity revision f41c9a7b23d1, read-only runtime identity
access, and all existing generic failures. Stop for every owner decision, obtain an independent
security review, update evidence, commit and push only after the gate passes, and stop before Phase
4.
```
