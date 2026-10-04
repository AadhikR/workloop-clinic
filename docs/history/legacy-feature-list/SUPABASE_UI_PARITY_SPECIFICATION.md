# Supabase-era portal UI parity specification

## Document status

This is a documentation-only implementation contract. It records how the final Supabase-era
Workloop portals presented and operated each module so that the current application can reproduce
that experience while retaining the current FastAPI, PostgreSQL, and Keycloak architecture.

The reference implementation is the `main` branch at commit
`b079236dad08ccf8e151b733f072a8dd297aae5d`. The functional companion is
[`SUPABASE_PORTAL_MODULE_FEATURE_CATALOGUE.md`](./SUPABASE_PORTAL_MODULE_FEATURE_CATALOGUE.md).
That catalogue defines what each module did. This specification defines how the same modules must
be arranged, styled, and operated.

This document does not claim that the current application already has parity. It defines the target
for later implementation and testing. No current application code is changed by this document.

## Scope and exclusions

In scope:

- Administrator, manager, and employee portal shells.
- Every module listed in the companion feature catalogue.
- Page hierarchy, labels, tabs, cards, forms, tables, drawers, modals, filters, status treatments,
  loading states, empty states, validation, responsive behavior, and print behavior.
- In-app notifications and task queues.
- The visible historical workflows, adapted to the current server APIs and authorization model.

Out of scope for this parity pass:

- Biometric integration of every kind, including device polling, webhooks, device mappings,
  biometric punch files, and biometric CSV import.
- Outbound email notifications. The product must not add email delivery as part of this work.
- Reintroducing Supabase, browser-side data authority, or historical access-control weaknesses.
- Features that appeared only in the retired PDF and were not present in the reference source.

Password recovery and identity-provider messages belong to Keycloak operations. They are not part
of the product email-notification scope in this document.

## Meaning of exact parity

Exact parity means that a user who knew the reference portals should recognize the same information
order, controls, status language, spacing, visual weight, and interaction sequence in the current
application.

The implementation must preserve:

1. The module names and their order within each portal.
2. The distinction between page headers, summary cards, work tables, detail panels, and dialogs.
3. The historical color, type, radius, shadow, spacing, hover, focus, disabled, loading, empty,
   success, warning, and error treatments.
4. The historical tab and filter structure within each module.
5. The historical mobile change from desktop sidebar navigation to bottom navigation for employee
   and manager portals.
6. The historical workflows described in the companion catalogue, except for the two exclusions.

Exact parity does not mean copying the old data layer. All reads and writes must use the current
server routes. Keycloak remains the identity authority, and the server remains responsible for
role, tenant, branch, employee, and record-level authorization. Historical browser-side filtering
is presentation evidence only.

## Shared visual system

### Color tokens

| Token | Reference value | Required use |
| --- | --- | --- |
| Primary | `#2563EB` | Primary actions, active controls, focus, links |
| Primary dark | `#1D4ED8` | Gradient end, emphasized active state |
| Primary tint | `rgba(37,99,235,0.10)` | Selected rows, soft information backgrounds |
| Secondary | `#38BDF8` | Cyan-blue supporting accents |
| Accent | `#06B6D4` | Active gradients and highlight details |
| Accent tint | `rgba(6,182,212,0.10)` | Soft supporting backgrounds |
| Success | `#16A34A` | Approved, complete, valid, paid |
| Danger | `#DC2626` | Rejected, invalid, expired, destructive |
| Warning | `#D97706` | Pending attention, due soon, unresolved |
| Page background | `#EEF2F7` | All authenticated portal pages |
| Sidebar | `#08122e` | Administrator, manager, and employee desktop navigation |
| Main text | `#0F172A` | Titles and primary values |
| Muted text | Slate scale | Labels, help, metadata, secondary values |
| Surface | `#FFFFFF` | Cards, headers, dialogs, table bodies |

The page background includes fixed blue and cyan radial gradients at low opacity. It must not be a
flat gray canvas. Semantic status colors must remain consistent across modules.

### Typography

- Use `-apple-system`, `BlinkMacSystemFont`, `SF Pro Display`, `SF Pro Text`, `Segoe UI`, and a
  sans-serif fallback in that order.
- Default text is 14px with a 1.5 line height and antialiasing.
- Page and card headings use tight negative letter spacing where present in the reference.
- Table headings use 11.5px, semibold uppercase text with increased letter spacing.
- Supporting metadata generally uses 10px to 12.5px slate text.
- Monetary and KPI values use stronger weight and tabular alignment where the table requires it.
- SIF previews use `SF Mono`, `Fira Code`, or a monospace fallback.

### Authenticated page canvas

- Administrator desktop sidebar: fixed, 240px wide, 64px when collapsed, and 12px from the viewport
  edges. The surface is navy with a 22px radius, cyan-tinted border, and layered dark shadow.
- Employee and manager desktop sidebar: fixed, 228px wide, 64px when collapsed, with the same
  12px gap and navy treatment.
