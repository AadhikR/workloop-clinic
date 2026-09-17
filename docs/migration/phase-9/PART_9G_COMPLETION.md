# Phase 9G completion

Status: implementation and local full-stack verification complete. Phase 9H is authorized next but
has not started.

## Delivered

- Added administrator-only WPS run and entry transitions, deterministic full and rejected-entry SIF
  input projections, immutable reasoned compliance overrides, and replaceable branch-period Nafis
  snapshots.
- Added revision `e3a7c9d1f5b2`. Runtime mutations use protected locking functions, direct table
  mutation remains revoked, and downgrade refuses to discard Phase 9G evidence.
- Added strict migration clients and views for WPS tracking, SIF preview data, compliance overrides,
  and Nafis snapshots. File generation and downloads remain assigned to Phase 12.
- Froze the matching legacy WPS, compliance, Nafis, and SIF-generation writers. The completed cutover
  names `migration-fastapi` as the sole read and write authority.
- Added Phase 9G contract, exact-predecessor, database-authority, lifecycle, frontend-client, and
  legacy-freeze checks to the routed workflow.

## Evidence

- The locked Python 3.12.10 backend gate passed 495 tests, Ruff lint and formatting, strict Pyright,
  and dependency checks. The unchanged disconnect-cancellation test crossed its half-second setup
  deadline under Docker Desktop; the routed GitHub backend job must pass the complete 496-test suite
  before this task closes.
- The canonical LF snapshot passed all 173 frontend unit tests, targeted ESLint, and both production
  builds.
- Fresh Compose project `workloop-phase9g-final` applied the migration repeatedly, replayed the full
  empty-schema chain, finished at the single drift-free `e3a7c9d1f5b2` head, and restored exact
  predecessor `b8e2c4d6f9a1` with audit-function digest
  `c6c027325e6c253383558f4da878f8b4f9b53db14f140c093f09a3775be87d94` before replaying the head.
- Phase 7G, Phase 8B through 8F, and Phase 9B through 9G database regressions passed. Phase 9G covered
  branch and role scope, optimistic concurrency, duplicate paid transitions, rejected-entry
  corrections, confirmation, closed compliance codes, immutable overrides, deterministic integer-AED
  rounding and ordering, Nafis replacement after a source change, audit actions, and cleanup.
- Container recreation preserved the database catalogue fingerprint, Keycloak signing-key IDs, and
  synthetic private-storage state. The post-restart authentication browser journey passed.
- Synthetic Workloop rows, Keycloak users, private objects, credentials, containers, networks, and
  temporary volumes were removed. `workloop-clinic_postgres_data` was not attached or changed; its
  creation time remains `2026-08-31T07:31:48Z`.

## GitHub result

The required routed GitHub result is recorded in the task report after the settled Phase 9G push.
