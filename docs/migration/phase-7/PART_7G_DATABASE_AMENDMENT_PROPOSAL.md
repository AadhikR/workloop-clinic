# Phase 7G database amendment proposal

## Status

The project owner authorized Phase 7G on 2026-09-11 and approved decisions `7G-DB-D1` and
`7G-DB-D2` on 2026-09-11. Implementation may use this design. Any amendment requires another review
before implementation.

Decision `7G-DB-D1` covers the new employee audit actions. Decision `7G-DB-D2` covers two
branch-scoped `user_profiles` policies required by the approved portal-role routes. Approval of one
decision did not imply approval of the other. The owner approved both decisions.

## Verified preflight

- Branch `migration/fastapi-keycloak` is clean and synchronized with its remote at
  `784c0710a3886a3cbafde398731acc7360d2c477`.
- The migration graph has one head, `7d4a9c2e6b10`.
- No Docker container is running. The preserved volume `workloop-clinic_postgres_data` exists and
  remains untouched.
- Ports 25432, 28000, 28080, and 29000 are free. The final stack is reserved as Compose project
  `workloop-phase7g-final`, with temporary volume `workloop-phase7g-final_postgres_data`.
- Revision `8f6b2d1a4c70` is unused. The reserved migration is
  `backend/alembic/versions/8f6b2d1a4c70_add_phase7g_employee_audit_actions.py`, with
  `down_revision = "7d4a9c2e6b10"`.
- Fixture UUID prefix `7c700000-0000-4000-8000-` is reserved for Phase 7G employees and related
  rows. Suffixes `000000000001` through `000000000040` are reserved.
- Fixture UUID prefix `7c700001-0000-4000-8000-` is reserved for Phase 7G application users.
  Suffixes `000000000001` through `000000000010` are reserved.
- Fixture UUID prefix `7c700002-0000-4000-8000-` is reserved for Phase 7G idempotency keys.
  Suffixes `000000000001` through `000000000020` are reserved.
- The Phase 7F handoff records GitHub Migration foundation run 34614904388 as passed. The current
  shell has no GitHub CLI, so this preflight could not query the run again.

## Finding 1: employee audit actions are denied

`public.append_audit_event` currently rejects `role_changed`, `employment_access_changed`,
`employee_branch_corrected`, and `payroll_wps_changed` before it delegates to the Phase 5G function.
The delegated function does not recognize any named Phase 7G action.

Phase 7A names six Phase 7G actions. It assigns title, department, salary, and general status changes
to append-only job history without naming another audit action. This proposal does not invent audit
actions for those four workflows.

## Decision 7G-DB-D1: audit function amendment

### Public signature and ownership

Keep the public signature unchanged:

```text
public.append_audit_event(text,text,uuid,text[],text,jsonb) returns uuid
```

The replacement remains `LANGUAGE plpgsql`, `VOLATILE`, and `SECURITY DEFINER`. Its owner remains
`workloop_migration`, and its `search_path` remains `pg_catalog, public, pg_temp`. Revoke execute
from `PUBLIC` and grant it only to `workloop_runtime`.

Rename the exact current function to
`public._append_audit_event_phase7g_prior(text,text,uuid,text[],text,jsonb)`. Revoke all access to the
renamed function from `PUBLIC` and `workloop_runtime`. The new public wrapper handles the six Phase
7G actions below and delegates every other action to the renamed predecessor. The predecessor keeps
the existing explicit denial of `role_changed` and `employment_access_changed`.

### Common authorization and input checks

Every Phase 7G action requires all of these checks:

- `session_user` is `workloop_runtime`.
- The actor kind is `human`, the actor key is null, and the trusted business date is present.
- The application user and company context are present.
- The current principal resolves exactly once and has an active account, an admin profile in the
  context company, no linked employee, and no principal branch.
- The context role is `admin`, the context employee is null, and the selected context branch is
  non-null and belongs to the context company.
