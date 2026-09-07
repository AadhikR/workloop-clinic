# Phase 6 subphase plan

## Status

Phase 5 received project-owner signoff on 2026-09-07. The project owner approved Phase 6A and
authorized Phases 6B, 6C, and 6D on the same date. The API contract, backend HTTP boundary, frontend
HTTP client, and dual-build cutover controls have complete local gates. Phase 6D awaits its required
GitHub result. Parts 6E through 6G remain unauthorized and separately gated.

Phase 6 is split into seven parts, 6A through 6G. The original scope mixed HTTP contracts, backend
middleware, frontend transport, migration compatibility, an end-to-end API slice, an independent
completion review, and the first billable cloud deployment. That is too much work for one safe
implementation and rollback boundary.

Parts 6A through 6F are local and use synthetic data. Part 6G is the existing early DigitalOcean
architecture proof. It remains a separate, billable gate with its own prerequisites.

## Starting point

- Branch `migration/fastapi-keycloak` is synchronized at Phase 5 commit `9d92e67`.
- Alembic head is `2c4d6e8f0a1b`.
- Phase 3 supplies Keycloak login, in-memory browser tokens, FastAPI token validation, and a separate
  migration frontend build.
- Phase 5 supplies trusted principals, authorized transactions, scoped repositories, PostgreSQL RLS,
  protected workflows, and append-only audit controls.
- The migration frontend has no shared HTTP client for business endpoints. The backend has health and
  authentication checks, but no Phase 6 business API convention.
- The legacy Supabase build remains the behavioral reference. Phase 6 must not mix its session or data
  writes with the Keycloak migration build.
- The preserved `workloop-clinic_postgres_data` volume remains outside local Phase 6 test stacks.
- Real data, production accounts, SMTP, and business-module migration remain out of scope.

## Part status

| Part | Scope | Status |
|---|---|---|
| 6A | API contract and error decisions | Complete; owner approved 2026-09-07 |
| 6B | Backend HTTP boundary and middleware | Complete; owner authorized 2026-09-07 |
| 6C | Frontend HTTP client | Complete; owner authorized 2026-09-07 |
| 6D | Dual-build compatibility and cutover controls | Implementation and local gate complete; GitHub result pending |
| 6E | Public and protected sample API slice | Not started; requires separate authorization |
| 6F | Independent review and local completion gate | Not started; requires separate authorization |
| 6G | Early DigitalOcean architecture proof | Not started; requires separate authorization and billable-resource approval |

## Rules shared by every part

- Prefix application endpoints with `/api/v1`.
- PostgreSQL remains the source of business roles and authorization scope. Browser fields and
  Keycloak roles do not grant business access.
- The frontend sends only Keycloak access tokens to FastAPI. It does not send them to Supabase or
  persist them in local storage, IndexedDB, caches, or cookies.
- Backend secrets never use a `VITE_` variable or enter a browser bundle.
- Errors expose a stable code, a safe message, and a correlation identifier. They do not expose SQL,
  Python, Keycloak internals, tokens, or cross-tenant object existence.
- CORS uses exact approved origins. Authenticated endpoints never use a wildcard origin.
- Each request has one documented transaction owner. Repository code does not commit independently.
- Cancellation and timeout behavior must leave transactions and pooled connections clean.
- Phase 6 adds no business feature migration. Phases 7 through 12 own their business routes and UI.
- Use only synthetic data. Part 6G may create cloud resources only after the owner authorizes its
  cost, security, and account prerequisites.
- Follow `docs/migration/VERIFICATION_WORKFLOW.md`. Run focused checks while working and one complete
  gate only after a part settles.

## 6A: API contract and error decisions

### Objective

Approve the shared HTTP contract before backend and frontend code depend on it.

### Scope

- Fix JSON field naming, UUID, date, time, decimal, money, null, and enum representations.
- Define request and response schema rules, list envelopes, pagination, filter allowlists, sorting,
  and validation behavior.
- Define the error body, stable error-code registry, safe messages, HTTP status mapping, correlation
  ID format, and response header.
- Define transaction ownership for request handlers, services, repositories, and protected database
  functions.
- Define the idempotency-key contract for later financial and approval mutations without adding a
  business mutation in this part.
- Fix local and cloud CORS origins, request and upload size limits, timeout defaults, and the rate-limit
  boundary required before public exposure.
- Define OpenAPI review rules and compatibility expectations for later phases.

### Decisions and dependencies

This part depends on the Phase 3 authentication contract and the Phase 5 authorization model. A
change to token storage, trusted role sources, cross-tenant disclosure, or database transaction
ownership returns to the project owner.

### Tests and review

This is a documentation-only part. Check that each convention has one canonical value and that the
backend, frontend, OpenAPI, and later module plans do not prescribe conflicting behavior. An
independent reviewer must inspect the error and idempotency contracts before approval.

