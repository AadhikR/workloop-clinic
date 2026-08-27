# Phase 0 synthetic test data

## Purpose and safety rules

This document defines deterministic fixtures for migration, API contract, RLS, file, report, and end-to-end tests. The data is fictional.

Fixture rules:

- Use only `.test` email addresses.
- Use the explicit UUIDs below. Derive every other persisted fixture ID with the UUIDv5 rule below; never generate a random seed ID.
- Use fictional identifiers that satisfy current format validators for successful paths. Keep invalid identifiers in separately labeled negative payloads.
- Never use production files, names, addresses, phone numbers, or credentials.
- Store passwords only in test environment setup, not in this document or seed SQL.
- Seed dates from the fixed clock below. Do not derive fixtures from the machine's real current date.
- A seed run must be idempotent and must not delete data outside the listed tenant IDs.

### Deterministic IDs and record counts

Use UUIDv5 namespace `00000000-0000-5000-8000-000000000001`. For any record without an explicit UUID, derive its ID from this canonical name:

```text
workloop/<table>/<tenant-key>/<branch-key-or-none>/<actor-key-or-none>/<scenario-key>
```

Examples:

```text
workloop/leave_requests/horizon/dubai/H-DXB-002/pending-annual
workloop/attendance_records/horizon/dubai/H-DXB-002/present
workloop/incidents/cedar/sharjah/C-SHJ-002/medication-error-open
```

Every item in a status list creates exactly one record unless a named required record already covers that status. Every named required case creates exactly one record unless it explicitly gives a count. “Both tenants” means one record per branch, for four records total. Negative request payloads are not persisted unless the case explicitly tests legacy invalid data.

Phase 0 defines the fixture identities, fixed clock, scenario catalogue, canonical naming rule, and expected outcomes. Phase 4 must compile them into a version-controlled executable manifest containing the canonical key, derived UUID, table, complete values, and expected count for every row before seed code is accepted. The seed may not invent additional rows. Its validation compares exact manifest counts and IDs after every run.

## Fixed clock and relative date strategy

Use this clock for all deterministic tests:

```yaml
clock_date: 2026-08-27
clock_timestamp: 2026-08-27T08:00:00Z
uae_timestamp: 2026-08-27T12:00:00+04:00
timezone: Asia/Dubai
```

Fixture builders may expose relative aliases, but must resolve them to fixed stored values before insertion:

| Alias | Stored value | Use |
|---|---|---|
| `TODAY` | `2026-08-27` | Current attendance and active leave |
| `YESTERDAY` | `2026-08-26` | Missing clock-out |
| `PLUS_7D` | `2026-09-03` | Urgent probation or expiry |
| `PLUS_14D` | `2026-09-10` | Notification threshold |
| `PLUS_30D` | `2026-09-26` | Warning threshold |
| `PLUS_60D` | `2026-10-26` | Standard document threshold |
| `PLUS_90D` | `2026-11-25` | Clinical credential threshold |
| `MINUS_1D` | `2026-08-26` | Newly expired document |
| `AUG_START` | `2026-08-01` | Current reporting period |
| `JUL_END` | `2026-07-31` | Closed attendance period |

Tests that run without a fake clock must compare against the fixed values, not phrases such as "expires in 7 days". Browser tests should install a clock at `2026-08-27T08:00:00Z` before loading React.

## Deterministic identity map

### Tenant A, Horizon Clinics LLC

```yaml
tenant_key: horizon
admin_auth_user_id: 10000000-0000-4000-8000-000000000001
admin_email: hr.admin@horizon.test
admin_profile:
  role: admin
  company_user_id: 10000000-0000-4000-8000-000000000001
  employee_id: null
```

Branches are current `companies` rows:

| ID | Branch | Fake employer data | Settings |
|---|---|---|---|
| `20000000-0000-4000-8000-000000000001` | Horizon Dubai Main | MOL `9000000816726`; route `999000001`; `payroll@horizon.test` | Mainland; Healthcare; salary day 25; Nafis 2%; all feature toggles true |
| `20000000-0000-4000-8000-000000000002` | Horizon Abu Dhabi | MOL `9000000816727`; route `999000002`; `auh-payroll@horizon.test` | Mainland; Healthcare; salary day 27; biometric false; other toggles true |

### Tenant B, Cedar Medical Group LLC

```yaml
tenant_key: cedar
admin_auth_user_id: 10000000-0000-4000-8000-000000000002
admin_email: hr.admin@cedar.test
admin_profile:
  role: admin
  company_user_id: 10000000-0000-4000-8000-000000000002
  employee_id: null
```