- `p_reason` equals its trimmed value and contains 1 through 1,000 characters.
- `p_metadata` is a JSON object. It must contain exactly the keys listed for the action.
- `p_changed_fields` equals the listed array. A subset, superset, duplicate, null, or different order
  is denied.

The function inserts the audit event with the context company and selected branch, actor kind
`human`, the context application user, null system and initiating actors, and the validated action,
entity, fields, reason, and metadata.

### Action catalogue

| Action | Entity and identifier | Exact changed fields | Exact metadata | Required committed state |
| --- | --- | --- | --- | --- |
| `employee_manager_changed` | `employee`, employee ID | `reporting_manager_id` | `previous_manager_id`, `new_manager_id` | The employee is in the context company and branch. Each metadata value is null or a canonical UUID. The values differ. `new_manager_id` equals the current employee value. A non-null new manager is a different active employee in the same branch with status `Active`, `Probation`, or `On Leave`. A non-null previous manager still identifies an employee in the same branch. |
| `employee_probation_confirmed` | `employee`, employee ID | `employment_status`, `probation_end_date` | `transition` equal to `probation_to_active` | The employee is active, has status `Active`, and has a null probation end date. |
| `employee_probation_extended` | `employee`, employee ID | `probation_end_date`, `probation_extended` | `previous_probation_end_date`, `new_probation_end_date` | Both metadata values are valid dates and the new date is later than the previous date. The employee is active, has status `Probation`, has `probation_extended = true`, and its probation end date equals the new date. |
| `employee_probation_terminated` | `employee`, employee ID | `active`, `employment_status`, `termination_date`, `termination_reason` | `transition` equal to `probation_to_terminated` | The employee is inactive, has status `Terminated`, has termination date equal to the trusted business date, and has termination reason equal to `p_reason`. |
| `employee_archived` | `employee`, employee ID | `active`, `employment_status`, `termination_date`, `termination_reason` | `transition` equal to `active_to_terminated` or `on_leave_to_terminated` | The employee is inactive, has status `Terminated`, has termination date equal to the trusted business date, and has termination reason equal to `p_reason`. Probation uses the separate termination action. |
| `employee_portal_role_changed` | `user_profile`, application-user ID | `role` | `transition` equal to `employee_to_manager` or `manager_to_employee` | Exactly one profile in the context company links the entity ID to an employee in the selected branch. The account and employee are active, employment status is `Active`, `Probation`, or `On Leave`, and the entity ID differs from the caller. The current role equals the transition target. |

The function validates UUID metadata with PostgreSQL UUID input validation before casting. JSON null
maps only to a null manager ID. String values must use canonical lowercase UUID spelling. Date
metadata must use `YYYY-MM-DD`.

A manager demotion writes one `employee_manager_changed` event for each reassigned report, then one
`employee_portal_role_changed` event for the profile. Archive and probation termination write one
manager event for each reassigned report, then the action event for the target employee. The service
performs these writes in the same transaction as the employee, history, and profile changes.

### Exact predecessor downgrade

The downgrade performs these operations in order:

1. Revoke runtime execute on the Phase 7G public wrapper.
2. Drop the Phase 7G public wrapper.
3. Rename `_append_audit_event_phase7g_prior` back to `append_audit_event`.
4. Restore owner `workloop_migration`, revoke all access from `PUBLIC`, and grant execute to
   `workloop_runtime`.

After downgrade, the function definition, owner, access control list, volatility, security mode,
configuration, and behavior must match revision `7d4a9c2e6b10`. The two older generic actions remain
denied before, during, and after Phase 7G.

### Catalogue and proof

Extend the `append_audit_event` entry in `scripts/phase-5g-catalogue.json` with the revision,
predecessor signature, six action definitions, entity types, exact field arrays, metadata keys, and
state checks above. Update the Phase 5G and 5H protected-function verifiers so they inspect the
delegation chain without granting runtime access to either private predecessor.

The focused Phase 7G verifier must prove every valid action and deny:

- non-runtime, non-human, scheduled-job, missing-date, inactive-principal, non-admin, manager,
  employee, unselected-branch, and foreign-branch contexts;
