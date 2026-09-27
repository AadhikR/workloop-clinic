# Part 14A deployment inventory

## Scope

This inventory starts at commit `d2d6c10d99599c2911cf02743cc93fc2bb0129c3`. It covers the
retired Phase 6G Terraform, the current application, and the controls needed for a persistent
synthetic shared-development deployment. The machine source is
`docs/migration/phase-14/deployment-catalogue.json`.

Each row has one action and one owner. Parts 14B through 14G implement and prove their rows. Part
14H reviews the whole set independently. No row authorizes a cloud change.

## Catalogue

| ID | Item and current state | Action | Owner | Evidence classes |
| --- | --- | --- | --- | --- |
| `P14-INF-001` | Phase 6G enablement still assumes a temporary proof and teardown deadline. | `replace proof control` | 14B | repository-static, focused-test |
| `P14-INF-002` | `workloop-clinic-dev` exists and was empty on 2026-09-27. | `retain and harden` | 14B | provider-readonly, provider-live |
| `P14-INF-003` | `fra1-default` is the empty default FRA1 VPC outside Terraform state. | `preserve unchanged` | 14B | provider-readonly, focused-test |
| `P14-INF-004` | No managed cluster exists. Phase 6G declares PostgreSQL 16 and two databases. | `replace proof control` | 14B | repository-static, provider-readonly, focused-test |
| `P14-INF-005` | No Space exists. Phase 6G enables forced deletion and disables versioning. | `replace proof control` | 14B | repository-static, provider-readonly, focused-test |
| `P14-INF-006` | No app exists. Phase 6G declares migration, API, Keycloak, web, and ingress. | `replace proof control` | 14B | repository-static, provider-readonly, focused-test |
| `P14-INF-007` | The proof database firewall allows only its app but uses proof resource names. | `retain and harden` | 14B | repository-static, focused-test |
| `P14-INF-008` | The USD 55.15 Phase 6G estimate omits the two required workers. | `replace proof control` | 14B | repository-static, provider-readonly, focused-test |
| `P14-INF-009` | Phase 6G derives routes, CORS, issuer, and callback values from `APP_URL`. | `retain and harden` | 14B | repository-static, focused-test |
| `P14-INF-010` | Terraform uses provider 2.100.0, Terraform 1.16, and an external local backend. | `retain and harden` | 14B | repository-static, operator-record |
| `P14-SEC-001` | `workloop_migration` owns the application database and schema. | `retain and harden` | 14C | repository-static, focused-test, local-runtime |
| `P14-SEC-002` | `workloop_runtime` has explicit table, function, and RLS access. | `retain and harden` | 14C | repository-static, focused-test, local-runtime |
| `P14-SEC-003` | `workloop_expiry_processing` exists, but Phase 6G deploys no expiry component. | `retain and harden` | 14C | repository-static, focused-test, local-runtime |
| `P14-SEC-004` | `workloop_file_scanner` has narrow grants, but Terraform does not create or route it. | `add missing control` | 14C | repository-static, focused-test, local-runtime |
| `P14-SEC-005` | `workloop_storage_reconciler` has a protected function, but Terraform omits it. | `add missing control` | 14C | repository-static, focused-test, local-runtime |
| `P14-SEC-006` | Keycloak has a separate database owner, while bootstrap access needs tighter removal proof. | `retain and harden` | 14C | repository-static, focused-test, provider-live |
| `P14-SEC-007` | Phase 6G gives one read-write object key to the API and no worker-specific keys. | `replace proof control` | 14C | repository-static, focused-test, provider-live |
| `P14-SEC-008` | Secret examples exist, but ownership, rotation, revocation, and routes are incomplete. | `replace proof control` | 14C | repository-static, focused-test, operator-record |
| `P14-SEC-009` | Named operators, MFA state, time limits, and backup custody are unresolved. | `add missing control` | 14C | provider-readonly, operator-record, owner-approval |
| `P14-DEP-001` | One Python image supplies the API, migration, expiry, scanner, and reconciler code. | `retain and harden` | 14D | repository-static, focused-test, local-runtime |
| `P14-DEP-002` | Keycloak 26.7.3 is digest pinned and imports the cloud realm. | `retain and harden` | 14D | repository-static, focused-test, local-runtime |
| `P14-DEP-003` | Vite emits `dist` with six public API and OIDC settings. | `retain and harden` | 14D | repository-static, focused-test, local-runtime |
| `P14-DEP-004` | `cloud_migrate` runs before services but lacks a release-manifest binding. | `retain and harden` | 14D | repository-static, focused-test, local-runtime |
| `P14-DEP-005` | FastAPI exposes database-backed `/health` on one Phase 6G instance. | `retain and harden` | 14D | repository-static, focused-test, local-runtime |
| `P14-DEP-006` | Keycloak disables registration, protects brute force, and has a manual TOTP helper. | `retain and harden` | 14D | repository-static, focused-test, local-runtime |
| `P14-DEP-007` | Expiry is a one-shot command with no cloud schedule or all-scope overlap guard. | `add missing control` | 14D | repository-static, focused-test, local-runtime |
| `P14-DEP-008` | The scanner has single-row claims, leases, and retries but no cloud worker. | `add missing control` | 14D | repository-static, focused-test, local-runtime |
| `P14-DEP-009` | The reconciler has single-row claims, leases, and retries but no cloud worker. | `add missing control` | 14D | repository-static, focused-test, local-runtime |
| `P14-DEP-010` | Phase 6G recorded a commit and deployment ID, not a complete artifact manifest. | `add missing control` | 14D | focused-test, local-runtime, operator-record |
| `P14-OPS-001` | Safe structured logs exist locally, but cloud fields and retention are not fixed. | `retain and harden` | 14E | repository-static, focused-test, provider-live |
| `P14-OPS-002` | API health and deployment alerts exist without the full shared signal set. | `add missing control` | 14E | focused-test, provider-live, operator-record |
| `P14-OPS-003` | Auth and Keycloak events lack alert owners, severities, retention, and tests. | `add missing control` | 14E | focused-test, provider-live, operator-record |
| `P14-OPS-004` | Database metrics will exist only after provisioning. No resource alert exists now. | `add missing control` | 14E | provider-readonly, provider-live, operator-record |
| `P14-OPS-005` | Storage errors are logged, while growth, versioning, and access alerts are absent. | `add missing control` | 14E | focused-test, provider-live, operator-record |
| `P14-OPS-006` | Worker failures are logged, but heartbeat and queue-age rules are incomplete. | `add missing control` | 14E | focused-test, local-runtime, provider-live |
| `P14-OPS-007` | A USD 20 alert exists at 75 and 100 percent but is not the Phase 14 budget. | `retain and harden` | 14E | provider-readonly, provider-live, operator-record |
| `P14-OPS-008` | Phase 6G has a proof runbook, not a persistent operations runbook. | `replace proof control` | 14E | repository-static, focused-test, operator-record |
| `P14-REC-001` | The future managed cluster has native backups, but no live retention is verified. | `exercise and record` | 14F | provider-live, operator-record, recovery-rehearsal |
| `P14-REC-002` | No encrypted portable `workloop` database export exists. | `add missing control` | 14F | operator-record, recovery-rehearsal |
| `P14-REC-003` | No encrypted Keycloak export and signing-key record exists. | `add missing control` | 14F | operator-record, recovery-rehearsal |
| `P14-REC-004` | Phase 6G disabled object versioning and deleted its bucket. | `add missing control` | 14F | provider-live, operator-record, recovery-rehearsal |
| `P14-REC-005` | Git history exists, but cloud configuration is not bundled with each release. | `add missing control` | 14F | repository-static, operator-record, recovery-rehearsal |
| `P14-REC-006` | Phase 6G proved restart persistence, not an isolated restore. | `exercise and record` | 14F | local-runtime, provider-live, recovery-rehearsal |
| `P14-REC-007` | No Phase 14 compatible-artifact rollback or named restore cleanup exists. | `exercise and record` | 14F | provider-live, operator-record, recovery-rehearsal |
| `P14-PRM-001` | 14A verified current DigitalOcean state. 14G must refresh it before apply. | `verify read-only` | 14G | provider-readonly, operator-record |
| `P14-PRM-002` | The baseline GitHub run passed, while App installation scope is unresolved. | `verify read-only` | 14G | github-check, provider-readonly, operator-record |
| `P14-PRM-003` | No paid target manifest has owner approval. | `add missing control` | 14G | operator-record, owner-approval |
| `P14-PRM-004` | No Phase 14 resource exists and 14A authorizes no apply. | `exercise and record` | 14G | provider-live, operator-record, owner-approval |
| `P14-PRM-005` | No live proof covers every migration, MFA, secret, worker, backup, and journey gate. | `exercise and record` | 14G | provider-live, operator-record, recovery-rehearsal |
| `P14-PRM-006` | Phase 6G restart proof did not cover the Phase 14 worker state. | `exercise and record` | 14G | provider-live, operator-record |
| `P14-PRM-007` | No digest-bound Phase 14 promotion record exists. | `add missing control` | 14G | operator-record, owner-approval |
| `P14-PRM-008` | Only the project and default VPC remain from the temporary proof. | `retain and harden` | 14G | provider-live, operator-record, owner-approval |
| `P14-REV-001` | The 14A catalogue defines the future independent trace set. | `review independently` | 14H | repository-static, focused-test, operator-record |
| `P14-REV-002` | Security, recovery, rollback, operations, cost, and safe-log review awaits 14B through 14G. | `review independently` | 14H | provider-readonly, provider-live, recovery-rehearsal |
| `P14-REV-003` | The complete phase-closing local and GitHub gates belong to 14H. | `exercise and record` | 14H | local-runtime, github-check |
| `P14-REV-004` | No live Phase 14 target exists for the closing read-only check. | `verify read-only` | 14H | provider-readonly, provider-live, operator-record |
| `P14-REV-005` | Whole-phase signoff remains pending, and Phase 15 cannot start automatically. | `review independently` | 14H | operator-record, owner-approval |

## Coverage decision

The catalogue covers infrastructure, database roles, Keycloak administration, object permissions,
runtime settings, all seven components, CI and release identity, monitoring, backups, recovery,
promotion, rollback, costs, operators, and external prerequisites. Later parts may split a row into
narrower implementation checks. They must not change its owner, weaken its denial behavior, or leave
any child item without evidence.

Part rollback follows `14H`, `14G`, `14F`, `14E`, `14D`, `14C`, `14B`, then `14A`. This order does
not authorize cloud destruction. The retained VPC, project, Phase 13 archive, and
`workloop-clinic_postgres_data` keep their separate preservation rules.
