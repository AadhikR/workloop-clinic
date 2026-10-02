# Part 15A golden cases

## Rules

The machine source is `integration-catalogue.json`. These 42 cases fix the acceptance boundary for
15B through 15H. A later part may add focused cases, but it may not weaken or remove one of these
without a recorded Phase 15 amendment.

Browser visibility alone never proves authorization. Any case that names denial requires an API
result at the protected boundary. Live cases use only synthetic identities, rows, and files.

## Cases

| ID | Area | Expected result | Owner |
| --- | --- | --- | --- |
| `15A-GC-001` | Shell | A signed-out root shows one sign-in path and no protected data. | 15B |
| `15A-GC-002` | Shell | A valid OIDC callback is consumed once, its URL state is cleared, and the server-derived role selects the home route. | 15B |
| `15A-GC-003` | Shell | Expired, inactive, missing, and unavailable account states fail closed without stale portal content. | 15B |
| `15A-GC-004` | Shell | Direct navigation to another role route produces a stable denial and makes no protected domain request. | 15B |
| `15A-GC-005` | Shell | Administrator branch selection uses only API-returned branches; staff cannot select a branch. | 15B |
| `15A-GC-006` | Shell | The architecture storage proof is absent from the portal shell while health and account checks remain available. | 15B |
| `15A-GC-007` | Administrator | Organization and people routes preserve selected-branch scope, idempotency, stale-write denial, and API errors. | 15C |
| `15A-GC-008` | Administrator | Leave routes preserve configuration, balance, request, attachment, approval, audit, and delegation contracts. | 15C |
| `15A-GC-009` | Administrator | Attendance and roster routes preserve source versions, validation, close rules, and conflict denial. | 15C |
| `15A-GC-010` | Administrator | Payroll, WPS, SIF, Nafis, expense, and advance actions use only current server contracts and exact decimal strings. | 15C |
| `15A-GC-011` | Administrator | Records, development, incidents, letters, and offboarding routes expose no private byte without backend authorization. | 15C |
| `15A-GC-012` | Administrator | Reports and exports use backend-produced output and never rebuild business files in the browser. | 15C |
| `15A-GC-013` | Manager | Home, profile, and team routes show only the manager identity and current direct reports. | 15D |
| `15A-GC-014` | Manager | Leave decisions cannot escape the server-derived report or delegation scope. | 15D |
| `15A-GC-015` | Manager | Expense decisions use the manager queue and cannot call administrator decisions. | 15D |
| `15A-GC-016` | Manager | Appraisal and development actions are limited to self and direct-report contracts. | 15D |
| `15A-GC-017` | Manager | Personal attendance, schedule, and request paths retain employee self scope. | 15D |
| `15A-GC-018` | Manager | Administrator-only routes and controls remain absent and return a stable denial when addressed directly. | 15D |
| `15A-GC-019` | Employee | Home and profile routes expose only the signed-in employee account and editable contact fields. | 15E |
| `15A-GC-020` | Employee | Leave requests, cancellations, calendars, balances, and attachments stay self-scoped. | 15E |
| `15A-GC-021` | Employee | Attendance corrections, schedules, colleagues, and swaps reveal no administrator data. | 15E |
| `15A-GC-022` | Employee | Payslip, expense, receipt, and advance routes deny another employee identifier. | 15E |
| `15A-GC-023` | Employee | Document, insurance, asset, evidence, CME, and appraisal routes remain self-scoped. | 15E |
| `15A-GC-024` | Employee | Unsupported administration actions remain absent and direct navigation returns a stable denial. | 15E |
| `15A-GC-025` | Product proof | All three role journeys use synthetic identities, rows, and files and clean them by exact identifier. | 15F |
| `15A-GC-026` | Security | Route hiding is never accepted as authorization proof; the API denies cross-role, cross-tenant, cross-branch, and cross-employee requests. | 15F |
| `15A-GC-027` | Files | Every upload and download flow proves type, size, authorization, failure, and cleanup without exposing a credential or object key. | 15F |
| `15A-GC-028` | Accessibility | Keyboard order, visible focus, skip navigation, landmarks, names, status updates, dialogs, contrast, zoom, and reduced motion pass on every route group. | 15F |
| `15A-GC-029` | Performance | A locked production build meets recorded initial transfer, route transfer, interaction, and API timing budgets on the local acceptance profile. | 15F |
| `15A-GC-030` | Regression | Existing frontend units, backend tests, one schema head, restart state, safe logs, and the Phase 14H review still pass. | 15F |
| `15A-GC-031` | Promotion | The reviewed commit, frontend build, public settings, backend image, Keycloak image, app spec, Terraform, and schema head are bound before promotion. | 15G |
| `15A-GC-032` | Promotion | Automatic deployment stays disabled and the provider default address is the only public address. | 15G |
| `15A-GC-033` | Live product | Synthetic administrator, manager, employee, file, denial, logout, expiry, and safe-log journeys pass on DigitalOcean. | 15G |
| `15A-GC-034` | Live performance | Recorded provider measurements meet the approved availability, transfer, interaction, and API timing thresholds. | 15G |
| `15A-GC-035` | Recovery | Portal artifact recovery, restart, and rollback retain database, signing-key, object, route, and authorization behavior. | 15G |
| `15A-GC-036` | Resources | The existing project, network, archive, and protected local volume remain preserved and live work stays within the existing USD 15 cap. | 15G |
| `15A-GC-037` | Review | Every inventory item, client contract, route, file flow, gap, and golden case has current evidence and one owner. | 15H |
| `15A-GC-038` | Review | The independent review finds no invented endpoint, client-only authorization, unowned gap, or new backend business capability. | 15H |
| `15A-GC-039` | Review | The closing local gate and all routed GitHub jobs pass from one clean reviewed commit. | 15H |
| `15A-GC-040` | Review | The closing live review confirms promoted artifact identity, role journeys, recovery evidence, performance record, and exact synthetic cleanup. | 15H |
| `15A-GC-041` | Review | One Alembic head remains `e8a1c3f5b7d9`; no schema, grant, RLS, Keycloak, credential, or preserved-resource change enters Phase 15 without explicit catalogue ownership. | 15H |
| `15A-GC-042` | Signoff | 15H records the complete phase result, requests one owner signoff, and does not start another phase. | 15H |

## Evidence use

15B through 15E use focused frontend and route tests plus the affected current client tests. 15F adds
the local runtime, browser, denial, accessibility, performance, restart, log, and cleanup evidence.
15G adds reviewed provider, recovery, and live performance records. 15H traces each case to the
current evidence and repeats the closing gates.
