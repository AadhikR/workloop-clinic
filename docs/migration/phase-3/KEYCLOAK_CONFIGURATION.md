# Phase 3C Keycloak configuration

## Status

**Completed on 2026-08-31.**

Phase 3C adds the local `workloop-dev` realm, the restricted
`workloop-migration-web` public client, and the `workloop-api` resource audience. It does not add
FastAPI token validation, application-user lookup, a migration frontend, account provisioning, or
a persistent Keycloak user.

## Realm source

`keycloak/realm/workloop-dev-realm.json` is the reviewed source configuration. Docker Compose
mounts the directory read-only at `/opt/keycloak/data/import` and starts Keycloak with
`--import-realm`.

The file contains no users, credentials, client secrets, tokens, SMTP settings, private keys,
public keys, certificates, generated signing keys, or generated object IDs. Keycloak creates its
local signing keys in PostgreSQL on first import. Startup import skips an existing realm, which
preserves realm state and signing keys across container replacement. It does not reconcile later
changes to the JSON into an existing realm.

## Realm policy

The imported realm uses these approved settings:

| Setting | Value |
|---|---|
| Realm | `workloop-dev` |
| Issuer | `http://127.0.0.1:8080/realms/workloop-dev` |
| SSL requirement | `external` for loopback development |
| Token signature | RS256 |
| Access-token lifetime | 5 minutes |
| SSO idle timeout | 30 minutes |
| SSO maximum | 8 hours |
| Refresh-token revocation | Enabled |
| Refresh-token reuse | 0 |
| Public registration | Disabled |
| Remember me | Disabled |
| Email verification | Disabled until SMTP is approved |
| Password-reset email | Disabled until SMTP is approved |
| SMTP configuration | Empty |
| Brute-force detection | Enabled |
| Failure threshold | 5 |
| Initial wait | 60 seconds |
| Maximum wait | 15 minutes |
| Failure reset window | 12 hours |
| Permanent lockout | Disabled for local development |

The local bootstrap administrator remains in the `master` realm. It is not a Workloop identity.
Its ignored local credential is not present in the realm file or test output.

## Client policy

`workloop-migration-web` is a public OIDC client with no secret. Its only login callback is:

```text
http://127.0.0.1:5174/auth/callback
```

Its only post-logout destination and web origin are:

```text
http://127.0.0.1:5174/
http://127.0.0.1:5174
```

The client enables Authorization Code flow and enforces PKCE `S256`. Implicit flow, Direct Access
Grants, service accounts, authorization services, token exchange, device authorization, CIBA, and
JWT authorization grants are disabled. Wildcard redirects and origins are absent. The assigned
scopes are `profile` and `email`; `offline_access` is neither a default nor optional client scope.

`workloop-api` is a bearer-only resource client. It has no login flow, service account, redirect,
origin, or assigned client scope. The browser client's audience mapper adds `workloop-api` only to
access tokens. ID tokens retain `workloop-migration-web` as their audience.

## Automated checks

`scripts/verify-phase-3c-keycloak.py` checks the source file, imported Admin API representation,
and OIDC endpoints. It verifies:

- The source file has no user, credential, secret, token, SMTP credential, or signing-key fields.
- Realm lifetimes, refresh rotation, brute-force controls, registration, remember-me, and email
  flags match the approved values.
- The browser client has one exact callback, logout URL, and origin.
- PKCE without a challenge and PKCE `plain` fail, while `S256` reaches authentication.
- Altered paths, ports, schemes, `localhost`, and unrelated hosts fail redirect validation.
- Implicit, password, client-credential, device, and CIBA requests fail.
- A real Authorization Code exchange accepts the matching verifier and rejects a mismatched one.
- A real access token contains `aud=workloop-api` and `azp=workloop-migration-web`.
- The ID token audience remains `workloop-migration-web`.
- Refresh rotation succeeds once and rejects reuse of the previous refresh token.
- A request for `offline_access` fails with `invalid_scope`.
- Exact logout redirection succeeds and altered logout destinations fail.

The protocol test creates one temporary local Keycloak identity with a random in-memory password.
It deletes the identity in `finally` and checks that the realm has zero users afterward. It creates
no Workloop application user and stores no test credential in a file, command output, or Git.

## Validation evidence

Local validation on 2026-08-31 passed:

- Realm import into Keycloak 26.7.2 and Admin API configuration checks.
- Protocol restrictions, real PKCE exchange, audience, offline-scope, logout, and refresh-reuse
  checks.
- Keycloak stop and start with unchanged realm signing-key provider IDs.
- Zero persistent users in `workloop-dev` after each test.
- Healthy PostgreSQL, FastAPI, and Keycloak services after restart.
- Alembic current, heads, and metadata check at `f41c9a7b23d1`.
- Nine backend tests, Ruff lint and formatting, strict Pyright, and `pip check`.
- Fourteen frontend unit tests and the production build.

The GitHub full-stack job now imports two realms, runs the Phase 3C security checks, replaces the
Keycloak container, and repeats them against the persisted PostgreSQL state.

GitHub Actions run 13 passed on commit `1efff76` on 2026-08-31. Backend quality, frontend
regression, and full-stack smoke all passed. The full-stack job imported the realm into a fresh
PostgreSQL volume, ran both Keycloak checks, replaced the Keycloak container, repeated the checks,
and removed the temporary stack.

## Security review

An independent GPT-5.6 review checked redirect and logout matching, PKCE enforcement, audience
placement, offline-scope removal, disabled browser grants, import behavior, session settings,
brute-force fields, and sanitization. The review led to these changes:

- Added a disabled-flow `workloop-api` resource client instead of relying on an unexplained
  audience string.
- Explicitly disabled device, CIBA, token-exchange, JWT authorization, and authorization-services
  capabilities.
- Tested a real code exchange and token claims instead of relying only on mapper inspection.
- Added wrong-verifier, refresh-reuse, and offline-scope failures.
- Expanded runtime checks for the resource client and sensitive source fields.

Residual risks remain bounded to local development. Keycloak still uses `start-dev`; the bootstrap
administrator has no MFA; and startup import does not update an existing realm after the JSON
changes. Production mode, TLS proxy behavior, administrator MFA, SMTP, cloud URLs, rate limiting,
and backup restore remain later approved work.

## Rollback

Removing the Compose import mount and command option stops automatic import for new databases. The
existing realm remains in PostgreSQL. Deleting or replacing the realm is destructive and requires
separate owner approval. Do not delete the shared PostgreSQL volume.

## Next part

Phase 3D remains on hold. It owns FastAPI JWT validation and must not begin without separate
project-owner authorization.

Use **GPT-5.6** for Phase 3D. Token signature, issuer, audience, algorithm, key rotation, and outage
handling are authentication-sensitive and need an independent security review.
