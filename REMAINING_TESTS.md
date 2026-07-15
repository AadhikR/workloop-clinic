# Remaining Tests — Split into 2 Sessions

> Generated from `MANUAL_TEST_CHECKLIST.md` — all incomplete items from Days 11, 12, and 13.
> Dates and statuses are current as of 2026-07-13.

## SQL prerequisites (run once before Session A)

```
sql/039_shifts_read_policy.sql
sql/040_training_manager_policies.sql
```
Then run: `GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;`

---

| Session | Scope | Portal(s) | Est. checks |
|---------|-------|-----------|-------------|
| A | Manager remaining + Employee Auth + Employee E-1–E-7 + Deferred admin items | Manager → Admin → Employee | ~35 |
| B | Employee E-8–E-12 + Cross-portal X-1–X-8 + Edge cases EDGE-1–EDGE-11 | Employee + Admin + Manager (multi-window) | ~30 |

---

# SESSION A — Manager remaining · Employee Auth · Employee tabs E-1–E-7

> **Order**: Manager items first (sign in as Manager), then Admin deferred items (sign in as Admin), then Employee Auth + tabs (sign in as Employee).

---

## A1. Manager — Retests (bugs fixed, need retest)

> Sign in as the **Manager** (use the Employee/Manager sign-in form).

### M1-1 · Leave Queue — view pending requests (retest) - completed + feature added
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Leave Queue** tab. A direct report must have a pending leave request.
- **Steps**:
  1. Confirm you're on the **Leave Queue** tab
  2. Look at the pending requests list
- **Pass**: Pending leave requests from direct reports are shown. Each request displays: **employee name**, **leave type**, **start/end dates**, **days requested**, **reason**, and **status badge**.
- **Previous bug**: Manager not getting leave requests; employee showed 0 annual leaves remaining.
- **Fixed**: Added `sql/037_leave_manager_read.sql` with manager read policies on leave_requests, leave_balances, and leave_types.
- **Bug**: No warnings shown to manager (probation, insufficient balance, low balance)
  - **Fixed**: Enhanced `getLeaveQueueForManager()` in `leaveStorage.js` to populate `warnings` array on each request with probation status, insufficient balance, and low-balance-after-approval alerts. UI already renders warnings as amber chips in `ManagerLeaveQueue.jsx`.

---

### M3-1 · Appraisals — view team appraisals (retest) bug 
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Appraisals** tab. At least one direct report must be assigned to an appraisal cycle.
- **Steps**:
  1. Click the **Appraisals** tab
  2. Wait for data to load
- **Pass**: Direct reports' appraisals are listed with: **employee name**, **job title**, **cycle name**, **review period**, **status badge**, **overall rating** (stars). Layout is properly spaced (not cramped). The manager's own appraisal does NOT appear in this list.
- **Previous bug**: UI too cramped.
- **Fixed**: Restructured layout — increased card gaps, padding, font sizes, separated page header.
- **Bug**: remove save button after confirming appraisal , appraisals shouldnt be able to be changed 

---

### M3-2 · Appraisals — rate sections (retest) - completed
- **Profile**: Manager (on Appraisals tab)
- **Setup**: M3-1 done, at least one appraisal visible with status `pending` or `reviewed`
- **Steps**:
  1. Click on an appraisal row to **expand** it
  2. Rate the first section — 4 out of 5 stars
  3. Enter a comment: `Strong clinical skills demonstrated`
  4. Rate remaining sections (any 1-5)
  5. Click **Save**
- **Pass**: A finality warning dialog appears before saving. After confirming, success flash. Stars reflect chosen ratings. Overall rating re-computes as weighted average. Status changes to **reviewed**. Reloading retains ratings.
- **Previous bug**: Saved but status remained "pending".
- **Fixed**: `managerRateSection()` now updates parent appraisal status and overall_rating. Requires `sql/038_appraisal_manager_update.sql`.
- **Bug**:

---

### M3-3 · Appraisals — calibrated appraisal is locked (retest) bug mentioned above 
- **Profile**: Manager (on Appraisals tab)
- **Setup**: An appraisal with `status = 'calibrated'` must exist (admin calibrated it).
- **Steps**:
  1. Find an appraisal with a **Calibrated** badge (green)
  2. Try to expand it and interact with the star ratings
