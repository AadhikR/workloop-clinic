# Remaining release evidence

The unit, API, database, and three-role browser suites cover the implemented migration application.
The following evidence remains before release.

## Phase 13

- [ ] Prove a fresh locked install and complete disposable setup with every retired provider input
  absent.
- [ ] Fail on any attempted retired-provider DNS, TCP, TLS, HTTP, WebSocket, database, or object-store
  connection.
- [ ] Complete approved external discovery, encrypted export, isolated restore, retention, and exact
  deletion approvals without committing secrets or personal data.
- [ ] Run the independent repository, runtime, external-state, rollback, and cleanup review.

## DigitalOcean deployment

- [ ] Provision the approved development and staging resources through reviewed infrastructure.
- [ ] Verify private networking, managed secrets, TLS, health checks, log retention, and least
  privilege.
- [ ] Prove PostgreSQL and object-storage backup restoration into isolated targets.
- [ ] Exercise frontend, API, worker, Keycloak, database, and object-store rollback procedures.

## Final validation

- [ ] Run the complete administrator, manager, and employee acceptance journey in staging.
- [ ] Run tenant, branch, role, object, and output authorization tests against the deployed stack.
- [ ] Record load, latency, timeout, and failure-recovery results for agreed workloads.
- [ ] Complete the operating runbooks, ownership table, alert routes, and release signoff.

Do not satisfy these items with production or real clinic data. Use synthetic records and isolated
restore targets.
