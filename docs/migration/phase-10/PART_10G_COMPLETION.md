# Part 10G completion

Status: complete.

## Result

Part 10G makes FastAPI the sole authority for selected-branch roster draft reads and mutations,
leave-conflict review, effective staffing gates, and immutable compliance overrides. Draft create,
replace, and guarded delete derive company and branch scope from trusted context, enforce the URL
month, reject ineligible employees and inactive shifts, and use optimistic versions and idempotency.

Validation returns approved and manager-approved leave conflicts plus exact effective staffing
shortfalls. Disabled staffing enforcement returns no staffing report. The two closed exception codes,
`leave_conflict` and `staffing_shortfall`, require a reason, trusted actor, affected month, canonical
violation digest, and immutable violation snapshot. An override applies only while that exact digest
remains current.

Alembic revision `a1c3e5f7b902` follows `d0f6b8e2a753`. It adds roster draft versions and bounds,
published-row and version guards, override linkage and uniqueness, a narrowly scoped protected
override function, and the roster idempotency resource. Its downgrade restores the exact 10F
catalogue and refuses to discard versioned drafts or immutable overrides.

The `roster-drafting` cutover is complete with `migration-fastapi` as its only read and write
authority. Matching legacy draft create, replace, and delete paths fail closed. Publication,
employee schedules, actual-hours evidence, payroll projection, and swaps remain disabled until their
later subphases.

## Review corrections

The inherited implementation was reviewed before completion. The review closed cross-month replace
and delete access, aligned planned-hour validation across browser, API, and database boundaries,
made response parsing reject inconsistent readiness and violation arithmetic, and added exact
override response validation. It also reconciled the approved leave-conflict golden case by adding
the immutable `leave_conflict` exception beside staffing exceptions, without making either exception
apply to a changed violation.

## Gate evidence

The final database-sensitive gate ran in the fresh `workloop-phase10g-gate` stack:

- Ruff formatting and lint, strict Pyright, dependency checks, and all 561 backend tests passed.
- All 208 frontend unit tests, changed-file ESLint, and both legacy and migration production builds
  passed.
- The migration applied twice. Single-head and model-drift checks, a complete empty-schema replay,
  exact 10G predecessor restoration, and deterministic replay passed.
- Current-head Phase 10D through 10G database checks passed on a clean database. The focused 10G
  proof covered month and branch scope, draft lifecycle, stale and concurrent writes, approved and
  manager-approved leave, effective and disabled staffing rules, both exact override codes, forced
  rollback, published-row immutability, and retained swap protection.
- FastAPI and Keycloak were healthy after a no-build restart. The full signed-in administrator,
  manager, and employee browser journey passed after that restart.
- The database catalogue fingerprint, Keycloak signing-key identifiers, and synthetic storage object
  were unchanged across the restart. Synthetic database rows, identities, and storage artifacts were
  removed, and service logs passed credential and token scans.

The routed GitHub result is reported in the task handoff after the final push. This local gate record
does not contain a workflow URL.

## Resource boundary

Verification used synthetic local data and the disposable `workloop-phase10g-gate` volumes. The
protected volume `workloop-clinic_postgres_data` was never attached, modified, deleted, or recreated.
The isolated Phase 10G stack remains available for the next authorized subphase.

## Writing review

The repository-required `.opencode/skill/unslop/SKILL.md` was absent. New prose received a manual
review for direct language, concrete claims, sentence-case headings, and consistent terms.

## Next subphase

Part 10H is authorized next. It owns atomic versioned roster publication, published personal
schedules, actual-hours and roster-overtime authority, and the approved roster projection consumed
by payroll. Shift swaps remain outside 10H and begin only after publication is verified.