- **Pass**: Star rating inputs are **disabled/locked** — clicking does nothing. Read-only. My Appraisals merged as sub-view toggle within same tab.
- **Previous bug**: Separate My Appraisals tab, no finality warning.
- **Fixed**: Merged into sub-view toggle. Added finality warning before saving.
- **Bug**:

---

### M4-1 · Home — welcome card and overview (retest) -c 
- **Profile**: Manager (signed in)
- **Setup**: None
- **Steps**:
  1. Click the **Home** tab (should be **first** tab in sidebar)
  2. Check welcome card, leave balance stat cards, assets card, schedule preview
- **Pass**: Home is the first/default tab. Welcome card shows manager's name and company name. Sidebar is collapsible (PanelLeftClose/PanelLeftOpen toggle). All sections render without errors.
- **Previous bug**: Home was not the first tab; sidebar not collapsible.
- **Fixed**: Reordered TABS so Home is first. Added collapsible sidebar with localStorage persistence.
- **Bug**:

---

### M6-1 · Schedule — view published roster (retest) -c 
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Schedule** tab. Admin must have published a roster including the manager for this month.
- **Steps**:
  1. Click the **Schedule** tab
  2. Check the monthly view
- **Pass**: Published shifts are visible with date, shift name, colour pill, start/end times. If no published roster, an empty state message appears.
- **Previous bug**: Manager and employee couldn't see published roster.
- **Fixed**: Added fallback direct query in `getMyRoster()` when RPC returns empty.
- **Bug**:

---

## A2. Manager — Untested items

### M6-2 · Schedule — request a shift swap -c 
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Schedule** tab. At least one upcoming shift must be visible. At least one colleague must exist.
- **Steps**:
  1. Find a shift on an **upcoming** date (today or future)
  2. Click **Request Swap**
  3. The **SwapModal** opens
  4. Select a **Target Colleague** from the dropdown
  5. Select a **Target Date**
  6. Enter **Reason**: `Schedule conflict — manual test`
  7. Click **Submit**
- **Pass**: Success flash. The swap request is created. It will appear in the admin's Roster → Swaps tab for approval.
- **Bug**:

---

### M7-3 · Attendance — history and regularisation - completed (by design: RECENT_DAYS=30)
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Attendance** tab. The manager must have clocked in at least once (Day 11 M7-1/M7-2) so history data exists.
- **Steps**:
  1. Scroll down to the **Attendance History** table
  2. Check past days: in/out times, total hours, status chips (PRESENT, ABSENT, etc.)
  3. Find or click **Request Regularisation**
  4. Fill in: a past date, expected clock-in time (`09:00`), expected clock-out time (`17:00`), reason: `Forgot to clock in — manual test`
  5. Submit
- **Pass**: History table shows past records with correct formatting (DD/MM/YYYY dates). Regularisation form submits successfully. Success toast confirms submission.
- **Bug**:

---

### M11-1 · Training — Team Training view (manager CRUD)
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Training** tab. The manager must have at least one direct report. Run `sql/040_training_manager_policies.sql` if not done yet.
- **Steps**:
  1. Click the **Training** tab
  2. Confirm "Team Training" / "My Training" sub-view toggle buttons are visible at the top
  3. Confirm **Team Training** is the default view
  4. Check summary stat cards: Total · Completed · In Progress (training) + Total · Expired · Expiring Soon (certs)
  5. Check for expired/expiring certification warning banners
  6. Click **+ Add Training** → fill in: select a direct report, title `CPR Refresher`, type `Internal`, status `Planned`, today's dates → **Save**
  7. Confirm the new record appears in the list
  8. Click **pencil (Edit)** on the new record → change status to `Completed` → **Save**
  9. Confirm status badge updates to green **Completed**
  10. Click **trash (Delete)** → confirm deletion
  11. Switch to **Certifications** → click **+ Add Certification** → fill in: select a direct report, name `ACLS`, issuing body `AHA`, expiry 60 days from today → **Save**
  12. Confirm the cert appears with an amber expiry badge
- **Pass**: Manager can create, edit, and delete training records and certifications for direct reports. Manager's own records do NOT appear in team view. Stat cards update after each action.
- **Bug**: shoudl give notifivcation of exipry to admin and manager instasly 

---

