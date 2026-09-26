# Contributor guide

## Read first

Follow `AGENTS.md` and the migration workflow files it names. Check the current phase plan before
changing migration-owned code or documents. Keep each migration part in its assigned task.

## Commands

Frontend checks from the repository root:

```powershell
npm ci --ignore-scripts
npm run test:unit
npm run build
npm run lint
node scripts/verify-phase-13e-repository-guard.mjs
```

Backend checks from `backend/` after installing the locked environment:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest
& ".\.venv\Scripts\python.exe" -m ruff check .
& ".\.venv\Scripts\python.exe" -m ruff format --check .
& ".\.venv\Scripts\pyright.exe"
& ".\.venv\Scripts\python.exe" -m pip check
```

Use focused tests while editing. Run the boundary-matched local gate once after the code settles.
Workflow, Compose, authentication, database, or shared-infrastructure changes require the complete
stack gate.

## Runtime ownership

- React and Vite own browser rendering.
- Keycloak owns interactive authentication and OIDC tokens.
- FastAPI owns authorization and all business behavior.
- PostgreSQL owns application state through the Alembic schema.
- The backend storage interface owns private files.
- Explicit commands own expiry processing, scanning, and reconciliation.

Do not add a second client, fallback runtime, browser database access, environment-selected backend,
or hidden compatibility path.

## Frontend rules

Use `src/api/` clients for network calls. Components should render state and collect input, not
reimplement authorization or database behavior. Keep the six public `VITE_` names in `.env.example`
as the complete browser configuration allowlist.

Use the existing API error mapping and OIDC session flow. A hidden control is not authorization.
Every protected operation must still fail at FastAPI when the user lacks the required role or scope.

The canonical production output is `dist/`. Do not add alternate source trees, build outputs, or
fallback commands.

## Backend rules

Keep routers thin. Put scoped database work in repositories and multi-step behavior in services or
transactions. Resolve the current application user from the validated issuer and subject. Preserve
company, branch, employee, and manager scope at every read and write boundary.

Use request schemas for writable fields. Reject unknown or protected fields. Keep concurrency and
idempotency behavior explicit, especially for approvals, payroll, attendance, roster publication,
files, and generated outputs.

Log stable identifiers and outcomes. Never log tokens, passwords, signed URLs, private object keys,
database URLs, or document contents.

## Database rules

Create a new Alembic revision for schema changes. Do not edit an applied revision. A schema change
must preserve one head and pass fresh-database, upgrade, and repeatability checks.

Keep runtime and worker roles least-privileged. Do not grant broad table or schema access to solve a
single route failure. Tests should prove both the allowed path and the closest denied path.

## Private-file rules

All object access goes through the backend storage interface. Keep uploads private, validate object
ownership and scope, and preserve quarantine and scanner state. Do not expose provider credentials or
long-lived object URLs to the browser.

## Tests

Add a focused regression test before a broad fix. Prefer deterministic synthetic IDs, dates, and
objects. Test administrators, managers, and employees separately when permissions differ. Include
cross-company and cross-branch denial when the changed operation accepts scoped identifiers.

Do not seed data through historical SQL. Use current API, repository, or synthetic fixture paths.

## Historical material

Current instructions live at the repository root and in `backend/README.md`. Earlier migration
records and `docs/history/` are evidence only. The repository guard permits named files there because
they carry labels and cannot enter build, bootstrap, fixture, or deployment inputs.
