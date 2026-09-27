# Part 14E completion

## Result

Part 14E defines the shared-development signal and incident contract without provisioning a
resource or enabling external alert delivery. It closes inventory items `P14-OPS-001` through
`P14-OPS-008` and golden cases `14A-GC-021` through `14A-GC-025`. The Phase 14A catalogue remains
unchanged, and Alembic remains at `e8a1c3f5b7d9`.

The contract contains 34 signals for frontend availability; API availability, latency, and
failures; authorization denials and rate limits; Keycloak readiness, login failures, and signing
key changes; PostgreSQL capacity, connections, locks, and backup state; private-object growth,
failures, versioning, and access; expiry; both workers; deployments; backups; and cost. Every
signal has one owner role, severity, threshold, response, retention period, and test method.

Provider alert configuration remains disabled. It has no delivery vendor and no live resource
reference. Part 14G must add the approved resource IDs and named primary and backup operators before
activation. No DigitalOcean API call, Terraform refresh, apply, paid resource, credential, public
route, or external message occurred in 14E.

## Safe logs and evidence

Application logs now accept only named safe fields. String values use a narrow character and length
rule, integer fields must be nonnegative, and event names use fixed lowercase identifiers. Unknown
fields cannot enter records through the safe event helper. A protected value or unsafe message
becomes `unsafe_log_rejected` without echoing its content. Correlation IDs must have canonical UUID
form. HTTP completion records contain method, status, duration, and a safe condition. They omit
paths, queries, headers, request bodies, identities, and response content.

Worker heartbeat, queue age, expired lease, retry, and terminal failure events use the same helper.
Scanner and reconciler claim queries return integer queue age and expired-lease age without an
object key, company, branch, or document value in the log. Expiry keeps its established single-line
safe failure output and adds a structured completion record after a successful run.

The evidence helper accepts only timestamps, signal and component identifiers, named operators,
counts, sizes, digests, release IDs, safe resource IDs, safe key suffixes, error codes, and statuses.
It refuses unknown fields, protected patterns, negative or noninteger counts, empty input, missing
operator identity, and output overwrite. Tokens, passwords, connection strings, private keys,
object secrets, signed URLs, document content, request bodies, filenames, full object keys, and
object bytes remain prohibited.

## Alerts, cost, and incidents

`infra/digitalocean/operations-alerts.json` maps each contract signal to an inert provider,
application, comparison, query, or operator-record source. The repository adds no alerting vendor.
Application and worker records have 30-day retention. Security, administrator, release, incident,
backup, restore, and rollback records have 365-day retention.

The fixed plan guard remains at USD 70. Terraform now also requires a reviewed monthly forecast for
an authorized plan and rejects a missing forecast or any value above USD 70 before provider access.
The focused fixture proved that USD 70.01 fails. The existing USD 20 account alert remains an early
warning. It does not cap spending.

The incident schema requires the open time, severity, maintenance action, owner notifications,
sanitized evidence reference and digest, compatible rollback selection, recovery times and result,
maintenance-disable time, and named operators. The runbook keeps maintenance enabled and workers
stopped until authentication, authorization, objects, leases, queues, and reconciliation pass. It
forbids automatic schema downgrade and leaves isolated restore work to Part 14F.

The fail-closed design choices were deliberate:

- strict allowlisting replaces best-effort text redaction because an unknown field may contain a
  protected value;
- provider alert mutation stays disabled because live resource IDs and named people do not exist
  inside the 14E boundary;
- the forecast is a required plan input rather than an informational output because work must stop
  before a plan over USD 70 reaches the provider; and
- the incident record stores sanitized references and digests instead of copied logs or provider
  pages.

## Focused evidence

The Part 14E contract and evidence slice passed 14 Node tests. Mutation cases rejected a missing
safe-log allowlist, a protected evidence class, incomplete signal ownership, missing worker
conditions, a higher cost ceiling, a spending-cap claim, an incomplete incident record, active
provider mutation, and an external alert vendor.

Combined Phase 14B through 14E contract coverage passed 43 tests. The retained Phase 14A contract
reported 57 inventory items, 38 golden cases, 12 external facts, and seven later-part owners. The
14D deployment verifier still reported seven components and the unchanged worker concurrency and
release rules.

