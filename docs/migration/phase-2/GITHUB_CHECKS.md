# Phase 2G tests and GitHub checks

## Status

**Completed on 2026-08-31.**

Phase 2G adds repeatable Linux checks for the migration foundation. The workflow runs when a
commit is pushed to `migration/fastapi-keycloak` or a pull request targets that branch.

## Workflow design

The workflow has three jobs:

| Job | Checks |
|---|---|
| Backend quality | Hash-locked installation, Pytest, Ruff lint and format, strict Pyright, and dependency consistency |
| Frontend regression | `npm ci`, 14 existing unit tests, and the Vite production build |
| Full stack smoke | Ephemeral credentials, Compose validation, PostgreSQL, FastAPI, Keycloak, Alembic, health, and database boundaries |

The full-stack job runs only after both code-quality jobs pass. It uses synthetic empty databases
and creates no cloud resource. The temporary GitHub runner and its Docker state are discarded by
GitHub after the run.

## Security and cost boundaries

- Workflow permissions grant read-only repository contents access.
- GitHub actions are pinned to full commit SHAs rather than mutable tags.
- The workflow generates credentials on the temporary runner and does not use repository secrets.
- Real employee, clinic, payroll, identity, or document data is prohibited.
- Failure logs must not print environment files, tokens, or connection strings.
- Compose shutdown does not pass `--volumes`.
- No branch-protection or repository setting changes are included.
- No DigitalOcean resource is created.

Private-repository Actions minutes count against the GitHub account's included allowance. One
full run is expected to consume roughly 5 to 15 Linux runner minutes, depending on image download
and Keycloak startup time. Concurrency cancellation stops an older run for the same branch when a
new commit supersedes it.

## Trigger and checks

Workflow file:

```text
.github/workflows/migration-foundation.yml
```

Expected check names:

```text
Backend quality
Frontend regression
Full stack smoke
```

The existing frontend-wide ESLint command is not part of this gate because Phase 0 recorded 114
errors and 9 warnings as baseline debt. New backend code must pass its independent Ruff and
Pyright checks. Playwright remains excluded because the repository has no Playwright
specifications and the existing command exits with `No tests found`.

## Candidate run evidence

Candidate commit `f769ff8` started GitHub Actions run `33379326541`. GitHub accepted the workflow
syntax and enforced read-only contents permission.

| Job | Result |
|---|---|
| Backend quality | Passed |
| Frontend regression | Failed during `npm ci` |
| Full stack smoke | Skipped because it depends on both earlier jobs |

Linux npm rejected an existing lock mismatch: `@emnapi/wasi-threads` 1.2.2 did not satisfy the
locked requirement for 1.2.3. Regenerating only the package lock with npm 11.6.2 changed that
single transitive package to 1.2.3. Local `npm ci --ignore-scripts`, all 14 unit tests, and the Vite
build then passed.

The lock refresh also exposed six existing npm advisories: one low, one moderate, and four high.
The production dependency audit contains only the moderate DOMPurify advisory. The high findings
are in development tooling, including Vite and transitive packages. `npm audit fix --dry-run`
offered no lock-only change. Resolving them requires a reviewed dependency update and remains
deferred; no vulnerable development server is exposed by this workflow.

## Successful remote evidence

Corrected commit `b377bf3` started GitHub Actions run `33379719477`:

```text
https://github.com/AadhikR/workloop-clinic/actions/runs/33379719477
```

| Job | Result | Runner duration |
|---|---|---:|
| Backend quality | Passed | 34 seconds |
| Frontend regression | Passed | 22 seconds |
| Full stack smoke | Passed | 67 seconds |

The jobs used 123 seconds of runner execution in total, with backend and frontend running in
parallel. GitHub allowance accounting may round each job separately. The full-stack log download
contained no secret variable assignments, connection URLs, bearer tokens, or credential values.

The remote smoke job proved that a fresh Ubuntu 24.04 runner can:

- Generate ignored, ephemeral service credentials.
- Validate the Compose model.
- Build FastAPI from the Linux lock installation.
- Start PostgreSQL, FastAPI, and Keycloak as healthy services.
- Run Alembic through the migration-only service.
- Reach the FastAPI and Keycloak readiness endpoints.
- Keep Workloop free of application tables and Keycloak limited to its built-in master realm.
- Stop the temporary stack without requesting volume deletion.

No repository secret, DigitalOcean resource, or branch-protection setting was created.

## Completion gate

Phase 2G passed because:

- Local backend and frontend checks pass.
- The workflow syntax is accepted by GitHub.
- All three checks pass on the migration branch.
- No credential is committed or printed by the workflow.
- PostgreSQL, FastAPI, and Keycloak remain healthy locally.
- Test evidence and any failures are recorded here.

## Files changed

- `.github/workflows/migration-foundation.yml`
- `package-lock.json`
- `docs/migration/phase-2/GITHUB_CHECKS.md`
- `backend/README.md`
- `docs/migration/phase-2/KEYCLOAK_RUNTIME.md`
- `DIGITALOCEAN_MIGRATION_PLAN.md`

## Rollback

Removing the workflow in a later commit stops future triggers. Active GitHub runs can be cancelled
without affecting local services or the PostgreSQL volume. Phase 2G does not authorize deleting
any local volume or changing repository protection settings.
