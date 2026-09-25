# Part 12G completion

Status: complete. The local gate passed. The routed GitHub result is recorded in the Part 12H
handoff rather than added in a follow-up documentation commit.

## Result

Part 12G moves approved report, payslip, letter, offboarding, and final-settlement PDF generation to
the FastAPI migration application. It also adds administrator bulk payslip ZIP delivery. Migration
print actions open the same authorized server PDF bytes used for download, so no browser print or
calculation path remains active.

The PDF renderer fixes its page dimensions, margins, built-in font declaration, checked-in font
metrics, logo digest, source timestamps, metadata, document identifiers, wrapping, pagination, and
Unicode fallback. Missing or changed approved assets fail closed. The ZIP renderer fixes source
ordering, safe filenames, entry timestamps, compression, permissions, UTF-8 metadata, and a manifest
of filenames, byte counts, and SHA-256 digests. Both renderers enforce page, entry, byte, time,
global-worker, and per-principal limits before delivery.

Letters use only the Phase 11 print-source and offboarding projections. Final-settlement output uses
the persisted approved settlement. Payslips use immutable Phase 9 snapshots. No output bytes are
stored in PostgreSQL, object storage, or audit metadata.

Alembic revision `e8a1c3f5b7d9` follows `d6f8a0c2e4b7`. It replaces the fixed-purpose
`append_phase12_output_audit` function without changing its signature. The function retains all
eight Part 12F tuples and adds the six approved PDF and ZIP tuples. Employees may audit only their
own payslip PDF and completed requested letter. Administrator outputs remain company and selected
branch scoped. The runtime login still has no direct `audit_events` insert grant.

## Cutover result

The canonical dependency catalogue records one disposition for all 97 Phase 12 inventory IDs. The
notification record remains valid, and `phase12-consumers.json` now covers tasks, dashboards,
reports, generated outputs, audit dependencies, and indirect consumers. Retained legacy readers and
browser generators remain only as the Phase 13 rollback boundary.

`P12-OUT-17` stays unavailable in the migration build. The approved contract names no employee
detail or leave-calendar print projection, so adding either would exceed Part 12G. Their retained
legacy callers may return only after the migration output routes are disabled during rollback.

## Gate evidence

- All 669 backend tests passed. Eighteen focused renderer and report-route tests cover deterministic
  PDF bytes across separate processes, fixed metadata, checked assets, Unicode fallback, page
  limits, source-only letters and settlement, ZIP order and manifest, unsafe filename material,
  bounded per-principal workers, required headers, and audit failure before response creation.
- All 282 frontend tests passed. Focused output tests prove that migration controls request server
  bytes, preserve delivery headers, save downloads, open the same PDF bytes for print, and revoke
  browser object URLs. Complete lint and both production builds passed with only the existing chunk
  size warnings.
- Complete Ruff lint and formatting passed. Strict Pyright reported zero findings in a disposable
  Python 3.12 environment built from `requirements-dev.lock`, and `pip check` found no broken
  requirements.
- `scripts/verify-phase-12g-boundary.py` passed. It checks every route, all 14 audit tuples, the
  97-entry catalogue, the fail-closed print decision, and the absence of migration browser
  generators. Both Phase 12 cutover records passed the canonical validator.
- `scripts/verify-phase-12g-database.py` passed at the new head before and after rollback testing. It
  proved function ownership, grants, all 14 admitted tuples, employee self scope, branch and source
  checks, safe metadata, denial cases, and no direct runtime insert grant.
- The fresh full-stack gate built the changed backend once, applied migrations twice, confirmed one
  head and no pending Alembic operation, and downgraded exactly to `d6f8a0c2e4b7`. A synthetic audit
  sentinel remained after downgrade, the Part 12F verifier passed, and upgrade back to
  `e8a1c3f5b7d9` restored all Part 12G checks.
- Live HTTP, Keycloak, and the complete migration browser journey passed. The gate recorded database
  and signing-key state, restarted the existing images without rebuilding, reproduced the exact
  state, verified persisted S3 and scan evidence, passed authentication without reconfiguration,
  and passed the service log-safety scan.

## Resource boundary

Verification used only synthetic records and disposable local services. Synthetic browser, audit,
database, and object-storage fixtures were removed. The `workloop-phase12g-dev` and
`workloop-phase12g-gate` containers, networks, and volumes were removed after verification.

The protected `workloop-clinic_postgres_data` volume remained present and was not attached,
modified, deleted, or recreated. No production provider, credential, cloud resource, paid service,
production data, real employee record, patient record, payroll record, or banking record was used.

## Rollback and next part

Rollback disables 12G routes and print controls before restoring retained browser generators. It
then disables 12F byte routes, 12E reports, 12D dashboards, 12C tasks, and 12B notification
producers and readers in reverse dependency order. Source rows, snapshots, notifications, read
timestamps, settlements, and audit events remain intact. The 12G database downgrade restores the
exact Part 12F audit allowlist and does not delete audit history.

After the routed GitHub gate passes and the branch is clean and synchronized, Part 12H starts in a
new task in the same saved project and local checkout. Part 12H independently reviews all Phase 12
dependencies and golden cases, exercises reverse rollback and restart proof, records Phase 12
completion, and requests the project owner's whole-phase signoff.
