# Phase 6F independent review

## Status

The read-only Phase 6F review closed on 2026-09-07. All findings `6F-F001` through `6F-F006` are
resolved. The final confirmation found no remaining Phase 6F finding or regression.

## Review scope

An independent reviewer inspected the Phase 6A through Phase 6E result against:

- [`API_CONTRACT.md`](API_CONTRACT.md)
- [`SUBPHASE_PLAN.md`](SUBPHASE_PLAN.md)
- [`AUTHENTICATION_DESIGN.md`](../phase-3/AUTHENTICATION_DESIGN.md)
- [`PERMISSION_MATRIX_AND_RLS_DESIGN.md`](../phase-5/PERMISSION_MATRIX_AND_RLS_DESIGN.md)
- [`cutover-record.schema.json`](cutover-record.schema.json)
- the current FastAPI HTTP boundary, authentication dependencies, route declarations, and tests
- the cutover record validator and its tests

The reviewer made no repository edits. The primary implementation pass applied each correction, and
the reviewer checked the revised code and regressions after every correction group.

## Findings and dispositions

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| `6F-F001` | High | The strict duplicate-key JSON parser existed but was not used by a routed request body. | A request-only dependency now runs the strict parser before Pydantic validation. A regression proves duplicate keys return the common `invalid_request` response. |
| `6F-F002` | High | Client disconnects were observed only while mutation bodies were buffered, not while a matched request or service transaction was still running. | The HTTP boundary now retains the client receive channel for every matched request, races application work against disconnect, and cancels and awaits in-flight work so transaction cleanup completes. |
| `6F-F003` | Medium | Authenticated company limits reused the lower per-user class instead of the contract's distinct company ceiling. | Read, write, and financial or approval limits now have separate user and company classes with exact ceilings of 300/3,000, 60/600, and 20/200 per minute. |
| `6F-F004` | Medium | The cutover validator did not enforce the canonical schema's required fields, discriminator, or `additionalProperties` rules. | The validator now applies the checked-in canonical schema before semantic checks. Regressions cover a missing required field, the wrong `$schema`, and extra root and nested properties. |
| `6F-F005` | Medium | The first strict-body correction removed the generated OpenAPI request-body schema. | Route documentation now supplies a required `application/json` schema with aliases, required fields, and closed-object behavior. |
| `6F-F006` | High | An attempted OpenAPI correction introduced a FastAPI body parameter that could validate the last duplicate value before the strict parser ran. | Runtime parsing remains Request-only and OpenAPI metadata is supplied separately. A schema-invalid final duplicate still returns `400 invalid_request`, while the same protected request returns `401` first. |

## Final review conclusion

The final pass confirmed that strict parsing runs before model validation, OpenAPI remains accurate,
authentication precedence is unchanged, disconnect cancellation reaches service-owned transactions,
the approved rate limits are exact, and the cutover validator enforces both schema and semantic
rules. All six findings are closed without an owner-decision issue.
