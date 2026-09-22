# Part 11A golden cases

## Use

Every case uses tracked synthetic tenants, branches, users, employees, and files. IDs in executable
fixtures must be stable. A verifier compares exact states, decimals, timestamps supplied by its test
clock, source identities, and audit actions. Denied and failed commands compare complete before and
after snapshots.

## Common storage recovery

| ID | Input | Expected result |
| --- | --- | --- |
| `11A-G-STO-01` | Upload the same valid PDF twice under one conditional key | First create succeeds. Second returns `storage_conflict`. One object and one metadata set remain. |
| `11A-G-STO-02` | PDF declared as PNG, a PNG with bytes after `IEND`, a JPEG with no final `FF D9`, and a 10,485,761-byte file | Each fails before a provider call. No metadata, operation, scan, or object remains. |
| `11A-G-STO-03` | Clean synthetic PDF, SHA-256 `sha256:...`, scanner definition `synthetic-v1` | Scan moves pending to claimed to clean. `validUntil` is exactly 30 days after `scannedAt`. A signed URL expires exactly 300 seconds after issue. |
| `11A-G-STO-04` | Synthetic infected marker | Scan becomes infected. Download returns no URL. Logs contain scan UUID and `infected`, but no key, filename, digest, employee ID, or bytes. |
| `11A-G-STO-05` | Scanner timeout on attempts one through eight | Delays are 1 minute, 5 minutes, 15 minutes, 1 hour, 6 hours, 24 hours, and 72 hours. Attempt eight is terminal with no next attempt. |
| `11A-G-STO-06` | Clean result older than 30 days | Download fails closed and queues a new scan. It does not return the old signed URL. |
| `11A-G-STO-07` | Database fails after provider create but before domain commit | The reserved upload operation remains recoverable. Reconciliation deletes only that object and marks the operation reconciled. |
| `11A-G-STO-08` | Domain metadata names a missing object | Download returns `503 service_unavailable`, preserves metadata, and emits a safe missing-object alert. |
| `11A-G-STO-09` | Snapshot three objects and restore into an empty disposable target | Manifest, three bodies, metadata, scan bindings, and operation rows match. Local restore completes within 15 minutes. This is not a production RPO or RTO promise. |
| `11A-G-STO-10` | Restart existing images with database, signing key, synthetic object volume, S3 objects, and scan rows | Every digest, row identity, key fingerprint, and allowed download result matches the pre-restart record. |

## Employee documents, insurance, and employment contracts

| ID | Input | Expected result |
| --- | --- | --- |
| `11A-G-DOC-01` | Employee uploads `passport.pdf`, 1,024 bytes, expiry 2028-06-30 | Pending document is self-visible. It is not signable until scan is clean. Object key and digest are absent from the response. |
| `11A-G-DOC-02` | Administrator uploads the same category for a selected-branch employee | Row starts verified with trusted reviewer and time, but signing still waits for a clean scan. |
| `11A-G-DOC-03` | Administrator rejects a pending employee submission with `Image is unreadable` | State becomes rejected once. Identical replay returns the same response. Another reason under the same key returns `409 idempotency_conflict`. |
| `11A-G-DOC-04` | Delete rejected document after object removal fails | Browser receives an accepted cleanup state. Metadata or tombstone and durable delete operation remain. Verified deletion is denied. |
| `11A-G-INS-01` | Policy premium `12000.50`, renewal 2027-12-31, then employee coverage 2026-10-01 through 2027-09-30 | Values return as exact strings. Self view exposes insurer and tier, but not premium, broker, dependants, or card number. |
| `11A-G-INS-02` | Two concurrent replacements for one employee coverage | One locks and succeeds. The other returns `409 state_conflict`. One current coverage row remains. |
| `11A-G-CON-01` | Current Limited contract 2025-01-01 through 2026-12-31, renewed to 2028-12-31 | One `renewed` event appends. Employee current end date becomes 2028-12-31 in the same transaction. Prior event is unchanged. |
| `11A-G-CON-02` | Convert Limited to Unlimited with null end date | One `converted` event appends and current fields match. An identical retry returns it. Concurrent renewal loses the expected snapshot check. |
| `11A-G-CON-03` | Attempt renewed contract with end before start | `422 validation_error`. No employee, contract history, job history, audit, or idempotency row changes. |

## Assets, training, certifications, and CME

