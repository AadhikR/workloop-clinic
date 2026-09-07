# Phase 6A independent review

## Status

The read-only Phase 6A review closed on 2026-09-07. All findings `6A-IR-01` through `6A-IR-12` are
resolved in [`API_CONTRACT.md`](API_CONTRACT.md). No error-safety or idempotency finding remains open.
The project owner approved the contract decisions without amendment on the same date.

## Review scope

An independent reviewer inspected the error and idempotency contracts against:

- [`API_CONTRACT.md`](API_CONTRACT.md)
- [`SUBPHASE_PLAN.md`](SUBPHASE_PLAN.md)
- [`AUTHENTICATION_DESIGN.md`](../phase-3/AUTHENTICATION_DESIGN.md)
- [`PERMISSION_MATRIX_AND_RLS_DESIGN.md`](../phase-5/PERMISSION_MATRIX_AND_RLS_DESIGN.md)
- the current FastAPI authentication, authorization, CORS, and transaction code

The reviewer made no repository edits. The primary implementation pass applied each correction, and
the reviewer confirmed the result after every group of changes.

## Findings and dispositions

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| `6A-IR-01` | High | A generic 409 code conflicted with Phase 5's workflow-specific conflict rule. | `state_conflict` now covers only non-workflow optimistic checks. Each workflow must register its own safe 409 code before its route ships. |
| `6A-IR-02` | High | A completed replay could return stored data after the caller's role, delegation, relationship, or object visibility changed. | Every replay now rechecks the current principal, route authorization, and stored-resource visibility. Failed checks return the normal safe 403 or 404. |
| `6A-IR-03` | High | An uncommitted idempotency row could not support the promised immediate in-progress response. | A precisely derived transaction-scoped advisory lock now gives a nonblocking 409 without a second transaction or visibility into an uncommitted row. |
| `6A-IR-04` | High | The request fingerprint did not define defaults, absent values, normalization, byte encoding, or deployment-version handling. | The contract now defines a typed value tree, an absent tag, canonical scalar forms, Unicode NFC, RFC 8785 bytes, SHA-256, and retained fingerprint versions. |
| `6A-IR-05` | High | An in-memory key could not recover from reload or restart, and ambiguous client outcomes had no exact retry rule. | The client keeps only scoped opaque recovery data for seven days, uses protected status recovery, and follows an outcome-by-outcome key rule. Replay-time 403 and 404 responses require a status check. |
| `6A-IR-06` | Medium | Several simultaneous faults could produce different public errors depending on framework execution order. | The contract now fixes request processing and error precedence from correlation and CORS through commit. Stage 12 alone validates and acquires an idempotency key. |
| `6A-IR-07` | Medium | Validation detail messages had no actual allowlist or deterministic path format. | Six detail codes now have exact messages, external paths, array-index syntax, a 20-item cap, and stable ordering. Raw validator messages are forbidden. |
| `6A-IR-08` | Medium | Replay storage allowed unspecified "safe" response headers. | Only `Location` may be stored. Every other response header is regenerated or excluded. |
| `6A-IR-09` | Medium | `/health` sat outside `/api/v1`, so its Phase 6B error behavior was ambiguous. | Health keeps its current 200 body. Its failures adopt the common safe 503 body and correlation header. |
| `6A-IR-10` | High | Route matching before CORS could return 404 or 405 before a preflight or disallowed-origin decision. | Origin and preflight handling now precede ordinary route matching. Allowed preflights end at that stage; supplied disallowed origins return the registered safe 403. |
| `6A-IR-11` | Medium | Anonymous, protected, authentication-check, and invalid-token limits had contradictory precedence. | Stage 4 now selects 60, 30, or 600 per trusted IP by route class. Stage 6 applies the separate 60-failure invalid-token bucket only after the route bucket passes. |
| `6A-IR-12` | Medium | An unkeyed account-derived recovery namespace could expose predictable application-user IDs. | Recovery namespaces now use a dedicated server-secret HMAC, a public random key ID, purpose separation, and at least seven days of current and prior-key overlap. |

## Final review conclusion

The final confirmation pass found no remaining omission, contradiction, unsafe disclosure, replay
authorization gap, ambiguous error order, or unresolved idempotency behavior. The review closes the
independent-review requirement only. It does not approve the contract or authorize Phase 6B.
