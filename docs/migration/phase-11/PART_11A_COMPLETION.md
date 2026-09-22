# Part 11A completion

Status: complete. The project owner approved decisions `11A-D1` through `11A-D18` on 2026-09-22,
and GitHub Migration foundation run `35745180197` passed.

## Result

Part 11A accounts for the common storage implementation, Phase 8 leave attachments, Phase 9 expense
receipts, every Phase 11 legacy module and screen, direct RPC and bucket calls, browser calculators,
and indirect notification, task, dashboard, report, print, and Supabase consumers.

The contract fixes role scope, list order, pagination, safe errors, idempotency, optimistic locking,
file validation, signing, malware quarantine, recovery, domain lifecycles, decimal behavior,
retention guards, and reverse rollback order. Eighteen decisions define the implementation boundary.
The common storage record is complete after Part 11B. The other nine records remain in
`preparation`, with legacy Supabase as their only read and write authority.

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
rules. Parts 11B through 11F may proceed under the approved sequential authorization.

## Local verification

- `node --test tests/phase-11a-contract.test.js`
- `node scripts/cutover-record-validator.mjs` against all ten Phase 11 records
- Markdown structure, local-link, whitespace, unfinished-marker, curved-quotation, and dash scans
- `git diff --check`

No backend, frontend, database, Compose, browser, or full-stack suite is required because Part 11A
changes documentation and a documentation verifier only. No migration, database object, runtime
route, storage object, credential, or cutover authority changed.

## Rollback and next step

Revert the Part 11A documents, verifier, and preparation records if the approved contract is
withdrawn. No data rollback is needed. Part 11B began only after its predecessor commit and routed
GitHub workflow passed and the project owner approved decisions `11A-D1` through `11A-D18`.
