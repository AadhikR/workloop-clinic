# Phase 5A completion record

## Status

Phase 5A completed its documentation-only gate on 2026-09-06. The project owner had already signed
off Phase 4 and authorized Phase 5A. The owner then approved `5A-D1` through `5A-D20`, the full
54-table catalogue, and all 119 legacy-policy reconciliation identities without amendment.

The commit containing this record must pass the existing GitHub workflow. The task handoff records
that post-commit result, so this file does not require another documentation-only commit. Phase 5B
has not started and requires separate authorization.

## Approved design

[`PERMISSION_MATRIX_AND_RLS_DESIGN.md`](PERMISSION_MATRIX_AND_RLS_DESIGN.md) is the authorization
contract for later Phase 5 work. It defines:

- every supported and unsupported read, create, update, delete, workflow, and system operation for
  the 54 Phase 4 target tables;
- tenant, selected-branch, self, one-level direct-report, current delegation, migration, seed,
  expiry-processing, and storage-reconciliation scope;
- protected fields, workflow states, separation of duties, inaccessible-object responses,
  transaction-local PostgreSQL context, RLS policy families, and exact operation grants;
- all 119 Phase 4 `Replace in Phase 5` and `Omit superseded` dispositions;
- domain audit history plus the approved future `audit_events` table, and the approved private
  storage-operation outbox with bounded, reserved retries; and
- application and RLS test obligations for all 19 fixture authorization controls.

PostgreSQL RLS remains defense in depth. FastAPI dependencies and scoped repository statements are
the primary authorization boundary. Keycloak roles, browser fields, email addresses, and
caller-supplied identifiers grant no business scope.

## Independent review

An independent GPT-5.6 reviewer inspected the named Phase 0, 3, 4, and 5 documents, authentication
code, models, migrations, runtime grants, fixtures, tests, and the draft. The reviewer made no edits.

The first pass found 45 issues. Corrections and owner decisions led to three more review cycles and
six further findings. The project owner approved the product and schema decisions. Editorial and
contract corrections stayed within those approvals. The final pass closed `IR-01` through `IR-51`
and found no remaining omission, contradiction, unsafe grant, unsupported scope, or new decision.
Every finding and disposition is recorded in the design.

## Documentation validation

The final checks proved:

- the numbered catalogue has 54 unique rows and exactly matches the 54 Phase 4 target tables;
- the reconciliation has 119 unique `(table, policy name)` identities and exactly matches the Phase
  4 source;
- the fixture mapping has 19 unique controls and exactly matches `NEGATIVE_CONTROL_MATRIX`;
- all 20 approved decision IDs and all 51 review finding IDs appear once;
- the allow-and-deny rules do not contradict the field, state, retention, scope, grant, or helper
  contracts; and
- Markdown fences and heading levels are valid, local links resolve, and the files contain no
  unresolved placeholder, trailing whitespace, nonstandard dash, or curved quotation mark.

`git diff --check` passed. Git printed only the preserved working-copy line-ending warnings. No
backend, frontend, Compose, or database suite ran because Phase 5A changed documentation only.

## Boundaries and next step

Phase 5A added no authorization code, repository, RLS policy, grant, database helper, schema
revision, API route, frontend change, fixture, secret, or external resource. It used no real data
and did not touch the preserved PostgreSQL 16 volume. The expected cloud cost change is zero.

Production audit retention still needs legal and security approval before real data is allowed.
Manual storage requeue needs its own approved operator procedure. Both limits are explicit in the
approved design and do not authorize any implementation.

Stop before Phase 5B. It requires separate project-owner authorization.
