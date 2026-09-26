# Manual three-role smoke checklist

Use only synthetic local identities and data. Start the current stack, apply Alembic, configure
Keycloak, and confirm the frontend, API, identity service, database, and private object store are
healthy before testing.

## Before the run

- [ ] `node scripts/verify-phase-13e-repository-guard.mjs` passes.
- [ ] `npm run test:unit` and `npm run build` pass.
- [ ] Alembic reports one head and applying migrations a second time makes no change.
- [ ] The browser uses `http://127.0.0.1:5174` and FastAPI uses `http://127.0.0.1:8000`.
- [ ] Test identities and business records are synthetic.
- [ ] Service logs contain no token, password, database URL, signed URL, or private object key.

## Administrator journey

- [ ] Sign in and confirm the administrator portal loads.
- [ ] Create a synthetic company and branch, then switch branch context.
- [ ] Create a department and employee. Confirm validation rejects protected or malformed fields.
- [ ] Exercise one leave, attendance, roster, payroll, document, notification, task, and report path.
- [ ] Upload a synthetic document and confirm the browser receives no storage credential.
- [ ] Confirm cross-company identifiers and employee-only routes are denied.

## Manager journey

- [ ] Sign in as a manager and see only assigned company, branch, and direct-report data.
- [ ] Review a direct report's leave and expense items.
- [ ] Open team appraisal, training, roster, attendance, and document views.
- [ ] Confirm another manager's team and administrator-only mutations are denied.

## Employee journey

- [ ] Sign in as an employee and see only the linked employee record.
- [ ] Submit and cancel an allowed leave request.
- [ ] Submit an expense, advance request, attendance action, document, and letter request.
- [ ] View published roster, payslips, training, appraisals, notifications, and tasks.
- [ ] Confirm another employee's identifier cannot read or change data.

## Cross-portal checks

- [ ] Employee leave moves through manager review and administrator completion.
- [ ] Employee expense moves through manager review and administrator handling.
- [ ] Administrator roster publication appears for the assigned manager and employee.
- [ ] File quarantine, scan state, scoped download, and denial paths behave as recorded.
- [ ] Notification and task state changes are visible to the intended recipient only.

## Restart and cleanup

- [ ] Record database, Keycloak signing-key, and synthetic object state.
- [ ] Restart the existing images without rebuilding or deleting volumes.
- [ ] Compare the recorded state and verify authentication again without reconfiguration.
- [ ] Remove synthetic users and business records created by the run.
- [ ] Remove only the named disposable Compose project and its confirmed resources.
- [ ] Recheck service logs after cleanup.

The automated equivalent is `npm run test:browser`. Migration parts may add stronger database,
authentication, storage, network, or recovery proof when their boundary requires it.
