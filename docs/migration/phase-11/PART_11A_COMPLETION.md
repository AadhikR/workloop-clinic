# Part 11A completion

Status: implementation and local documentation gate complete; awaiting project-owner contract
approval and the routed GitHub result before 11B.

## Result

Part 11A accounts for the common storage implementation, Phase 8 leave attachments, Phase 9 expense
receipts, every Phase 11 legacy module and screen, direct RPC and bucket calls, browser calculators,
and indirect notification, task, dashboard, report, print, and Supabase consumers.

The contract fixes role scope, list order, pagination, safe errors, idempotency, optimistic locking,
file validation, signing, malware quarantine, recovery, domain lifecycles, decimal behavior,
retention guards, and reverse rollback order. Eighteen decisions define the implementation boundary.
Ten cutover records remain in `preparation`, with legacy Supabase as the only read and write authority.

The amendment proposal reserves one append-only revision per implementation part. It proposes a
file-security scan queue and dedicated scanner login, scan links for all private-file domains,
missing optimistic-lock fields, offboarding task provenance, request snapshots, and immutable
settlement records.

## Deliberate stops

The repository has no approved production file-retention schedule, backup target, backup schedule,
RPO, RTO, or restore owner. Part 11B may implement and test the stated disposable local recovery
objectives, but production storage remains disabled until those choices receive separate approval.

The legacy settlement code contains contradictory service-date comments, unapproved legal claims,
and binary floating-point arithmetic. It is not the Phase 11 settlement contract. Part 11G
calculation remains blocked until the project owner approves jurisdiction, gratuity, leave
encashment, notice, final salary, deduction, advance, asset, rounding, negative-net, and reviewer
rules. Parts 11B through 11F can proceed after this contract is approved.

## Local verification

- `node --test tests/phase-11a-contract.test.js`
- `node scripts/cutover-record-validator.mjs` against all ten Phase 11 records
- Markdown structure, local-link, whitespace, unfinished-marker, curved-quotation, and dash scans
- `git diff --check`

No backend, frontend, database, Compose, browser, or full-stack suite is required because Part 11A
changes documentation and a documentation verifier only. No migration, database object, runtime
route, storage object, credential, or cutover authority changed.

## Rollback and next step

Revert the Part 11A documents, verifier, and preparation records if the contract is rejected. No data
rollback is needed. Do not start 11B until the documentation commit is pushed, its routed GitHub
workflow passes, and the project owner explicitly approves decisions `11A-D1` through `11A-D18`.
