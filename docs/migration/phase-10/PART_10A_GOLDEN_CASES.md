# Part 10A synthetic golden cases

## Fixed context

Use the Phase 0 clock `2026-08-27T08:00:00Z`, Dubai time `2026-08-27T12:00:00+04:00`.
H-DXB-002 has monthly basic AED 12,000. The standard shift is 08:00 through 17:00 with a
60-minute break, eight expected hours, and ten-minute arrival and departure grace.

## Configuration and assignment

| ID | Input | Exact result |
| --- | --- | --- |
| `CFG-01` | Working `Sun`-`Thu`, weekend `Fri`,`Sat` | Accepted; arrays cover seven unique days. |
| `CFG-02` | Working omits `Sun` | `422 validation_failed`; settings unchanged. |
| `CFG-03` | Biometric enabled with omitted key and no configured secret | `422 validation_failed`; no secret appears in response or log. |
| `CFG-04` | Fixed 08:00-17:00, break 60, expected 8.00 | Accepted. |
| `CFG-05` | Overnight 20:00-08:00, break 60, expected 11.00, category night | Accepted and owned by the start date. |
| `CFG-06` | Split 08:00-12:00 and 16:00-20:00, expected 8.00 | Accepted. |
| `CFG-07` | Flexible expected 8.00, minimum 6.00, no times | Accepted. |
| `CFG-08` | Assign morning from 2026-09-01 over open prior assignment | Prior ends 2026-08-31; one new row begins 2026-09-01. |
| `CFG-09` | Concurrent assignments with the same expected current snapshot | One commits; one returns `409 state_conflict`; no overlap exists. |
| `CFG-10` | Deactivate a shift used by a future assignment | `409 retained_shift`; all rows unchanged. |

## Events and attendance

| ID | Input | Exact result |
| --- | --- | --- |
| `EVT-01` | Manual `CLOCK_IN` at 08:00+04 and `CLOCK_OUT` at 17:00+04 | Two append-only `MANUAL` events with trusted actor. |
| `EVT-02` | CSV `BIOMETRIC_API` fixture | Normalizes to `BIOMETRIC`; the legacy name is not stored. |
| `EVT-03` | Same normalized badge, type, instant, and device twice | First inserts; second is skipped as the same fingerprint. |
| `EVT-04` | Same employee, type, method, and UTC minute with a different device | Second is skipped by minute tolerance. |
| `EVT-05` | Unknown badge among two valid rows | Valid rows insert; unknown row reports `unknown_badge`; batch evidence records all three outcomes. |
| `EVT-06` | 5,001 rows or more than 2 MiB | `413 request_too_large`; no event or batch row commits. |
| `EVT-07` | Overnight in 2026-08-26 20:02+04, out 2026-08-27 08:01+04 | Both events belong to attendance date 2026-08-26. |
| `EVT-08` | Late event for an open calculated date | Event appends; record source becomes stale until recalculated. |
| `EVT-09` | Late event for a closed date | Amendment evidence appends; closed version and payroll projection do not change. |

| ID | Evidence | Exact status and values |
| --- | --- | --- |
| `ATT-01` | 08:00-17:00 normal day | `PRESENT`; total `8.00`, late `0`, early `0`. |
| `ATT-02` | 08:16-17:00 | `LATE`; chargeable late `6` minutes after grace. |
| `ATT-03` | 08:00-16:44 | `EARLY_DEPARTURE`; chargeable early `6` minutes. |
| `ATT-04` | Four worked hours | `HALF_DAY`; total `4.00`. |
| `ATT-05` | Clock-in only | `MISSING_CLOCK_OUT`; close blocker. |
| `ATT-06` | Required day, no evidence | `UNEXPLAINED_ABSENCE`; close blocker until resolution. |
| `ATT-07` | Approved leave, no work | `ON_LEAVE`; no attendance deduction. |
| `ATT-08` | Holiday, no work | `PUBLIC_HOLIDAY`. |
| `ATT-09` | Friday, no work | `WEEKEND`. |
| `ATT-10` | Approved WFH with eight hours | `PRESENT_REMOTE`; total `8.00`. |
| `ATT-11` | Ramadan date, six worked hours | `PRESENT`; expected `6.00`. |
| `ATT-12` | Three consecutive required days unresolved | Third record sets the consecutive-absence flag; an intervening weekend does not count or break the run. |

