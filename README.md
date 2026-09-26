# Workloop Clinic

Workloop Clinic is a UAE payroll and HR application for administrators, managers, and employees.
The React frontend uses one authenticated FastAPI API. Keycloak owns sign-in, portable PostgreSQL
owns application data, and private object storage holds documents and generated files.

## Runtime

| Responsibility | Current owner |
| --- | --- |
| Browser application | React 19 and Vite |
| Authentication | Keycloak with OpenID Connect |
| Business API | FastAPI under `/api/v1` |
| Database | PostgreSQL 17, managed by Alembic |
| Private files | Backend storage adapter, using a local private store or an S3-compatible service |
| Background work | Expiry processing, file scanning, and storage reconciliation commands |

The browser never connects to the database or object store. It sends an access token to FastAPI,
which resolves the application user and applies role, company, and branch checks before reading or
changing data.

## Main product areas

- Organization, branch, department, and employee administration
- Leave configuration, balances, requests, attachments, and approval
- Attendance, biometric ingestion, roster planning, publication, and shift swaps
- Payroll, payslips, WPS, Nafis, expenses, and advances
- Documents, insurance, contracts, assets, training, certifications, appraisals, and incidents
- Notifications, tasks, dashboards, reports, exports, and rendered outputs
- Employee and manager self-service workflows

## Local setup

Requirements:

- Node.js 24.11.1 and npm 11.6.2
- Docker with Compose
- PowerShell 5.1 or later on Windows

From the repository root:

```powershell
npm ci --ignore-scripts
Copy-Item .env.example .env
./scripts/new-local-postgres-env.ps1
docker compose up --build --detach --wait postgres backend keycloak
docker compose --profile tools run --rm migrate
python scripts/configure-phase-3d-keycloak.py
npm run dev
```

The frontend listens on `http://127.0.0.1:5174`, FastAPI on `http://127.0.0.1:8000`, and Keycloak
on `http://127.0.0.1:8080`. Generated environment files under `backend/` contain local secrets and
remain untracked.

Stop the local services without deleting their volumes:

```powershell
docker compose down
```

Do not use `docker compose down --volumes` against a checkout that owns data you intend to keep.

## Development checks

```powershell
node scripts/verify-phase-13e-repository-guard.mjs
npm run test:unit
npm run build
npm run lint
```

Run the complete synthetic three-role browser journey only when the local stack and test identities
are configured:

```powershell
npm run test:browser
```

Backend checks and dependency commands are documented in `backend/README.md`.

## Database changes

Alembic is the only current schema mechanism. Add a new append-only revision under
`backend/alembic/versions/`, then verify that a fresh database reaches the same single head as an
upgraded database. Never edit an applied revision.

## Documentation

- `ARCHITECTURE.md` explains the current request, identity, data, and file flows.
- `CLAUDE.md` is the contributor guide.
- `DIGITALOCEAN_MIGRATION_PLAN.md` records the current deployment and recovery plan.
- `FEATURES_ROADMAP.md` records implemented areas and remaining release work.
- `MANUAL_TEST_CHECKLIST.md` contains the current three-role manual smoke check.
- `docs/migration/` contains phase evidence. Records through Phase 12 are historical.
- `docs/history/` contains inert source-system artifacts and the retired feature-list PDF.

## Data and secret rules

- Use synthetic local data for development and migration verification.
- Keep credentials, exports, private files, and personal records out of Git and task output.
- Treat object keys, signed URLs, access tokens, and database URLs as secrets.
- Verify the exact Compose project and volume names before cleanup.
