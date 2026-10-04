# Portal restoration A completion

## Work completed

On October 4, 2026, this task compared the historical departments, assets, development, appraisal,
and incident components with their current counterparts. It restored separate work areas, named
employee controls, populated tables, summaries, and dialog-based editing. The organization chart
follows employee reporting managers, as the historical source does. It is not a department tree.

The module comparison and required follow-up work are in `PORTAL_RESTORATION_PROGRESS.md`.
Part A does not certify complete historical parity for these modules. Parts C, E, and F must close
the named dependencies before the whole phase can finish.

The backend now supports paged asset assignment history, dated asset handovers and returns,
certification metadata edits with resubmission, and paged branch-wide CME summaries. Current tenant,
branch, ownership, version, idempotency, evidence-scan, audit, and transaction rules remain in place.
No database revision, grant, identity-provider setting, or protected-file contract changed.

The existing untracked `src/PortalUi.jsx` helper was preserved and adopted. This task added its
confirmation dialog. Payroll's accepted populated review was not redesigned.

## Local evidence

- Frontend unit gate passed all 417 tests. The suite also built the production graph.
- Changed frontend and verifier files passed lint. Repository whitespace validation passed.
- Backend gate passed all 720 tests, lint, formatting, type checks, and dependency checks.
  The suite emitted six existing SQLAlchemy relationship warnings.
- The focused backend verifier passed 16 tests for the added operations and denial behavior.
- The populated browser verifier passed the changed desktop workflows, mutation payloads,
  failed-save retention, and 390-pixel page containment. It saves 15 populated screenshots in
  `evidence/restoration-a`. Screenshots wait for the active sidebar pill to reach the selected item.
- The schema head remains `e8a1c3f5b7d9`.
- Shared route checks passed all 46 current navigation routes, control names, contrast, heading
  focus, reduced motion, page containment at zoom, notification dialog focus, and contact-save
  failure recovery. These synthetic states do not prove populated historical parity for all modules.

The first frontend gate caught an obsolete source-label assertion. The assertion now checks the
restored labels, and the complete gate passed on rerun. Browser setup also required permission to
launch the locally installed test browser. That setup failure did not submit a product write.

The first GitHub run passed frontend regression and backend quality, but its full-stack job stopped
at the old Phase 9E payroll label assertion. The accepted payroll code no longer has that heading.
The adjacent Phase 9F verifier had the same case-sensitive label problem. Both verifiers now check
the actual warning and protected-command wiring. Payroll application code did not change. Focused
checks prove that both verifiers still reject removal of those required connections. The corrected
commit must pass the independent full-stack gate before B starts.

The rerun reached restart persistence and authentication checks, then the historical browser
verifier waited for the retired directory wrapper on the employee profile route. It now uses current
role-specific pages, dialogs, tabs, and dedicated task and approval routes. Actual API projections,
authorization denials, response codes, versions, and write-result assertions remain in place.
The next independent run must prove this correction and finish the gate.

That run passed backend quality, restart persistence, and authentication. It then found another
obsolete browser heading expectation. Staff appraisals now use the narrower Appraisals heading,
because clinical incidents are admin-only. The journey now visits dedicated staff training and
appraisal pages and checks their role-specific headings. The 46-route local check verifies those
headings too. This verifier correction still requires a successful independent run.

The next browser run passed development and stopped at a leave row selector that expected spaces
between adjacent date elements. Cancellation now targets the table's date elements, checks both
dates, and accepts the expected confirmation dialog. A focused production-component fixture checks
the confirmed cancellation route, empty command body, idempotency key, and rendered Cancelled state.
The full-stack test still checks the audit and attachment cleanup in PostgreSQL and object storage.

The expanded browser check exposed faint sidebar and tab text, inaccessible financial route
headings, and an overescaped phone pattern that rejected valid UAE numbers. This task corrected
the shared colors and heading semantics without changing financial layouts. The phone pattern now
accepts international and local UAE mobile formats and rejects a nonmobile example. The contrast
check now accounts for alpha and gradient backgrounds. Focus checks accept outline or shadow rings.

The Windows backend virtual environment points to a missing Python installation. Backend quality
therefore ran under Python 3.12 in the existing `workloop-api:phase7c-test` image, using a disposable
container and the pinned development dependencies. Type checking used Linux dependencies rather
than the broken Windows virtual environment. Cleanup removes only that task-owned container.

The focused service tests use stubs for database execution. The browser uses synthetic responses
through the production clients and parsers. Neither is proof of every new PostgreSQL transaction.
GitHub supplies the independently routed full-stack gate. Part F must also prove the new operations
against the database before deploying the final backend artifacts.

## Preservation and continuation

No live app deployment, real employee record, credential, or provider resource changed. Preserve
`workloop-clinic_postgres_data`, the Phase 13 external archive, `workloop-clinic-dev`, and
`fra1-default`. Autodeploy remains off. The accepted live payroll release remains
`e42808894b1c1a66c5e42738bbf9fa0cb46c538e` until restoration Part F.

Commit and push this settled part, wait for every required GitHub job, then create restoration
Part B in the same saved project and local checkout. Its scope is company settings, employee views
and the tabbed editor, employee records and lifecycle work, and all-role letter/custom requests.
The owner already authorized that continuation. Do not implement B in this task or start Phase 16.
Carry the verified commit and successful workflow URL in the handoff rather than another evidence
commit.
