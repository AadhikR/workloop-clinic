# Phase 2B Backend Scaffold

## Status

**Completed on 2026-08-27.**

Phase 2B created the isolated Python package and dependency foundation. It did not create a FastAPI application object, endpoint, database connection, Alembic environment, container, Keycloak configuration, cloud resource, or secret.

## Files Added

| Path | Purpose |
|---|---|
| `backend/.python-version` | Records Python 3.12 as the backend version |
| `backend/app/__init__.py` | Creates the importable `app` package and version |
| `backend/tests/test_package.py` | Proves that the package imports and exposes the expected version |
| `backend/pyproject.toml` | Defines package metadata, dependencies, and Python tool settings |
| `backend/requirements.lock` | Hash-locked runtime dependencies |
| `backend/requirements-dev.lock` | Hash-locked runtime and development dependencies |
| `backend/README.md` | Documents environment creation, installation, checks, lock generation, and boundaries |

The root `.gitignore` now excludes the local virtual environment, Python bytecode, coverage output, and tool caches.

## Local Environment

The ignored environment is located at:

```text
backend/.venv
```

It was created with the explicit Python 3.12 interpreter so the existing Anaconda Python 3.9 environment remains unchanged.

The virtual environment is local machine state. It is not committed, copied, or deployed. Another computer recreates it from the lock file.

## Dependency Policy

- `pyproject.toml` declares direct dependency compatibility ranges.
- `requirements.lock` resolves runtime dependencies to exact versions and hashes.
- `requirements-dev.lock` resolves runtime and development dependencies to exact versions and hashes.
- Installation uses `pip --require-hashes` so an unrecorded package artifact is rejected.
- `pip-tools` generates lock files from `pyproject.toml`.
- Lock files are generated with Python 3.12 and reviewed before commit.
- Application packages are never installed into Anaconda or global Python.
- Dependencies are changed in `pyproject.toml`, not by manually editing generated locks.

## Direct Runtime Dependencies

| Package | Purpose | Resolved version |
|---|---|---:|
| FastAPI | HTTP API framework used in Phase 2D | `0.141.1` |
| Uvicorn | ASGI development and container server | `0.52.4` |
| SQLAlchemy | Portable database query and transaction layer | `2.0.52` |
| Psycopg | PostgreSQL driver and connection pool | `3.3.4` |
| Alembic | Database migration management used in Phase 2E | `1.19.1` |
| Pydantic Settings | Validated environment configuration | `2.15.0` |

## Development Dependencies

| Package | Purpose | Resolved version |
|---|---|---:|
| Pytest | Python tests | `9.1.1` |
| pytest-asyncio | Async test support | `1.4.0` |
| pytest-cov | Coverage reporting | `7.1.0` |
| HTTPX | FastAPI and HTTP integration tests | `0.28.1` |
| Ruff | Python linting and formatting | `0.16.5` |
| Pyright | Static type checking | `1.1.411` |
| pip-tools | Dependency lock generation | `7.6.1` |

Transitive packages and every accepted distribution hash are recorded in the lock files.

## Tool Configuration

`backend/pyproject.toml` establishes:

- Python `>=3.12,<3.13`.
- Ruff targeting Python 3.12 with a 100-character line limit.
- Ruff error, import, upgrade, bugbear, simplification, and Ruff-specific rules.
- Strict Pyright checking for `app` and `tests`.
- Strict Pytest configuration and marker handling.
- Setuptools package discovery limited to `app*`.

## Verification Evidence

| Check | Result |
|---|---|
| Package build and installation | `workloop-api` wheel built and installed successfully |
| Package import | Returned version `0.1.0` |
| Runtime imports | FastAPI, SQLAlchemy, Psycopg, Alembic, Pydantic Settings, and Uvicorn imported successfully |
| Backend tests | 1 passed |
| Ruff lint | All checks passed |
| Ruff format check | 3 files already formatted |
| Pyright | 0 errors, 0 warnings, 0 information messages |
| Dependency consistency | `pip check` reported no broken requirements |
| Hash-locked installation | Completed successfully from `requirements-dev.lock` |
| Lock regeneration | Repeated development-lock generation produced the same SHA-256 hash, `0551453F79DBD806CD559BE9BA65CD9AD6D5D2A394F4D74E16A93FC174B17C14`; runtime lock hash is `AD233EC48BA45096EAABA72DCF42FB4032F5480EC136C694E2D63A42E0967DE4` |
| Existing JavaScript unit tests | 14 passed |
| Existing Vite production build | Passed with the existing large-chunk warning |

## Secrets and External Effects

- No `.env` file was created.
- No password, API key, token, database URL, or Keycloak credential was created.
- No dependency was installed into Anaconda or global Python.
- Public Python packages were downloaded into `backend/.venv`.
- No Docker image, container, network, or volume was created.
- No DigitalOcean resource was created.
- DigitalOcean cost remains USD 0.

## Known Constraints

- The plain Windows `python` command still selects Anaconda Python 3.9. Backend commands must use `backend/.venv/Scripts/python.exe` or activate that environment.
- The dependency locks were generated on Windows with Python 3.12. Container installation must be tested when the Linux Dockerfile is added.
- The existing frontend ESLint baseline remains failing and is outside Phase 2B.
- FastAPI is declared as a dependency but has no application or endpoint yet; that belongs to Phase 2D.
- Alembic is declared as a dependency but has no migration environment yet; that belongs to Phase 2E.

## Rollback

Before commit, Phase 2B can be rolled back by removing the new `backend` files and the ignored `backend/.venv`, then reverting only the Python additions to `.gitignore`. Removing the virtual environment deletes downloaded project packages but does not affect Anaconda, Docker, React, Supabase, or cloud resources.

No rollback action should be taken without explicit project-owner approval.

## Completion Gate

Phase 2B passes because:

- The backend package structure is minimal and importable.
- Python 3.12 is isolated from Anaconda.
- Runtime and development dependencies are declared and hash-locked.
- A clean lock installation succeeds.
- Package, test, lint, format, type, and dependency checks pass.
- Existing JavaScript unit tests and production build still pass.
- No credentials were committed or created.
- No business feature, database, endpoint, container, or cloud resource was added prematurely.
- Setup and maintenance commands are documented.

## Next Part

Phase 2C configures local PostgreSQL. It is on hold until the project owner explicitly authorizes it.