- The desktop page header is sticky, white, rounded to 18px, and offset 12px from the top and sides.
  It contains the module title, short description or context, and page-level actions.
- Administrator body padding is 20px 12px 28px. Employee and manager body padding is 22px 26px on
  desktop and 16px 18px on mobile.
- Sidebar collapse state persists locally. The active item is marked by a moving blue-to-cyan pill,
  10px radius, and a blue shadow. The pill moves with a spring-like 0.40-second transition.
- Navigation icons remain visible in collapsed mode. Labels disappear without changing the target
  order.

### Cards and summary blocks

- Standard administrator cards use a white surface, 22px radius, one-pixel translucent slate
  border, and a low slate shadow.
- Card headers use 18px 22px padding. Card bodies use 22px padding.
- Employee and manager cards use a 16px radius, 14px 18px header padding, 16px 18px body padding,
  and 10px bottom spacing.
- KPI grids use `auto-fit` columns with a 160px minimum and a 16px gap.
- KPI cards use 20px padding, a 16px radius, an uppercase 11.5px label, and a 28px bold value.
- Clickable cards must show a clear hover response without changing the information layout.

### Buttons and links

- Standard buttons use 8px 16px padding, a 12px radius, and 13.5px medium text.
- Primary buttons use a royal-blue gradient. Success and danger actions use green and red gradients.
- Outline buttons use a white or pale-slate surface. Ghost actions remain transparent.
- Hover lifts the control by 1px and increases the shadow. Disabled controls use 0.45 opacity and
  do not lift.
- Icon-only buttons require a visible title or accessible label and the same focus treatment as
  text buttons.
- Destructive actions require confirmation when the historical flow used confirmation.

### Forms

- Use one-, two-, or three-column form grids with 18px gaps. At 768px or below, multi-column forms
  collapse to one column.
- Inputs, selects, and textareas use 9px 13px padding, a 12px radius, pale-slate background, and
  13.5px text.
- Focus changes the control to white, adds a primary border, and adds a 3px translucent blue ring.
- Labels sit directly above their controls. Required markers, help text, and field errors remain
  next to the affected field.
- Checkboxes use the primary blue accent.
- File inputs use a 2px dashed slate drop zone, 16px radius, 36px padding, and a blue hover or drag
  state.
- Saving, saved, validation, and failure feedback must appear near the edited content. A successful
  auto-save uses a green pill rather than a blocking dialog.

### Tables and lists

- Tables use white rows and a slate `#E2E8F0` header.
- Cells use about 11px 14px padding. Rows gain a subtle blue tint on hover.
- Wide operational tables remain inside their card and scroll horizontally instead of widening the
  whole page.
- Status appears in compact pills. Blue means active or changed, green means successful or ready,
  amber means pending or warning, red means rejected or blocked, and gray means inactive or
  excluded.
- Row actions stay at the right edge and preserve a stable order.
- Expanded details appear directly under the selected row when the historical module used an
  expandable list. Complex payroll details use a right-side drawer.

### Tabs, alerts, and dialogs

- Tabs sit on a bottom border. Each tab uses 10px 18px padding and 13.5px text. The active tab is
  primary blue with a 2px underline.
- Alerts use 13px 17px padding, a 12px radius, and a semantic tinted background and border.
- Modal backdrops use `rgba(8,18,46,0.50)`. Dialogs are white with a 22px radius and a maximum
  height of 90vh.
- Use the historical dialog widths: 600px for forms, 900px for broad reviews, and 1100px for dense
  operational work.
- Keep the title and close control in a fixed dialog header when the body scrolls. Put the primary
  action last in the footer.

### Loading, empty, and error states

- A page load centers a 32px circular spinner in at least 300px of vertical space. The spinner uses
  a slate track and primary-blue leading edge.
- Empty states center an icon, title, explanation, and optional action with 56px 24px padding. The
  icon is low opacity, the title is 16px semibold, and the explanation is 13.5px muted text.
- Inline validation stays close to the failing field or record. Page failures use a semantic alert
  with a retry action when retry is possible.
- The offline banner remains visible when connectivity is lost. The application must not imply that
  writes are queued when they are not.
- The error boundary must provide a controlled recovery screen instead of leaving a blank portal.

### Accessibility, motion, and print

- Preserve the skip-to-main link, screen-reader-only helper class, visible keyboard focus, and
  accessible labels.
- `:focus-visible` uses a 2px primary outline with 2px offset.
- Honor reduced-motion preferences by reducing animation and transition duration to near zero.
- Calendar print mode hides unrelated page content and prints only the calendar region.
- Color is never the only status signal. Keep the text status and icon where the reference used it.

## Shared portal modules

### Landing and authentication

Historical presentation:

- The marketing landing page uses a full-height navy hero with animated blue, cyan, and indigo line
  ribbons. The fixed 56px navigation changes from translucent dark to translucent white after the
  hero scroll threshold.
- The hero centers a small audience pill, an oversized responsive heading, a short description,
  and rounded primary and secondary calls to action.
- Product sections alternate white and `#F5F5F7` surfaces, with a five-to-two image and copy grid,
  16px image corners, and large soft shadows.