| ID | Branch | Fake employer data | Settings |
|---|---|---|---|
| `30000000-0000-4000-8000-000000000001` | Cedar Sharjah | MOL `9000000910001`; route `999000101`; `payroll@cedar.test` | Mainland; Healthcare; salary day 25; all toggles true |
| `30000000-0000-4000-8000-000000000002` | Cedar DHCC | MOL `9000000910002`; route `999000102`; `dhcc-payroll@cedar.test` | Free Zone; Dubai Healthcare City; staffing rules false |

The application currently treats each branch as a company row. The word tenant here means one owning admin and their company rows.

## Employee and role fixtures

All bank and government identifiers below are fake and intentionally fail real-world lookup.

### Tenant A employees

| Employee ID | No. and name | Branch | Portal user and role | Employment state | Reporting manager | Test purpose |
|---|---|---|---|---|---|---|
| `21000000-0000-4000-8000-000000000001` | `H-DXB-001`, Dr Aisha Test | Dubai | `11000000-0000-4000-8000-000000000001`, `aisha.manager@horizon.test`, manager | Active, Unlimited | None | Dubai manager, UAE national, long service, valid DHA |
| `21000000-0000-4000-8000-000000000002` | `H-DXB-002`, Ravi Test | Dubai | `11000000-0000-4000-8000-000000000002`, `ravi.employee@horizon.test`, employee | Active, Limited | H-DXB-001 | Golden payroll, expense, advance, OT |
| `21000000-0000-4000-8000-000000000003` | `H-DXB-003`, Maria Test | Dubai | `11000000-0000-4000-8000-000000000003`, `maria.employee@horizon.test`, employee | Probation, Limited | H-DXB-001 | Probation and 14-day passport threshold |
| `21000000-0000-4000-8000-000000000004` | `H-DXB-004`, Noor Test | Dubai | `11000000-0000-4000-8000-000000000004`, `noor.employee@horizon.test`, employee | On Leave, Unlimited | H-DXB-001 | Current leave and roster conflict |
| `21000000-0000-4000-8000-000000000005` | `H-DXB-005`, Fatima Test | Dubai | `11000000-0000-4000-8000-000000000005`, `fatima.employee@horizon.test`, employee | Active, Unlimited | H-DXB-001 | Second UAE national, maternity detail |
| `21000000-0000-4000-8000-000000000006` | `H-DXB-006`, John Test | Dubai | No auth link | Terminated, inactive | H-DXB-001 | EOS, offboarding, historical payroll |
| `22000000-0000-4000-8000-000000000001` | `H-AUH-001`, Dr Omar Test | Abu Dhabi | `12000000-0000-4000-8000-000000000001`, `omar.manager@horizon.test`, manager | Active, Unlimited | None | Abu Dhabi manager and branch isolation |
| `22000000-0000-4000-8000-000000000002` | `H-AUH-002`, Leila Test | Abu Dhabi | `12000000-0000-4000-8000-000000000002`, `leila.employee@horizon.test`, employee | Active, Limited | H-AUH-001 | Manager queues and schedule |
| `22000000-0000-4000-8000-000000000003` | `H-AUH-003`, Sara Test | Abu Dhabi | `12000000-0000-4000-8000-000000000003`, `sara.employee@horizon.test`, employee | Active, Limited | H-AUH-001 | Rejected document and certification |
| `22000000-0000-4000-8000-000000000099` | `H-LEG-001`, Legacy Null Test | null | No auth link | Active | None | Current `company_id IS NULL` branch behavior |

Key employee values:

```yaml
H-DXB-001:
  employment_start_date: 2017-01-01
  nationality: United Arab Emirates
  department: Clinical
  job_title: Medical Director
  basic_salary: 30000.00
  housing_allowance: 8000.00
  transport_allowance: 2000.00
  allowance: 1000.00
  licence_authority: DHA
  licence_number: FAKE-DHA-0001
  licence_expiry: 2027-05-31

H-DXB-002:
  employment_start_date: 2022-03-15
  contract_type: Limited
  contract_end_date: 2027-03-14
  nationality: India
  department: Nursing
  job_title: Registered Nurse
  basic_salary: 12000.00
  housing_allowance: 3000.00
  transport_allowance: 1000.00
  allowance: 500.00
  mol_id: 90000000000002
  bank_routing_code: 999000001
  iban: AE000000000000000000002

H-DXB-003:
  employment_start_date: 2026-03-05
  probation_end_date: 2026-09-03
  employment_status: Probation
  passport_number: TESTP000003
  passport_expiry: 2026-09-10

H-DXB-004:
  employment_status: On Leave

H-DXB-005:
  nationality: UAE

H-DXB-006:
  employment_start_date: 2019-02-01
  employment_status: Terminated
  active: false
  termination_date: 2026-08-20
  termination_reason: Resignation
```

