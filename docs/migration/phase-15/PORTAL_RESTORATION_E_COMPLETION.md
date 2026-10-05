# Portal restoration E completion

Status: the October 5 local gate passed. E closes when every routed GitHub job for the commit
containing this record passes. The October 4 restoration authorization continues through F.
E does not deploy.

## Work completed

Employee and manager shells now show the company, portal role, and employee identity. Account
changes remount the personal workspace. Managers use their personal home with Dubai greetings,
read-only attendance status, recent leave, assigned assets, identity warnings, server cards, and
quick links. The administrator welcome remains separate.

Profiles restore the avatar and employment, salary, contact, emergency, and UAE groups. The
contact editor sends only the permitted fields, keeps failed entries, and restores saved values
on cancel. Personal leave restores balance cards, expandable history with reasons and attachment
actions, and a Monday-first calendar. Schedule restores published shift cards and a named swap
dialog. Attendance restores read-only status, history, and an inline correction form. Swap,
correction, and personal training retries retain the original key for an unchanged payload.

Payslips expand earnings, deductions, gross and net pay and open the protected server PDF. Managers
can use only their own payslips. Personal expenses reuse D's protected receipt locator and retain
the claim after failed delivery. Advances and expenses retain D's scoped request dialogs and
history. Documents restore the personal submission form, expiry/status table, protected evidence,
and insurance panel. Letter and custom requests keep separate forms and distinguish completed
custom requests from printable standard letters. Tasks reuse D's grouped role-aware workspace.

Manager development separates Team and My Training. All Reports resolves the server-approved
report list and reads each report through its required employee-scoped routes. It never calls the
personal endpoint for a team collection. Personal training and certifications appear together.
Named add/edit/result dialogs, status commands, evidence controls, and the CME summary retain
server authority. Personal result submission cannot grant verified CME credit. Manager appraisals
separate current-report review from read-only personal results. Result cards expand sections,
weights, comments, and development plans. Rating controls require a pending review and active
cycle. Administrator review and calibration remain separate.

Manager leave restores the reason column, refresh, decisions, and a rejection dialog that keeps
failed input. Expense review restores filters, refresh, current-report decisions, and protected
receipts. Existing expense DELETE restrictions remain.

## Schema, authority, and rollback

Revision `e2c4f6a8b0d3` follows `f1a3c5e7b9d2`. It adds result provenance and the protected
start/cancel/self-complete training command. The command requires current human authority, an
expected version, and an idempotency key. It locks the training record and employee in that order,
rechecks scope after waiting, and appends audit in the same transaction. Ordinary personal UPDATE
cannot write result, verification, cost, or CME authority fields.

Personal completion sets `result_verified=false` and `is_cme=false`. Existing trusted completion
can verify the result for an administrator or current manager. CME totals retain their scan
predicate and now require verified results. The command rejects foreign tenant/branch records,
inactive owners, stale versions, terminal transitions, invalid decimals, and invalid dates.
Replays recheck current authority.

An additive payslip policy allows manager-own SELECT. The output audit amendment permits only
manager-own payslip PDF and completed standard-letter PDF. Custom requests and foreign records
remain denied. The migration keeps the exact previous function privately without PUBLIC or
runtime execution. Downgrade refuses while an unverified personal result exists. An eligible
downgrade removes E's objects and restores the prior function and grants. Never downgrade the
schema automatically during release rollback.

Historical revision identities, catalogue baselines, and release manifests retain their recorded
heads. Current-head verifiers accept E's append-only revision. F must publish the matching backend
and migrations before promoting the final frontend.

## Verification and limits

The frontend gate passed 437 tests, the production build, changed-file lint, the clean-install
boundary, and repository and integration guards. Seventeen focused source checks passed after
the final selector and styling changes. The backend suite passed 739 tests. Three tests could not
create a Windows temporary directory and passed on retry with a workspace-owned directory.
Backend lint, formatting, types, and dependency checks passed. The nine new E backend tests passed.

The isolated database gate passed the affected historical checks, current-head metadata, D and E
authority checks, and E's exact predecessor downgrade and upgrade. Database and signing-key state
matched across restart without rebuilding. Authentication and protected storage persistence
passed after restart. The shared route check passed all 46 accessibility and recovery cases.
Shared payroll layout checks passed. Evidence includes 65 populated staff captures and six shared
captures in the E evidence directory.

Performance stayed within every unchanged limit. Initial compressed bytes were 224375 against
225000; later warm-route bytes were zero against 1024; the largest compressed asset was 196018
against 210000. Route, feedback, and health p95 measurements were 118.1, 65.6, and 8.08 milliseconds.
The recorded environment is Windows x64, Node 24.11.1, Chromium 148.0.7778.96, and unthrottled
loopback. These figures describe the synthetic local run.

The final real administrator, manager, and employee browser journeys passed after restart,
including protected uploads/downloads, role restrictions, session behavior, and synthetic fixture
cleanup. Updated selectors follow the restored personal leave cards and manager queue headings.
The earlier selector failures did not require changes to product authority or validation.

The browser fixture uses production components, clients, and parsers with synthetic replies.
It covers every personal route in both staff portals, manager review areas, failed forms and
receipt delivery, current-report selection, personal output restrictions, keyboard expansion,
and 390-pixel dark containment. Captures wait for deferred training records to load. These
fixtures prove interactions and populated appearance, not every live record or exact historical
layout. Final all-state comparison across all 46 views belongs to F.

The PostgreSQL verifier checks personal result provenance and CME exclusion, trusted verification,
raw result UPDATE denial, stale and terminal transitions, replay, account and tenant/branch denial,
reassignment while waiting on an employee lock, audit failure rollback, downgrade refusal,
manager own PDFs, custom/foreign output denial, exact predecessor restoration, and cleanup.

`PORTAL_RESTORATION_PROGRESS.md` records the remaining required work. A-01 is closed by E.
A-04 pagination, the earlier A/B/D dependencies, E-01 manager action history, E-02 personal advance
repayment detail, and E-03 final personal presentation/state comparisons remain required in F.
E does not certify those gaps or invent missing data.

## Preservation and continuation

The disposable stack is `workloop-restoration-e`, using separate images, ports, and volumes.
Verification used synthetic data only. Final empty-state and safe-log assertions passed. Cleanup
removed only the verified E containers, network, and three project-owned volumes. Preserve
`workloop-clinic_postgres_data`, the Phase 13 external archive, `workloop-clinic-dev`, and
`fra1-default`. Autodeploy remains off. Accepted payroll release
`e42808894b1c1a66c5e42738bbf9fa0cb46c538e` remains live until F. E changes no real records,
provider resources, credentials, biometric integration, or outbound email.

After every required GitHub job passes, confirm a clean synchronized `migration/fastapi-keycloak`
branch. Generate the verified F handoff, create and start its task automatically in saved project
`workloop-clinic` and the same local checkout, report that task, and stop E. F requests whole-phase
signoff after final closure and live verification. It must not start Phase 16.