### M11-2 · Training — My Training sub-view (with self-enrollment)
- **Profile**: Manager (on Training tab)
- **Setup**: M11-1 done. Admin should have added training records for the manager employee (Day 9).
- **Steps**:
  1. Click **"My Training"** toggle button
  2. View switches to the manager's own training records and certifications
  3. Confirm **Add Training** button is visible — manager can self-enroll
  4. Add a training record, edit it, verify persistence
  5. Certifications remain **read-only** (managed by HR)
  6. Click **"Team Training"** to switch back
- **Pass**: My Training shows manager's own records with Add/Edit for training. Certifications are read-only. Switching back restores interactive team view.
- **Bug**: let manager add their on training records as well
  - **Fixed**: Converted `MyTrainingView` from read-only to interactive — added `MyTrainingForm` inline form and `employeeSaveTrainingRecord` integration. Managers can now add/edit their own training records. Certifications remain HR-managed (read-only).

---

### M12-1 · My Appraisals — view own appraisal (read-only) - bug (fixed)
- **Profile**: Manager (signed in)
- **Setup**: Click the **Appraisals** tab. The manager must have been assigned to an appraisal cycle by admin.
- **Steps**:
  1. Click **"My Appraisals"** toggle button at the top
  2. Check appraisal rows: cycle name, review period, overall rating stars, status badge
  3. Click on a row to **expand** — check sections, star rating, comments
  4. Try clicking on star rating inputs
  5. Click **"Team Appraisals"** to switch back
- **Pass**: My Appraisals shows the manager's own reviews. Star inputs are **read-only**. Status badges correct. Switching back restores interactive team view.
- **Bug**: Review period not displayed (used non-existent `reviewPeriod` field)
  - **Fixed**: Changed `a.reviewPeriod` to `a.reviewFrom` + `a.reviewTo` in `ManagerAppraisals.jsx` My Appraisals view, matching the team view format.

---

### M13-1 · Documents — view and upload -c 
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Documents** tab (FolderOpen icon)
- **Steps**:
  1. Click the **Documents** tab
  2. Check existing documents with status badges
  3. Check clinical credentials show cyan "Clinical" badge
  4. Find the **Upload Document** form
  5. Select **Document Type** from grouped dropdown
  6. Enter **Document Number**: `DOC-MGR-001`
  7. Set **Expiry Date**: 6 months from today
  8. Enter **Notes**: `Manager test upload`
  9. Click drop-zone to choose a file → click **Submit**
- **Pass**: Upload succeeds — new row with "Pending Review" badge and "Self-submitted" label.
- **Bug**:

---

### M14-1 · Requests — submit a letter request -c 
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Requests** tab
- **Steps**:
  1. Click the **Requests** tab
  2. Select **Letter Type**: "Salary Certificate — Bank"
  3. Enter **Purpose**: `Bank mortgage application — manager test`
  4. Click **Submit Request**
- **Pass**: Success toast. Form resets. Request appears in My Requests table with Pending Review status.
- **Bug**:

---

### M14-2 · Requests — view request history -c 
- **Profile**: Manager (on Requests tab)
- **Setup**: M14-1 done
- **Steps**:
  1. Check the **My Requests** table
  2. Verify columns: Letter Type, Purpose, Requested date (DD/MM/YYYY), Status
  3. Check status badges
- **Pass**: Table shows correct data. Date format DD/MM/YYYY. Badges render correctly.
- **Bug**:

---

### M15-1 · Profile — view and edit , can only change phone email etc , none of the real employment information can be changed 
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Profile** tab (last tab)
- **Steps**:
  1. Click the **Profile** tab
  2. Verify profile loads: name, job title, department, start date, phone, emergency contact, bank details
  3. All fields **read-only**
  4. Click **Edit** → change phone to `+971 55 999 8888` → click **Save**
  5. Verify toast and updated value
  6. Click **Edit** again → change something → click **Cancel**
- **Pass**: Read-only mode works. Edit persists. Cancel discards.
- **Bug**:

---

### MN-1 · Notification bell — visibility and interaction - completed (already implemented in ManagerShell)
- **Profile**: Manager (signed in on any tab)
- **Setup**: Leave approval from M1-2 should have generated notifications.
- **Steps**:
  1. Find the **bell icon** in the sidebar
  2. If red badge visible, note the count
  3. Click the bell → panel opens
  4. Click a notification to mark as read
  5. Click bell again to close
- **Pass**: Bell visible and clickable. Panel opens smoothly. Notifications show with emoji icons. Click marks read (badge decrements). Panel closes on second click.
- **Bug**:

---

## A3. Deferred Admin items