Give every active employee unique fictional values for `mol_id`, IBAN, Emirates ID, visa, passport, labour card, phone, and work email. Assign these fixture sequences:

| Sequence | Employee |
|---:|---|
| 01 | H-DXB-001 |
| 02 | H-DXB-002 |
| 03 | H-DXB-003 |
| 04 | H-DXB-004 |
| 05 | H-DXB-005 |
| 06 | H-AUH-001 |
| 07 | H-AUH-002 |
| 08 | H-AUH-003 |
| 09 | H-LEG-001 |
| 10 | C-SHJ-001 |
| 11 | C-SHJ-002 |
| 12 | C-SHJ-003 |
| 13 | C-DHC-001 |
| 14 | C-DHC-002 |

For integer sequence `n`, generate the values exactly as follows:

```yaml
mol_id: "900000000000" + n padded to 2 digits
iban: "AE" + n padded to 21 digits
emirates_id_raw: "7841990" + n padded to 8 digits
emirates_id_display: split raw as 3-4-7-1 digits
visa_number: "999/2026/" + n padded to 7 digits
passport_number: "TESTP" + n padded to 6 digits
labour_card_number: "TESTLC" + n padded to 6 digits
phone: "+971" + (500000000 + n)
```

For H-DXB-002, sequence 2 produces MOL `90000000000002`, IBAN `AE000000000000000000002`, Emirates ID `784-1990-0000000-2`, visa `999/2026/0000002`, passport `TESTP000002`, labour card `TESTLC000002`, and phone `+971500000002`. Add validator tests that run every successful fixture through `src/utils/uaeValidators.js`. Invalid-format fixtures such as a missing MOL ID or malformed IBAN belong only to the explicit negative payroll cases.

### Tenant B employees

| Employee ID | No. and name | Branch | Portal user and role | State | Manager |
|---|---|---|---|---|---|
| `31000000-0000-4000-8000-000000000001` | `C-SHJ-001`, Priya Test | Sharjah | `13000000-0000-4000-8000-000000000001`, `priya.manager@cedar.test`, manager | Active | None |
| `31000000-0000-4000-8000-000000000002` | `C-SHJ-002`, Ahmed Test | Sharjah | `13000000-0000-4000-8000-000000000002`, `ahmed.employee@cedar.test`, employee | Active | C-SHJ-001 |
| `31000000-0000-4000-8000-000000000003` | `C-SHJ-003`, Eva Test | Sharjah | `13000000-0000-4000-8000-000000000003`, `eva.employee@cedar.test`, employee | Probation | C-SHJ-001 |
| `32000000-0000-4000-8000-000000000001` | `C-DHC-001`, Dr Lina Test | DHCC | `14000000-0000-4000-8000-000000000001`, `lina.manager@cedar.test`, manager | Active | None |
| `32000000-0000-4000-8000-000000000002` | `C-DHC-002`, Bilal Test | DHCC | `14000000-0000-4000-8000-000000000002`, `bilal.employee@cedar.test`, employee | Active | C-DHC-001 |
| `32000000-0000-4000-8000-000000000003` | `C-DHC-003`, Grace Test | DHCC | No auth link | Terminated | C-DHC-001 |

Use overlapping display names, employee numbers, descriptions, and file names between tenants where constraints permit. This catches scoping by display text instead of tenant-owned UUID.

## Departments and staffing fixtures

Tenant A departments:

```yaml
- Clinical
- Nursing
- Reception
- Laboratory
- Pharmacy
- Administration
```

Hierarchy and rules:

```yaml
hierarchy:
  Clinical:
    head: H-DXB-001
    children: [Nursing, Laboratory, Pharmacy]

staffing_rules:
  - { department: Nursing, shift_category: morning, min_staff: 2, effective_from: 2026-08-01 }
  - { department: Nursing, shift_category: night, min_staff: 1, effective_from: 2026-08-01 }
  - { department: Clinical, shift_category: morning, min_staff: 1, effective_from: 2026-08-01 }
```

Create one compliant day and one under-staffed day. Tenant B DHCC has staffing disabled and must not show staffing reports or block publication.

## Shift, roster, and swap fixtures