- The historical sign-in chooser uses a translucent white 420px card, 22px radius, 32px 28px
  padding, a blurred background, and three full-width choices for company creation, administrator
  sign-in, and employee or manager sign-in.
- Sign-in forms use icon-prefixed fields, show or hide password controls, inline error and success
  alerts, and centered spinner states after successful submission.

Current parity requirement:

- Preserve the public visual language if the current application exposes the marketing route.
- Preserve portal-selection clarity, but let Keycloak own authentication and password recovery.
- Do not recreate Supabase registration or password-reset logic in the browser.

### Portal shells and navigation

Historical presentation:

- Administrator navigation contains Dashboard, Clinical Dashboard, Company Settings, Employees,
  Departments, Requests, Payroll Module, Advances, Expenses, Leave, Attendance, Assets, Training,
  Appraisals, Roster, Incidents, Reports, and Tasks in that order.
- Manager navigation contains Home, Leave Queue, Expense Queue, Appraisals, My Leave, Schedule, My
  Attendance, Payslips, Advances, Expenses, Training, Documents, Requests, Profile, and Tasks.
- Employee navigation contains Home, Leave, Schedule, Attendance, Payslips, Advances, Expenses,
  Training, Appraisals, Documents, Requests, Profile, and Tasks.
- Tasks is separated from the preceding navigation items by a divider.
- Manager and employee sidebars show company name, portal name, signed-in employee identity, job
  title, notification bell, and sign-out action.
- At widths below 768px, the employee and manager sidebar disappears and a fixed 62px white bottom
  bar appears. The active icon and label are primary blue.

Current parity requirement:

- Use the same module names, ordering, active treatment, collapse behavior, identity block, and
  desktop/mobile navigation switch.
- Render the full historical mobile module list in the same order. Any later accessibility change
  to that navigation requires a recorded parity exception.

### Branch switcher

Historical presentation:

- The administrator brand block contains a full-width branch button beneath the Workloop name.
- The button uses an 11px label, building icon, ellipsis for long names, optional branch-count pill,
  and rotating chevron.
- The dropdown uses `#0d1b3e`, an 8px radius, cyan-tinted borders, and a dark floating shadow.
- The active branch has a blue tint and cyan check. Other branches expose a delete icon when more
  than one branch exists. Add Branch is the final cyan action.
- Branch creation opens a form dialog. A successful create changes context and opens Company
  Settings for configuration.

Current parity requirement:

- Preserve this compact sidebar interaction and its branch labels.
- All context changes and branch mutations must be validated and authorized by the current server.

### In-app notifications

Historical presentation:

- A bell sits in the portal identity area and shows an unread count badge.
- Opening the bell reveals a compact overlay list with title, message, time, unread emphasis, and
  mark-read behavior.
- Selecting a notification navigates to the related module where a route is available.

Current parity requirement:

- Preserve the bell, unread count, overlay, read state, and module navigation.
- Keep notifications inside the application. Do not add outbound email delivery.

### Tasks

Historical presentation:

- A page header introduces the work queue. Summary cards show the number of actionable items by
  urgency or category.
- Filters narrow the list by category and state. Each row or card shows the task type, subject,
  supporting date or age, status, and an action that opens the owning module.
- Empty queues use the shared centered empty state.

Current parity requirement:

- Preserve role-specific task composition and navigation. Task visibility must come from server
  authorization, not client-only filtering.

### Error and offline handling

Historical presentation:

- A connectivity banner appears above portal content when offline.
- Recoverable failures show an alert and retry. Unexpected render failures show a controlled error
  boundary screen.

Current parity requirement:

- Reproduce both states and their visual treatment. Never show a successful state for an
  unconfirmed write.

## Administrator portal modules

### Dashboard

Page structure:

- Sticky page header, setup checklist when configuration is incomplete, KPI card grid, alerts and
  warnings, payroll trend and recent-run content, then compliance and action panels.
- Clickable summary cards route to their owning modules. Expiry and compliance panels keep their
  supporting names, dates, counts, and severity visible.
- The Nafis action opens a modal over the dashboard instead of replacing the page.

Controls and states:

- Show loading before any KPI totals. Distinguish zero values from unavailable data.
- WPS deadlines, pending payroll approval, document expiry, credential expiry, probation,
  contracts, HR requests, and appraisals use warning or danger treatment according to urgency.
- Nafis summary and stored snapshots use the historical calculation labels and AED formatting.

Exact parity requirement:

- Match the historical card order, warning hierarchy, drill-through actions, trend presentation,
  and modal flow described above and in the companion catalogue.

### Clinical Dashboard

Page structure:

- Use a 12-card KPI grid for active staff, credential compliance, licences expiring in 90 days,
  expired credentials, today's roster coverage, probation, new joiners, birthdays, staff on leave,
  pending leave, staff on duty, and staffing-ratio failures.
- Place the department headcount table below the KPI grid.
- Expanding a KPI reveals an in-page detail panel. It does not navigate away.

Controls and states:

- Credential states are valid, expiring, expired, and missing, each with a text label and semantic
  color.
- Empty drill-downs show a positive empty state. Staffing failures remain visually prominent.

Exact parity requirement:

- Preserve the twelve-card order, local expansion behavior, department table, and credential and
  staffing status vocabulary.

### Company Settings

Page structure:

- Group employer identity, branch details, payment defaults, jurisdiction, feature switches, WPS
  reference, and insurance into separate cards rather than one long unbroken form.
- Place the logo preview and upload controls with company identity fields.
- Show insurance policies in a table or stacked mobile cards with renewal state and row actions.

Controls and states:

- Use two-column forms for common fields and full-width rows for address, notes, and record-format
  guidance.
- Keep mainland or Free Zone selection and conditional free-zone choice together.
- Preserve switches for Nafis and staffing rules. Do not show a biometric switch in this parity
  scope.
- When the routing code changes, present the historical option to cascade it to draft payroll runs.
- Logo upload shows preview, replace, remove, progress, validation, and failure feedback.

Exact parity requirement:

- Match the historical section order, field labels, logo handling, renewal warnings, policy dialog,
  and WPS reference presentation, minus biometric configuration.

### Employees

Page structure:

- Start with summary counts and view controls for active employees, document expiry, and terminated
  employees.
- Follow with search, import and export actions, Add Employee, and the employee table.
- Employee create and edit opens a broad dialog with Personal, Job and Contract, Salary and Bank,
  UAE Compliance, Documents, Insurance, and Contracts tabs. Child-record tabs appear only after the
  employee exists.
- Job history, offboarding, and end-of-service work open dedicated detail views or dialogs from the
  selected employee.

Controls and states:

- Search matches name, MOL ID, and department. Expiry and terminated views keep their counts and
  selected state visible.
- The employee table shows identity, employee number, job or department, employment state, key
  expiry warning, and stable right-aligned actions.
- CSV import uses template download, file selection or drop, validation summary, row errors, import
  confirmation, and completion feedback.
- Form validation stays beside UAE phone, email, IBAN, Emirates ID, MOL ID, routing code, identity
  document, and date fields.
- Documents use upload progress, metadata forms, signed-open actions, review status pills, reject
  reason, and confirmation before delete.
- Contracts use a dated lifecycle list with renew, convert, non-renew, and print actions.
- Offboarding uses a checklist with completion controls, visa-cancellation state, printable letters,
  and a clearly separated end-of-service calculation.

Exact parity requirement:

- Preserve the view tabs, toolbar order, modal tab order, field grouping, lifecycle actions,
  document-review presentation, and printable outputs.

### Departments

Page structure:

- Header actions create a department, expand all, collapse all, and reload employee data.
- Use tabs or adjacent cards for the department list, organization chart, and staffing rules.
- The organization chart nests departments and employees, with color markers and collapse controls.

Controls and states:

- Department forms include parent, color, description, sort order, and head.
- Staffing rules pair department and shift category with minimum headcount and effective dates.
- Delete actions require confirmation and show server rejection when dependent records prevent
  deletion.

Exact parity requirement:

- Match the collapsible hierarchy, department color use, employee and manager labels, and staffing
  rule editor.

### Requests

Page structure:

- Place Pending, Completed, Rejected, and All filters above a single request table.
- Rows show employee, request type, purpose or detail preview, request date, current state, and
  actions.
- Expanding a row shows full custom-request details or the standard letter context.

Controls and states:

- Complete and Reject are visible only when valid for the current state. Reject opens a reason
  prompt or dialog and displays the reason afterward.
- Completed standard letters expose Print. Custom requests do not pretend to have a standard
  letter template.

Exact parity requirement:

- Preserve filters, combined queue, state pills, completion and rejection flow, and print layout.

### Payroll Module

Page structure:

- The run list provides period, state, payment date, employee count, totals, and actions to create,
  repeat, open, or delete a run.
- The editor places run metadata and lifecycle actions above an automatic-review card and a wide
  employee-entry table.
- The table remains inside its card, uses a fixed layout with an approximately 1180px minimum
  width, and scrolls horizontally.
- Complex employee detail opens in a right-side drawer up to 480px wide. Validation opens in a
  dialog up to 680px wide. SIF preview opens in a dark monospaced dialog.

Controls and states:

- The editor toolbar contains search, review-state filter, save-state pill, Save Draft or Retry
  Save, CSV import, and lifecycle actions.
- Save-state pills distinguish saved, unsaved, saving, and failed. Row pills distinguish ready,
  changed, needs review, and excluded.
- Editable money fields use compact 13px inputs with an 8px radius and the shared blue focus ring.
- Automatic items expose Apply, Applied, and Undo in compact 28px controls. Apply All is available
  when multiple valid items are pending.
- The validation summary is green when ready and red when blocked. Error and warning rows are
  clickable and take the user to the affected run entry.
- The drawer shows employee identity, issues, earnings sections, deduction sections, totals, and a
  blue-gradient net-pay result.
