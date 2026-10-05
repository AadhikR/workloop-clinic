# Portal restoration F working record

Part F is in progress on `migration/fastapi-keycloak`, starting from
`6b4913824f547dce21c5f19e0ea15e689ec055ae`. This file records decisions and focused evidence.
It is not the completion gate or a parity certificate.

## Scope and preservation

The standing restoration authorization covers the remaining backend gaps, all 46 historical views,
the final local and GitHub gates, and promotion to the existing development app. Phase 16 remains
outside this task. The accepted payroll release stays live until the settled F release passes.

Use only synthetic records and files. Preserve the Phase 13 archive, `workloop-clinic-dev`,
`fra1-default`, resource counts and sizes, the USD 15 cap, and disabled automatic deployment.
Never attach, mount, inspect, modify, delete, or recreate `workloop-clinic_postgres_data`.

## Decisions

- Add append-only revision `f3a5c7e9b1d4` after `e2c4f6a8b0d3`. Earlier revisions remain unchanged.
- Administrator removal archives pending appraisals in active cycles, open incidents, and expenses
  that remain pending or rejected and have no payroll link. Restoration checks the same states.
  Source rows, receipts, and audit remain. Completed or closed records cannot be removed.
- Administrator cancellation applies only to pending advances with no disbursement or repayments.
  Active and settled advances retain the existing repayment and settlement commands.
- Administrator section rating has a separate database-owned command and audit action. It locks
  the appraisal and active cycle, checks the expected version, and retains manager restrictions.
- Manager recent history includes the actor's own decisions from the last 90 days. Every page
  checks current report or delegation visibility. Former reports and expired delegations disappear.
  The response includes a safe actor label, reason, and time, without application-user identifiers.
- Own advance detail exposes installment and payment amounts, dates, and payroll periods. It
  omits reviewer and payroll-run identifiers. Every page carries the same source version. The
  client checks payment totals and installment totals against the authoritative balance.
- Shared collections use stable cursors and complete traversal before publishing totals. A failed
  later page or duplicate row rejects the collection instead of presenting a partial summary.
- Branch expiry reads fixed dates and uploaded document dates through one paged projection.
  Fixed dates use 60 days. Uploaded clinical documents use 90 days. It excludes private document
  numbers, storage paths, hashes, and signed URLs.
- Clinical counts and detail use the same scan-aware credential selection. Safe detail includes
  employee name, source type, expiry date, and status.
- Asset history uses an approved identity join for assigned-by labels. Administrator identities
  display `Administrator`; unavailable labels display `Unknown actor`.
- Manager appraisal submission saves the complete canonical five-section review in one transaction.
  It locks the appraisal, active cycle, and employee, then rechecks the current reporting relationship.
  It derives the weighted rating on the server and writes reviewed status and audit together.
  It accepts no reviewer identity, overall rating, calibration, or administrator comment fields.
- Clinical workforce cards use active staff, scan-eligible verified credentials, and current immutable
  roster publication membership. Each paged detail uses the same predicate as its count. Fixed licence
  profile dates remain expiry warnings and do not create verified credential compliance.
- Manager report selectors and the employee directory traverse the complete collection before
  rendering rows or counts. They reject duplicate rows, broken cursors, and failed later pages.
- Administrator home restores the ten warning groups, conditional setup checklist, five summary
  cards, optional Nafis panel, payroll trend, and recent runs in that order. It reads scoped server
  aggregates and the complete payroll collection. Changed dates, headcount, or run counts fail closed.
- Employee home places today's status above the two leave and payslip summaries, then optional
  document warnings, assigned assets, and recent leave. Fixed identity warnings use 60 days and
  also retain overdue dates so an unresolved expiry does not disappear.
- Insurance reads current coverage and its version from a protected selected-employee route.
  Policy and dependant editors use typed fields and confirmations. Identical failed retries keep
  their inputs and idempotency key. Contract actions read the authoritative current snapshot.
- Contract printing uses the existing bounded server PDF renderer and protected output audit.
  It records the employee's current four salary components, matching the historical contract letter.
  The directory's separate legacy allowance remains in its total package. Neither view recalculates
  payroll or changes salary authority.