### Rollback boundary

No runtime or schema change occurs. Revert the Phase 6 contract documents if the owner rejects them.

### Completion gate

The owner approves every contract decision. No status, payload, header, pagination, casing,
transaction, CORS, size, timeout, idempotency, or rate-limit rule remains open.

### Recommended model and effort

Use GPT-5.6 with high reasoning. Expect one focused session plus review.

## 6B: Backend HTTP boundary and middleware

### Objective

Implement the approved backend conventions once, before business routes multiply them.

### Scope

- Add correlation-ID middleware with trusted generation, response propagation, and structured-log
  binding.
- Add safe exception handlers for authentication, authorization, validation, conflict, rate-limit,
  availability, and unexpected server failures.
- Configure exact-origin CORS separately for local and later cloud settings.
- Enforce the approved request-size boundary and provide the upload-size hook that Phase 11 will use.
- Add shared pagination, filtering, sorting, and response helpers only where the 6A contract requires
  reusable code.
- Add the service transaction pattern without weakening the Phase 5 authorized transaction factory.
- Add an idempotency interface for later protected mutations. Do not invent a financial workflow or
  persistence table without a separate decision.

### Tests and negative tests

- Accept or generate correlation IDs according to the 6A format and include them in safe logs and
  responses.
- Reject spoofed, malformed, oversized, disallowed-origin, and unsupported-content requests.
- Map failures to the exact public error body without raw exception text.
- Prove transaction cleanup after success, handled error, unexpected error, timeout, and cancellation.
- Prove wildcard CORS and credentialed unapproved origins remain disabled.

### Rollback boundary

Remove the new middleware, handlers, and helpers together. Phase 6C and later parts must not depend on
them during rollback.

### Completion gate

Backend tests, lint, formatting, types, dependency checks, focused middleware tests, and the affected
local integration checks pass. OpenAPI exposes only the approved shared responses and headers.

### Recommended model and effort

Use GPT-5.6 with high reasoning. Expect one or two sessions.

## 6C: Frontend HTTP client

### Objective

Create the migration frontend's only path for calling FastAPI.

### Scope

- Implement one client for the API base URL, in-memory access-token retrieval, JSON parsing,
  correlation IDs, timeouts, cancellation, and normalized errors.
- Distinguish authentication, authorization, validation, conflict, rate-limit, availability, and
  unexpected server failures without displaying raw backend messages.
- Keep public requests token-free and protected requests on the Keycloak-to-FastAPI path.
- Preserve existing screen-facing storage interfaces only when an adapter can do so without hidden
  dual writes.
- Keep all backend credentials and database details out of the browser build.

### Tests and negative tests

- Cover public and protected requests, empty responses, malformed JSON, timeouts, cancellation,
  network failure, token expiry, forbidden access, validation errors, conflicts, and server errors.
- Prove the client never writes tokens to durable browser storage or logs them.
- Prove it refuses an unapproved API origin and never forwards a token to Supabase or another host.
- Build both legacy and migration frontends and verify their dependency graphs remain separate.

### Rollback boundary

Remove the client and its migration-build wiring. No business screen moves in this part, so the legacy
build remains the fallback.

### Completion gate

Frontend unit tests and both production builds pass. A focused browser test proves public calls omit
tokens and protected calls use the in-memory Keycloak token only for the approved FastAPI origin.

### Recommended model and effort

Use GPT-5.6 with high reasoning. Expect one or two sessions.

## 6D: Dual-build compatibility and cutover controls

### Objective

Turn the migration compatibility rules into checks that later feature phases can reuse.

### Scope

- Create the authoritative-system declaration and dependency checklist required for each feature
  cutover.
- Define read-freeze, write-freeze, rollback, synthetic refresh, source record, refresh command, and
  last-refresh evidence.
- Define the synthetic mapping between legacy Supabase user IDs and application-owned IDs.
- Add a check that rejects a migrated slice when both builds can write the same business record.
- Add a check that keeps Supabase modules out of the migration build and Keycloak or FastAPI tokens out
  of the legacy build.
- Do not move a business screen or run a cross-database refresh in this part.

### Tests and negative tests

- Validate complete and incomplete cutover declarations.
- Reject missing dependencies, ambiguous authority, partial rollback, two writable systems, and
  refresh records without a source or timestamp.
- Build both entry points and scan their dependency graphs and environment variables.

### Rollback boundary

These controls have no production data effect. Revert the templates and checks before a feature phase
depends on them.

### Completion gate

Later feature phases have one reusable cutover record and one automated no-dual-write check. The
legacy and migration builds still run independently.

### Recommended model and effort

Use GPT-5.6 with medium reasoning. Expect one focused session.

## 6E: Public and protected sample API slice

### Objective

Prove the shared backend and frontend conventions through one dependency-complete, non-business
sample slice.