- unknown actions and both older generic employee actions;
- wrong, missing, foreign, or mismatched entity types and identifiers;
- empty, untrimmed, or overlong reasons;
- null, non-object, missing-key, extra-key, malformed, stale, or state-inconsistent metadata;
- reordered, duplicate, null, missing, extra, or unapproved changed fields;
- portal-role audit attempts for the caller, an admin profile, an unlinked profile, an inactive
  account, an inactive employee, an ineligible employee, or an employee outside the selected branch;
  and
- every action whose committed source state does not match its claimed action.

Each denial check compares employee, profile, job-history, and audit state before and after the
transaction. Migration checks prove one head, a repeated upgrade, downgrade to `7d4a9c2e6b10`, and
upgrade back to `8f6b2d1a4c70`.

## Finding 2: selected-branch portal-role access is blocked

The approved portal-role routes require an admin-selected branch. Role change, report reassignment,
and audit must commit in one transaction. The current `user_profiles` select and update policies
allow an admin to access another profile only when `public.workloop_branch_id()` is null. Employee
and report updates require that value to be the selected branch. Switching the trusted context
during a transaction would violate the fixed-context execution model.

No new table, role, column, function, or grant is needed. Runtime already has table select and
column-level update access for `user_profiles.role`.

## Decision 7G-DB-D2: branch-scoped profile policies

Add two permissive policies without changing the existing Phase 5E policies.

`phase7g_user_profiles_select_branch_runtime` allows `SELECT` to `workloop_runtime` only when:

- the trusted human context and currently resolved active admin principal match the context company;
- the context employee is null and the selected context branch is non-null;
- the profile company equals the context company and its employee link is non-null; and
- the linked employee exists in that company and selected branch.

This policy lets the portal-role reader distinguish an eligible active link from a present but
inactive or ineligible link. The repository checks account and employee eligibility through the
existing `public.is_scoped_active_app_user(app_user_id)` protected reader because target application
users are not directly visible through the runtime `app_users` select policy. The API still returns
only `{ employeeId, activated, role }`.

`phase7g_user_profiles_update_role_branch_runtime` allows `UPDATE` to `workloop_runtime` with equal
`USING` and `WITH CHECK` expressions only when:

- the same trusted admin and selected-branch checks pass;
- the profile belongs to the context company, links an employee in the selected branch, and is not
  the caller's profile;
- `public.is_scoped_active_app_user(app_user_id)` returns true for the linked application account;
- the linked employee is active and has status `Active`, `Probation`, or `On Leave`; and
- both the old and new profile roles are `employee` or `manager`.

The existing column grant limits the update to `role`. The policy creates no identity link, profile,
or Keycloak user. The service remains responsible for `expectedRole`, deterministic report locks,
complete reassignment, cycle checks, and one transaction.

The migration downgrade drops these two policies before restoring the audit predecessor. It leaves
the Phase 5E select and update policies unchanged.

Focused RLS proof must cover selected-branch read and role update, foreign company and branch denial,
self-role denial, inactive account denial, unlinked and ineligible employee denial, unsupported role
denial, unchanged state after each denial, and the exact Phase 5E policy definitions before and after
round trip.

## Scope that remains unchanged

This proposal adds no table, column, enum, job-history type, role, broad grant, default privilege, or
Keycloak operation. It does not alter employee, history, audit-table, or idempotency RLS. It does not
approve hard deletion, branch transfer, identity linking, account provisioning, contract lifecycle,
documents, insurance, offboarding, payroll, attendance, roster, or shift work.

## Decision request

Approve `7G-DB-D1` to add the six exact audit actions, protected wrapper, catalogue changes,
downgrade, and denial proof above.

Approve `7G-DB-D2` to add the two exact branch-scoped `user_profiles` policies, downgrade, and RLS
proof above.

Approval authorizes these database changes only as part of the already authorized Phase 7G. It does
not authorize Phase 7H or Phase 8.
