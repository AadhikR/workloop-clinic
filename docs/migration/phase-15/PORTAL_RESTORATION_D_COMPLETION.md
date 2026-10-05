# Portal restoration D completion

Status: D closes when every routed GitHub job for the commit containing this record passes.
The implementation and local gate passed on October 5, 2026. Required shared dependencies remain
assigned to F in `PORTAL_RESTORATION_PROGRESS.md`.

## Work completed

The administrator dashboard now has a setup checklist, server summary cards, warning links,
Emiratization compliance, and payroll cost tables and charts. The clinical dashboard has server
credential cards, staffing compliance, and a broader document expiry panel. Clinical card details
currently expand the confirmed count and work-area link. They do not reproduce the historical
employee drill-down. D-01 defines the missing shared projection that F must implement.

Reports now have family selection, supported filters with named employee and department choices,
and distinct tables and charts for all 13 current report types. Server totals remain authoritative.
Charts label partial loaded rows. Protected CSV and PDF actions retain filters and preview on
failure. Dashboard report readers traverse every page and reject changing source versions.

Tasks now group current server tasks by category, support collapse and keyboard navigation, refresh
each minute, and link to the correct role workspace. Notifications refresh the unread count, page
the inbox, and confirm read-one and read-all writes before updating the view. Failures retain items
and offer a retry. Role, account, and branch changes clear the prior workspace.

Payroll retains the accepted salary review and server calculations. Advances and expenses now use
the shared dialogs and complete collection traversal. Expense receipt viewing uses a new protected
claim-based locator that delegates to the existing scan and object integrity checks. Failed
decisions and file requests retain their context. Existing expense DELETE stays restricted to
pending, manager-rejected, or rejected claims outside payroll. WPS and Nafis retain confirmed state and entered
values on failure. The SIF preview separates employee and control records and exposes server
control totals. Downloads still use server bytes. Managers and employees cannot mount WPS controls
or send WPS requests. Historical financial removal and cancellation remain D-02 dependencies.

The PDF opener now opens a blank window, clears its opener, and navigates to the protected blob.
The previous call could report a blocked popup after the browser had opened it successfully.

The independent shift controls in the employee Job and contract tab no longer require a shift
when saving ordinary profile changes. Their separate save button still requires a selected shift
and effective date. The real browser journey caught this form-validation regression from C.
Its leave fixture now selects a future Dubai date so approved cancellation remains valid after
October 5. Notification and dashboard assertions use the restored drawer and heading semantics.

## Routing command and schema

Revision `f1a3c5e7b9d2` follows `e8a1c3f5b7d9`. It adds only
`public.change_branch_payroll_routing(uuid,timestamptz,text,jsonb)`. The migration role owns the
function, PUBLIC has no execution grant, and the runtime role must resolve to an active human
administrator in the selected company and branch.

`GET /api/v1/branches/{branchId}/payroll-routing` returns the branch and complete draft set.
The matching POST requires an idempotency key, branch version, every draft version and source
digest, and a nine-digit routing code. It locks the branch and drafts before writing, changes only
the selected branch default and eligible draft SCR codes, and appends allowlisted audit events.
Approved drafts, stale or incomplete sets, and scope mismatches fail before writes. Ordinary branch
PATCH cannot bypass this operation. Confirmed replies return changed run identifiers and versions.
The dialog retains the exact key and payload for a retry. Downgrade removes only the function.

Current-head verifiers now accept the new revision. Historical revision identities and historical
release manifests retain their original values. F must publish the backend and apply this migration
before promoting the final frontend.

## Verification and limits

- The final frontend gate passed 434 tests and the production build. Changed files pass lint.
- The backend gate passed 732 tests, lint, formatting, whole-tree types, and dependency checks.
  The six existing SQLAlchemy relationship warnings remain.
- Seven new backend tests cover request contracts, role denial, selected-branch equality,
  operation registration, lock ordering, and branch-update bypass denial.
- The PostgreSQL verifier proves rollback after an audit failure, exact idempotent replay,
  fingerprint conflict, complete draft sets, approved-run denial, source and version conflicts,
  concurrent branch and draft locks, audit metadata, role denial, and unchanged other branches and
  generated runs. It cleans its fixtures.
- The isolated gate built the changed backend once, applied head twice, exercised the affected
  historical downgrade and upgrade checks, passed deep database boundaries, and proved the exact
  D predecessor rollback. Restart proof compares the database catalogue and signing keys without
  rebuilding images or reconfiguring authentication. Storage, real sign-in journeys, and synthetic
  cleanup pass after restart.
- The populated D browser fixture passes all 13 report types, dashboard links, task roles,
  notification writes and failures, payroll detail, advance creation, expense decisions and
  protected receipts, routing retry, SIF failure and download, keyboard use, and 390-pixel
  containment. Fifteen desktop and dark mobile screenshots are in `evidence/restoration-d`.
- Shared navigation and recovery checks pass all 46 views.
- The shared visual regression passes populated payroll edits, approval guards, breakdowns,
  mobile table scrolling, leave tab separation, and staff shell layout. Six captures have the
  `shared-` prefix in `evidence/restoration-d`. The deferred loader returns the module directly
  so its wrapper cannot widen mobile cards. The visual fixture waits for the loaded payroll
  module and uses the current paged payroll request.

The performance fixture records 219,469 compressed initial bytes, zero warm-route transfer bytes,
a 196,056-byte largest bundle, 94.7 ms route-change p95, 56.6 ms form-feedback p95, and 7.7 ms
read-only health p95. Administrator payroll, reports, settings, and WPS load on demand. Limits remain
unchanged. The warm-route metric now measures browser resource transfer after routes have loaded,
instead of summing cold chunks on disk. These local fixture timings are not production benchmarks.
The final health measurement used the preserved local API's read-only health endpoint after the
isolated stack had been removed.

The browser fixtures prove production parsers and interactions with synthetic replies. They do not
certify every live dataset or close the shared dependencies listed in the progress record. The
independent GitHub run and commit binding travel in the E handoff.

## Preservation and continuation

The disposable stack is `workloop-restoration-d`, with separate images, ports, and volumes. Its
synthetic records and owned volumes are cleaned after verification. Preserve
`workloop-clinic_postgres_data`, the Phase 13 external archive, `workloop-clinic-dev`, and
`fra1-default`. Autodeploy stays off. The accepted payroll release
`e42808894b1c1a66c5e42738bbf9fa0cb46c538e` stays live until F. No real records, credentials,
provider resources, biometric integration, or outbound email changed.

After D passes GitHub and the branch is clean and synchronized, create and start restoration E in
the same saved project and local checkout. E owns manager and employee shells, personal modules,
and direct-report queues. Carry D-01 and D-02 into F. Do not deploy or start Phase 16.
