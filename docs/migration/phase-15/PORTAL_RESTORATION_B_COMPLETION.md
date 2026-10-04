# Portal restoration B completion

## Work completed

On October 4, 2026, this task restored the administrator company settings, employee
summary views, employee editor, selected-employee records, lifecycle work, and letter and
custom-request views. Company settings now use grouped employer, payroll, jurisdiction,
module, insurance, and WPS areas. Branch branding supports validated logo preview,
replacement, and removal. Biometric integration remains excluded.

The employee editor now keeps the selected employee in context across personal, job,
document, insurance, contract, offboarding, and settlement work. Its profile save uses one
idempotent server command for ordinary profile fields, title, department, manager, and salary
changes. The service locks and validates the employee before it writes profile history and
audit records in the same transaction.

Letter and custom requests now have Pending, Completed, Rejected, and All filters. Printable
source and PDF actions appear only for completed standard letters. Managers can print their
own completed standard letters. Custom requests cannot use the standard-letter source route.

The comparison and remaining dependencies are recorded in
`PORTAL_RESTORATION_PROGRESS.md`. B's assigned work is complete. B-01 through B-05 remain
owned by C, D, and F as listed there.

## Local evidence

- The final local gate passed 422 frontend tests and 724 backend tests.
- Changed frontend files passed lint. Repository whitespace validation passed.
- Backend lint, formatting, dependency checks, and changed-file type checks passed. The
  backend suite emitted the six existing SQLAlchemy relationship warnings.
- Four focused backend tests cover the atomic profile command, history and audit writes,
  manager self-letter scope, custom-request source denial, and OpenAPI registration.
- Eight focused frontend tests cover restored module wiring and output rules.
- The populated browser check passed grouped settings, branch-save confirmation, the
  selected-employee editor, failed-save retention and retry, the combined profile payload,
  request filters, output controls, manager print access, and 390-pixel containment. It saves
  six screenshots in `evidence/restoration-b`.
- Shared accessibility and recovery checks passed all 46 route groups.
- The final focused performance check measured 224,978 compressed initial bytes, no
  later-route transfer, a 206,144-byte largest route bundle, 105.3 ms route-change p95,
  67.9 ms form-feedback p95, and 8.21 ms read-only health p95. All values remain inside the
  existing limits.
- The schema head remains `e8a1c3f5b7d9`.

The complete local gate ran once after the implementation settled. Later changes only corrected
historical browser selectors and preserved branch-save feedback, so their checks stayed focused.
The browser and API timing fixtures are synthetic local evidence, not production benchmarks.

## Independent completion gate

GitHub run 286 found a retired branch-settings heading in the historical browser journey. Run
287 reached the same form and found its retired field label. Run 289 passed classification,
frontend regression, backend quality, stack recreation, restart persistence, and authentication,
then found that a successful branch update remounted the form before its confirmation could be
observed. The form now keeps a stable branch key, and the populated fixture changes the branch
version so the browser check proves the real update path and visible confirmation.

The final routed GitHub gate passed for code commit
`6be3ee454ae38c5f046a800b8fda2c103cef8bda` in run 290:
`https://github.com/AadhikR/workloop-clinic/actions/runs/37226144469`. Change classification and
frontend regression passed. Backend quality and full-stack smoke were not routed for the final
frontend-only correction. Run 289 supplies the independent backend, stack, restart, and
authentication evidence up to the corrected browser step.

B's implementation and assigned gates are complete. This does not close B-01 through B-05,
certify the whole restoration, or publish a backend artifact.

## Preservation and continuation

No live app deployment, real employee record, credential, provider resource, or preserved volume
changed. Preserve `workloop-clinic_postgres_data`, the Phase 13 external archive,
`workloop-clinic-dev`, and `fra1-default`. Autodeploy remains off. The accepted live payroll
release remains `e42808894b1c1a66c5e42738bbf9fa0cb46c538e` until restoration Part F.

Create restoration Part C after this completion record is synchronized in the same saved project
and local checkout. C owns leave, attendance, and roster restoration. It must also close B-02 by
showing and changing the effective default shift through the current versioned assignment API, and
close A-06 by respecting the branch staffing enable setting. The owner already authorized this
continuation. Do not deploy or start Phase 16. DigitalOcean deployment remains part of F after the
whole restoration and its final gates pass.
