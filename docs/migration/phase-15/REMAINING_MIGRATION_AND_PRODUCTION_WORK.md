# Remaining migration and production work

Recorded on October 5, 2026, at 5:55 PM Dubai time.

The reviewed app is running on DigitalOcean. Its runtime uses FastAPI, Keycloak, PostgreSQL,
and private object storage. The former external project remains preserved as an archive.
The current deployment uses synthetic data and has not passed the complete production launch gate.

## Finish live acceptance and Phase 15 signoff

All three temporary test accounts authenticated. The live storage check returned a timeout,
so that needs resolving before acceptance can pass.

Remaining work includes the live role and file checks, authorization denials, recovery and
performance checks, and exact cleanup of temporary test data, files, and accounts. Record the
verified release and acceptance results, then obtain whole Phase 15 owner signoff.

## Prepare the production launch

The current deployment uses synthetic data. Real records, documents, user onboarding, and the
final switch to the new app need a separate migration and validation step.

Agree the production scope, migrate the required records and files, configure real user access,
and verify the transferred data and workflows before switching users to the new app.

## Complete additional product features

The roadmap lists these as later work:

- Arabic and right to left interface support
- Production email delivery and message templates
- Provider backed malware scanning operations
- Maps and geofenced attendance
- DEWS and GPSSA contribution workflows
- Production analytics, alerting, and service level objectives

These features need separate approval and do not change the completed removal of the former
service from the application runtime.

## Source records

- [Product roadmap](../../../FEATURES_ROADMAP.md)
- [Phase 15 plan](SUBPHASE_PLAN.md)
- [Restoration F completion record](PORTAL_RESTORATION_F_COMPLETION.md)
- [Phase 13 runtime and archive completion](../phase-13/PART_13H_COMPLETION.md)

This note records outstanding work. It does not grant production data access, authorize another
phase, or declare the current live acceptance complete.