- Submitted, approved, or generated runs visibly lock editing.
- Approval, rejection, recall, generation, employee payment result, payslip download, ZIP download,
  SIF download, and corrected SIF actions remain distinct.
- SIF preview uses navy, blue EDR lines, amber bold SCR lines, and preserves whitespace.

Responsive behavior:

- At narrower desktop widths, reduce table cell padding and text to 11.5px before using horizontal
  scroll.
- At 640px or below, stack the automatic-review card and make the payroll drawer full width.

Exact parity requirement:

- Match the run lifecycle, table density, toolbar, save feedback, review workflow, drawer,
  validation dialog, automatic-adjustment controls, and SIF presentation. Preserve current
  server-side approval rules even where they are stricter than the historical interface.

### Advances

Page structure:

- Use status filters for pending, active, settled, and cancelled records above the advances table.
- Create and edit actions open forms for amount, disbursement, start month, reason, term, and monthly
  deduction.
- Expanded rows show repayment progress, payroll-linked history, and the calculated schedule.

Controls and states:

- Summary progress uses three equal columns on desktop and one column at 640px or below.
- Schedule items use a responsive grid with at least 115px per installment. Paid installments are
  green; the next installment is blue with a soft focus ring.
- Approve, reject, cancel, reschedule, and settle actions use clear state-dependent availability.

Exact parity requirement:

- Preserve the filters, expandable repayment view, status language, installment coloring, and
  action sequence.

### Expenses

Page structure:

- Put state filters and refresh or export actions above the claims table.
- Rows show employee, category, amount, expense date, description, receipt link, status, and
  actions. Long descriptions truncate in the row and remain available in detail.

Controls and states:

- Use distinct pills for pending, manager approved, manager rejected, approved, paid, and rejected.
- Approval and final approval are separate actions. Rejection requires a reason. Delete requires
  confirmation and appears only for allowed states.
- Receipt opens in a safe new view without losing queue position.

Exact parity requirement:

- Preserve the state filters, two-stage approval language, amount formatting, receipt access,
  rejection reason, and payroll reimbursement state.

### Leave

Page structure:

- Use Overview, Requests, Calendar, Balances, Leave Types, Settings, Holidays, and Delegates as the
  working areas represented in the historical screen.
- The overview starts with staff-on-leave and pending-approval summaries.
- Requests use filters and expandable details. Balances use a table with progress bars. Calendar
  uses a seven-column month grid and exposes Print.

Controls and states:

- Request actions include submit for an employee, approve, reject with reason, and cancel when
  allowed. Manager-approved and manager-rejected remain visible intermediate states.
- The request form calculates days before submission and reveals type-specific fields only when
  required. Required evidence uses the shared drop zone.
- Calendar cells have an 80px desktop minimum height, 50px on mobile. Weekends are slate, today is
  blue-tinted, holidays are amber-tinted, and events use compact colored labels.
- Balance bars use blue-to-cyan fill, amber warning, and red danger variants.
- Ramadan configuration displays in a navy banner with white text.
- Leave type, holiday, policy, and delegate forms use dialogs with confirmation for destructive
  actions.

Exact parity requirement:

- Preserve the work-area order, day calculation feedback, expandable requests, calendar coloring,
  print view, balance bars, policy grouping, and conditional request fields.

### Attendance

Page structure:

- Include Dashboard, Manual Entry, Records, Unexplained Absences, Overtime, Corrections, Monthly
  Summary, Settings, and Period Close.
- Do not include a biometric tab, biometric file controls, badge mapping, or device integration.
- Dashboard cards show current-month attendance counts and today's late arrivals.

Controls and states:

- Manual Entry collects employee, event type, event time, source note, and reason.
- Records and Monthly Summary use month selection, dense tables, and CSV export.
- Unexplained Absences supports unauthorized and work-from-home resolution.
- Overtime and Corrections use actionable queues with approve or reject controls and clear reasons.
- Settings groups attendance rules and shift templates. Period Close shows blocking issues before
  confirmation.

Exact parity requirement:

- Match every non-biometric tab, table, filter, export, queue, dialog, and status treatment from the
  historical module. The removed biometric area must not leave an empty tab or unexplained gap.

### Assets

Page structure:

- Start with Total, Available, Assigned, and Under Repair summary cards.
- Use Asset Register and Assignment History tabs.
- Place state filter, Add Asset, and reload actions above the register table.

Controls and states:

- Asset forms group identity, category, make and model, serial number, purchase details, state, and
  notes.
- Assign and Return open focused dialogs with employee, date, condition, and notes.
- State pills cover available, assigned, under repair, retired, and lost.
- An attempted delete with an active assignment shows a clear blocking error.

Exact parity requirement:

- Preserve summary cards, tab split, state filters, assignment and return flows, and retained
  history.

### Training

Page structure:

- Use Training, Certifications, and CME tabs.
- Each tab starts with relevant summary or filter controls, then a table or card list.
- Create and edit forms open in dialogs. File handling stays within the relevant training or
  certification form.

Controls and states:

- Training state pills distinguish planned, in progress, completed, and cancelled.
- Certification filters distinguish active, due soon, and expired. Review states distinguish
  pending review, verified, and rejected.
- Upload permits a file or external URL, shows progress and validation, and provides an open action
  through a server-authorized file URL.
- CME compares required and achieved hours per employee and year with clear totals.

Exact parity requirement:

- Preserve the three-tab structure, filters, forms, review actions, expiry treatment, file access,
  and CME comparison.

### Appraisals

Page structure:

- Show appraisal cycles first, with review period, state, and summary counts.
- Opening a cycle reveals employee appraisals and cycle-level actions.
- Opening an appraisal reveals fixed weighted sections, one-to-five ratings, comments, reviewer
  summary, development plan, and calculated overall rating.

Controls and states:

- Cycle actions create, edit, generate missing records, calibrate, close, and delete when allowed.
- Ratings use an immediately understandable selected state and keep the numeric value visible.
- Reviewed, pending, calibrated, and closed states use stable pills and locked controls where
  editing is no longer allowed.

Exact parity requirement:

- Preserve cycle-first navigation, summary cards, section order, rating controls, one-decimal
  weighted result, confirmation, and close behavior.

### Roster

Page structure:

- Put shift-template management and the monthly roster in the same module.
- The monthly view has previous and next controls, month label, department filter, publication
  state, export, validate, and publish actions.
- The grid keeps employees on rows and dates on columns, with daily coverage totals and a pending
  swap queue in its own panel.

Controls and states:

- Shift templates show short code, name, category, start and end, expected hours, color, and rest
  day state.
- Roster cells show assigned shift color and code, leave conflict warning, planned or actual hours,
  compensatory time where present, and a professional-licence status badge.
- Staffing failures show the affected department, shift category, date, required count, and actual
  count. Publish stays blocked unless a valid override reason of at least ten characters is entered.
- Publication confirmation and swap approval or rejection use dialogs. Employee notification from
  publication remains in-app only.

Exact parity requirement:

- Preserve the dense month grid, shift colors, coverage summaries, department filter, warning and
  override flow, licence badges, publication state, CSV export, and swap queue.

### Incidents

Page structure:

- Use filters and Add Incident above the incident table or card list.
- The record form groups event facts, people, immediate action, investigation, corrective action,
  closure, and notes.

Controls and states:

- State pills are open, investigating, and closed. Severity pills are low, moderate, high, and
  critical.
- Closing without a date fills the date but still shows the resolved value for review.
- Edit and delete remain right-aligned actions. Delete requires confirmation.

Exact parity requirement:

- Preserve form grouping, filters, severity hierarchy, state progression, and closure details.

### Reports

Page structure:

- Present the thirteen report families as a clear selector or card grid before the active report.
- The selected report shows its own filter row, summary cards, detail table, and export actions.
- Do not force every report into one universal table if the historical report used separate joiner
  and leaver sections or compliance summaries.

Controls and states:

- Filters use the relevant period, date range, year, expiry threshold, department, or organization
  fields.
- CSV remains available for every major report. PDF remains available where the historical module
  provided it. Turnover keeps separate joiner and leaver CSV exports.
- Disabled feature areas, such as Nafis or staffing reports, remain hidden or clearly unavailable
  according to company configuration.

Exact parity requirement:

- Preserve all thirteen report families, report-specific filters, summary measures, column order,
  empty states, and export choices.

### Tasks

Use the shared task presentation. Administrator categories include leave, expenses, advances, HR
requests, document review, certification review, attendance corrections, shift swaps, payroll
approval, expiries, probation, contracts, offboarding, and appraisal review. Selecting a task opens
the matching administrator module and preserves enough context to find the affected record.

## Manager portal modules

Manager pages use the employee and manager shell described above. Personal modules must match their
employee equivalents. Team queues add manager-only actions without exposing administrator controls.

### Home

- Use a greeting and employment summary at the top.
- Follow with personal KPI cards for annual leave, pending leave, today's attendance, and latest
  payslip. Cards for leave, attendance, and payslip navigate to their modules.
- Show current assigned assets and identity-document expiry warnings below the KPIs.
- Preserve the personal scope. Do not add team headcount or team payroll cards.

### Leave Queue

- Header actions include Refresh and a Show Processed or Hide Processed control.
- Queue items show employee, leave type, dates, days, reason, available balance, probation state,
  warnings, and an expand control.
- Approve acts directly after confirmation. Reject opens a mandatory reason flow.
- One-level approval displays Approved. Two-level approval displays Manager Approved and indicates
  that HR review remains. Manager rejection displays Manager Rejected.
- Delegated items use the same presentation and make the delegated context visible.

### Expense Queue

- Use Pending, Manager Approved, Manager Rejected, and All filters.
- Rows show employee, category, amount, date, description, receipt, state, and actions.
- Approve moves the claim to Manager Approved for HR review. Reject requires and displays a reason.
- Keep Refresh in the page action area and preserve the user's selected filter.

### Appraisals

