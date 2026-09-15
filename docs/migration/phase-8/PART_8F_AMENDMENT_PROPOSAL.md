# Phase 8F amendment record

Status: approved by the project owner on 2026-09-15 through the standing Phase 8F authorization.

The Phase 8F preflight found two database gaps. Delegations had no optimistic version, and the
runtime role could not safely project or lock current approval authority without broadening table
access. The existing protected audit function also had no human-decision or delegation actions.
Revision `e8f4c7b2a610`, with predecessor `d1e5f8a2c904`, makes only the amendments listed here.

## Delegation version

Add `leave_approval_delegates.updated_at` as non-null `timestamptz`, defaulted from
`statement_timestamp()`. Administrator update and delete commands require the returned timestamp.
The service permits both commands only while the existing and replacement `from_date` are later
than the trusted business date. Active and expired rows remain immutable.

The revision adds no new delegation constraint or index. Creation and mutation take a
`SHARE ROW EXCLUSIVE` table lock, then lock the two employee rows in UUID order. That order makes
the existing overlap check safe against concurrent administrator writes without changing the
historical table contract.

## Protected authority functions

Add six `SECURITY DEFINER` functions owned by `workloop_migration`. Each has the pinned search path
`pg_catalog, public, pg_temp`; public access is revoked; `workloop_runtime` receives execute only.
No table grant is added.

| Function | Purpose |
| --- | --- |
| `leave_decision_visibility(uuid)` | Return `directReport`, `activeDelegation`, `administrator`, or null from the verified human context, current employee relationship, trusted date, and same branch. |
| `leave_queue_employee(uuid)` | Return the exact queue employee projection after the same authority check. |
| `leave_decision_employee_status(uuid)` | Return only the status needed for sick-balance accounting after the same check. |
| `lock_leave_decision_authority(uuid)` | Lock the target, current reporting manager, and active delegation where applicable, then repeat the authority check. |
| `read_leave_audit_projection(uuid)` | Return the bounded domain-audit projection to the request owner, a current approver, a recorded decision actor, or the selected-branch administrator. |
| `append_leave_domain_decision_audit(uuid,text,text,text,text)` | Insert one validated human decision into `leave_audit_log` after proving current request state, actor fields, transition, authority, and required reason. |

These functions are narrow substitutes for direct reads or writes that forced RLS intentionally
hides from the runtime role. They expose no company-wide employee row, delegation row, actor email,
balance value, request reason, attachment key, or provider field.

## Protected audit actions

Rename the existing protected function to `_append_audit_event_phase8f_prior`, remove runtime access
to that predecessor, and install a wrapper with the original signature, owner, volatility, security
mode, search path, and runtime execute grant. Unknown actions delegate unchanged.

The wrapper adds exactly these request actions:

- `leave_request_manager_approved`
- `leave_request_manager_rejected`
- `leave_request_approved`
- `leave_request_rejected`

Each requires entity type `leave_request`, changed fields `status,balance`, the matching latest
domain-audit row, the recorded current actor, and metadata containing only `transition` and
`decision_source`. The source must be current `directReport`, `activeDelegation`, or
`administrator` authority. Rejection reasons cannot be blank.

It also adds `leave_delegation_created`, `leave_delegation_updated`, and
`leave_delegation_deleted`. Those actions require a selected-branch administrator, the exact field
list and fixed reason, and no metadata except the two employee IDs needed to validate deletion
before the row is removed.

The decision transaction locks request, authority, leave type, settings, attachment, and balance;
changes request and balance; writes domain audit; appends protected audit; and completes
idempotency under one transaction owner. It calls no leave notification function.

## RLS and transition rationale

No RLS policy, role, table grant, business constraint, or index changes. Existing forced RLS stays
in force. The protected functions re-evaluate the same trusted context and return null for an
inaccessible target, preserving the safe not-found boundary.

The existing six-status constraint already permits the Phase 8A transition table. This amendment
clarifies that a selected-branch administrator may decide a one-level `Pending` request directly:
approval becomes `Approved`, and rejection becomes `Rejected`. A staff decision on a one-level
request becomes `Approved`; a two-level approval becomes `ManagerApproved`; a staff rejection
becomes `ManagerRejected`; and an administrator finalizes `ManagerApproved` as `Approved` or
`Rejected`. No new status or legal-policy rule is introduced.

## Rollback

Downgrade removes the delegation timestamp and all six Phase 8F functions, drops the audit wrapper,
and restores `_append_audit_event_phase8f_prior` under its original name with its original owner and
runtime grant. The exact predecessor definition and access list must hash identically after the
round trip. Committed request, balance, delegation, and audit history is not deleted by operational
rollback; migration decision routes must be disabled before any legacy writer is restored.
