# Part 10A attendance and roster contract

## Common authority and HTTP rules

PostgreSQL is authoritative. FastAPI derives company, selected branch, actor, employee, UAE
business date, attendance date, payroll period, state, and calculated values. Dates use
`YYYY-MM-DD`, periods use `YYYY-MM`, instants use UTC RFC 3339 milliseconds, hours and money are
decimal strings with two places, and optional response fields are present as `null`.

Administrator lists are selected-branch only. Employee and manager lists are self-only. Managers
receive no team attendance or roster-management authority. Lists use `{data, page}` with `limit`
1 through 100, default 50, an opaque cursor, deterministic sort, and `Cache-Control: no-store`.
Missing and inaccessible rows share `404 resource_not_found`. Mutations reject unknown fields.
Protected commands require `Idempotency-Key`; changed-payload reuse fails with
`409 idempotency_conflict`. Stale state fails with `409 state_conflict` and changes nothing.

## Time, dates, and shift selection

`Asia/Dubai` is the only attendance timezone. A business date is the Dubai calendar date containing
the trusted instant. There is no browser-offset input and no daylight-saving adjustment.

For an employee and attendance date, a published roster row takes precedence when one exists.
Otherwise the effective assignment with `effectiveFrom <= date <= effectiveTo`, treating null
`effectiveTo` as infinity, applies. Overlap is invalid rather than resolved by row order. If neither
exists, branch attendance settings define a flexible default day with no scheduled clock boundary.

A fixed shift belongs to its start-date and ends on that date. An overnight shift belongs to the
Dubai date on which it starts and ends on the next date. Its event window begins four hours before
the scheduled start and ends four hours after scheduled end. An event that matches two candidate
windows is a blocker and is never assigned by nearest-time guess. Split shifts contain two ordered,
nonoverlapping intervals on one date. Break minutes are subtracted once from the combined interval
duration. Flexible shifts have no scheduled time; `minHoursFlexible` is the presence threshold.

Settings working and weekend day arrays are nonempty, duplicate-free, disjoint, and together cover
exactly `Sun` through `Sat`. The default is working `Sun` through `Thu` and weekend `Fri`, `Sat`.

## Part 10B administrator routes

| Method and path | Contract |
| --- | --- |
| `GET /api/v1/attendance-settings` | Return the selected branch row. The secret is omitted and `biometricApiKeyConfigured` is boolean. |
| `PUT /api/v1/attendance-settings` | Replace public settings under `expectedUpdatedAt`; omitted `biometricApiKey` preserves it, a nonempty value replaces it, and null clears it only while biometric API is disabled. |
| `GET /api/v1/shifts` | Filters `active`, `shiftType`, `shiftCategory`, and `search`; sort `name,id`. |
| `POST /api/v1/shifts` | Create one selected-branch template. |
| `PATCH /api/v1/shifts/{shiftId}` | Change an unreferenced template under `expectedUpdatedAt`. A referenced template permits only soft deactivation. |
| `POST /api/v1/shifts/{shiftId}/deactivate` | Set `isActive=false` under `expectedUpdatedAt`; reject an active or future assignment. Historical references remain. |
| `GET /api/v1/shift-assignments` | Required `employeeId`; optional `effectiveOn`; sort `effectiveFrom desc,id`. |
| `POST /api/v1/shift-assignments` | Assign an active same-branch employee to an active shift from a current or future date, under an expected-current snapshot. |

Settings bounds are: `defaultHoursPerDay` 0.25 through 24.00; grace values 0 through 240 minutes;
`maxDailyOvertimeHours` 0.00 through 12.00; nonnegative late amount within `NUMERIC(12,2)`;
regularisation monthly limit 0 through 31 and window 0 through 365 days. A configured biometric key
is 16 through 512 characters and is never returned, logged, audited, or copied into an error.

Shift names are trimmed 1 through 80 characters. Codes are null or 1 through 12 uppercase letters,
digits, or hyphens. Color is `#RRGGBB`. Hours use scale two. Break and grace values are 0 through
240 minutes; expected hours are 0.25 through 24.00; minimum staff is 0 through 999. Fixed shifts
require distinct same-day start and end, `isOvernight=false`, and no split or flexible fields.
Overnight shifts require end not later than start, `isOvernight=true`, category `night`, and no split
or flexible fields. Split shifts require four ordered same-day times, category `split`, and no
overnight or flexible fields. Flexible shifts require null time fields, category `flexible`,
`isOvernight=false`, zero break, and `0.25 <= minHoursFlexible <= expectedHours`.