- Browser timestamps contain milliseconds. Shared version comparison accepts the corresponding
  stored instant within that wire precision. It still rejects changed timestamps.
- Document editors reset on selected-employee changes. Rejection and removal require dialogs,
  retain failed inputs and keys, and publish success only after the server confirms the write.
- The employee lifecycle disclosure retains its open state for the same employee through a confirmed
  portal-role refresh. Branch or employee changes reset its scope.
- The cloud migration entrypoint requires F's head. A regression resolves the checked-in Alembic
  scripts and compares their actual single head to the release guard. The final provider migration
  job must receive the same head before the frontend changes.
- Documents, benefits, appraisal, and incident work areas load through the existing deferred-module
  loader. The initial production download exceeded its budget before this change. The final build
  meets the unchanged limit and retains explicit loading and load-failure recovery.

## Focused evidence

The isolated `workloop-restoration-f-proof` PostgreSQL project applies the F head. Its checked
Compose configuration uses only project-prefixed volumes. The focused database verifier proves
archival and restoration, retained source rows, stale-version rejection, branch denial, staff
denial, idempotent replay without duplicate audit, raw archival-marker denial, audit-failure
rollback, concurrent section rating, owner-only repayment totals, scan-aware count/detail
agreement, current-report history, and the 90-day history window.

Focused frontend tests cover complete traversal, malformed pages, later-page failure, repayment
source changes, mismatched totals, and rejection of private projection fields. New client and
connected view lint passes.

The PostgreSQL proof also passes composite profile rollback and replay, self and indirect manager
cycle denial, delegation expiry, pending advance cancellation, a 101-record training collection,
clinical workforce count/detail agreement, CME contribution totals, atomic administrator review,
and atomic manager submission. Manager submission rejects changed reporting scope, rolls back every
rating when its final audit fails, and replays without duplicate audit. Exact predecessor downgrade
and repeated upgrade pass after clearing only the disposable proof's retained markers and audit.

The updated personal browser proof passes for both staff roles. It covers complete manager appraisal
submission, failure retention, identical retry payload and key, all personal routes, and dark mobile
containment. New captures are in `evidence/restoration-f/personal`. The historical E captures remain.

## Remaining gate work

The complete route audit passes all 46 views with 506 captures covering populated desktop, light
mobile, dark mobile, empty, unavailable, loading, denied, and keyboard navigation. Its manifest is
`evidence/restoration-f/routes/route-audit.json`. Focused action checks pass all clinical detail
groups, retained conflict and restoration retries, advance cancellation replay, and CME contributors.
Updated A through E interaction checks pass for the changed controls. The document proof covers
rejection and removal failures with identical retry payloads and keys. Insurance and contract proof
covers failed saves, authoritative coverage and contract snapshots, and protected PDF opening.

Disposable PostgreSQL proof also passes the branch-logo update with rollback and staff denial,
101 additional training, certification, and incident records across pages, current coverage reads,
insurance and contract write rollback, contract PDF audit and scope denial, exact predecessor
rollback, and repeated upgrade. The contract renderer regression passes deterministic output,
fixed source time, and changed-source digest checks.

The settled backend gate passes 763 tests, lint, formatting, types, and dependency checks. The
frontend gate passes 449 tests, production build, changed-file lint, and repository guards. The
isolated database gate passes the affected historical chain and deep authority checks. F's verifier
now removes its exact synthetic additions and base fixtures before the storage restart proof.
The final performance profile passes 221,627 compressed initial bytes, zero warm-route transfer,
192,536 bytes for the largest compressed chunk, 111.5 ms route-change p95, 57.9 ms form-feedback p95,
and 7.05 ms representative API p95. Limits remain unchanged. `evidence/restoration-f/performance.json`
records the runner, browser, cache state, samples, and budgets.
The final image's restart, real three-role journeys, shared accessibility and recovery, populated
payroll and leave layouts, and acceptance checks pass. The refreshed 46-view audit and focused B,
E, and F interactions pass after deferred loading. Exact synthetic cleanup and safe logs pass.
Only the verified task-owned stack and its volumes were removed. Push the settled F commit once,
wait for all GitHub jobs, publish the matching backend and migrations before the frontend, and
verify the delivered release. No deployment has occurred yet.