## Money and close

For H-DXB-002, hourly attendance rate is `12000 * 12 / 52 / 48 = 57.6923076923...`.

| ID | Calculation | Exact persisted result |
| --- | --- | --- |
| `MNY-01` | One unauthorized absence: `12000 / 30 * 1` | AED `400.00`. |
| `MNY-02` | Two standard OT hours: hourly rate times `1.25 * 2` | AED `144.23`. |
| `MNY-03` | Two night OT hours: hourly rate times `1.50 * 2` | AED `173.08`. |
| `MNY-04` | Two rest-day OT hours without substitute | AED `173.08`. |
| `MNY-05` | Two rest-day OT hours with substitute | AED `0.00`. |
| `MNY-06` | Per-minute late amount `1.25`, six chargeable minutes | AED `7.50`. |
| `MNY-07` | Per-occurrence late amount `25.00` | AED `25.00`. |

| ID | Command | Exact result |
| --- | --- | --- |
| `CLS-01` | Close with complete fresh records | One closed version, `payrollReady=true`, stable source version, and one audit event. |
| `CLS-02` | Close with a missing clock-out, pending correction, or unresolved absence | `409 attendance_period_not_ready`; no close field changes. |
| `CLS-03` | Two close commands with distinct keys | One commits; the other returns the original closed result or a state conflict; one version exists. |
| `CLS-04` | Same idempotency key and changed payload | `409 idempotency_conflict`; source and audit unchanged. |
| `CLS-05` | Amend a closed period with a reason | New linked closed version; old version and any payroll snapshot remain unchanged. |

## Roster and swap

| ID | Input | Exact result |
| --- | --- | --- |
| `ROS-01` | Complete eligible draft without conflicts | Publication version 1, trusted `publishedAt`, affected-row digest, and source version. |
| `ROS-02` | Approved or manager-approved leave conflict | Publication blocked until draft changes or an exact immutable override applies. |
| `ROS-03` | Nursing morning minimum 2 with one eligible row | Publication blocked with count 1, required 2. |
| `ROS-04` | Same rows in a branch with staffing disabled | No staffing report and no staffing blocker. |
| `ROS-05` | Stale row during publication | `409 state_conflict`; no row becomes published. |
| `ROS-06` | Actual 12.00, planned 8.00, approved four hours, no attendance overlap | Roster overtime uses `12000 / 208 * 1.25 * 4 = 288.4615...`, persisted AED `288.46`. |
| `ROS-07` | Same overtime source also appears in attendance | Roster projection returns `409 payroll_input_not_ready`. |
| `ROS-08` | Actual-hours evidence after publication | Scheduling row stays immutable; evidence appends and source version increments. |
| `ROS-09` | Swap two rows in current published version | New publication version changes exactly two memberships and one request state. |
| `ROS-10` | Swap after generated payroll references current version | `409 roster_version_frozen`; no request or membership change. |
| `ROS-11` | Concurrent approval of one swap | One commits; one replays or conflicts; exactly one successor version exists. |

## Phase 9 projection

| ID | Projection | Exact result |
| --- | --- | --- |
| `PAY10-01` | Closed attendance with one unauthorized day, 6 late minutes, two standard OT hours | Deduction `407.50`; OT `144.23`; sorted source IDs and deterministic source version. |
| `PAY10-02` | Open, stale, mixed-branch, or `payrollReady=false` attendance | `409 payroll_input_not_ready`. |
| `PAY10-03` | Published roster case `ROS-06` | Actual `12.00`, approved OT `4.00`, amount `288.46`, sorted source IDs. |
| `PAY10-04` | Missing actual hours, overlap, stale version, or draft roster | `409 payroll_input_not_ready`. |
| `PAY10-05` | Payroll snapshot version differs from current source | Approval and generation fail stale; recall and refresh are required. |