Assignment creation locks the employee, shift, and all that employee's assignments in ID order. It
compares `expectedCurrentAssignmentId` and `expectedCurrentAssignmentUpdatedAt`, where both are null
only when no assignment is effective on the new start date. It ends a covering prior assignment on
the preceding date. An omitted end date becomes the day before the next future assignment, or null
when none exists. A same-start replacement, past start, inactive employee, inactive shift,
cross-branch row, or overlap fails. There is no assignment update or delete route.

Staff can read only safe active shift fields embedded in later personal projections: ID, name, code,
type, category, display color, start and end times, split times, overnight flag, expected hours, and
minimum flexible hours. They cannot list settings or assignment history.

## Event ingestion and provenance

Public event methods are `MANUAL` and `BIOMETRIC`. Legacy `BIOMETRIC_API` normalizes to
`BIOMETRIC` during synthetic conversion and is never persisted. `WEB`, `MOBILE`, and
`EMPLOYEE_APP` are historical values only and have no Phase 10 writer.

Manual events record the trusted administrator actor. Biometric events record an import batch,
source row number, normalized badge, device name, and SHA-256 fingerprint; they have no human event
actor. Accepted CSV columns are `badgeNo,eventType,eventTime` with optional `deviceName`. Extra
columns, blank required values, formulas, and NUL bytes fail validation. A batch contains at most
5,000 data rows and 2 MiB of UTF-8 CSV. `eventTime` must be RFC 3339 with an explicit offset, within
31 days before through one day after the trusted business date.

The server sorts valid candidates by instant, badge, event type, and source row. A fingerprint is
the SHA-256 of company, branch, normalized badge, event type, UTC instant, and normalized device.
Exact fingerprints are duplicates. In addition, the same employee, event type, method, and UTC
minute is a duplicate. A batch is atomic for accepted rows: malformed or unknown badges are
reported per row, valid unique rows insert, and an infrastructure or concurrent failure rolls back
the whole batch. A late event in an open period is accepted and marks affected derivation stale. A
closed-period event is retained in a new append-only amendment batch but never changes the closed
version without the period-amendment command.

## Attendance calculation

Calculation snapshots settings, chosen shift, nonsuperseded events, employment state, approved
leave, holiday, salary, Ramadan range, and source row IDs. Status precedence is:

1. `ON_LEAVE` when approved leave covers the date and there is no work.
2. `PUBLIC_HOLIDAY` when the date is a holiday and there is no work.
3. `WEEKEND` when the date is a configured weekend and there is no work.
4. `MISSING_CLOCK_OUT` when a valid clock-in lacks a later clock-out.
5. `PRESENT_REMOTE` for an approved WFH resolution with valid hours.
6. `UNEXPLAINED_ABSENCE` for a required workday without events, leave, or resolution.
7. `HALF_DAY` when hours are at least half but less than the required threshold.
8. `LATE` when late minutes remain after grace.
9. `EARLY_DEPARTURE` when early minutes remain after grace and the record is not late.
10. `OVERTIME` when otherwise present and overtime hours are positive.
11. `PRESENT` otherwise.

Worked holidays and weekends are present records with rest-day evidence; they are not labelled as
nonworking. A record may carry late, early, overtime, holiday, and rest-day facts even though only
one display status is stored. `ABSENT` remains a historical import value; new calculation emits
`UNEXPLAINED_ABSENCE` until resolution. Three consecutive required workdays with unresolved absence
set the consecutive flag; weekends, holidays, and approved leave do not break or count the run.

Expected hours are the shift value, reduced to six hours on a Phase 8 Ramadan date, never below
zero. A flexible record is present at its minimum threshold and half-day at half that threshold.
Clock pairs use alternating in/out evidence in time order. An unmatched out, ambiguous window, or
negative interval is a blocker. Total hours are the sum of pairs less the configured break, floored
at zero. Lateness and early departure compare the first in and last out with scheduled bounds and
grace. A split shift additionally requires evidence for both intervals; missing either interval is
a close blocker.

## Decimals and payroll authority

All arithmetic uses `Decimal` and PostgreSQL `NUMERIC`. Inputs reject exponent notation, nonfinite
values, excess scale, excess precision, and out-of-range values. Intermediate rates are not rounded.
Persisted hours and money use `ROUND_HALF_UP` to two places at the final component boundary.

- Daily absence rate is monthly basic divided by 30; absence deduction is rate times unauthorized
  days, rounded once.
