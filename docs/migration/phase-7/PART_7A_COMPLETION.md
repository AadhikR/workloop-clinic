# Phase 7A completion record

## Status

The project owner approved decisions `7A-D1` through `7A-D9` on 2026-09-09. Phase 7A defines the
organization and workforce contract, records the complete legacy dependency inventory, and prepares
the independent cutover records. It changes no runtime, database, React, infrastructure, or
identity-provider behavior.

Phase 7B remains unauthorized. Completing this design phase does not authorize implementation or a
cutover authority change.

## Approved contract

`PART_7A_DOMAIN_CONTRACT.md` is the canonical Phase 7 contract. The approved decisions establish:

- separate legal-company and operating-branch projections;
- create-only employee CSV import until a schema-backed employee identity exists;
- transactional history for title, department, salary, and status changes;
- status history for probation confirmation and termination, with audit-only probation extension;
- optimistic concurrency and locked exact snapshots where `updated_at` is unavailable;
- complete, atomic direct-report reassignment for manager ineligibility;
- seven independently controlled cutover units with one writable system and reverse-order rollback;
- the Phase 7 routes, projections, writable fields, filters, sorts, null rules, and enums.

Decision `7A-D5` approves reliable idempotency for non-repeatable mutations and the requirement for a
separately reviewed exact schema amendment. Phase 7A adds no idempotency table or migration. The
affected work in 7C, 7F, and 7G must not begin until the table, constraints, retention behavior, and
migration design are approved.

## Inventory and cutover preparation

The contract inventories every known legacy reader, writer, converter, direct React consumer,
indirect consumer, and target migration dependency for `companies`, `branches`, `employees`,
`user_profiles`, `employee_job_history`, `departments`, and `department_staffing_rules`.

Seven draft cutover records exist for organization context, organization administration, employee
directory, departments, staffing rules, employee administration, and employee lifecycle. Every
record remains in `preparation`. Legacy Supabase remains the sole read and write authority, and all
planned migration dependencies remain frozen.

The attached synthetic refresh evidence validates only the declared two-person Phase 6 identity map.
It does not claim Phase 7 API, database, UI, or cutover coverage. Each implementation part must
replace its planned locators and attach fresh feature evidence before changing authority.

## Verification

The Phase 7A documentation gate includes:

- validation of all seven cutover records with `scripts/cutover-record-validator.mjs`;
- JSON parsing and declared evidence-hash checks;
- decision-register completeness and uniqueness checks;
- Markdown fence, heading, placeholder, character, and trailing-whitespace checks;
- changed-path and staged-diff checks proving that the phase contains documentation only.

No local application stack, Docker service, browser suite, database migration, cloud resource, or
production-data check is required for this documentation-only phase. The path-routed GitHub workflow
for the Phase 7A commit must pass. The final task report records that workflow result.

## Resource and rollback boundary

The preserved `workloop-clinic_postgres_data` volume was not attached, upgraded, recreated, or
deleted. Services remain stopped. No cloud resource or credential was created.

Rollback is a documentation revert. It changes no data authority and requires no database or
infrastructure recovery.

## Stop condition

Phase 7A stops here. Phase 7B requires separate owner authorization.