- Use Team and My Appraisals tabs.
- Team rows identify employee and cycle and expand to section ratings and comments.
- Each section uses a one-to-five control and comment field. Save follows confirmation and shows
  success or validation feedback.
- The parent becomes Reviewed only when every section has a rating.
- My Appraisals is read-only and uses the same result presentation as the employee module.

### My Leave

- Reuse the employee Leave page exactly, including Requests, Balances, Calendar, request dialog,
  calculated days, conditional fields, evidence upload, validation, and pending cancellation.

### Schedule

- Reuse the employee Schedule page exactly. Only the manager's own published shifts and swap
  requests appear.

### My Attendance

- Reuse the employee Attendance page exactly. The manager has no team clock-entry or attendance
  administration controls here.

### Payslips

- Reuse the employee Payslips page exactly and show only the manager's own issued payslips.

### Advances

- Reuse the employee Advances page exactly. Do not add an approval queue for team advances.

### Expenses

- Reuse the employee Expenses page exactly. Team claims remain in Expense Queue.

### Training

- Use Team and My Training as the first-level switch.
- Team uses Training and Certifications tabs, direct-report filters, create and edit dialogs, file
  or URL controls, and signed open actions.
- My Training uses the employee-style summary cards and personal training and certification lists.
- Preserve expiry states and review states. File access must use current server-authorized URLs.

### Documents

- Reuse the employee Documents page for the manager's own records. Do not add team document review.

### Requests

- Reuse the employee Requests page for the manager's own HR letters and custom requests. Do not add
  a manager letter-approval queue.

### Profile

- Reuse the employee Profile presentation. Only personal email, UAE phone, emergency contact name,
  and emergency contact phone are editable.

### Tasks

- Use the shared task presentation. Combine personal tasks with authorized team leave, team expense,
  appraisal, and certification work. Selecting an item opens the correct personal module or team
  queue.

## Employee portal modules

### Home

Page structure and parity requirement:

- Start with a time-based greeting, employee name, job or employment context, and active status.
- Use cards for annual-leave balance and pending count, today's attendance and punch times, latest
  payslip period and net amount, and current assigned assets.
- Leave, attendance, and payslip cards act as shortcuts.
- Put visa, passport, Emirates ID, and labour-card warnings in a separate expiry panel with dates
  and semantic urgency.
- Preserve the compact employee-card spacing and single-column mobile flow.

### Leave

Page structure and parity requirement:

- Use Requests, Balances, and Calendar tabs.
- Requests list current and past entries with state pills and expandable dates, day count, reason,
  approval details, and rejection reason.
- Balances show each type, allowance, used, pending, remaining, and a colored progress bar.
- Calendar shows approved leave in the shared seven-column month layout.
- New Request opens the historical form with full or half day, live day calculation, type-specific
  conditional fields, evidence upload when required, inline validation, and submit feedback.
- A pending own request exposes Cancel after confirmation.

### Schedule

Page structure and parity requirement:

- Show a month header with previous and next controls and a calendar or roster list containing only
  published shifts.
- Each shift uses the configured color and shows name, code where used, start and end time, and
  expected hours.
- A month without published shifts uses the shared empty state.
- Request Swap opens a form for colleague, own date, target date, and reason. Show success or failure
  without clearing useful context.

### Attendance

Page structure and parity requirement:

- Start with today's status card showing clock-in, clock-out, total hours, lateness, early departure,
  and overtime.
- Follow with recent history in a compact table or mobile cards.
- Correction Request opens a form for date, corrected clock-in, corrected clock-out, and reason and
  then shows the request state.
- Keep the module read-only apart from correction requests. Do not show Clock In, Clock Out, or any
  biometric controls.

### Payslips

Page structure and parity requirement:

- List issued payslips newest first with period, payment date, net pay, state, expand, and PDF
  download actions.
- Expanded content groups fixed earnings, variable earnings, named allowances, deductions, gross,
  and net. Use right alignment and AED formatting for money.
- The PDF action uses the payroll snapshot and company branding and shows a clear generating or
  failure state.

### Advances

Page structure and parity requirement:

- Put the request form or Request Advance action above pending, active, and history sections.
- The form collects amount and reason and explains the one-basic-salary cap before submission.
- Active cards show approved amount, monthly deduction, outstanding balance, progress summary, and
  installment schedule using the shared green paid and blue next states.
- Pending records expose Withdraw after confirmation. Rejected, cancelled, and settled records keep
  their reasons or completion context.

### Expenses

Page structure and parity requirement:

- The claim form collects category, amount, expense date, description, and receipt URL.
- Keep inline validation for positive amount, AED 100,000 maximum, and future dates.
- Group or filter claims by pending, manager approved, manager rejected, approved, paid, and
  rejected. Show the manager or HR rejection reason with the affected record.
- Pending and rejected own claims expose Delete after confirmation.

### Training

Page structure and parity requirement:

- Start with summary cards for total training, completed training, and certifications.
- Use Training and Certifications tabs with personal history beneath each.
- Training create and edit captures type, provider, dates, duration, state, score, pass state, CME,
  notes, and certificate.