| ID suffix | Code | Category | Time | Break | Expected hours | Purpose |
|---|---|---|---|---:|---:|---|
| `...001` | `M` | `morning` | 08:00 to 17:00 | 60 | 8 | Normal day |
| `...002` | `A` | `afternoon` | 13:00 to 22:00 | 60 | 8 | Afternoon |
| `...003` | `N` | `night` | 20:00 to 08:00 | 60 | 11 | Overnight and night work |
| `...004` | `F` | `flexible` | null | 0 | 8 | Flexible |
| `...005` | `S` | `split` | 08:00 to 12:00; 16:00 to 20:00 | 0 | 8 | Split shift |

Seed:

- Published August 2026 assignments for both tenants.
- An unpublished edit after publication.
- Approved leave conflict for H-DXB-004.
- Manager-approved leave conflict for H-AUH-002.
- A staffing violation on 2026-08-29.
- H-DXB-002 with `planned_hours=8` and `actual_hours=12` for four roster OT hours.
- Pending, approved, and rejected swaps.
- An approved swap whose two source roster rows exist, so the RPC can exchange them.
- A rejected swap with a nonempty reason.
- One roster row in each branch with the same date and shift code.

## Attendance fixtures

Create at least one record for each exact state:

```text
PRESENT
ABSENT
ON_LEAVE
PUBLIC_HOLIDAY
WEEKEND
LATE
EARLY_DEPARTURE
HALF_DAY
OVERTIME
UNEXPLAINED_ABSENCE
PRESENT_REMOTE
MISSING_CLOCK_OUT
```

Also seed:

- Raw `CLOCK_IN` and `CLOCK_OUT` rows using `WEB`, `MANUAL`, and `BIOMETRIC_API`.
- A clock-in on 2026-08-26 without clock-out.
- One unresolved unexplained absence.
- One `UNAUTHORISED` resolution with deduction.
- One `LEAVE_LINKED` resolution.
- One `WFH` resolution.
- One OT record awaiting approval and one approved.
- Corrections in `Pending`, `Approved`, and `Rejected`.
- July 2026 period `closed`, `payroll_ready=true`.
- August 2026 period `open` with unresolved items.
- Biometric mappings for a matched badge, an unknown badge, and a duplicate punch.

### Attendance financial golden case

For H-DXB-002 with basic salary AED 12,000:

```yaml
unauthorised_absence:
  days: 1
  daily_rate: 400.00
  expected_deduction: 400.00

standard_overtime:
  hours: 2
  weekly_hours: 48
  hourly_rate_unrounded: 57.6923076923
  multiplier: 1.25
  expected_amount_rounded: 144.23

rest_day_no_substitute:
  hours: 2
  multiplier: 1.50
  expected_amount_rounded: 173.08
```

The separate roster-to-payroll formula uses `basic / 208 * 1.25`. Four hours for the same employee must produce AED 288.46.

## Leave fixtures

Seed every default leave type plus `CUSTOM_COMPASSIONATE`. Include annual, sick, maternity, parental, bereavement, study, Hajj, and unpaid behavior.

Create requests in every state:

| State | Required case |
|---|---|
| `Pending` | H-DXB-002 waits for H-DXB-001 |
| `ManagerApproved` | H-AUH-002 waits for HR under two-level approval |
| `ManagerRejected` | Direct report request with manager reason |
| `Approved` | H-DXB-004 covers `TODAY`; another historical request feeds payroll |
| `Rejected` | HR reason present |
| `Cancelled` | Employee-cancelled pending request |

Add cases for half day, weekend span, public holiday span, overlap, insufficient balance, probation-ineligible type, attachment-required type, maternity child fields, bereavement relationship and death fields, study institution and exam dates, and Hajj already taken.

Sick balance fixture:

```yaml
leave_type_code: SICK
approved_days: 50
sick_full_pay_used: 15
sick_half_pay_used: 30
sick_unpaid_used: 5
```

Add an active approval delegate from 2026-08-01 through 2026-08-31 and an expired delegate ending 2026-07-31.

## Payroll fixtures

### Run state coverage

Tenant A Dubai:

| ID | Period | Run status | Approval | WPS |
|---|---|---|---|---|
| `41000000-0000-4000-8000-000000000001` | `2026-05` | `generated` | `approved` | `confirmed` |
| `41000000-0000-4000-8000-000000000002` | `2026-06` | `generated` | `approved` | `partial_rejection` |
| `41000000-0000-4000-8000-000000000003` | `2026-07` | `draft` | `pending_approval` | `draft` |
| `41000000-0000-4000-8000-000000000004` | `2026-08` | `draft` | `draft` | `draft` |