- Hourly attendance rate is monthly basic times 12 divided by 52 divided by 48.
- Standard overtime is hourly rate times 1.25 times hours.
- Night overtime is hourly rate times 1.50 times hours when any approved work is between 21:00 and
  04:00 Dubai time.
- Rest-day overtime without substitute is hourly rate times 1.50 times hours. With a substitute it
  is recorded with amount `0.00`.
- Per-minute late deduction is configured amount times chargeable minutes. Per-occurrence deduction
  is the configured amount once. Each daily result rounds once; payroll sums rounded daily values.

Salary is snapshotted at daily calculation and rechecked at period close. Close stores the exact
salary source version used by each record. A changed salary before close requires recalculation;
after close it cannot rewrite that source.

Attendance is the only authority for worked overtime created from clock evidence. Roster overtime
is a distinct, administrator-approved scheduled-duty adjustment based on actual roster hours and is
allowed only when its evidence declares `attendanceOverlapHours=0.00`. Any overlap or shared source
event makes the roster payroll projection not ready.

## Corrections, close, and amendments

Regularisation transitions are `pending -> approved|rejected`; decisions are final. Approval appends
superseding evidence, marks affected raw events superseded, recalculates from a new source snapshot,
and appends audit in one transaction. Absence resolution and overtime approval are locked,
versioned, and audited. A period cannot close with missing calculations, missing clock-outs,
unresolved absences, ambiguous events, pending corrections, required unapproved overtime, or stale
source snapshots.

Close freezes one attendance source version. Ordinary events, recalculation, decisions, and edits
are forbidden against it. A permitted amendment is append-only: an administrator supplies a
reason, the service creates an amendment version linked to the prior version, applies only new or
superseding evidence, revalidates the complete period, and closes the new version. The prior version
and any payroll snapshot remain immutable. Payroll using an older version becomes stale and must be
recalled and refreshed; generated payroll is never changed by Phase 10.

## Roster lifecycle

A roster month is `draft -> published`. Draft rows may be replaced or deleted under expected
versions. Publication locks the month, rows, employees, shifts, leave sources, staffing rules, and
overrides in deterministic ID order. It rejects ineligible employees, inactive shifts, approved or
manager-approved leave conflicts, duplicate employee dates, missing days required by the submitted
set, and unoverridden staffing shortfalls.

Disabled branch staffing enforcement produces no report and no blocker. Enabled rules use the most
recent effective rule whose inclusive range contains the date. Counts group eligible roster rows by
employee department, date, and shift category. An override is immutable, has a closed rule code,
reason, actor, month, and exact violation digest, and applies only to that digest.

Publication creates a month entity with `status=published`, `publishedAt`, actor, monotonically
increasing version, canonical affected-row digest, and `sourceVersion`. Rows join that publication
version; their published scheduling fields never update directly. Republishing creates a new version
from a new draft and preserves old membership. A payroll snapshot of an earlier version becomes
stale but remains immutable.

Actual hours do not update published scheduling rows. Administrators append actual-hours evidence
for a publication row with source, reason, actor, and expected publication version. Overtime from
actual hours requires a separate approval row with the roster formula, overlap declaration, and
actor. Each accepted evidence change creates a new month source version. The exact source remains
available for payroll replay.

Swaps operate only on two rows in one published source version. The colleague selector returns only
active same-branch employees with a published row on the target date and exposes ID, display name,
job title, date, and safe shift fields. Approval locks the request and both rows, rechecks leave,
staffing, employment, branch, and payroll state, then creates a new publication version containing
the swapped membership. If a generated payroll references the current version, approval fails.

## Phase 9 projections

The attendance projection is internal, read-only, and keyed by company, branch, and period. It is
ready only for a closed version with `payrollReady=true`. It returns `sourceVersion`, `closedAt`, and
employee rows ordered by employee ID. Each row contains absence days and amount, late minutes and
amount, approved standard and rest-day overtime hours and amount, and sorted source row IDs.

The roster projection is internal, read-only, and keyed by company, branch, and period. It is ready
only for a published month version whose actual-hours and overtime evidence is complete. It returns
`sourceVersion`, `publishedAt`, and employee rows ordered by employee ID with actual hours, approved
overtime hours and amount, and sorted source row IDs. `sourceVersion` is `sha256:` plus the lowercase
SHA-256 of canonical JSON containing scope, period, version number, affected row IDs, evidence IDs,
and their immutable values. Missing, provisional, mixed-branch, duplicate, changed, or overlapping
input returns `409 payroll_input_not_ready`.
