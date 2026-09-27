# Part 14D completion

## Result

Part 14D established immutable release inputs, exact deployment order, component health rules,
bounded worker execution, and fail-closed promotion controls for the shared-development design.
The local gate passed on 2026-09-27. Provisioning remains disabled, no provider credential was
supplied, and no DigitalOcean resource, route, state, secret, or application deployment changed.

The work closes inventory items `P14-DEP-001` through `P14-DEP-010` and golden cases
`14A-GC-013` through `14A-GC-020`. It keeps the Phase 14A catalogue unchanged and retains the
single Alembic head `e8a1c3f5b7d9`.

## Immutable release boundary

The release schema binds one full Git commit, backend and Keycloak image digests, frontend tree
and root digests, three dependency lock digests, Terraform and app-spec digests, the exact Alembic
head, creation time, and reviewer. The committed example cannot deploy. The release helper creates
a record only from a clean worktree, refuses to overwrite an output file, rejects unrecorded or
mutable fields, and validates the current source artifacts before use.

Terraform accepts only complete deployable release inputs. Backend-based components and Keycloak
use reviewed image digests without a branch rebuild or mutable tag. The static site builds the
manifest's full commit with automatic deployment disabled, then verifies both emitted frontend
digests. No workflow applies Terraform or starts a provider deployment.

The seven components remain in their fixed order: migration, API, Keycloak, web, expiry, scanner,
and reconciler. The pre-deploy migration requires the manifest head, verifies exactly one database
head after Alembic, and reports whether the schema was already current. A failed or incompatible
manifest blocks activation. Maintenance stays enabled until a compatible release has its separate
promotion approval.

## Processing and shutdown boundary

Expiry is a manual one-shot App Platform job. Promotion requires a nonempty list of approved
synthetic company and optional branch scopes. One invocation processes every scope with a separate
advisory lock for the scope and business date. The command uses an explicit controlled date when
provided and otherwise derives the current `Asia/Dubai` date. Missing promotion, missing scopes,
invalid scope fields, or processing failure returns a safe error and no partial success claim.

The scanner and reconciler have one instance each, one-row claims, 15-minute leases, eight total
attempts, and the fixed 1, 5, 15, 60, 360, 1440, and 4320 minute retry schedule. Their promotion
gate is independent of the expiry scope list. Each worker polls at five seconds and emits a safe
heartbeat every minute while idle. App Platform grants 120 seconds for termination. On a stop
signal, the worker accepts no new claim, gives the current claim 105 seconds to finish, then clears
the lease and schedules the bounded retry if work is still running.

## Focused evidence

The Part 14D contract and release-manifest slice passed 13 tests. Combined Phase 14B, 14C, and 14D
contract coverage passed 25 tests. Mutation cases rejected missing release digests, an incompatible
schema head, incomplete health rules, changed claim or lease limits, a missing expiry lock, an
unsafe shutdown path, branch deployment, mutable tags, and workflow deployment commands.

Backend deployment, expiry, worker-control, and health coverage passed 29 focused tests. The final
backend gate passed 681 tests with six unchanged SQLAlchemy relationship warnings, Ruff lint and
format checks across 534 files, pinned Pyright 1.1.411 with zero findings, and the dependency check.
The frontend gate passed 321 tests and built the 91-module production graph. The existing chunk-size
warning remained informational. The emitted frontend tree and root matched their computed release
digests.

Terraform 1.16.1 formatted and validated the module with DigitalOcean provider 2.100.0. Its default
disabled plan reported no changes. Synthetic enabled plans without approval, operator, secret, or
release-manifest records failed before a provider call. Static checks confirmed digest sources,
full-commit web input, disabled automatic deployment, exact component health rules, and no secret
output.

## Boundary-matched local gate

Compose project `workloop-phase14d-gate` used fresh synthetic credentials and three disposable
volumes. It built the current backend image, started PostgreSQL, FastAPI, Keycloak, and private S3,
applied migrations twice, and verified the single head `e8a1c3f5b7d9`. Keycloak configuration ran
twice without drift. API health, Keycloak readiness, issuer discovery, JWKS validation,
authentication, and the HTTP boundary passed.

The database proofs exercised expiry advisory-lock concurrency, scanner claim and retry behavior,
reconciler stale-lease recovery, and the Part 14C role and grant boundary. Disabled expiry failed
closed. Disabled workers made no claim. Promoted one-shot workers completed maintenance, emitted a
safe heartbeat, and exited without work. Unit coverage exercised termination during an active
claim, including completion inside the drain window and lease release after timeout.

The restart proof recorded the database security fingerprint, Keycloak signing-key IDs, local
object state, private S3 bytes, and scanner state. It stopped the stack and recreated the existing
images without a build. Every recorded value matched after restart, the repeat migration remained
current, and authentication passed without another Keycloak configuration run.

The final evidence scan found no token, connection string, generated password, application
identity, or SQL identity query in service logs. The repository guard inspected 1038 files. The
deployment contract, frontend artifact proof, and whitespace check passed.

The first routed GitHub run exposed one stale Phase 12B source assertion. It required the expiry
command's safe JSON serializer and `print` call to share one line. Part 14D had kept the same JSON
output with multiline formatting. The retained verifier now checks the serializer without fixing
its layout. The exact Phase 12B workflow step passed locally after the repair; no runtime code or
schema changed.

The replacement run reached the retained three-role browser journey and exposed one missing test
harness input. The new worker gate correctly kept the one-shot malware scanner idle because the
harness had not marked it as promoted. The browser journey now enables processing only for that
explicit scanner invocation. The complete guarded journey passed against the disposable repair
stack after the change; the production gate remains disabled by default.

Cleanup verified and removed only:

- `workloop-phase14d-gate_postgres_data`
- `workloop-phase14d-gate_storage_data`
- `workloop-phase14d-gate_phase11b_s3_data`
- `workloop-phase14d-pyright-cache`
- `workloop-phase14d-repair_postgres_data`
- `workloop-phase14d-repair_storage_data`
- `workloop-phase14d-repair_phase11b_s3_data`

`workloop-clinic_postgres_data` was checked by name only and remains present. It was never attached,
mounted, modified, deleted, or recreated. The Phase 13 archive, `workloop-clinic-dev`, and
`fra1-default` were not inspected or changed.

## Rollback

Before provisioning, rollback is a repository revert of the Part 14D release schema, manifest
tooling, deployment inputs, migration checks, processing controls, tests, and documentation. It
needs no provider action.

After a later approved apply, enable maintenance and stop new worker claims first. Select the last
compatible reviewed manifest, confirm its exact schema head and artifact digests, run the
pre-deploy migration, and restore traffic only after every component health or completion rule
passes. Resource destruction still needs fresh approval for exact names and retained external
state. Never delete the existing project, default VPC, Phase 13 archive, or protected local volume.

## Next part

Part 14E starts only after this commit and every routed GitHub job pass, and the branch is clean and
synchronized. It owns structured logs, monitoring, alert ownership and thresholds, worker signal
coverage, cost response, and incident evidence for inventory items `P14-OPS-001` through
`P14-OPS-008` and golden cases `14A-GC-021` through `14A-GC-025`. It must not provision the shared
environment or implement Part 14F recovery work.