Create equivalent Abu Dhabi and Tenant B periods with distinct IDs. Repeating a period in another branch is intentional. A branch-scoped API should allow that if database constraints do.

### Canonical payroll golden case

Use H-DXB-002 in run `41000000-0000-4000-8000-000000000004`:

```yaml
input:
  basicSalary: 12000.00
  housingAllowance: 3000.00
  transportAllowance: 1000.00
  allowance: 500.00
  increment: 0.00
  bonus: 1000.00
  otherPay: 0.00
  additionalAllowances:
    - { label: Expense Reimbursement, amount: 350.00, recurrence: one_time, source: automatic }
    - { label: Overtime (Roster), amount: 288.46, recurrence: one_time, source: automatic }
  deductions:
    - label: Advance Repayment
      amount: 500.00
      recurrence: one_time
      source: automatic
      payrollPeriod: 2026-08
      advanceRepayments:
        - { id: 51000000-0000-4000-8000-000000000002, amount: 500.00 }
  leaveDeduction: 400.00
  duCost: 0.00
  excluded: false

expected:
  fixedEarnings: 16500.00
  variableEarnings: 1638.46
  grossEarnings: 18138.46
  namedDeductions: 500.00
  leaveDeduction: 400.00
  otherDirectDeduction: 0.00
  totalDeductions: 900.00
  netPay: 17238.46
  wpsVariableAmount: 5238.46
```

Persist `leaveDeduction` as `payroll_entries.du_cost=400.00` and persist `variable_allowance=5238.46`. A round trip through the converter must reproduce the UI values.

### SIF golden case

For a one-entry file using the golden case:

```text
EDR,90000000000002,999000001,AE000000000000000000002,2026-08-01,2026-08-31,31,12000,5238,0\r\n
SCR,9000000816726,999000001,2026-08-25,1430,082026,1,17238,AED,Sal for Aug 2026
```

Assertions:

- The separator is CRLF.
- Basic and variable are rounded independently to integer AED.
- SCR count is 1.
- SCR total is 17,238.
- An excluded entry emits no EDR and does not affect SCR.
- Corrected SIF includes only entries whose WPS entry state is `rejected`.

### Additional payroll entries

Seed entries for:

- Fixed earnings only.
- A legacy signed `variableAllowance` with no detailed fields.
- Excluded employee.
- Missing MOL ID validation error.
- Invalid IBAN validation error.
- Expired document warning that does not block generation.
- Named deductions large enough to reduce WPS variable capacity.
- WPS states `pending`, `paid`, and `rejected`.
- One recurring allowance and one one-time bonus to test Repeat Last Payroll.
- Payroll approval audit actions `submitted`, `recalled`, `approved`, and `rejected`.

## Advance fixtures

| ID | Employee | State | Amount and schedule | Purpose |
|---|---|---|---|---|
| `51000000-0000-4000-8000-000000000001` | H-DXB-003 | `pending` | AED 1,000 | Employee request awaiting HR |
| `51000000-0000-4000-8000-000000000002` | H-DXB-002 | `active` | AED 1,500; starts `2026-08`; 3 months; AED 500 monthly | Golden payroll deduction |
| `51000000-0000-4000-8000-000000000003` | H-DXB-005 | `active` | Starts `2026-09` | Out-of-period exclusion |
| `51000000-0000-4000-8000-000000000004` | H-AUH-002 | `settled` | Outstanding zero | Historical state |
| `51000000-0000-4000-8000-000000000005` | H-AUH-003 | `cancelled` | HR rejection reason | Rejected request |
| `51000000-0000-4000-8000-000000000006` | H-DXB-004 | `cancelled` | `Withdrawn by employee` | Employee cancel path |

Record the August AED 500 repayment against the golden payroll. Calling `record_advance_repayment` again with the same advance and payroll must not double-reduce the balance.

Advance-plan golden values for H-DXB-002:

```yaml
amount: 1500.00
requested_months: 3
fixed_wps_capacity: 4500.00
requested_installment: 500.00
monthly_deduction: 500.00
effective_months: 3
extended_for_wps: false
end_month: 2026-10
```

## Expense fixtures

Seed all exact states:

```text
pending
manager_approved
manager_rejected
approved
paid
rejected
```

Required records:

- H-DXB-002 approved unpaid claim for AED 350, used by the payroll golden case.
- Paid claim linked to a generated payroll.
- Claim with a receipt object and claim with an empty receipt URL.
- Manager rejection and HR rejection with distinct reasons.
- Employee-deletable pending and rejected claims.
- Approved claim that employee deletion must reject.
- Future-dated request payload that the frontend rejects before RPC.

