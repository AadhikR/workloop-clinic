# Part 10I completion

Status: complete.

## Result

Part 10I makes FastAPI the sole authority for shift-swap reads and commands. Employees and managers
can list swaps in which they participate, submit a request against the current published roster, and
cancel their own pending request. Administrators can list the selected branch, reject a pending
request with a reason, or approve it through the protected database function.

Submission is a protected database operation. It derives the requester and scope from the trusted
transaction context, resolves only the two requested publication memberships, validates both
employees, and records the request and first history row atomically. Participant names are exposed
through a separate protected lookup that revalidates the principal and returns names only for a
visible request. The runtime role no longer has direct insert permission on the request table.

Approval locks and rechecks the request, published month, both employees, both assignments, and both
publication memberships. It rejects changed roster sources, ineligible employees, actual-hours
evidence, inactive shifts, approved leave on the exchanged dates, and a roster source already used
by payroll. A successful approval changes exactly two assignment owners, creates one immutable
successor publication, updates the request, and appends history and audit in one transaction.

Alembic revision `c6e8a1b3d927` follows `b4d7f9a2c816`. Its downgrade restores the exact 10H
function, grants, policies, and idempotency constraint, and refuses to discard retained swap,
history, or swap-publication data. The `shift-swaps` cutover is complete with `migration-fastapi` as
its only read and write authority. Matching legacy swap helpers fail closed.

## Review corrections

The inherited implementation was reviewed before completion. Staff submission initially tried to
read and lock another employee's private publication membership. That was replaced with a narrow
protected submission function; roster visibility was not widened. The review also removed employee
table joins from participant reads, added a principal-revalidating name lookup, used PostgreSQL's
built-in SHA-256 function instead of an unavailable extension, aligned rejection fields with the
retained schema constraints, made verification cleanup retry-safe, and declared the partial
expression index in ORM metadata so Alembic reports no drift.

## Gate evidence

The final database-sensitive gate ran against the fresh isolated `workloop-phase10i-gate` stack:

- All 569 backend tests and all 217 frontend unit tests passed. Ruff lint and formatting, strict
  Pyright 1.1.411, changed-file ESLint, and the migration production build passed.
- The migration applied repeatedly with one head and no model drift. The exact 10I predecessor
  rollback preserved the retained 10H function body and replayed deterministically.
- Current-head deep verifiers passed from employee lifecycle through Phase 10B and from Phase 10D
  through Phase 10I. The 10C assertions also passed; its standalone cleanup cannot follow a verifier
  that deliberately retains an attendance period, so CI keeps those checks in their supported
  isolation order.
- The 10I database proof covered protected submission, participant privacy, duplicate rejection,
  forced rollback, exact two-row approval, successor publication identity, cancellation, rejection,
  history, and audit.
- Strict frontend tests cover personal and selected-branch reads, request, cancellation, rejection,
  approval, malformed responses, unsafe queries, changed command shapes, and the complete legacy
  freeze.

The routed GitHub result is reported in the task handoff after the final push. This local record does
not contain a workflow URL.

## Resource boundary

Verification used synthetic local data and disposable `workloop-phase10i-gate` volumes. The
protected volume `workloop-clinic_postgres_data` was never attached, modified, deleted, or
recreated.

## Writing review

The repository-required `.opencode/skill/unslop/SKILL.md` was absent. New prose received a manual
review for direct language, concrete claims, sentence-case headings, and consistent terms.

## Next subphase

Part 10J is authorized next. It owns the independent Phase 10 review, complete dependency and
cutover proof, append-only history and rollback review, final restart and browser journey, resource
cleanup, and the Phase 10 signoff request. Phase 11 remains outside the current authorization.
