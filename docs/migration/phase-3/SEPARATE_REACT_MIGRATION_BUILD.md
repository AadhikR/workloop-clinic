# Phase 3F separate React migration build

## Status

**Completed locally on 2026-08-31. GitHub Actions confirmation is pending the Phase 3F commit.**

Phase 3F adds an isolated Vite build for later migration work. It does not add login, OIDC session
handling, FastAPI calls, application-user provisioning, authorization, a Keycloak user, or a business
screen.

## Build boundary

The migration root is `migration/`. It has its own `index.html`, React entry, app component, styles,
public configuration module, and Vite configuration. It writes only to `dist-migration` and listens
only on `http://127.0.0.1:5174` with `strictPort: true`.

The legacy `index.html`, `src/` entry graph, Vite configuration, scripts, and Supabase authentication
remain unchanged. The legacy build still uses its existing `npm run dev` and `npm run build` commands.

Use these commands from the repository root:

```powershell
npm.cmd run dev:migration
npm.cmd run build:migration
npm.cmd run test:migration-build
```

## Isolation rules

`migration/vite-isolation.js` runs before Vite's resolver. It rejects every import of:

- A module in the legacy `src/` directory.
- `@supabase/supabase-js`.
- Every other `@supabase/*` package.

The same plugin checks resolved module transforms. A direct import, a relative import of
`src/lib/supabase.js`, or a dependency that imports a Supabase package therefore fails in development
and production builds.

The migration configuration exposes exactly these public names through `import.meta.env`:

```text
VITE_API_BASE_URL
VITE_OIDC_AUTHORITY
VITE_OIDC_CLIENT_ID
VITE_OIDC_REDIRECT_URI
VITE_OIDC_POST_LOGOUT_REDIRECT_URI
VITE_OIDC_AUDIENCE
```

The build does not use or expose other `VITE_` names. Tokens, passwords, private keys, database URLs,
client secrets, and administrator credentials remain forbidden in browser configuration.

## Automated checks

`tests/migration-build.test.js` verifies:

- Direct and transitive forbidden-import fixtures fail through Vite.
- The production module graph has no legacy `src/` module or `@supabase/` package.
- The production build succeeds with no Supabase environment file and omits an injected unapproved
  `VITE_SUPABASE_URL`.
- Every production output file contains none of the Supabase, auth-storage, token, credential, or
  database-URL markers checked by the test.
- The migration development server returns the separate root on port 5174.
- A listener already using port 5174 makes the migration server fail rather than choose another port.

The GitHub `frontend-regression` job runs the legacy unit tests and build, then the migration isolation
suite. No new backend, Keycloak, Docker Compose, or Alembic behavior is required for this phase.

## Local evidence

On 2026-08-31, the local gate passed:

- `npm.cmd run test:migration-build` with four passing checks.
- `npm.cmd run build:migration`.
- `npm.cmd run test:unit` with the existing 14 legacy unit tests plus four migration-build checks.
- `npm.cmd run build` through the unchanged legacy entry point.
- Compose configuration validation, healthy PostgreSQL, FastAPI, and Keycloak services, and Alembic at
  `f41c9a7b23d1`.
- The existing FastAPI token and application-user behavior was not modified.

An independent review found no isolation or secret-boundary issue. It requested real Vite fixture
builds, dev-entry transformation, and an unapproved-environment-output check. Those checks were added
before this record.

## Rollback

Removing `migration/`, `tests/migration-build.test.js`, the three migration npm scripts, the CI step,
and the `dist-migration` ignore rule returns the repository to the Phase 3E frontend state. This does
not alter the legacy frontend, backend, Keycloak realm, database schema, or local PostgreSQL volume.

## Next part

Phase 3G is on hold. It owns synthetic login and account lifecycle work and requires separate
project-owner authorization.