> Sign out of Manager, sign in as **Admin**.

### DOC-4 · Verify a pending document -c 
- **Profile**: Admin
- **Setup**: The manager must have uploaded a document via their portal (M13-1 above).
- **Steps**:
  1. Sign in as **Admin**
  2. Go to **Employees** → open the manager's record → **Documents** tab
  3. Find the self-submitted document ("Pending Review" status, "Self-submitted" label)
  4. Click the **✓** (verify) button
- **Pass**: Status badge changes to **Verified**. "Self-submitted" label remains.
- **Bug**:

---

### DOC-5 · Reject a pending document -c 
- **Profile**: Admin
- **Setup**: A second self-submitted document must exist (upload another from manager or employee portal if needed).
- **Steps**:
  1. Find the second self-submitted document
  2. Click the **✗** (reject) button
  3. Enter a rejection reason
  4. Confirm
- **Pass**: Status badge changes to **Rejected**, rejection reason visible on the row.
- **Bug**:

---

### PORTAL-1 · Portal Role dropdown -c 
- **Profile**: Admin
- **Setup**: An employee must have completed self-registration (EA-1 below). Their `authUserId` is now set.
- **Steps**:
  1. Go to **Employees** → open the registered employee's record → **Job & Contract** tab
  2. Find the **Portal Role** dropdown (only appears when `employee.authUserId` is set)
  3. Change the role (e.g. Employee → Manager or vice versa)
- **Pass**: Dropdown appears. Change takes effect immediately (direct RPC call). If changed to Manager, next sign-in loads ManagerShell.
- **Note**: Do this AFTER Employee Auth (EA-1) is done.
- **Bug**:

---

## A4. Employee Auth

> Sign out of Admin, switch to **Employee** sign-in.

### EA-1 · First-time employee registration -c 
- **Profile**: Employee (not yet registered)
- **Setup**: Sign out. An employee must exist in admin portal with a valid `work_email`.
- **Steps**:
  1. Go to `http://localhost:5173`
  2. Find the **"Sign in as Employee / Manager"** form
  3. Click **"Register as Employee"**
  4. Enter the email matching the employee's `work_email`
  5. Enter a password and confirm
  6. Click **Register**
- **Pass**: Green success banner. Form switches to sign-in mode. Employee does NOT auto-login.
- **Bug**:

---

### EA-2 · Sign in as employee -c 
- **Profile**: Employee (registered from EA-1)
- **Setup**: EA-1 done
- **Steps**:
  1. Enter email and password in the Employee/Manager form
  2. Click **Sign in**
- **Pass**: Lands on **EmployeeShell** with **Home** tab active. Sidebar shows employee's **name** (bold) and **job title** — NOT email. Notification bell visible.
- **Bug**:

---

### EA-3 · Employee sign-out -c 
- **Profile**: Employee (signed in)
- **Setup**: EA-2 done
- **Steps**:
  1. Click **Sign Out**
- **Pass**: Returns to login page. No console errors.
- **Note**: Sign back in for the remaining tests.
- **Bug**:

---

## A5. Employee tabs E-1 through E-7

> Sign back in as the **Employee**.

### E1-1 · Home — welcome card and overview -c 
- **Profile**: Employee (signed in)
- **Steps**:
  1. Confirm **Home** tab is active
  2. Check welcome card, leave balance stats, assets card, schedule preview
- **Pass**: Welcome card shows employee name and company name. All sections render — empty sections show empty states, not crashes.
- **Bug**:

---

### E2-1 · Leave — view balances and apply - leave balances not updating (fixed)
- **Profile**: Employee (signed in)
- **Setup**: Switch to **Leave** tab
- **Steps**:
  1. Check leave balances per type
  2. If on probation, check amber banner with restricted types
  3. Click **Apply** → inline form (NOT modal)
  4. Select **Annual Leave**, set dates next week (2 days), reason: `Personal travel — employee test`
  5. Click **Submit**
- **Pass**: Success toast. Request appears in history with **Pending** badge. Balance adjusts.
- **Bug**: Leave balance not updating after employee submits request
  - **Fixed**: `EmpLeave.jsx` `handleSubmit` now updates local balance state (pendingDays +, remaining -) after successful submission, matching the existing pattern used in `handleCancel`. Admin recalculation on `loadAll` already worked correctly.

---

