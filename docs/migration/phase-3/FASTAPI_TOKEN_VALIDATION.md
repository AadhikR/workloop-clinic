# Phase 3D FastAPI token validation

## Status

**Completed on 2026-08-31.**

Phase 3D adds bearer access-token validation to FastAPI. It does not resolve an application user,
query PostgreSQL for account status, trust token roles, or make a business authorization decision.
Those boundaries remain unchanged.

## Request boundary

The `require_access_token` dependency reads one `Authorization` header. It accepts the `Bearer`
scheme without case sensitivity but requires one non-empty JWT credential and rejects duplicate or
malformed headers. Tokens in cookies, query strings, request bodies, or alternate headers are not
read.

`GET /api/v1/auth/token-check` applies the dependency and returns an empty `204` response with
`Cache-Control: no-store`. It returns no claims or application-user data. Missing and invalid tokens
receive the same `401` body and `WWW-Authenticate: Bearer` header.

## Validation rules

FastAPI accepts only a token that passes all of these checks:

- The JOSE algorithm is exactly `RS256` before key selection and during signature verification.
- The token has one non-empty signing-key ID and a valid signature from the configured realm JWKS.
- The issuer is exactly `http://127.0.0.1:8080/realms/workloop-dev` locally.
- The audience contains `workloop-api`.
- `iss`, `sub`, `aud`, `exp`, `iat`, and `typ` are present and have the required types.
- `exp`, `iat`, and an optional `nbf` are valid integer NumericDate values.
- `sub` is a non-empty opaque string.
- The signed payload has `typ=Bearer`. A signed ID token has a different type and is rejected.

Unsigned JWTs, HMAC algorithms, alternate RSA algorithms, malformed tokens, unsupported JOSE types,
bad signatures, missing claims, malformed audiences, expired tokens, and future `iat` or `nbf` values
fail with `401`. The validator never uses realm roles, client roles, email, company data, or employee
data.

The restricted Keycloak web client now has the standard access-token subject mapper. The idempotent
`scripts/configure-phase-3d-keycloak.py` command adds it to fresh and existing realms, then rejects a
conflicting mapper instead of replacing unreviewed configuration. It adds the opaque Keycloak
subject to access tokens and introspection output only. The mapper does not add a business role or
another authorization claim.

## JWKS behavior

The FastAPI process creates one bounded HTTP client and loads JWKS lazily on the first protected
request. Local containers use the internal `keycloak` service address for retrieval while validating
the canonical browser-facing issuer. Redirects are disabled.

The defaults are:

| Setting | Value |
|---|---:|
| Connect timeout | 2 seconds |
| Read inactivity timeout | 2 seconds |
| Total JWKS transfer timeout | 5 seconds |
| Successful cache lifetime | 300 seconds |
| Refresh cooldown | 1 second |
| Maximum decoded JWKS body | 64 KiB |
| Maximum published keys | 32 |
| Maximum HTTP connections | 10 |
| Maximum idle connections | 5 |

JWKS requests ask for an uncompressed response and reject another content encoding. The reader
stops above the body limit. The parser ignores encryption keys and signing keys for other
algorithms, then accepts only public RSA signature keys marked for `RS256`. It rejects private key
members, malformed eligible keys, duplicate eligible key IDs, and a set with no usable key.

A token with an unknown key ID can trigger one refresh after the cooldown. An asynchronous lock
coalesces concurrent refreshes, and a cache generation check prevents queued requests from repeating
a successful rotation fetch. Failed fetches start the cooldown when the attempt finishes.

During a JWKS outage, a known key remains usable only until the successful cache lifetime expires.
Cold starts, unknown keys, and requests after cache expiry fail closed. Stale keys are not extended
after a failed fetch. Validation recovers after the cooldown when JWKS retrieval succeeds. This
allows a short Keycloak interruption without turning an old key into an indefinite trust source.

`OIDC_ISSUER` and `OIDC_JWKS_URL` may use HTTP only in `local` and `test`. Development, staging, and
production settings require HTTPS.

## Configuration

The backend adds these non-secret settings:

