# Part 12B completion

Status: implementation and local gate complete. The routed GitHub gate must pass before Part 12C
starts.

## Result

Part 12B moves the notification inbox, unread count, read-one, and read-all actions to FastAPI and
the migration frontend. Administrators read their tenant-wide and selected-branch notifications.
Managers and employees read only their own branch inbox. The response omits creator, recipient,
company, branch, and unrelated source details. Cursor order is `createdAt DESC, id DESC`; read-one
is monotonic; read-all is partition-scoped and idempotent.

Leave approval, payslip generation, and roster publication now call the existing fixed-purpose
database producer for the four approved workflow types. Each call stays inside its source
transaction, after the authoritative source transition. The browser cannot choose notification
recipients, tenant scope, source identity, title, or body.

Expiry production is an explicit command under the existing `workloop_expiry_processing` login. It
requires company, branch or approved tenant-wide scope, and a trusted business date. It takes the
tuple advisory lock, reads only granted source columns, inserts through the existing source-linked
policy, and writes the matching protected audit. Exact thresholds prevent catch-up production.
Replay and concurrency preserve one row per source, type, recipient, and threshold. No scheduler or
schema revision was added; Alembic head remains `c3e5a7b9d1f6`.

The migration shell now shows the FastAPI-backed bell for administrators, managers, and employees.
It polls the count once per minute, exposes explicit unavailable state, and never imports the legacy
Supabase notification module. The completed notification cutover record freezes the legacy browser
reader and producers for the migration build.

## Gate evidence

- All 616 backend tests passed. Ruff lint and formatting, strict Pyright checks for every changed
  backend file, and locked dependency checks passed.
- All 265 frontend tests passed. Focused frontend lint, the legacy production build, and the isolated
  migration production graph passed. The existing migration chunk-size warning remains unchanged.
- Focused API, service, client, and command checks covered exact shapes, every role, branch and
  recipient isolation, monotonic reads, idempotent read-all, safe failures, and legacy-free imports.
- A fresh isolated database applied the migration twice, retained one head with no drift, and passed
  the Phase 5G RLS and Phase 5H security controls.
- The Phase 12B database verifier covered every approved expiry type and threshold, off-threshold
  and expired exclusions, inactive and terminated exclusions, wrong login and scope denials,
  replay, audit linkage, and concurrent tuple execution. It then restored all 334 fixture rows
  exactly and left no verifier-created row behind.
- Existing images restarted without rebuilding. The schema and security catalogue, Keycloak signing
  keys, notification data, and the complete fixture matched before and after restart.
- Authentication passed after restart without reconfiguration. The complete administrator, manager,
  and employee browser journey passed, including workflow notification cleanup. Application and
  Keycloak synthetic row counts returned to zero, and the final service-log scan passed.

## Resource boundary

Verification used only synthetic local rows in disposable containers, networks, and volumes. The
`workloop-phase12b-focus` and `workloop-phase12b-gate` environments and their volumes were removed.
The protected `workloop-clinic_postgres_data` volume was not attached, modified, deleted, or
recreated.

No production provider, credential, cloud resource, paid service, production data, or real employee
or patient record was used. The explicit expiry command has no scheduler and no shared web-service
credential.

## Rollback and continuation

Rollback disables the explicit expiry command and migration workflow producers before restoring one
legacy writer. It then disables the migration bell and inbox routes before restoring the legacy
reader. Notification rows, read timestamps, source state, source links, and audits remain intact.

After the routed Migration foundation jobs pass and the branch is clean and synchronized, Part 12C
starts automatically in a new Codex task in the same saved project and local checkout. Part 12C
implements task aggregation only; it does not begin dashboard work.