### E2-2 · Leave — validation and cancel -c (completed)
- **Profile**: Employee (on Leave tab)
- **Setup**: E2-1 done
- **Steps**:
  1. Apply → set End Date before Start Date → Submit → validation error
  2. Find pending request from E2-1 → click **Cancel**
- **Pass**: Validation blocks. Cancel changes status to **Cancelled**, balance restored.
- **Bug**:

---

### E3-1 · Schedule — view published roster and request swap -c 
- **Profile**: Employee (signed in)
- **Setup**: Switch to **Schedule** tab. Published roster must include this employee.
- **Steps**:
  1. Check monthly view — shifts with date, name, colour, times
  2. Click **Request Swap** on an upcoming shift → SwapModal
  3. Select colleague, target date, reason: `Schedule conflict — employee test` → Submit
- **Pass**: Shifts visible. Swap submits successfully. Empty state if no roster.
- **Bug**:

---

### E4-1 · Attendance — clock in, clock out, and regularisation
- **Profile**: Employee (signed in)
- **Setup**: Switch to **Attendance** tab. Must NOT have clocked in today.
- **Steps**:
  1. Click **Clock In** → optimistic switch to Clock Out
  2. Click **Clock Out** → total hours shown. Clock In stays **disabled** (cannot clock in again)
  3. Check history table: dates (DD/MM/YYYY), times, hours, status chips
  4. **Request Regularisation**: past date, 09:00–17:00, reason → Submit
- **Pass**: Clock in/out works. Can't re-clock-in. History correct. Regularisation submits.
- **Bug**:

---

### E5-1 · Payslips — view and download -c 
- **Profile**: Employee (signed in)
- **Setup**: Switch to **Payslips** tab. Payslips must exist from Day 5 payroll.
- **Steps**:
  1. Check payslip list: period, gross, deductions, net pay
  2. Check WPS status badge
  3. Click **Download** (PDF) on one
- **Pass**: List loads. PDF downloads with company header and salary breakdown.
- **Bug**:

---

### E6-1 · Advances — view and request -c 
- **Profile**: Employee (signed in)
- **Setup**: Switch to **Advances** tab
- **Steps**:
  1. Check active advances (progress bar at correct %, not 5% for new ones)
  2. Check pending advances (amber badges)
  3. Request: Amount `2000`, Reason: `Emergency medical expense — employee test` → Submit
- **Pass**: New advance with **Pending** / "Awaiting Approval" badge. Panels properly padded.
- **Bug**:

---

### E7-1 · Expenses — view and submit claim -c 
- **Profile**: Employee (signed in)
- **Setup**: Switch to **Expenses** tab
- **Steps**:
  1. Check expense history with status badges
  2. Submit: Category `meals`, Amount `120`, Date today, Description `Working lunch — employee test` → Submit
- **Pass**: New claim with **Pending** badge. Panels properly padded.
- **Bug**:

---

---

# SESSION B — Employee tabs E-8–E-12 · Cross-portal flows · Edge cases

> **Before you start**: Session A must be complete — employee account registered, E-1 through E-7 tested.
> Have **three browser windows** ready: Employee, Manager, Admin.

---

## B1. Employee tabs E-8 through E-12

> Sign in as the **Employee**.

### E8-1 · Training — summary cards and training records -c , add training button too cramped space it out some more 
- **Profile**: Employee (signed in)
- **Setup**: Switch to **Training** tab. Training records should exist from admin (Day 9) or manager (Session A M11-1).
- **Steps**:
  1. Check summary stat cards: Total Trainings, Completed, Certifications, Active Certs
  2. Check expired/expiring cert alert cards (red/amber)
  3. Check training records: title, type badge, date range, duration, score/passed
  4. Check "View Certificate" link opens in new tab (if URL provided)
- **Pass**: Stats correct. Alerts show when relevant. Records display properly.
- **Bug**: Add Training button too cramped
  - **Fixed**: Increased button padding to `8px 16px`, added `gap: 16` to header flex, added `whiteSpace: nowrap` and explicit `gap: 6` for icon alignment in `EmpTraining.jsx`.

---

### E8-2 · Training — employee self-enrollment -c 
- **Profile**: Employee (on Training tab)
- **Steps**:
  1. Click **Add Training** → inline form appears
  2. Fill: Title `Employee Self-Enrollment Test`, type `external`, provider `Online Academy`, dates today + 1 week, status `planned`
  3. Click **Save** → new record appears
  4. Click **Edit** on the record → change status to `in_progress` → **Save**