| ID | Input | Expected result |
| --- | --- | --- |
| `11A-G-AST-01` | Create asset code ` lap-001 ` and cost `1250.75` | Code stores as `LAP-001`; cost returns `1250.75`. Duplicate nonempty code in the branch fails. |
| `11A-G-AST-02` | Assign available asset to active same-branch employee on 2026-10-01 | One open assignment is appended and asset becomes assigned. A concurrent assignment fails without a second row. |
| `11A-G-AST-03` | Return on 2026-10-10 with condition `good` | Open assignment closes, custody history remains, and asset becomes available. Deleting the asset is denied because history exists. |
| `11A-G-TRN-01` | Employee self-enrols in a 12.50-hour course costing `0.00` | Planned row is created. Employee can change title, provider, and planned dates, but cannot set completed, score, passed, cost, or CME. |
| `11A-G-TRN-02` | Manager completes a direct-report CME course with 12.50 hours and passed true | Completion records trusted actor and end date. The same manager cannot act after reassignment. |
| `11A-G-CERT-01` | Employee submits a PDF certificate | Certification starts pending, file starts quarantined, and no signed URL exists before clean scan and admin verification. |
| `11A-G-CERT-02` | Admin verifies the clean pending certificate | It becomes retained verified evidence. Delete is denied. |
| `11A-G-CME-01` | Target 25.0 hours; qualifying completed rows 12.50 and 8.25; planned row 10.00; failed row 4.00 | Achieved is `20.8` after exact sum 20.75 rounds half up once. Gap is `4.2`. Planned and failed rows do not count. |

## Appraisals and clinical incidents

| ID | Input | Expected result |
| --- | --- | --- |
| `11A-G-APP-01` | Generate twice for three eligible employees in one active cycle | Exactly three appraisals and fifteen fixed sections exist. Replay returns the same identities. Concurrent generation creates no duplicate. |
| `11A-G-APP-02` | Section ratings 4.0, 4.0, 3.0, 3.0, and 5.0 in fixed order | Weighted numerator is 28.50, denominator is 7.50, and overall rating is `3.8`. |
| `11A-G-APP-03` | Manager rates a report while administrator reviews the same appraisal | Both lock the parent. One succeeds; the stale command returns `409 state_conflict`. No lost section or review update occurs. |
| `11A-G-APP-04` | Close a cycle with one pending appraisal | Closure fails unchanged. After every appraisal is reviewed or calibrated, closure records trusted actor and time. |
| `11A-G-INC-01` | Create critical medication error involving a same-branch employee | Report is open and retained. List ordering uses date, time, then ID. No sensitive text appears in logs. |
| `11A-G-INC-02` | Investigate, record corrective action, then close | States move open to investigating to closed. Close derives actor and trusted date. Replay is stable. |
| `11A-G-INC-03` | Use another branch employee as involved person | Generic `404 resource_not_found`. The response does not reveal whether that employee exists. |

## Letter and custom requests

| ID | Input | Expected result |
| --- | --- | --- |
| `11A-G-REQ-01` | Employee submits Salary Certificate for Bank with purpose `Emirates NBD` | Pending request stores a trusted employee and employer snapshot. Staff list omits salary fields. |
| `11A-G-REQ-02` | Employee submits custom subject of 3 characters and detail of 5 characters | Boundary succeeds. Subject 2, subject 121, detail 4, and detail 2001 fail without a row. |
| `11A-G-REQ-03` | Administrator completes while another administrator rejects the same pending request | One command succeeds. The other returns `409 state_conflict`. The decided row and snapshot remain immutable. |
| `11A-G-REQ-04` | Owner requests print source for completed request | Response contains allowlisted snapshot fields and no HTML, template, PDF, object key, or unrelated employee data. |

## Offboarding and final settlement

| ID | Input | Expected result |
| --- | --- | --- |
| `11A-G-OFF-01` | Initialize twice for one selected-branch employee | One checklist exists. Each immutable template creates one template-provenance task once. |
| `11A-G-OFF-02` | Add custom task, then delete it before completion | Provenance is `custom`; deletion succeeds. A template task delete is denied. |
| `11A-G-OFF-03` | Complete with one required task open or one open asset assignment | `409 offboarding_blocked`. Checklist, employee, assets, tasks, settlement, audit, and idempotency remain unchanged. |
| `11A-G-OFF-04` | Visa state moves from initiated back to not started | `409 state_conflict`. Technical rollback does not reverse business state. |
| `11A-G-SET-01` | Preview before settlement policy approval | `409 settlement_policy_unavailable`. The response names missing policy IDs, not calculated amounts. No settlement row is inserted. |
| `11A-G-SET-02` | Source snapshot with salary `10000.00`, allowance `2500.00`, leave balance `7.50`, advance balance `333.34`, one finalized payroll source, and no open asset | Snapshot preserves exact strings, source row IDs, versions, and digest. No gratuity, leave, notice, or net amount is calculated before approval. |
| `11A-G-SET-03` | One source version changes after preview | Completion returns `409 state_conflict` and changes nothing. |

## Settlement cases that require owner values

The implementation verifier will add exact monetary outcomes after the owner approves the settlement
policy. At minimum it must cover less than one year, exactly one year, exactly five years, more than
five years, resignation, termination, any approved jurisdiction variant, the approved cap, leave
encashment, notice pay, advance deduction, final payroll treatment, rounding boundaries, a negative
net result, stale source versions, and concurrent completion. These cases are blocked by the
production-policy stop in `11A-D16`; legacy browser outputs are not expected values.
