# Complete portal restoration execution

## Authorization and reference

The owner authorized restoration of every module in every portal on October 4, 2026. The requested
result preserves the historical workflows, panels, buttons, positions, and responsive layouts.
The reference is `a3b72a22924d1b56b5603ee8e0069ddecee65f43`. Its frontend tree matches the final
historical product reference in `docs/history/legacy-feature-list`.

Use `PORTAL_UI_RESTORATION_INVENTORY.md` for the module map and the historical UI specification
and feature catalogue for each module's target. Read each historical component and its shared and
inline styles before changing its current counterpart. A shared stylesheet does not prove module parity.

This is a frontend restoration continuation of Phase 15, not authorization to start Phase 16.
Follow the phase execution, verification, and handoff workflows. Run one part per Codex task.
Every part below is authorized. Create and start the next task automatically after local and GitHub
gates pass. Ask for signoff only after Part F.

The owner also authorized implementing missing backend features required by these historical
workflows. Record every gap and add the server operation with current authorization, validation,
audit, transaction, and protected-file rules. This amendment includes required schema changes and
their migrations when an existing schema cannot support the feature. It does not authorize unrelated
features, new paid infrastructure, real regulated test data, or changes to identity-provider security.

## Parts

| Part | Assigned work |
| --- | --- |
| A | Shared presentation controls; departments and staffing; assets; training, certifications, and CME; appraisal cycles and reviews; incidents. Shared components must retain role-specific restrictions. |
| B | Administrator company settings; employee summary views and tabbed editor; documents, insurance, contracts, offboarding, and end-of-service views; administrator and personal letter/custom requests. |
| C | Administrator leave work areas, policies, holidays, delegates, approvals, balances, and calendar; attendance work areas, rules, periods, corrections, overtime, and summaries; roster templates, monthly grid, validation, publication, and swaps. |
| D | Administrator and clinical dashboards; report families and report-specific layouts; all-role task groups and notifications; remaining payroll, advances, expenses, WPS, SIF, and output presentation differences. Preserve the accepted payroll correction. |
| E | Manager and employee shells and every personal module; manager leave/expense queues, direct-report training and appraisal reviews; personal home, profile, leave, schedule, attendance, payslips, advances, expenses, training, appraisals, documents, requests, and tasks. Reuse earlier work and prove role-specific behavior. |
| F | Audit every historical module against the inventory, implement outstanding backend gaps, close remaining presentation/workflow gaps, collect populated and main-state desktop/mobile evidence for all 46 views, verify keyboard and failure states, then deploy the settled release and verify it live. Do not certify unresolved workflows. |

## Boundaries

Keep current server clients, payloads, optimistic versions, idempotency keys, protected-file handling,
and server-derived role and record scope. Never restore retired storage code or browser-side data
authority. Biometric integration and outbound email remain excluded. Do not change credentials,
paid resources, or provider security settings as part of this work.

Use synthetic fixtures for populated verification. Existing cloud services, databases, preserved
data, and infrastructure remain unchanged. Deploy only to the existing development app when the
settled restoration reaches Part F. Keep the currently accepted payroll release live until then.

When a historical workflow lacks a current service operation, document the exact missing contract
and implement it in the assigned module part when bounded. Carry cross-module gaps into Part F
with an explicit dependency and required server behavior. Do not fabricate data or show success
without a confirmed write. Whole-phase signoff requires the authorized workflows to work.

## Evidence and continuation

Each part adds focused interaction verification before broad edits, then runs frontend unit tests,
changed-file lint, a production build, and browser checks for its changed workflows. A route list or
unavailable-state screenshot is not evidence of a populated workflow. Check dialogs, payloads,
failures, and role restrictions as well as appearance. Run the boundary-matched gate once after the
code settles, push once, and wait for the required GitHub result.

Record completion and necessary service differences in `PORTAL_RESTORATION_PROGRESS.md`. Keep the
working tree clean and synchronized before generating the next handoff. Carry the authorized scope,
verified commit, successful workflow, preserved resources, and next part boundary into that task.