- **Pass**: Employee can create and edit own training. Form saves. Edit pre-fills. Status updates.
- **Bug**:

---

### E8-3 · Training — certifications self-service - add (implemented)
- **Profile**: Employee (on Training tab)
- **Steps**:
  1. Scroll to **Certifications** section
  2. Click **Add Certification** → fill form → Submit for Review
  3. Check new cert shows with "Pending Review" amber badge
  4. Check expiry badges on verified certs: Expired (red), ≤30d (red), ≤60d (yellow), Active (green), No Expiry (grey)
  5. Click **Edit** on a pending cert → change details → Save
  6. (Admin) Go to Training → Certifications tab → filter by "Pending Review"
  7. (Admin) Click verify (green check) or reject (red X) on submitted cert
- **Pass**: Employee can submit certifications for review. Pending certs show amber badge + Edit button. Admin sees "Pending Review" filter with count, verify/reject buttons. Verified certs show expiry badges.
- **Bug**: was read-only, no self-service
  - **Fixed**: Added `employeeSaveCertification()` in `trainingStorage.js` (submits with `status: pending_review`). `EmpTraining.jsx` now has Add/Edit certification form. Admin `TrainingManager.jsx` shows pending count, verify/reject buttons, and "Self-submitted" label. Requires `sql/042_certification_self_service.sql` for `status` column + employee insert/update RLS policies.

---

### E9-1 · Appraisals — view ratings (read-only) -too cramped  spaceit out 
- **Profile**: Employee (signed in)
- **Setup**: Switch to **Appraisals** tab. Must have been rated by manager.
- **Steps**:
  1. Check appraisal list: cycle name, review period, overall rating stars, status badge
  2. Expand a row → check sections: name, weight, star rating, comments
  3. Check development plan and reviewer comments
  4. Check badges: Pending (grey), Reviewed (blue), Calibrated (green)
  5. Try clicking star inputs — should NOT respond
- **Pass**: Data displays correctly. Fully read-only. Empty state if no appraisals (not a crash).
- **Bug**: Too cramped, space it out
  - **Fixed**: Increased card gap from 12px to 14px, header padding from 14px to 16px/20px, expanded section padding to 20px/24px, added marginBottom to page header in `EmpAppraisal.jsx`.

---

### E10-1 · Documents — view existing and self-upload
- **Profile**: Employee (signed in)
- **Setup**: Switch to **Documents** tab. Admin should have uploaded docs for this employee.
- **Steps**:
  1. Check existing docs: type, document number, expiry (DD/MM/YYYY), status badge
  2. Clinical credentials show cyan "Clinical" badge
  3. Admin-uploaded docs do NOT show "Self-submitted" label
  4. Upload: Document type from grouped dropdown, Number `TEST-DOC-001`, Expiry 6 months, Notes `Employee self-upload test`, choose file → Submit
- **Pass**: New row with "Pending Review" badge and "Self-submitted" label. File uploads to Supabase Storage.
- **Bug**:notify employee and admin of document expriry as well , in dashboard for employee , and notifications for both employee and admin , when employee tries to submit document this error comes "Employee record not loaded."
  - **Fixed** (document submit bug): `EmpDocuments.jsx` used `emp.userId` (camelCase) but `getMyEmployeeRecord()` returns raw snake_case DB data — fixed to `emp.user_id`. Storage path now correctly resolves as `{admin_user_id}/{employee_id}/{timestamp}_{filename}`.

---

### E11-1 · Letter Requests — submit and view history - add feature 
- **Profile**: Employee (signed in)
- **Setup**: Switch to **Requests** tab
- **Steps**:
  1. Check card padding — no text overflow
  2. Select **Salary Certificate — Bank**, Purpose `Bank loan application — employee test`, Addressed To `National Bank UAE`
  3. Click **Submit Request** → success toast, form resets
  4. Check My Requests table: Letter Type, Purpose, Requested date, Status
  5. New request shows **Pending Review** (amber clock badge)
- **Pass**: Form submits. Request in table. Completed requests show "Ready" with green checkmark. Rejected show reason inline.
- **Bug**: allow the employee to download the document after admin confirms the letter requests
  - **Fixed**: Added "View Letter" button on completed requests in `EmpRequests.jsx`. Button uses `printLetter()` to generate the letter HTML (same template the admin uses) and opens it in a new tab for viewing/printing. Requires employee record + company data (fetched on mount via `getMyEmployeeRecord()` + `getMyCompany()`).