```text
OIDC_ISSUER
OIDC_AUDIENCE
OIDC_JWKS_URL
OIDC_JWKS_CONNECT_TIMEOUT_SECONDS
OIDC_JWKS_READ_TIMEOUT_SECONDS
OIDC_JWKS_TOTAL_TIMEOUT_SECONDS
OIDC_JWKS_CACHE_TTL_SECONDS
OIDC_JWKS_REFRESH_COOLDOWN_SECONDS
```

No token, password, client secret, private key, administrator credential, or database URL was added
to tracked configuration. `PyJWT` 2.13.0, `cryptography` 50.0.1, and the existing `httpx` 0.28.1 are
hash-locked as runtime dependencies.

## Test evidence

Local validation passed:

- 55 backend tests covering valid cold and warm validation, expiry, future times, issuer, audience,
  subject, malformed claims, ID tokens, bad signatures, JOSE algorithm restrictions, malformed
  headers, unknown keys, rotation, cache expiry, outage recovery, refresh coalescing, response-size
  limits, total transfer timeout, HTTPS configuration, and response and log leakage.
- Ruff lint and format checks, strict Pyright, and `pip check`.
- A real Authorization Code and PKCE exchange through the local Keycloak realm. FastAPI accepted
  the access token and rejected the ID token without printing either token.
- Keycloak container replacement followed by the same real token checks. The realm, subject mapper,
  signing keys, and zero-persistent-user boundary survived.
- Healthy PostgreSQL, FastAPI, and Keycloak services.
- Alembic current, head, and metadata checks at `f41c9a7b23d1` with no schema change.
- Fourteen frontend unit tests and the legacy production build.
- Compose configuration validation.
- The Phase 3D Keycloak configuration command run twice against the persisted Phase 3C realm.

An independent GPT-5.6 security review found and drove fixes for mixed signing and encryption keys in
Keycloak JWKS, streamed response limits, outage cooldown timing, total transfer deadlines, HTTPS
enforcement, and the missing access-token subject. The final live token flow passed after those
fixes.

GitHub Actions run 16 passed on commit `b753ce8` on 2026-08-31. Backend quality, frontend regression,
and full-stack smoke all passed. The fresh full-stack job imported the mapper-free Phase 3C realm,
ran the Phase 3D mapper command twice, validated a real access token, rejected the ID token, replaced
Keycloak, repeated the live checks, and removed the temporary stack.

## Rollback

Removing the authentication package, OIDC settings, token-check route, and runtime JWT dependencies
returns FastAPI to the Phase 3C state. The administrative command is the source of the mapper on an
existing realm, so removing the command does not remove a mapper already stored in Keycloak. Mapper
removal is a separate administrative change. No Workloop table or Alembic revision changed. Do not
delete the realm or PostgreSQL volume as part of rollback.

## Next part

Phase 3E remains on hold. It owns issuer-and-subject application-user resolution and current account
status checks. It must not start without separate project-owner authorization.

Use **GPT-5.6** for Phase 3E. Mapping an authenticated subject to an active Workloop account is an
authorization boundary, and mistakes could admit disabled or incorrectly linked users.

### Phase 3E handoff prompt

```text
Continue the Workloop Clinic migration with Phase 3E only: application-user resolution.

Read AGENTS.md, DIGITALOCEAN_MIGRATION_PLAN.md, the Phase 2 foundation records, and every Phase 3
design and evidence document. Inspect the synchronized migration/fastapi-keycloak branch, FastAPI
token dependency, identity schema and revision state, Keycloak realm, Compose stack, tests, and
GitHub checks.

Expected state: Phase 3A through Phase 3D are complete; FastAPI validates only RS256 bearer access
tokens from the approved issuer and audience; the Workloop identity schema is at f41c9a7b23d1; no
application-user resolution, role authorization, migration frontend, persistent Workloop user, or
business feature exists.

Do not begin without explicit Phase 3E authorization. When authorized, implement only issuer and
subject lookup against app_users plus the approved current account-status checks. Do not add role or
tenant authorization, provisioning, synthetic persistent users, frontend login, business routes,
DigitalOcean resources, email delivery, or Supabase coupling. Keep failures generic, test missing,
duplicate, pending, disabled, and active mappings, update evidence, and pass the completion gate
before committing and pushing. Stop before Phase 3F and every owner decision.
```
