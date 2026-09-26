# Part 13F completion

## Result

Part 13F is complete. A fresh locked install, two production builds, the disposable application,
the restart check, and the three-role browser journey passed without using the retired provider.
Catalogue entries `P13-NET-001` through `P13-NET-004` and the assigned golden cases are closed.
Alembic still has one head at `e8a1c3f5b7d9`.

## Fail-closed network proof

The proof checks attempts before name resolution or connection handling. The Node guard covers DNS,
TCP, TLS, HTTP, HTTPS, and WebSocket entry points. The Python startup guard covers resolver and
socket entry points used by FastAPI, migrations, database clients, object-storage clients, and
workers. Playwright checks each browser request before it leaves the browser context.

The protocol fixtures also name PostgreSQL and object-storage paths. Negative fixtures use reserved
invalid hosts and non-credential sentinel values. Positive fixtures retain the approved local
Keycloak, FastAPI, PostgreSQL, package-registry, and private object-storage destinations.

This process-level design was the narrowest reliable choice. Packet capture alone can miss an
attempt that fails during name resolution. The guards reject that attempt at the calling API and do
not depend on a response. The full-stack overlay mounts the Python guard into the backend, migration
runner, storage reconciler, expiry command, and file scanner. The browser wrapper injects hostile
values into its test-helper process and starts the same Node guard.

The Part 13E allowlist did not change. Its SHA-256 remains
`9ebd61b461d3080a96111dd5e7b6ed49e47e41b410578f1fa9f0e4d6dc1d4176`.

## Clean install and build evidence

`scripts/verify-phase-13f-clean-setup.mjs` copied tracked and unignored source into a uniquely named
temporary directory. It then:

- removed every retired-provider variable from the child environment;
- ran `npm ci --ignore-scripts --no-audit --no-fund` against the lockfile;
- rejected retired packages and tarballs in the lockfile and installed graph;
- built once with the forbidden inputs absent and once with the reserved hostile values present;
- checked module output and emitted bytes; and
- required the two complete `dist` digests to match.

The verifier removed its temporary directory in a `finally` block. The focused protocol suite and
the clean locked-install proof both passed.

## Disposable application evidence

The local gate used Compose project `workloop-phase13f-verify` with the base, private S3, and Part
13F overlays. It generated fresh local credentials without printing them and created only these
volumes:

- `workloop-phase13f-verify_postgres_data`
- `workloop-phase13f-verify_storage_data`
- `workloop-phase13f-verify_phase11b_s3_data`

The gate built the API image once, started PostgreSQL, FastAPI, Keycloak, and private S3, applied
migrations twice, and confirmed one current head with no pending operation. It configured Keycloak
twice to prove idempotence. The API health and authentication checks passed.

The administrator, manager, and employee browser journeys passed after restart. They covered
authentication, authorization denials, branch scope, API reads and writes, file upload and scanning,
private object access, command workers, notifications, tasks, dashboards, reports, rendered output,
payroll output, logout, callback replay denial, and synthetic cleanup.

## Restart and cleanup evidence

Before restart, the gate recorded the database catalogue fingerprint and Keycloak signing-key IDs.
It also stored one local synthetic object and one private S3 object with matching scan state. The
gate stopped the stack and recreated the existing images without rebuilding. The database
fingerprint and signing keys matched, both stored-object checks passed, and authentication passed
without another Keycloak configuration run.

The final checks found no synthetic company, branch, employee, application-user, profile, or
Keycloak user rows. Service logs contained no token, database credential, generated password, or
application-identity query. Cleanup verified the exact Compose project label before removing the
three disposable volumes, its containers, and its network.

`workloop-clinic_postgres_data` was inspected by name only. It was never attached, mounted,
modified, deleted, or recreated, and it remained present after cleanup.

## Repository checks

- The 269-test frontend unit suite passed.
- The canonical production build passed with 91 modules.
- The repository guard passed with 997 files inspected, 234 classified, and 763 reference-free.
- The focused Part 13E and Part 13F suite passed all 19 cases.
- The clean install, full-stack, restart, browser, log-safety, and exact cleanup checks passed.
- The routed GitHub result is recorded in the Part 13G handoff rather than in a follow-up commit.

## Rollback

Repository rollback starts by reverting Part 13F. If broader rollback is required, continue through
13E, 13D, 13C, and 13B in that order. Do not restore a retired runtime beside the canonical
application. Part 13F did not inspect or change any external project, secret store, paid service,
production record, or cloud object.
