# Phase 6A completion record

## Status

The project owner approved Phase 6A decisions `6A-D1` through `6A-D14` without amendment on
2026-09-07. The API contract, independent review, and documentation validation are complete. Phase
6A is closed. Phase 6B requires separate project-owner authorization.

## Approved contract

[`API_CONTRACT.md`](API_CONTRACT.md) is the canonical HTTP contract for later Phase 6 work and
business-module migrations. It fixes:

- `/api/v1`, camelCase JSON, and exact UUID, date, time, instant, decimal, money, null, and enum forms;
- strict request and response models, success envelopes, cursor pagination, filters, sorts, and
  validation behavior;
- one error body, 24 registered safe error codes, deterministic error precedence, server-generated
  UUIDv4 correlation IDs, and `X-Correlation-ID`;
- service-owned authorized transactions that keep Phase 5 context, protected SQL, audit, commit, and
  rollback in one transaction;
- UUIDv4 idempotency keys, versioned canonical fingerprints, transaction-scoped nonblocking locks,
  current-authorization replay checks, seven-day retention, and HMAC-bound browser recovery;
- the exact local CORS origin, an empty cloud allowlist until Phase 6G, fixed request and future upload
  limits, server and browser deadlines, cancellation cleanup, and pre-public rate limits; and
- generated OpenAPI review and `/api/v2` rules for breaking changes after a consumer ships.

The contract preserves in-memory access tokens, PostgreSQL-owned business authorization,
non-disclosing 403 and 404 behavior, exact-origin CORS, and one transaction owner per request. It adds
no business endpoint, mutation, persistence table, upload route, or cloud origin.

## Independent review

An independent read-only reviewer checked the error and idempotency sections against the Phase 3
authentication and Phase 5 authorization designs and the current FastAPI boundary. The review raised
12 findings. The contract resolved all of them, including workflow-specific conflict codes, replay
authorization, nonblocking duplicate claims, canonical fingerprints, browser recovery, error order,
validation messages, replay headers, health errors, CORS ordering, rate-limit precedence, and account
privacy. The closed ledger is in
[`PART_6A_INDEPENDENT_REVIEW.md`](PART_6A_INDEPENDENT_REVIEW.md).

## Validation

The documentation gate checked the four changed design and status files plus this completion record.
Decision IDs `6A-D1` through `6A-D14`, all 24 error codes, and review IDs `6A-IR-01` through
`6A-IR-12` are present and unique. Markdown fences are balanced, headings have no level jumps, local
links resolve, and the unfinished-marker, trailing-space, curved-quotation, and changed-file checks
pass.

No backend, frontend, database, Alembic, Docker, authentication, restart, or full-stack gate ran.
Phase 6A changed documentation only, as required by
[`VERIFICATION_WORKFLOW.md`](../VERIFICATION_WORKFLOW.md).

## Resource and rollback boundary

Phase 6A used no real data, production account, SMTP service, paid service, database, container,
cloud resource, runtime environment file, or generated OpenAPI artifact. The preserved
`workloop-clinic_postgres_data` volume remains untouched at its PostgreSQL 16 boundary.

Rollback is one documentation revert. No runtime or schema rollback is needed.

## Stop condition

Phase 6A is complete after its documentation commit passes the required GitHub workflow. Record the
workflow URL in the completion report rather than creating another commit. Stop before Phase 6B and
request separate authorization.
