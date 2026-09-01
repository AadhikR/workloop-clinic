# Phase 3G synthetic login and account lifecycle

## Status

**Local completion gate passed on 2026-09-01. GitHub Actions evidence is pending.**

Phase 3G adds browser login and account-state handling to the isolated migration frontend. It uses
the approved local Keycloak realm and the existing FastAPI token and application-user checks. The
legacy frontend and its Supabase session are unchanged.

## Browser flow

The migration frontend uses `oidc-client-ts` 3.5.0 with Authorization Code flow, PKCE `S256`, a
library-generated state value, and a fresh 256-bit nonce for each authorization request. The client
requests only `openid profile email`. Keycloak supplies the `workloop-api` audience through the
existing audience mapper.

Access, ID, and refresh tokens use an in-memory store. Session storage holds only temporary redirect
state, nonce, and the PKCE verifier. Callback processing consumes that transaction. The callback URL
is copied to memory and removed from the address bar before application modules load. The page and
local Vite servers set a `no-referrer` policy so an authorization code is not sent as a subresource
referrer.

A page reload loses the in-memory user. The frontend makes one top-level authorization request with
`prompt=none` and uses the Keycloak SSO cookie to restore the session. `login_required` returns to a
signed-out screen without another redirect. While the page remains open, the library renews with the
in-memory refresh token. Renewal failure removes the in-memory user.

Sign-out uses the Keycloak end-session endpoint and the exact approved post-logout URI. The frontend
reports an incomplete logout instead of claiming success when it cannot confirm the provider
request or callback. Unknown root `state` values are removed and do not clear an active local user.

## Account states

After login, restoration, or renewal, the frontend calls `GET /api/v1/auth/token-check` with the
access token. FastAPI still validates RS256, issuer, audience, lifetime, token type, signing key, and
subject before resolving exactly one active `app_users` row by issuer and opaque subject.

The frontend maps the existing responses without reading or displaying their bodies:

| Response | Browser state |
|---|---|
| `204` | Signed in |
| `401` | Session expired; in-memory user removed |
| `403` | Application account unavailable |
| `503` | Account check temporarily unavailable |
| Other response | Generic authentication error |

FastAPI now allows CORS only from `http://127.0.0.1:5174`, only for `GET` with the `Authorization`
header, and without browser credentials. The browser also refuses an API base URL outside the exact
approved local FastAPI origin.

## Synthetic lifecycle verifier

`npm run test:migration-auth` creates temporary local admin, manager, and employee identities. It
creates matching Workloop rows through the test administrator and migration database identities,
then exercises the real browser flow. The script keeps generated passwords in process memory and
does not print credentials, tokens, authorization codes, callback URLs, subjects, or administrator
output.

The verifier checks:

- Initial `prompt=none` failure and user-initiated login.
- PKCE, state, nonce, API audience, and FastAPI account resolution through the real services.
- Exact token absence from local storage, session storage, cookies, Cache Storage, and IndexedDB.
- No callback-code referrer on migration subresources.
- A real refresh-token renewal through the browser client.
- Reload restoration through the Keycloak SSO cookie.
- Email change without changing issuer-and-subject ownership.
- Immediate rejection after changing the employee mapping to `disabled`.
- Confirmed Keycloak logout followed by failed silent restoration.
- Replayed callback, wrong state, and wrong nonce rejection.

The script records each row and Keycloak ID that it creates, deletes only those exact records in
`finally`, and verifies their absence. It creates no provisioning endpoint or runtime Admin API
client. FastAPI keeps read-only identity-table access.

## Local evidence

The 2026-09-01 local gate passed:

- 77 backend tests, Ruff lint and formatting, strict Pyright, and `pip check`.
- 28 Node tests: 14 legacy unit tests, 10 browser-session unit tests, and four migration isolation
  tests.
- The unchanged legacy production build and the isolated migration production build.
- Compose configuration validation and healthy PostgreSQL, FastAPI, and Keycloak services.
- Alembic upgrade, current, heads, and metadata checks at `f41c9a7b23d1` with no schema change.
- The existing real Keycloak authorization-code, PKCE, JWT, JWKS, refresh-rotation, API audience,
  application-user, disabled-account, cleanup, and realm-policy checks.
- The Phase 3G three-persona browser verifier before and after Keycloak container replacement.
- Zero retained Phase 3G Keycloak users and Workloop fixture rows.
- A backend log scan for bearer headers, refresh-token fields, identity mapping fields, database URLs,
  and account-query text.

The first concurrent frontend run failed because two commands used the same fixed Vite port and
fixture directory. Both commands passed when run in the required sequence. This was test-runner
interference, not an application failure.

## Security review

An independent GPT-5.6 review covered callback handling, state and nonce checks, browser storage,
renewal, logout, CORS, token destinations, synthetic cleanup, secrets, schema access, and legacy
isolation. Review findings led to these changes:

- Callback parameters are removed before module requests, and referrers are disabled.
- Failed logout has a separate retry state.
- API tokens can go only to the approved local FastAPI origin.
- Unknown logout state cannot clear the in-memory user.
- Test cleanup uses only IDs created by the current run.
- Storage checks compare the actual in-memory token values instead of searching only for token field
  names.
- The browser performs a real renewal and rejects a deliberately mismatched nonce.

The final review returned no findings. The browser renewal test observes one new token-endpoint
request and a valid account check. The existing protocol test separately proves refresh rotation and
rejection of the old refresh token.

## Unchanged boundaries

- The Keycloak realm policy, clients, mapper, signing keys, and sanitized realm source did not change.
- The identity schema remains at `f41c9a7b23d1`; no Alembic revision or runtime write grant was added.
- The FastAPI JWT, JWKS cache, issuer-and-subject lookup, active-account rule, and generic failures are
  unchanged.
- The legacy Vite graph, entry point, and Supabase authentication are unchanged.
- The migration graph still rejects all legacy `src/` and `@supabase/*` imports and exposes only the
  six approved public configuration names.
- There is no role, tenant, company, employee, manager, or business authorization decision.
- There is no business route, migrated business screen, persistent synthetic user, provisioning API,
  runtime Keycloak Admin API access, DigitalOcean resource, SMTP setting, or email delivery.

## Cost, secrets, and rollback

No external resource or ongoing cost was added. The only new dependency is the approved and locked
`oidc-client-ts` 3.5.0 package.

No new stored secret was created. Existing ignored local database and Keycloak administrator
credentials remain in their Phase 2 environment files. Temporary passwords and protocol values live
only in test-process memory.

Rollback removes the migration authentication module and UI, local public environment example,
`oidc-client-ts` dependency, exact CORS rule, Phase 3G tests and CI steps, and this evidence record. It
does not delete the Keycloak realm, signing keys, shared PostgreSQL volume, or identity schema.

## Completion gate

The local Phase 3G gate has passed. Final completion requires a successful GitHub Actions run for the
implementation commit. Phase 3H remains on hold and requires separate project-owner authorization.