---

### E12-1 · Profile — view and edit
- **Profile**: Employee (signed in)
- **Setup**: Switch to **Profile** tab
- **Steps**:
  1. Verify profile: name, job title, department, start date, phone, emergency contact, bank details, IBAN
  2. All fields **read-only**
  3. Click **Edit** → change Phone to `+971501234567` → **Save** → toast, value updates
  4. Click **Edit** again → change something → **Cancel** → discards, returns to read-only
- **Pass**: Read-only works. Edit persists. Cancel discards.
- **Bug**: cant edit profile information , leave salary information locked , do this for manager portal as well
  - **Fixed**: Root cause was missing RLS policy — employees had no UPDATE permission on their own `employees` row. Created `sql/041_employee_contact_update.sql` with `employees_self_update_contact` policy (UPDATE WHERE `auth_user_id = auth.uid()`). The app code (`EmpProfile.jsx`) already restricts edits to contact fields only (phone, personal email, emergency contact). Salary/employment sections remain display-only. Manager portal already uses the same `EmpProfile` component — fix applies to both portals.

---

## B2. Cross-portal workflows

> Requires **three browser windows** open: Employee (window 1), Manager (window 2), Admin (window 3).

### X-1 · Leave Request Flow (Employee → Manager → Admin) - check 
- **Steps**:
  1. **Employee**: Leave tab → Apply → Annual, 2 days, future dates, reason `Cross-portal test` → Submit
  2. **Manager**: Leave Queue → refresh → find request → **Approve**
  3. **Admin**: Leave → Requests → find ManagerApproved request → **Final OK**
  4. **Employee**: refresh Leave tab → check status
- **Pass**: Pending → ManagerApproved → **Approved**.
- **Bug**: make sure the balances for manager , and employee updated correctly , check code flow 

---

### X-2 · Expense Claim Flow (Employee → Manager → Admin → Payroll) -c 
- **Steps**:
  1. **Employee**: Expenses → submit (meals, AED 150, today, `Cross-portal expense test`)
  2. **Manager**: Expense Queue → refresh → **Approve**
  3. **Admin**: Expenses → find manager_approved claim → **Approve**
  4. **Admin**: open Payroll for current month → verify expense appears → Generate → check status = **Paid**
- **Pass**: Pending → manager_approved → approved → **paid**.
- **Bug**:

---

### X-3 · Advance Flow (Employee → Admin) -c 
- **Steps**:
  1. **Employee**: Advances → request (AED 2000, `Cross-portal advance test`)
  2. **Admin**: Advances → find pending → **Approve** → set repayment terms
  3. **Employee**: refresh → see **Active** advance with progress bar
- **Pass**: Employee sees Active advance with repayment schedule.
- **Bug**:

---

### X-4 · Letter Flow (Employee → Admin → Employee) -c 
- **Steps**:
  1. **Employee**: Requests → submit NOC, `Cross-portal letter test`
  2. **Admin**: Dashboard pending badge / Letter Requests → complete → print → Completed
  3. **Employee**: refresh → status **"Ready"** with green checkmark + collection note
- **Pass**: Status flows through to Ready with completion date.
- **Bug**:

---

### X-5 · Appraisal Flow (Admin → Manager → Employee) -c 
- **Steps**:
  1. **Admin**: Appraisals → create/use cycle → Reviews → Assign Staff (include the employee)
  2. **Manager**: Appraisals → Team Appraisals → rate sections with stars → Save
  3. **Admin**: refresh → see ratings → calibrate final score
  4. **Employee**: Appraisals → expand row → see calibrated rating
- **Pass**: Employee sees **Calibrated** (green) badge with sections, ratings, and comments.
- **Bug**: on the employee give more information for what apprisal cycle it is , or what period. notify about the new appraisals 


---

### X-6 · Attendance Clock (Employee → Admin visibility) -c 
- **Steps**:
  1. **Employee**: Attendance → **Clock In**
  2. **Admin**: Attendance module → Refresh
- **Pass**: Admin sees employee as **Present** with clock-in time.
- **Bug**:

---

