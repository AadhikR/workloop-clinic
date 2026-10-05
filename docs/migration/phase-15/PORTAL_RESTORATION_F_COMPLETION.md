# Portal restoration F completion

Status: the final local gate passed on October 5. GitHub and provider promotion remain pending.
This is the final restoration part. It must request whole-Phase-15 signoff after the delivered
release passes. It must stop before Phase 16.

## Restored workflows

F closes the inherited implementation gaps listed in `PORTAL_RESTORATION_PROGRESS.md`. The
administrator dashboard restores its warning groups, conditional setup checklist, five summaries,
optional Nafis panel, payroll trend, and recent runs. Both staff homes restore today's read-only
status, two summary cards, expiry warnings, assigned assets, and recent leave.

Complete pagination now precedes directory, development, appraisal, incident, asset, and repayment
totals. Failed later pages, duplicate records, malformed cursors, and changed source versions fail
closed. Clinical credential and workforce cards have sanitized paged detail with the same eligibility
rules as their counts. Branch expiry combines fixed dates and uploaded clinical documents without
private document or storage values. CME detail lists the records that contribute to confirmed totals.

Administrator appraisal review and manager submission save all five canonical sections in one
transaction. Eligible appraisal, incident, and expense removal archives the source row and permits
scoped restoration. Pending advance cancellation retains financial history. Manager leave history
uses current report or delegation scope and the actor's last 90 days of decisions. Personal advance
detail exposes confirmed installments and payments without reviewer or payroll-run identifiers.

Insurance and contract forms use typed fields, authoritative current snapshots, and confirmations.
Identical failed retries retain input and keys. Contract PDF delivery uses server-rendered bytes and
the protected output audit. Document rejection and removal retain their failed reason and reset
with employee selection. The lifecycle disclosure stays open through a confirmed portal-role refresh.

Documents, benefits, appraisals, and incidents use the existing deferred loader. This keeps the
production download inside the unchanged budget and retains explicit loading and failure recovery.

## Schema and recovery

Append-only revision `f3a5c7e9b1d4` follows `e2c4f6a8b0d3`. Earlier revisions remain unchanged.
Seven migration-owned protected functions cover retained records, administrator section rating,
pending cancellation, manager leave history, owner repayment progress, manager section rating,
and complete manager submission. Runtime execution is explicit and PUBLIC execution is denied.

Protected commands recheck current scope, lock authoritative rows, require versions and idempotency,
and commit their audit with the mutation. Ordinary writes cannot change archival markers. Downgrade
refuses retained markers or F audit that require preservation. An eligible exact predecessor
downgrade and repeated upgrade pass after clearing only disposable proof data. Recovery must retain
compatible frontend, backend, and schema artifacts and must never downgrade automatically.

The cloud migration entrypoint now requires the F head. A regression compares its release guard
with the actual single head resolved from the checked-in Alembic scripts. Provider promotion must
update the compatible backend components and migration manifest before publishing the frontend.

## Verification

The settled backend gate passes 763 tests with the six existing relationship warnings, whole-backend
lint and formatting, types, and dependency checks. The frontend gate passes 449 tests, production
build, changed-file lint, and repository guards. Focused cloud deployment tests pass the checked-in
head guard and pre-deploy failure behavior.

Disposable PostgreSQL proof covers scope and raw-write denial, versions, locks, replay, audit rollback,
concurrent reviews, composite profile rollback, manager cycles, delegation expiry, clinical
count/detail agreement, owner repayment totals, and 101 additional training, certification, and
incident records across pages. It also proves branch-logo rollback, current insurance and contract
reads, failed insurance and contract writes, protected contract PDF audit, and exact cleanup.
The affected historical chain and deep database authority checks pass.

The complete historical route audit and updated A through F interactions are in
`evidence/restoration-f`. The audit manifest records each view and state separately. Browser fixtures
prove presentation, keyboard use, payloads, confirmations, conflict, failed retry retention, and
mobile containment. All 46 views pass with 506 state captures. The final B, E, and F interaction
checks also pass after deferred loading. Real administrator, manager, and employee journeys pass
against the final isolated backend. The persisted catalogue, signing keys, synthetic files, S3
objects, and scan state survive restart. Shared accessibility and recovery pass all 46 routes.
Populated payroll and leave layouts pass. The final gate verifies zero synthetic company, branch,
employee, application-user, profile, and realm-user rows and safe logs. It then removes only the
verified task-owned stack. GitHub and delivered verification remain separate release gates.

`evidence/restoration-f/performance.json` records the settled local profile. It passes 221,627
compressed initial bytes, zero warm-route transfer, a 192,536-byte largest compressed chunk,
111.5 ms route-change p95, 57.9 ms form-feedback p95, and 7.05 ms representative API p95.
Budgets remain unchanged.

## Release and preservation

The accepted payroll frontend `e42808894b1c1a66c5e42738bbf9fa0cb46c538e` remains live. The current
provider deployment is `6be23b76-d3a8-4d93-8172-7b12baeb7a4d`. F has not promoted yet.
The final release must bind its reviewed commit, passing GitHub run, backend digest, frontend
digests, migration head, deployment identities, live synthetic evidence, and exact cleanup.

The task uses only synthetic data and files. It preserves the Phase 13 archive, `workloop-clinic-dev`,
`fra1-default`, provider resource counts and sizes, disabled automatic deployment, and the USD 15
temporary-run cap. `workloop-clinic_postgres_data` is never attached, mounted, inspected, modified,
deleted, or recreated. The local stack uses only verified `workloop-restoration-f` resources.