- Certification submit and edit captures issuer, number, dates, notes, and file or URL. New
  submissions display Pending Review.
- Expiry status and signed file-open actions match the administrator module's semantic treatment.

### Appraisals

Page structure and parity requirement:

- List the employee's appraisal cycles with period, state, and overall rating where available.
- Expanded results show every section rating and comment, overall rating, reviewer comments,
  development plan, and review dates.
- Keep the module read-only. Do not add self-rating controls as part of parity.

### Documents

Page structure and parity requirement:

- Show personal documents in a list with type, number where present, expiry, review state, rejection
  reason, and signed open action.
- Submit Document opens a form for type, number, expiry, notes, and file.
- The drop zone accepts PDF, JPG, and PNG up to 10 MB and shows selected file, upload progress,
  validation, success, and failure.
- Preserve Pending Review, Verified, and Rejected pills and the full rejection reason.

### Requests

Page structure and parity requirement:

- Separate standard HR letters from custom requests in the submission area while keeping one
  history list.
- Standard letters collect type and purpose. Custom requests collect subject and details with the
  historical length rules.
- History uses Pending, Ready, and Rejected states and shows rejection reason.
- Ready standard letters expose Print using employee and company details.

### Profile

Page structure and parity requirement:

- Group read-only data into Personal, Job, Salary, Bank, UAE Compliance, and Employment sections.
- Show identity-document expiry state next to its date.
- Edit mode enables only personal email, UAE phone, emergency contact name, and emergency contact
  phone. Save uses inline validation and visible progress, success, or failure.
- Keep Sign Out as a separate final action, not beside Save.

### Tasks

- Use the shared task presentation for document and certification expiry, rejected submissions,
  missing clock-out, pending leave, pending advances, pending expenses, and pending HR requests.
- Selecting a task opens the related employee module and leaves the user at a useful record or view.

## Responsive contract

The following behavior applies to every module unless a module section states otherwise:

- At 768px or below, forms become one column and the administrator sidebar moves off canvas.
- Employee and manager desktop sidebars are hidden below 768px and replaced by the 62px bottom
  navigation.
- Tables remain readable through horizontal scrolling. Do not shrink controls below usable sizes.
- Toolbars wrap into multiple rows while keeping the primary action easy to find.
- Dialogs use the available viewport width with 16px side clearance and a scrollable body.
- Drawers use the full viewport width at 640px or below.
- KPI grids collapse naturally without changing card order.
- Calendar columns keep a minimum usable width and may scroll when seven columns cannot fit.
- Print layouts exclude navigation, actions, and unrelated page content.

## Later implementation acceptance checklist

### Visual acceptance

- [ ] Shared colors, typography, radii, shadows, and spacing match this specification.
- [ ] Desktop shell widths, offsets, collapse states, and active navigation pill match the reference.
- [ ] Employee and manager mobile bottom navigation matches the reference.
- [ ] Every module preserves its historical page hierarchy, control order, and status language.
- [ ] Loading, empty, warning, error, success, disabled, and locked states are all represented.
- [ ] Dense tables, payroll drawer, dialogs, calendars, and print layouts remain usable at target
  widths.

### Interaction acceptance

- [ ] Filters preserve their selection through refreshes that do not change module context.
- [ ] Create, edit, approve, reject, cancel, delete, publish, close, print, download, and export
  actions show progress and a confirmed result.
- [ ] Rejection and override reasons remain visible after submission.
- [ ] Expandable rows, tabs, drawers, and dialogs follow the historical sequence.
- [ ] Keyboard focus, accessible labels, reduced motion, and skip navigation are verified.

### Functional acceptance

- [ ] Every in-scope feature in the companion catalogue is reachable in the correct portal.
- [ ] Biometric integration and biometric CSV import are absent.
- [ ] Outbound email notifications are absent. In-app notifications still work.
- [ ] Employee and manager personal views cannot access another employee's records.
- [ ] Manager queues contain only authorized direct-report or delegated work.
- [ ] Administrator data is tenant and branch scoped by the server.
- [ ] Current approval, audit, transaction, and file-authorization controls are not weakened to mimic
  historical client behavior.

### Evidence required before declaring parity

- [ ] Desktop and mobile screenshots exist for every module and its main states.
- [ ] Screenshot comparison covers the reference information hierarchy, spacing, and styling.
- [ ] Automated tests cover role access, navigation order, status transitions, and excluded features.
- [ ] Manual checks cover keyboard use, overflow, dialogs, print views, downloads, and failure states.
- [ ] Any intentional difference is recorded with a security, accessibility, or current-platform
  reason and owner approval.

## Historical source index

Primary presentation sources:

- `src/index.css`
- `src/App.jsx`
- `src/components/AuthPage.jsx`
- `src/components/LandingPage.jsx`
- `src/components/ManagerShell.jsx`
- `src/components/employee/EmployeeShell.jsx`

Module sources are listed under every module in the companion feature catalogue. The reference code
contains both shared CSS classes and component-level inline styles. An implementation must review
both sources before declaring visual parity.