## Documents, files, insurance, and notifications

### Document and certification coverage

Create records in these date bands:

```text
expired at MINUS_1D
PLUS_7D
PLUS_14D
PLUS_30D
PLUS_60D
PLUS_90D
more than one year
no expiry
```

Document states:

```text
pending_verification
verified
rejected
```

Certification states:

```text
pending_review
verified
rejected
```

Types to cover:

- Visa, Passport, Emirates ID, Labour Card, and Work Permit.
- DHA, DOH, and MOH licences.
- BLS, ACLS, PALS, NRP, and CME certificates.
- Medical Fitness, Educational Certificate, NOC, and Other.

Include insurance policy renewal at PLUS_30D, employee coverage at PLUS_60D, and a dependant without an expiry field.

### Safe fake files

Check in or generate only tiny inert fixtures under a test-only temporary directory. Do not add them as part of this documentation change.

| File | Content rule | Expected use |
|---|---|---|
| `fake-document.pdf` | Minimal valid one-page PDF containing `SYNTHETIC TEST FILE`; under 5 KB | Employee document and signed URL |
| `fake-receipt.jpg` | 1 by 1 pixel JPEG; no EXIF | Expense receipt |
| `fake-credential.png` | 1 by 1 pixel PNG | Certification upload |
| `fake-biometric.csv` | Header plus three fake badge punches | Biometric parser |
| `oversize-placeholder.bin` | Generate in memory at 10 MB plus 1 byte; do not commit | File size rejection |
| `fake-malware.exe` | Zero-byte or text placeholder with `.exe`; never executable content | Extension rejection |

Use paths that follow current ownership:

```text
10000000-0000-4000-8000-000000000001/21000000-0000-4000-8000-000000000002/1700000000000_fake-document.pdf
10000000-0000-4000-8000-000000000001/21000000-0000-4000-8000-000000000002/leave/1700000000001_fake-document.pdf
10000000-0000-4000-8000-000000000001/certs/21000000-0000-4000-8000-000000000002/1700000000002_fake-credential.png
```

Also insert one metadata row whose object does not exist. The list must render and signed URL creation must fail without exposing another file.

### Notification coverage

Seed read and unread examples of:

```text
document_expiry
clinical_credential_expiry
insurance_expiry
probation_ending
contract_expiry
cert_expiry
clinical_licence_expiry
policy_renewal
leave_approved
leave_rejected
payslip_available
roster_published
```

Insert the same `(recipient_user_id, type, related_entity_id)` twice and assert one row remains.

## Training and CME fixtures

Create training states:

```text
planned
in_progress
completed with passed=true
completed with passed=false
cancelled
```

Create types `internal`, `external`, `online`, and `conference`.

CME cases:

| Employee | Year | Required | Completed CME | Expected |
|---|---:|---:|---:|---|
| H-DXB-001 | 2026 | 25 | 30 | Complete, 5 over |
| H-DXB-002 | 2026 | 25 | 12 | Gap 13 |
| H-DXB-003 | 2026 | 25 | 0 | Gap 25 |
| H-DXB-005 | 2026 | no explicit target | 8 | Default target behavior |
| H-DXB-001 | 2025 | 25 | 25 | Year filter control |

Manager H-DXB-001 must see Dubai direct-report training and not Abu Dhabi or Tenant B records.

## Appraisal fixtures

Create cycles in `draft`, `active`, and `closed`. Create appraisals in `pending`, `reviewed`, and `calibrated`.

Required cases:

- Appraisal with seeded but unrated sections.
- Partially rated appraisal that remains `pending`.
- Fully rated direct-report appraisal that becomes `reviewed`.
- Reviewed appraisal waiting for HR calibration.
- Calibrated appraisal.
- Manager's own appraisal, shown outside the team list.
- Appraisal belonging to another manager's report, which must not appear.

Weighted rating golden case:

```yaml
sections:
  - { name: Clinical Competency, rating: 4, weight: 2.0 }
  - { name: Patient Care Quality, rating: 5, weight: 2.0 }
  - { name: Communication and Teamwork, rating: 3, weight: 1.5 }
  - { name: Punctuality and Attendance, rating: 4, weight: 1.0 }
  - { name: Professional Development, rating: 2, weight: 1.0 }
weighted_sum: 28.5
total_weight: 7.5
expected_overall_rating: 3.8
expected_status: reviewed
```