### Scope

- Add one versioned public endpoint that returns no tenant data.
- Add one authenticated current-account or profile endpoint that uses the Phase 5 principal and
  authorized transaction path.
- Add Pydantic request and response schemas and review the generated OpenAPI document.
- Call both endpoints through the Phase 6C client in the migration build.
- Keep the legacy build unchanged and do not expose another employee, company, branch, or role.

### Tests and negative tests

- Cover valid admin, manager, and employee accounts plus expired token, disabled account, stale
  profile, missing context, guessed identity, and unavailable database cases.
- Prove the public endpoint receives no authorization header.
- Prove the protected endpoint returns only the caller's approved projection and preserves the Phase
  5 non-disclosure rule.
- Verify error bodies, correlation IDs, CORS, timeouts, cancellation, OpenAPI, logs, and transaction
  cleanup through the real client and local stack.

### Rollback boundary

Remove the sample endpoints and migration UI together, then remove the shared client dependency if
needed. No business table or legacy write path changes.

### Completion gate

The migration browser calls both endpoints through the shared client. Authentication, authorization,
error handling, CORS, logging, OpenAPI, and transaction cleanup match the 6A contract.

### Recommended model and effort

Use GPT-5.6 with high reasoning. Expect one or two sessions.

## 6F: Independent review and local completion gate

### Objective

Review Parts 6A through 6E independently and close the local shared-API foundation before cloud work.

### Scope

- Arrange a read-only independent review of the contracts, middleware, frontend client, compatibility
  checks, sample endpoints, tests, and rollback boundaries.
- Record every finding and disposition. Return any contract or security change to the project owner.
- Run one complete local gate after all findings settle.
- Commit and push once, wait for the required GitHub result, and obtain project-owner signoff before
  Part 6G.

### Required proof

- Stable errors, correlation IDs, CORS, limits, timeouts, cancellation, transaction ownership, and
  OpenAPI match the approved contract.
- Browser tokens remain in memory and travel only to the approved FastAPI origin.
- Both frontend builds remain independent and no dual-write path exists.
- The sample protected endpoint preserves every Phase 5 authorization and non-disclosure rule.
- Backend, frontend, authentication, restart, persistence, log-safety, and cleanup gates pass in a
  fresh isolated environment.

### Rollback boundary

Parts 6B through 6E remain reversible while no business module imports them. After Phase 7 starts,
roll back dependent feature slices before removing the shared API foundation.

### Completion gate

The independent review has no unresolved finding. Local and GitHub gates pass, the branch is clean
and synchronized, and the owner signs off Parts 6A through 6F. Stop before billable Part 6G.

### Recommended model and effort

Use GPT-5.6 with high reasoning. Expect one or two sessions if earlier parts close their own findings.

## 6G: Early DigitalOcean architecture proof

### Objective

Prove the selected cloud architecture before business-module conversion.

### Hard prerequisites

- The owner separately authorizes billable DigitalOcean work and an expected monthly cost ceiling.
- Create the deferred spend alert or record a new explicit waiver.
- Verify the GitHub App installation is limited to `AadhikR/workloop-clinic`.
- Enable the approved administrator MFA control before exposing Keycloak.
- Confirm the target region, App Platform plan, managed PostgreSQL size, Spaces region, secret owners,
  teardown procedure, and acceptable test window.

### Scope

- Deploy the React migration shell from a locked install and production build.
- Deploy FastAPI with health and the Phase 6E protected profile endpoint.
- Deploy one production-mode Keycloak replica with external managed PostgreSQL.
- Create separate Workloop and Keycloak databases and users.
- Verify TLS termination, proxy headers, fixed Keycloak hostname, issuer, callback URLs, exact CORS,
  health endpoints, and private network behavior.
- Store and retrieve one private synthetic object in Spaces through FastAPI.
- Run Alembic through one controlled deployment job.
- Restart and redeploy every component, then prove that identities, schema, and the object persist.
- Record actual monthly cost, resource sizes, and teardown evidence.

### Security and data boundaries

Use synthetic identities and data only. Do not configure SMTP, invite real users, migrate a business
module, open public object access, use wildcard callbacks or CORS, or place a database credential in
the browser.

### Completion gate

The deployed browser completes a real Keycloak login, calls the protected FastAPI endpoint, reaches
managed PostgreSQL, stores and retrieves a private test object, survives redeployment, and exposes no
wildcard callback, CORS, or public-storage access. Cost evidence and teardown instructions are
complete, GitHub passes, and the owner signs off before Phase 7.

### Recommended model and effort

Use GPT-5.6 with high reasoning. Expect two or three sessions plus deployment wait time.

## Overall completion rule

Phase 6 closes only after Parts 6A through 6G pass their gates and receive project-owner signoff.
Planning this split does not authorize Part 6A or any cloud action.