Affected backend coverage passed 50 tests during development. It exercised safe formatter output,
protected-value rejection, unsafe correlation rejection, API request logging, expiry output,
heartbeat, queue age, expired lease, scanner and reconciler retries, terminal failure, shutdown,
and storage behavior. The final backend gate passed 695 tests with the six existing SQLAlchemy
relationship warnings. Ruff lint passed, all 535 checked files were formatted, pinned Pyright
1.1.411 reported zero findings, and the dependency check found no broken requirements.

Frontend regression passed 335 tests. The production build compiled 91 modules. The existing
chunk-size warning remained informational. The repository guard inspected 1,050 files.

Terraform 1.16.1 initialized with DigitalOcean provider 2.100.0, formatted and validated the module,
and produced a disabled plan with no changes. The retained 14B plan checks passed. The 14E check
rejected an authorized synthetic plan with a reviewed monthly forecast of USD 70.01 before any
provider call.

The first backend completion attempt found one unnecessary integer-construction lint error in the
response-status tracker. The focused lint and type checks passed after the tracker used a typed
state object, and the complete backend gate then passed. Pyright initially saw an ignored stale
host virtual environment through the container mount. Directing it to a clean container-only venv
path reproduced GitHub's clean-checkout behavior and passed without a code change.

## Boundary-matched local gate

Compose project `workloop-phase14e-gate` used fresh ignored local credentials and three disposable
volumes. It built the current backend image, started PostgreSQL, FastAPI, Keycloak, and private S3,
and applied migrations twice. Keycloak configuration ran twice without drift. API health,
Keycloak readiness, issuer discovery, JWKS validation, authentication, and the HTTP boundary passed.

One-shot scanner and reconciler processes ran with processing enabled against an empty synthetic
queue. Both emitted a safe `worker_heartbeat` record and executed their updated maintenance and
claim queries successfully. The focused tests supplied queue-age, expired-lease, retry, and terminal
paths without exposing object keys or document content.

The restart proof recorded the database security fingerprint, Keycloak signing-key IDs, local
object state, private S3 bytes, and scanner state. It stopped the stack and recreated the existing
images without a build. Every recorded value matched after restart. The repeat migration remained
current, authentication passed without another Keycloak configuration run, and the complete
three-role browser journey passed. Final service logs passed the protected-value scan.

The first restart command used a host `sh` alias that is not installed in this PowerShell session.
It stopped before a valid fingerprint comparison. No code, database, or volume was removed. The
same restart segment then passed with the exact Git Bash executable and the prepared synthetic state.

The browser journey removed its synthetic application and Keycloak identities. Cleanup verified
zero companies, branches, employees, application users, profiles, and synthetic realm users. It
then removed only:

- `workloop-phase14e-gate_postgres_data`
- `workloop-phase14e-gate_storage_data`
- `workloop-phase14e-gate_phase11b_s3_data`
- `workloop-phase14e-pyright-cache`

`workloop-clinic_postgres_data` was checked by exact name before and after cleanup. It remains
present and was never attached, mounted, modified, deleted, or recreated. The Phase 13 external
archive, DigitalOcean project `workloop-clinic-dev`, and VPC `fra1-default` were not inspected or
changed.

## Rollback

Before provisioning, rollback is a repository revert of the signal and alert contracts, incident
schema and runbook, evidence helper, forecast guard, safe logger, request instrumentation, worker
signals, tests, and this record. It needs no provider action.

After a later approved apply, retain required logs and incident records first. Enable maintenance,
stop expiry and worker claims, and remove alert configuration only after the incident operator
confirms that its evidence is preserved. Roll back only to a reviewed release compatible with the
current Alembic head. Never downgrade the schema automatically or delete a database, private object,
external archive, project, VPC, or protected local volume as part of the 14E configuration rollback.

## Next part

Part 14F owns backup custody, portable exports, isolated restore targets, signing-key continuity,
matching release artifacts, recovery comparisons, write blocking, rollback rehearsal, and exact
restore-target cleanup. It must not restore over the shared environment or provision the Part 14G
deployment.