## Asset fixtures

Create `available`, `assigned`, `under_repair`, `retired`, and `lost` assets.

Required assignment cases:

- Open assignment to H-DXB-002.
- Returned assignment with handover and return conditions.
- Employee Home shows only the caller's open assignment.
- Deleting an assigned asset fails.
- Tenant A cannot mutate a Tenant B asset ID.

## Incident fixtures

Cover incident states `open`, `investigating`, and `closed`; severities `low`, `moderate`, `high`, and `critical`; and these types:

```text
patient_safety
medication_error
injury
needlestick
infection
equipment
near_miss
workplace
other
```

Include reporter-only, reporter plus involved employee, and closed records with root cause, corrective action, closed date, and closed by. Put records in every branch to verify branch filters.

## Offboarding, contracts, and EOS fixtures

Create:

- Contract actions `new`, `renewed`, `converted`, and `not_renewed`.
- One checklist in `in_progress` with mixed task completion.
- One checklist in `completed`.
- Visa cancellation states `not_started`, `initiated`, `submitted_gdrfa`, and `cancelled` across records.
- A custom task and the default task list.

### Gratuity golden cases

Use exact anniversary dates to avoid partial-year ambiguity:

| Basic salary | Start | End | Reason | Expected gratuity |
|---:|---|---|---|---:|
| 6,000 | 2025-02-01 | 2026-01-01 | Termination | 0.00, under one year |
| 6,000 | 2024-01-01 | 2026-01-01 | Termination | 8,400.00 |
| 6,000 | 2022-01-01 | 2026-01-01 | Termination | 16,800.00 |
| 6,000 | 2020-01-01 | 2026-01-01 | Termination | 27,000.00 |
| 6,000 | 2024-01-01 | 2026-01-01 | Resignation | 2,800.00 using current one-third rule |
| 6,000 | 2022-01-01 | 2026-01-01 | Resignation | 11,200.00 using current two-thirds rule |

Six-year calculation:

```text
daily rate = 6000 / 30 = 200
first five years = 5 * 21 * 200 = 21000
year six = 1 * 30 * 200 = 6000
total = 27000
```

Add a long-service case whose raw result exceeds `basic_salary * 24`, and assert the cap. Add a final settlement with partial-month salary, leave encashment, and outstanding advance, with each intermediate value asserted separately.

## Requests and task fixtures

Letter types must include salary certificate for bank, salary certificate for embassy, NOC, salary transfer letter, and an internal employment confirmation. Add one custom request.

Request states are `pending`, `completed`, and `rejected`. Completed letters must be printable. Rejected records must have a reason.

Boundary payloads for custom requests:

| Field | Invalid low | Valid low | Valid high | Invalid high |
|---|---:|---:|---:|---:|
| Subject length | 2 | 3 | 120 | 121 |
| Details length | 4 | 5 | 2,000 | 2,001 |

Create at least one source record for every Task Center category. The seed validation must detect the current `doc_type`, `eid_expiry`, and payroll `month/year` task query mismatches rather than accepting an empty category list.

## Cross-tenant, cross-branch, and cross-manager negative tests

| Actor | Attempt | Required result |
|---|---|---|
| Horizon admin | Read, update, or delete Cedar employee UUID | No row returned or affected |
| Horizon admin | Open Cedar payroll run or entries | No data returned |
| Horizon admin | Call `replace_payroll_entries` with Cedar run | RPC rejects; no mutation |
| Horizon admin | Record repayment against Cedar advance | RPC rejects; balance unchanged |
| Horizon admin | Approve Cedar shift swap | RPC rejects; both rosters unchanged |
| Aisha manager | Approve Omar's Abu Dhabi report leave | RPC rejects because not a direct report or delegate |
| Aisha manager | Act on Priya's Cedar report expense | RPC rejects |
| Aisha manager | Rate appraisal section for Leila or Tenant B employee | RLS rejects |
| Ravi employee | Read another employee's payslip, attendance, document, advance, expense, or appraisal | Empty or denied |
| Ravi employee | Upload into Maria's storage folder | Storage RLS denies |
| Ravi employee | Delete approved or paid expense | RPC rejects; row remains |
| Ravi employee | Cancel active or settled advance | RPC rejects; state remains |
| Ravi employee | Request swap with Cedar employee | RPC rejects |
| Dubai admin branch view | Show Abu Dhabi employee, payroll, roster, swap, or incident | Must not appear |
| Dubai admin branch view | Show Abu Dhabi leave, expense, asset, training, appraisal, department, or attendance | Record as current branch-scope defect if it appears |
| Branch switch | Legacy null-company employee | Expected current behavior is appearance in both Horizon branches; flag as migration debt |
| Leila employee | Resolve employer with `getMyCompany()` | Test exposes current first-company behavior; target backend should resolve Abu Dhabi explicitly |
| Any caller | Reuse expired signed URL | Access denied |
| Horizon user | Sign Cedar object path | Storage RLS denies |
| Aisha manager | View a direct report after `reporting_manager_id` changes to Omar | Disappears from Aisha queue and appears only for Omar where branch rules allow |

