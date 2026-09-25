# Part 12H completion

Status: implementation complete; project-owner Phase 12 signoff pending. The local gate passed. The
routed GitHub result is recorded in the owner-signoff response rather than added in a follow-up
documentation commit.

## Result

Part 12H independently reviewed the complete Phase 12 boundary from the completed Part 12G
baseline. It traced all 97 inventory entries, all 52 upstream assignments, and all 50 golden cases.
It validated both cutover records, the reverse rollback order, the fixed expiry login, the protected
output audit writer, every migration consumer, and the absence of Supabase or browser document
generation from the migration build.

The review found and resolved five gaps:

- The routed workflow omitted several Phase 12 static, database, rollback, and closing checks. The
  workflow now runs every Phase 12 verifier and the exact Part 12G predecessor proof.
- The post-restart browser journey stopped at Phase 11. It now covers Phase 12 notifications, tasks,
  dashboards, reports, outputs, and role denials for administrators, managers, and employees.
- Managers saw completed-letter PDF controls that their approved role does not own. Those controls
  now remain limited to administrators and employees.
- The notification query corrupted its own branch bind name, and Phase 12 read models emitted
  microseconds where the client requires milliseconds. Query construction and notification, task,
  dashboard, and report serialization now satisfy the approved contract.
- CORS hid two headers that the binary client validates, and the retained payslip policy denied the
  administrator output route. The header allowlist now exposes both values. The Part 12G head grants
  verified administrators branch-scoped payslip reads while preserving employee self scope and
  manager denial; downgrade restores the employee-only policy.

No finding added a table, cloud resource, scheduler, production credential, optional report,
legacy fallback, or Phase 13 work.

## Gate evidence

- All 673 backend tests passed in Python 3.12. Complete Ruff lint and formatting passed, strict
  Pyright reported zero findings, and `pip check` found no broken requirements.
- All 290 frontend tests passed. Scoped ESLint and both production builds passed; the builds emitted
  only the existing chunk-size warning.
- The closing verifier accounted for all 97 inventory entries, all 52 upstream assignments, and all
  50 golden cases. It proved 90 completed catalogue entries, six Phase 13 entries, and one explicit
  fail-closed omission. Both cutover records and their evidence passed the canonical validator.
- Every Phase 12 static, cutover, revision, and database verifier passed. The complete historical
  database sequence also passed from Phase 4 through Phase 12G.
- The exact rollback gate created an audit sentinel, downgraded from `e8a1c3f5b7d9` to
  `d6f8a0c2e4b7`, confirmed the Part 12F audit allowlist and employee-only payslip policy, preserved
  the sentinel, returned to the Part 12G head, and restored the administrator output boundary.
- A fresh isolated stack applied migrations repeatedly, retained one head with no pending operation,
  and passed service health, HTTP, Keycloak, database, and log-safety checks.
- Existing images restarted without rebuilding. The database fingerprint, Keycloak signing keys,
  stored object, scanner state, and transaction-context isolation remained unchanged. The complete
  three-role browser journey then passed against the restarted stack.

## Resource boundary

Verification used synthetic rows and disposable local services only. Browser identities, database
rows, audit evidence, stored objects, and scan fixtures were removed. The
`workloop-phase12h-gate` containers, network, and three disposable volumes were removed.

The protected `workloop-clinic_postgres_data` volume remained present and was not attached,
modified, deleted, or recreated. No production provider, credential, cloud resource, paid service,
production data, real employee record, patient record, payroll record, or banking record was used.

## Rollback and signoff

Rollback freezes Part 12G rendered outputs before Part 12F byte exports, Part 12E reports, Part 12D
dashboards, Part 12C tasks, and Part 12B notification producers and readers. A legacy reader or
writer may return only after its migration counterpart is disabled. Source rows, snapshots,
notifications, read timestamps, settlements, audit events, and generated-object evidence remain
intact.

Phase 12 implementation is complete. Project-owner signoff is the remaining phase gate. Phase 13
has not started and will not start without that signoff and a separate owner instruction.