### X-7 · Document Self-Upload (Employee → Admin review) -c 
- **Steps**:
  1. **Employee**: Documents → upload clinical credential (DHA Licence, `CRED-XP-001`)
  2. **Admin**: EmployeeModal → Documents → see "Self-submitted" + Pending Review
  3. **Admin**: click **✓** Verify
  4. **Employee**: refresh → badge changes to **Verified**
- **Pass**: End-to-end document submission and verification flow.
- **Bug**:

---

### X-8 · Roster Publish (Admin → Employee + Manager visible) -c 
- **Steps**:
  1. **Admin**: confirm roster is published for current month
  2. **Employee**: Schedule tab → shifts visible
  3. **Manager**: Schedule tab → shifts visible
- **Pass**: Both see assigned shifts with correct names, times, and colour indicators.
- **Bug**:

---

## B3. Edge cases

### EDGE-1 · Probation + Leave restriction -c 
- **Profile**: Admin + Employee
- **Steps**:
  1. **Admin**: set employee to **Probation** status
  2. **Employee**: Leave → Apply → check dropdown hides restricted types (Hajj, Study) + amber banner
- **Pass**: Restricted types hidden. Amber banner lists them.
- **Bug**:

---

### EDGE-2 · SIF Compliance Gate -c 
- **Profile**: Admin
- **Steps**:
  1. Set a licensed employee's professional licence expiry to yesterday
  2. Payroll → Download SIF → gate modal fires listing violation
  3. Enter reason (≥10 chars) → confirm → SIF downloads
- **Pass**: Download blocked until override reason entered.
- **Bug**:

---

### EDGE-3 · Staffing Rule Gate -c 
- **Profile**: Admin
- **Steps**:
  1. Build roster with fewer staff than a staffing rule requires
  2. Click **Publish** → gate modal lists the shortfall
- **Pass**: Publish blocked. Override allows after reason.
- **Bug**:

---

### EDGE-4 · Manager's own appraisal excluded -c 
- **Profile**: Manager
- **Steps**:
  1. Appraisals → Team Appraisals view → manager's own appraisal NOT in list
  2. Switch to My Appraisals → own appraisal appears here
- **Pass**: Self-exclusion works in team view.
- **Bug**:

---

### EDGE-5 · Salary Compliance bars -c 
- **Profile**: Admin
- **Steps**:
  1. Open Salary Compliance view
  2. Check: Basic < 50% = red; 50–60% = amber; ≥60% = green; Housing > 25% = amber/red; Transport > 10% = amber/red
- **Pass**: Correct colour coding.
- **Bug**:

---

### EDGE-6 · Notification bell on leave approval -c 
- **Profile**: Admin + Employee
- **Steps**:
  1. **Admin**: approve a pending leave request
  2. **Employee**: check bell icon → `leave_approved` notification appears
- **Pass**: Notification shows for the employee.
- **Bug**:

---

### EDGE-7 · Sidebar collapse persistence -c 
- **Profile**: Employee or Manager
- **Steps**:
  1. Collapse sidebar → reload page (F5)
- **Pass**: Sidebar remains collapsed (localStorage).
- **Bug**:

---

### EDGE-8 · Empty states — no crashes -c 
- **Profile**: Any portal
- **Steps**:
  1. Open Appraisals before any cycles exist
  2. Open Training before any records exist
  3. Open Advances before any advances exist
- **Pass**: Empty state messages, not crashes or blank screens.
- **Bug**:

---

### EDGE-9 · Clinical credential 90-day threshold -c 
- **Profile**: Admin
- **Steps**:
  1. Set DHA Licence expiry to **70 days** from today
  2. Check alert — should be **amber** (within 90d clinical threshold)
  3. Compare: normal doc at 70 days would be green (60d threshold)
- **Pass**: Clinical uses 90d threshold. Normal uses 60d.
- **Bug**:

---

### EDGE-10 · Duplicate clock-in blocked -c 
- **Profile**: Employee (already clocked in and out today)
- **Steps**:
  1. Attendance tab → check Clock In button
- **Pass**: Button is **disabled** (not hidden). `isEnabled()` check prevents re-clocking.
- **Bug**:

---

### EDGE-11 · Multi-branch data isolation -c 
- **Profile**: Admin (with 2+ companies/branches)
- **Steps**:
  1. Switch to Branch A → note employees
  2. Switch to Branch B → check employees
- **Pass**: Only Branch B employees visible. Full data isolation.
- **Bug**:

---

*Generated from MANUAL_TEST_CHECKLIST.md on 2026-07-13*