For every denied mutation, assert both the response and database state. A thrown frontend error alone is not proof of isolation.

## Seed order

1. Auth users and admin profiles.
2. Company branch rows.
3. Departments and shifts that have no employee foreign keys.
4. Manager employees.
5. Employee auth users, employee rows, and employee or manager profiles.
6. Department heads, reporting relationships, and shift assignments.
7. Leave, attendance, roster, payroll, expenses, advances, and repayments.
8. Documents, Storage objects, insurance, training, certifications, and CME.
9. Appraisals, incidents, contracts, assets, offboarding, requests, and notifications.
10. Negative-control rows in Tenant B and legacy null-company rows.

Use upserts only on stable fixture keys. Child tables that represent immutable history should use deterministic IDs and conflict-safe inserts.

## Seed validation checks

### Identity and ownership

- Exactly two admin tenants exist.
- Each tenant has exactly two company rows.
- Every activated employee has one `user_profiles` row linked to the same employee.
- Every manager has direct reports; no report points across tenants.
- Every non-null `company_id` belongs to the employee owner's tenant.
- Work emails are unique where account linking requires uniqueness.
- Every successful employee identifier passes the current MOL, IBAN, Emirates ID, visa, passport, routing-code, email, and phone validators.
- Invalid identifier cases are isolated negative payloads and are not reused by successful payroll or SIF cases.

### Status coverage

- Every status listed in `docs/migration/phase-0/FEATURE_AND_CONTRACT_MATRIX.md` has a fixture or an explicit negative payload.
- Every admin, manager, and employee task category has source data.
- Every incident type and severity is represented.
- Training, certification, appraisal, document, expense, leave, advance, payroll, WPS, roster swap, correction, offboarding, and employment states are represented.

### Financial checks

- Canonical payroll golden values match exactly to two decimals.
- Payroll persisted round trip preserves leave deduction and WPS variable amount.
- SIF golden text, CRLF, EDR count, SCR count, and integer total match.
- Absence, attendance OT, roster OT, advance schedule, and gratuity golden values match.
- Payroll total equals the sum of non-excluded entry net pay.
- Payslip gross and net match the corresponding finalized entry.
- Expense reimbursement is marked paid only when its automatic payroll item was applied to a non-excluded employee.
- Advance balance changes exactly once for an idempotent repayment.

### Date and workflow checks

- Fake clock produces the documented 7, 14, 30, 60, and 90-day bands.
- Closed July attendance is payroll-ready; open August is not.
- Period close fails with unresolved items and succeeds after resolution.
- One-level and two-level leave approvals end in their expected states.
- Roster publish blocks on staffing or leave conflict until corrected or overridden.
- Completing all appraisal sections produces the 3.8 golden rating and `reviewed` state.
- Closing an incident fills closed date when absent.
- Completing all offboarding tasks permits checklist completion.

### File checks

- Safe files contain no personal metadata or executable content.
- Authorized users can create fresh signed URLs for their own files.
- Unauthorized users cannot list, sign, download, replace, or delete another tenant's object.
- Missing object metadata does not crash a list screen.
- Failed metadata creation cleans up a newly uploaded object where the current workflow promises cleanup.
- Oversize and disallowed-extension payloads fail before persistence.

### Isolation checks

- Run every negative test table row under the named authenticated user.
- Compare row counts and hashes before and after denied mutations.
- Test tenant isolation and branch isolation separately.
- Test manager relationships after reassignment, not only at initial seed state.
- Test direct API calls without relying on hidden frontend buttons.

### Idempotence and cleanup

- The committed fixture manifest contains one canonical key, deterministic UUID, and expected table count for every persisted scenario.
- Running the seed twice produces the same IDs and row counts.
- Notification deduplication leaves one row per dedup key.
- Repayment idempotence leaves one effective repayment per advance and payroll.
- Cleanup deletes only rows owned by the two listed admin IDs and only Storage objects under their fixture prefixes.
- Cleanup leaves unrelated local or shared test data untouched.
