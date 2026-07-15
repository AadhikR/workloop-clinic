# Manual Test Checklist — Workloop Clinic HRMS

Three portals, all from `http://localhost:5173`.  
Sign in as **Admin** → AppShell | **Employee/Manager** → respective Shell.

Legend: `[ ]` = not tested · `[x]` = pass · `[!]` = bug found

---

## 13-DAY SCHEDULE

| Day | Area | Portal |
|-----|------|--------|
| 1 | Admin Auth · Dashboard · Clinical Dashboard | Admin |
| 2 | Company Settings · Employees (basic CRUD, 4 tabs) | Admin |
| 3 | Employees (advanced: Documents · Insurance · Contracts · Probation · Offboarding) | Admin |
| 4 | Departments · Letter Requests | Admin |
| 5 | Payroll (full cycle: create → approve → SIF → WPS) | Admin |
| 6 | Advances · Expenses | Admin |
| 7 | Leave (all 5 tabs) | Admin |
| 8 | Attendance · Biometric Import · Assets | Admin |
| 9 | Training · Appraisals | Admin |
| 10 | Roster · Reports (all 8 tabs) | Admin |
| 11 | Manager Portal (queue tabs · auth · appraisals · home · leave · schedule · attendance) | Manager |
| 12 | Manager Portal (remaining) · Employee Auth · Employee tabs E-1 through E-7 · Deferred DOC-4/5, PORTAL-1 | Manager + Employee |
| 13 | Employee tabs E-8 through E-12 · Cross-portal flows X-1 through X-8 · Edge cases | Employee + Cross-portal |

---

---

# DAY 1 — Admin Auth · Dashboard · Clinical Dashboard

> **Before you start**
> Have your admin credentials ready (email + password you used when creating the company).
> Open `http://localhost:5173` in a browser.
> All tests below use the **Admin** profile unless stated otherwise.
> Items marked ⏭ **DEFER** cannot be tested today — the required data is created on the indicated day. Return to tick them off when that day is reached.

---

## ADMIN AUTH

### A-1 · Sign in with valid credentials - completed 
- **Profile**: Admin
- **Setup**: None
- **Steps**:
  1. Open `http://localhost:5173`
  2. On the login page, locate the left/top form labelled **"Sign in as Admin"**
  3. Enter your admin email and password exactly as registered
  4. Click the **"Sign in as Admin"** submit button
- **Pass**: Page transitions to the Admin shell. The sidebar is visible on the left, Dashboard content loads in the main area, your company name appears at the top of the sidebar.
- **Bug**:

---

### A-2 · Wrong password is rejected - completed 
- **Profile**: Admin (not yet signed in)
- **Setup**: Sign out first if already signed in (sidebar → Sign Out)
- **Steps**:
  1. Enter your correct email but type a deliberately wrong password (e.g. `wrongpassword123`)
  2. Click the submit button
- **Pass**: An error message appears on the form (e.g. "Invalid login credentials"). The page stays on the login screen — no navigation happens.
- **Bug**:

---

### A-3 · Email is case-insensitive - completed 
- **Profile**: Admin (not yet signed in)
- **Setup**: Sign out if already signed in
- **Steps**:
  1. Type your email in ALL CAPS (e.g. `RAJ@INTUITME.COM`)
  2. Enter the correct password
  3. Click the submit button
- **Pass**: You land on the Admin shell exactly the same as A-1. No error is shown.
- **Bug**:

---

### A-4 · Sign Out returns to login - completed 
- **Profile**: Admin (signed in)
- **Setup**: Be signed in as Admin
- **Steps**:
  1. Scroll to the bottom of the left sidebar
  2. Click the **"Sign Out"** button (with a LogOut icon)
- **Pass**: The app navigates back to the login page. No admin data is visible.
- **Bug**:

---

### A-5 · Sidebar collapse to icon-only mode - completed 
- **Profile**: Admin (signed in)
- **Setup**: Sidebar must be in expanded state (you can see text labels next to nav icons)
- **Steps**:
  1. Find the collapse arrow button (◄) at the top-right edge of the sidebar
  2. Click it once
- **Pass**: The sidebar shrinks to show only icons — no text labels. The main content area expands to fill the space.
- **Bug**:

---

### A-6 · Sidebar expand restores labels and nav pill - completed 
- **Profile**: Admin (signed in, sidebar collapsed from A-5)
- **Setup**: Sidebar must be in collapsed/icon-only state
- **Steps**:
  1. Click the expand arrow button (►) that now appears at the edge of the collapsed sidebar
- **Pass**: Sidebar expands back to full width with text labels visible. The active nav item's sliding pill indicator animates smoothly to the correct position.
- **Bug**:

---

### A-7 · Sidebar collapse state survives a page reload - completed 
- **Profile**: Admin (signed in)
- **Setup**: None — works from any sidebar state
- **Steps**:
  1. Collapse the sidebar (A-5) so it is in icon-only mode
  2. Reload the page (`F5` or `Ctrl+R`)
  3. Wait for the app to finish loading
- **Pass**: After reload the sidebar is still collapsed (icon-only). It did not reset to expanded.
- **Bonus**: Repeat with the sidebar expanded — reload — sidebar stays expanded.
- **Bug**:

---

### A-8 · Branch switcher dropdown opens - completed 
- **Profile**: Admin (signed in)
- **Setup**: None
- **Steps**:
  1. Look at the very top of the sidebar — you should see your company name (e.g. "Workloop Clinic") with a small chevron or indicator
  2. Click on the company name / branch switcher area
- **Pass**: A dropdown appears listing at least one branch (your current company). A checkmark (✓) shows next to the currently active branch. An "Add Branch" option is visible at the bottom of the dropdown.
- **Bug**:

---

### A-9 · Add a new branch - completed 
- **Profile**: Admin (signed in)
- **Setup**: Branch switcher dropdown must be open (A-8)
- **Steps**:
  1. Click **"Add Branch"** inside the dropdown
  2. A modal or inline input appears asking for a branch name
  3. Type `Test Branch` as the name
  4. Click the **Create** / **Save** button
- **Pass**: The modal closes. The page automatically redirects to **Company Settings** for the new branch. The sidebar now shows "Test Branch" as the active company. The branch switcher dropdown now lists both branches.
- **Bug**:

---

### A-10 · Switch between branches - completed 
- **Profile**: Admin (signed in, at least 2 branches exist from A-9)
- **Setup**: A-9 must be completed so there are 2 branches
- **Steps**:
  1. Click the branch switcher at the top of the sidebar
  2. In the dropdown, click the **original** branch (your main company — the one without a checkmark)
- **Pass**: The active branch switches. The sidebar updates to show the original company name. All data in the main area (Dashboard stat cards, etc.) reloads for that branch. The employee count, payroll runs, etc. reflect the original branch's data.
- **Bug**:

---

### A-11 · Delete a non-active branch - completed 
- **Profile**: Admin (signed in, currently on the original branch)
- **Setup**: "Test Branch" from A-9 must exist and must NOT be the active branch (switch back to original first using A-10)
- **Steps**:
  1. Click the branch switcher dropdown
  2. Find "Test Branch" in the list
  3. Click the **X** (delete) button next to "Test Branch"
  4. Confirm the deletion in the dialog that appears
- **Pass**: "Test Branch" disappears from the dropdown. The active branch is unchanged.
- **Note**: If you try to delete the currently active branch, the app should block it with an error. You can test this by switching to "Test Branch" first and trying to delete it — you should see a guard error.
- **Bug**:

---

### A-12 · Notification bell opens the panel - partial 
- **Profile**: Admin (signed in)
- **Setup**: None
- **Steps**:
  1. Look for the bell icon near the top of the sidebar (above or below the nav items)
  2. Click the bell icon
- **Pass**: A panel slides in from the right side of the screen (fixed position, ~380px wide). It shows either "No notifications yet" (empty state on a fresh install) or a list of notifications if any exist.
  3. Click anywhere outside the panel (or the X close button) to dismiss it
- **Pass for dismiss**: Panel slides closed.
- **Bug**: make sure expiry comes up immediately in notficiatioons , verify it is there for all possible expirable dates
  - **Fixed**: `NotificationBell` now listens for `workloop-notifications-updated` window event — count badge refreshes immediately when `generateExpiryNotifications` runs on Dashboard load, not after the 60-second poll. Also added missing notification type icons (probation_ending ⏳, contract_expiry 📋, cert_expiry 🎓, clinical_licence_expiry 🪪, clinical_credential_expiry 🏥). All expiry types (visa, passport, EID, labour card, professional licence, clinical credentials, certifications, insurance, probation, contract) are already covered by `generateExpiryNotifications`.

---

### A-13 · Notification bell shows unread count badge — ⏭ deferred from Day 1, do this now
- **Profile**: Admin (signed in)
- **Setup**: Do this **after** finishing DOC-2 below (Day 3), so a document-expiry notification exists alongside the probation/contract ones already generated from Day 1's D-7/D-8 setup.
- **Steps**:
  1. Navigate to **Dashboard** (this is what triggers `generateExpiryNotifications`)
  2. Wait 2–3 seconds for the async expiry check to run
  3. Look at the bell icon in the sidebar
- **Pass**: A red count badge appears on the bell showing at least 1 unread notification. Click the bell — the panel lists entries such as "Probation ending soon", "Contract expiring", and (after DOC-2) a document-expiry alert, each with the correct icon (⏳ probation, 📋 contract, 📄 document).
- **Bug**:

---

## 1. DASHBOARD

### D-1 · Navigate to Dashboard and verify stat cards load -completed 
- **Profile**: Admin (signed in)
- **Setup**: None — works even with zero employees
- **Steps**:
  1. Click **"Dashboard"** (first item in the sidebar nav, LayoutDashboard icon)
- **Pass**: The Dashboard page loads. You can see stat cards (Active Employees, Payroll Runs, etc.) — they may show 0 on a fresh install, but the cards themselves must be visible with no blank screen, no spinner stuck, and no error message.
- **Bug**:

---

### D-2 · Emiratization / Nafis card renders - completed 
- **Profile**: Admin (signed in)
- **Setup**: None — card renders even with 0 UAE nationals
- **Steps**:
  1. On the Dashboard, look for the **Emiratization / Nafis** compliance card
  2. Note the ratio shown (e.g. "0 / 0 — 0%") and whether it shows Compliant or Not Compliant
- **Pass**: The card is visible. If no UAE national employees exist it shows 0% — that is correct, not a bug.
- **Bug**:

---

### D-3 · Generate Nafis Report modal - completed 
- **Profile**: Admin (signed in)
- **Setup**: None
- **Steps**:
  1. On the Dashboard, find the Nafis / Emiratization card
  2. Click the **"Generate Nafis Report"** button inside that card
  3. A modal opens — inspect the contents (employee list will be empty on a fresh install)
  4. Click **"Download CSV"** — a CSV file should download to your machine
  5. Click **"Save Snapshot"** — a success toast should appear
  6. Click the **X** or close button on the modal
- **Pass**: Modal opens without errors. CSV downloads (even if the file only contains headers). Snapshot saved toast appears. Modal closes cleanly.
- **Bug**:

---

### D-4 · Payroll cost trend chart renders - bug
- **Profile**: Admin (signed in)
- **Setup**: None — chart renders even with no payroll runs
- **Steps**:
  1. Scroll down the Dashboard page
  2. Find the payroll cost trend chart / graph area
- **Pass**: The chart area renders — it may show an empty state message or a flat chart with no bars, but it must not be a blank white box, a JavaScript error, or a loading spinner that never resolves.
- **Bug**: on the dashboard after  the emiratization/Nafis compliance bar , nothing is there
  - **Fixed**: Payroll trend card now always renders. When fewer than 2 generated runs exist it shows "Generate at least 2 payroll runs to see the cost trend chart" with a navigation link instead of hiding the section entirely.

---

### D-5 · Pending payroll approval alert and navigation - completed  
- **Profile**: Admin (signed in)
- **Setup**: A payroll run must be in `pending_approval` state. Quick setup (takes ~2 minutes):
  1. Click **"Payroll Module"** in the sidebar
  2. Click the **+** button to create a new run
  3. Select any month/year, type any name (e.g. "Test Run"), click **Create**
  4. Inside the PayrollEditor, click **"Submit for Approval"**
  5. Click **"Dashboard"** in the sidebar to go back
- **Steps** (after setup):
  1. On the Dashboard, look for a blue info alert mentioning pending payroll approval
  2. Click the **"Go to Payroll"** link/button inside that alert
- **Pass**: The alert is visible on the Dashboard. Clicking it navigates you directly to the Payroll Module page.
- **Cleanup**: After testing, go to Payroll Module → open the run → click **Recall** to return it to draft status, so it does not interfere with Day 5 testing.
- **Bug**:

---

### D-6 · Pending letter requests alert and navigation
- **Profile**: Admin for verification · Employee for setup
- **Setup**: A letter request must exist in `pending` state. Quick setup:
  1. Open a **new incognito / private browser window**
  2. Go to `http://localhost:5173`
  3. If you have an employee portal account, sign in using the **"Sign in as Employee / Manager"** form with employee credentials
  4. If no employee account exists yet: ⏭ **DEFER to Day 4** — employee portal accounts are set up in Days 2–3. Return to this check then.
  5. Once signed in as employee: click the **"Requests"** tab in the sidebar
  6. In the "Request a Letter" form, select any letter type, optionally add a purpose, click **"Submit Request"**
  7. Switch back to your admin browser window
  8. Reload the Dashboard (`F5`)
- **Steps** (after setup):
  1. On the Dashboard, look for an amber alert showing a count of pending letter requests
  2. Click the link/button inside that alert
- **Pass**: The amber alert shows the correct count (at least 1). Clicking it navigates to the **Letter Requests** page in the admin portal.
- **Bug**:the "1 letter request pending. Employees are waiting for HR letters to be generated. View Letter Requests" shows , but when i got to letter requests i do not see it
  - **Fixed**: `getLetterRequests()` was using an implicit INNER JOIN to `employees` — if PostgREST's RLS evaluation dropped the employee row from the join, the entire letter_request row was silently excluded (count query has no join so it still returned 1). Changed to `employees!left(...)` so the letter_request is always returned regardless of the join result.

---

### D-7 · Probation ending alert and navigation - completed 
- **Profile**: Admin
- **Setup**: An employee must have `employmentStatus = 'Probation'` with a `probationEndDate` within the next 14 days. Quick setup:
  1. Go to **Employees** in the sidebar
  2. Click **+** to add a new employee (fill minimum required fields: Name, Work Email, MOL ID, Bank Name, IBAN)
  3. On the **Job & Contract** tab, set **Employment Status** to **Probation** and set **Probation End Date** to tomorrow's date
  4. Save the employee
  5. Click **Dashboard** to go back and reload
- **Steps** (after setup):
  1. On the Dashboard, look for an amber alert about probation periods ending soon
  2. Click **"Manage in Employees"** or the link inside that alert
- **Pass**: Alert is visible showing the employee's name. Clicking it navigates to the **Employees** page.
- **Note**: If you already have a probation employee from a previous test run, skip the setup.
- **Bug**:

---

### D-8 · Contract expiring alert and navigation - completed 
- **Profile**: Admin
- **Setup**: An employee must have a **Limited** contract with an end date within 60 days. Quick setup:
  1. Go to **Employees**, open any existing employee (or create one)
  2. On the **Job & Contract** tab, set **Contract Type** to **Limited** and set **Contract End Date** to 30 days from today
  3. Save
  4. Return to Dashboard and reload
- **Steps**:
  1. Look for an amber alert about expiring contracts
  2. Click the link/button inside it
- **Pass**: Alert is visible. Clicking navigates to **Employees**.
- **Bug**:

---

### D-9 · Certification expiry alert and navigation — ⏭ DEFER to Day 9
- **Profile**: Admin
- **Setup**: ⏭ **DEFER to Day 9** — certifications are created in TR-4. After TR-4 (BLS cert with 30-day expiry added), return to Dashboard and complete the steps in the **D-9** section at the top of the Day 9 block.
- **Bug**:

---

### D-10 · Document expiry alert — ⏭ deferred from Day 1, covered by DOC-2 on Day 3
- **Profile**: Admin
- **Setup**: Completed as part of **DOC-2** in the Day 3 section below — upload a document with an expiry date within 60 days, then return to Dashboard.
- **Steps**: see DOC-2.
- **Pass**: see DOC-2's Pass criteria, plus: a "Doc Expiry Alerts" or document-expiry related alert/count is visible on the Dashboard or Employees page after the upload.
- **Bug**:

---

### D-11 · Pending appraisals alert and navigation — ⏭ DEFER to Day 9
- **Profile**: Admin
- **Setup**: ⏭ **DEFER to Day 9** — appraisal cycles and staff assignments are created in AP-4. After AP-4 (staff assigned to an open/active cycle), return to Dashboard and complete the steps in the **D-11** section at the top of the Day 9 block.
- **Bug**:

---

## 2. CLINICAL DASHBOARD 

### C-1 · Navigate to Clinical Dashboard - partial  
- **Profile**: Admin (signed in)
- **Setup**: None
- **Steps**:
  1. Click **"Clinical Dashboard"** in the sidebar (second nav item, Activity icon)
- **Pass**: The Clinical Dashboard page loads. You see a grid of KPI cards at the top. No error, no blank screen.
- **Bug**: i added , employees from an csv file , i did it multiple times accidentalty becuase it didnt show in the employees field , but it does show in the clinical dhasboard as 57 employees , make sure imported csv files correctly show in the employees module , check any other aspects in this area for eorrors and bugs and fix them.
  - **Fixed**: Root cause — CSV import inserted employees with `company_id = null`. `getEmployees(activeCompanyId)` filtered by exact match so null-company employees were invisible in EmployeeManager but visible in ClinicalDashboard (which called `getEmployees()` with no filter). Three changes: (1) `getEmployees(companyId)` now uses `OR company_id IS NULL` so pre-migration/CSV-imported employees always appear. (2) CSV import now stamps `companyId: activeCompanyId` on all imported employees going forward. (3) ClinicalDashboard now passes `activeCompanyId` to `getEmployees()` for consistency. **Note**: If CSV was imported multiple times, duplicate employee rows may now appear — you can delete duplicates via the Employees list (archive the extras).

---

### C-2 · All 11 KPI cards are visible - completed
- **Profile**: Admin (signed in, on Clinical Dashboard)
- **Setup**: None — cards render with 0 values on a fresh install
- **Steps**:
  1. Count the KPI stat cards across the grid
  2. Verify these 11 are present (values may be 0):
     - Active Staff
     - Credential Compliance
     - Licences Expiring ≤90d
     - Expired Credentials
     - Today's Roster Coverage
     - On Probation
     - New Joiners This Month
     - Birthdays This Month
     - On Leave Today
     - Pending Leave Requests
     - Staff On Duty Now
- **Pass**: All 11 cards visible. Values may be 0 but each card must show a label and a number (not blank or broken).
- **Bug**:

---

### C-3 · Click a KPI card to expand its drill-down panel - completed 
- **Profile**: Admin (signed in, on Clinical Dashboard)
- **Setup**: None
- **Steps**:
  1. Click on any one KPI card (e.g. **Active Staff**)
- **Pass**: A detail panel expands directly below the stats grid, showing a table of relevant records (or an empty-state message if no data). The clicked card may get a highlighted border or indicator.
- **Bug**:

---

### C-4 · Click the same card again to collapse the panel - completed 
- **Profile**: Admin (signed in, drill-down panel open from C-3)
- **Setup**: One drill-down panel is currently open
- **Steps**:
  1. Click the same KPI card that is currently expanded
- **Pass**: The drill-down panel collapses/hides. The page returns to showing only the KPI grid.
- **Bug**:

---

### C-5 · Clicking a different card closes the old panel and opens the new one - completed 
- **Profile**: Admin (signed in, on Clinical Dashboard)
- **Setup**: One drill-down panel is open (from C-3)
- **Steps**:
  1. With card A's panel already open, click a different card (card B)
- **Pass**: Card A's panel closes and card B's panel opens immediately. Only one panel is visible at a time.
- **Bug**:

---

### C-6 · Department Headcount table renders - partial 
- **Profile**: Admin (signed in, on Clinical Dashboard)
- **Setup**: None — table renders with empty rows on a fresh install
- **Steps**:
  1. Scroll below the KPI cards grid on the Clinical Dashboard
  2. Find the Department Headcount table
- **Pass**: Table is visible. On a fresh install it may have no rows or show all departments at 0 — that is correct. It must not be a blank area or show an error. Columns should include department name, headcount, compliance %, and a coverage progress bar.
- **Bug**: the department headcount header come outside the box , adjust the panel size or text so it doesnt come out
  - **Fixed**: Wrapped the `h3` in a proper `card-header` div (18px 22px padding, bottom border) matching all other card headers in the app. Empty state also moved into a padded div.

---

### C-7 · Test all 11 KPI card drill-downs individually - completed 
- **Profile**: Admin (signed in, on Clinical Dashboard)
- **Setup**: None
- **Steps**:
  1. Click each of the 11 cards one by one, in order
  2. After clicking each one, verify a panel appears (or a clear "no data" empty state)
  3. Click it again to collapse before moving to the next card
- **Pass**: Every card responds to the click — none are inert/broken. Drill-down panels show either data or a proper empty state. No JavaScript errors in the browser console during this test.
- **Bug**:

  - [ ] Active Staff — drill-down opens
  - [ ] Credential Compliance — drill-down opens
  - [ ] Licences Expiring ≤90d — drill-down opens
  - [ ] Expired Credentials — drill-down opens
  - [ ] Today's Roster Coverage — drill-down opens
  - [ ] On Probation — drill-down opens
  - [ ] New Joiners This Month — drill-down opens
  - [ ] Birthdays This Month — drill-down opens
  - [ ] On Leave Today — drill-down opens
  - [ ] Pending Leave Requests — drill-down opens
  - [ ] Staff On Duty Now — drill-down opens

---

---

# DAY 2 — Company Settings · Employees (basic CRUD)

> **Before you start**
> Be signed in as **Admin**. All tests below use the Admin profile unless stated otherwise.
> No items from Day 1 are deferred to Day 2.

---

## 3. COMPANY SETTINGS

### CS-1 · Navigate to Company Settings and verify fields load -completed 
- **Profile**: Admin (signed in)
- **Setup**: None
- **Steps**:
  1. Click **"Company Settings"** in the sidebar
  2. Observe the form fields: Company Name, MOL Employer ID, Sector, IBAN, Address
- **Pass**: The page heading reads **"Company / Employer Settings"** (note the slash). All fields are populated with existing company data (or blank on a fresh install) — no blank screen, stuck spinner, or console error.
- **Bug**:

---

### CS-2 · Edit company name and save
- **Profile**: Admin (signed in, on Company Settings)
- **Setup**: None
- **Steps**:
  1. Change the **Company Name** field (e.g. append " Test")
  2. Click **Save**
  3. Check the sidebar branch label at the top
- **Pass**: Success toast confirms the save. If the branch label is tied to company name, the sidebar switcher updates. Reload — the new name persists.
- **Bug**:

---

### CS-3 · Sector dropdown auto-fills Nafis Quota % - completed 
- **Profile**: Admin (signed in, on Company Settings)
- **Setup**: None
- **Steps**:
  1. Open the **Sector** dropdown
  2. Select any industry sector (e.g. "Healthcare")
- **Pass**: The **Nafis Quota %** field auto-updates to that sector's default quota (from the `SECTORS` constant) without manual entry.
- **Bug**:

---

### CS-4 · Manually override Nafis Quota %
- **Profile**: Admin (signed in, on Company Settings)
- **Setup**: CS-3 completed (sector selected, quota auto-filled)
- **Steps**:
  1. Clear the **Nafis Quota %** field and type a different value (e.g. `10`)
  2. Click **Save**
- **Pass**: Success toast appears. Reload — the manually entered value persists (does not revert to the sector default).
- **Bug**:

---

### CS-5 · Insurance Policies — Add a policy - completed 
- **Profile**: Admin (signed in, on Company Settings)
- **Setup**: None
- **Steps**:
  1. Scroll to the **Insurance Policies** card → click **Add Policy**
  2. Fill: Insurer Name, Policy Number, Tier, Annual Premium, Renewal Date, Broker (optional)
  3. Click **Save**
- **Pass**: Modal closes. New policy appears in the list with the correct renewal-status badge colour (green/amber/red based on how soon it renews).
- **Bug**:

---

### CS-6 · Insurance Policies — Edit a policy - completed 
- **Profile**: Admin (signed in, on Company Settings)
- **Setup**: At least one policy exists (CS-5)
- **Steps**:
  1. Click the edit icon on an existing policy row
  2. Change one field (e.g. Annual Premium) → **Save**
- **Pass**: Row updates with the new value immediately; no duplicate row is created.
- **Bug**:

---

### CS-7 · Insurance Policies — Delete a policy - completed 
- **Profile**: Admin (signed in, on Company Settings)
- **Setup**: A policy you don't need exists
- **Steps**:
  1. Click the delete icon on a policy row → confirm in the dialog
- **Pass**: Policy disappears from the list.
- **Note**: Keep at least one policy alive — it's needed for the Employees → Insurance tab test on Day 3.
- **Bug**:

---

## 4. EMPLOYEES — Basic CRUD

### EC-1 · Navigate to Employees and verify list loads - completed 
- **Profile**: Admin (signed in)
- **Setup**: None — works even with zero employees
- **Steps**:
  1. Click **"Employees"** in the sidebar
- **Pass**: Table loads with columns for name, department, status, salary. Empty company shows an empty-state message, not a blank screen or error.
- **Bug**:

---

### EC-2 · Search box filters the list live - completed 
- **Profile**: Admin (signed in, on Employees)
- **Setup**: At least one employee must exist (e.g. the Probation/Limited-contract employees created in Day 1's D-7/D-8 setup)
- **Steps**:
  1. Type part of an existing employee's name into the search box
- **Pass**: List filters live as you type, no Enter required. Clearing the box restores the full list.
- **Bug**:

---

### EC-3 · Status filter switches correctly - completed 
- **Profile**: Admin (signed in, on Employees)
- **Setup**: An employee in a non-Active status helps (e.g. the Probation employee from D-7)
- **Steps**:
  1. Click through the status filter: **All Statuses → Active → Probation → On Leave**
- **Pass**: List updates to show only matching employees at each step; "All Statuses" restores everyone (minus any Terminated employees — see EC-5 fix below, the status filter no longer offers "Terminated" since those employees live in their own tab).
- **Bug**:

---

### EC-4 · Add Employee — Personal tab validation - partial 
- **Profile**: Admin (signed in, on Employees)
- **Setup**: None
- **Steps**:
  1. Click the **+** button to add a new employee
  2. Confirm the modal opens with **4 tabs**: Personal · Job & Contract · Salary & Bank · UAE Compliance (Documents/Insurance/Contracts are correctly absent for a new, unsaved employee)
  3. On Personal, leave **Name** and **Work Email** blank and try to save
- **Pass**: Save is blocked until required fields (Name, Work Email, MOL ID, Bank Name, IBAN) are filled. The Name field placeholder reads "e.g. John Smith".
- **Bug**: i am able to add the employee with only name and no.  also make sure no "no." can be repeated , make all important fields for setting up new employee mandatory 
  - **Fixed**: `validate()` in `EmployeeModal.jsx` only format-checked MOL ID/IBAN/Emirates ID *if present* — it never actually required them, so the DB's NOT NULL columns (`emp_no`, `mol_id`, `bank_name`, `bank_routing_code`, `iban`) were satisfied with empty strings. Now Employee No., Work Email, MOL ID, Bank Name, Bank Routing Code, IBAN, and a positive Basic Salary are all required before save, with inline errors + the cross-tab error banner switching to the first offending tab. Added a duplicate **Employee No.** check (MOL ID duplicate check already existed) — both now block save with "already used by {name}".

---

### EC-5 · Add Employee — Personal + Job & Contract tabs - partial 
- **Profile**: Admin (signed in, modal open from EC-4)
- **Setup**: None
- **Steps**:
  1. On Personal: enter Name, a unique Work Email, Phone, Emergency Contact
  2. Switch to **Job & Contract**: enter Job Title; start typing in **Department** and check for autocomplete suggestions (datalist from the `departments` table — free text still works if none match)
  3. Select a **Reporting Manager** if any employees exist; set **Start Date** and **Contract Type** (Limited/Unlimited)
- **Pass**: Department field offers autocomplete but accepts free text. All fields retain their values when switching tabs.
- **Bug**: if an  employee has been terminated , it should be moved to another list for terminated , and now come in the employee list or any other place like reporting manager in the employee set up modal 
  - **Fixed (pickers)**: Checked both pickers that list "all employees". `DepartmentManager.jsx`'s Department Head dropdown was already correctly filtering out Terminated employees at load time. `EmployeeModal.jsx`'s **Reporting Manager** dropdown only excluded the employee being edited (`e.id !== form.id`) and listed Terminated staff alongside active ones — fixed to also filter `e.employmentStatus !== 'Terminated'`.
  - **Fixed (employee list)**: per a follow-up request, Terminated employees are now fully moved out of the main Employee List rather than staying badge-visible there. `EmployeeManager.jsx` gained a third tab, **"Terminated Employees"** (alongside Employee List / Document Expiry, `UserX` icon, clickable from the existing "Terminated" stat card), and the Employee List's `filtered` array now always excludes Terminated rows — the status filter dropdown no longer offers a "Terminated" option there. Archiving an employee now makes them disappear from the Employee List and reappear under the Terminated Employees tab, with the same row actions (incl. the offboarding checklist icon). Updated `tests/employees.spec.js` (status-filter options, new tab assertions, archive-flow assertions) and `tests/offboarding.spec.js` (`findOffboardingButton` now switches to the Terminated Employees tab first) to match. Updated the corresponding note in `CLAUDE.md`.

---

### EC-6 · Add Employee — Salary & Bank tab compliance bars - completed 
- **Profile**: Admin (signed in, modal open from EC-5)
- **Setup**: None
- **Steps**:
  1. Switch to **Salary & Bank**, enter MOL ID and **Basic Salary** (placeholder "e.g. 5000")
  2. Set Housing/Transport so Basic is first ≥60% of gross, then 50–60%, then <50%
  3. Enter Bank Name (free text, e.g. "ENBD"), IBAN, Routing Code
- **Pass**: Compliance bars update live — Basic ≥60% green, 50–60% amber, <50% red; Housing ≤25% compliant else warns; Transport ≤10% compliant else warns. Bank Name is a plain text input, not a dropdown.
- **Bug**:

---

### EC-7 · Add Employee — UAE Compliance tab + Professional Licence - bug 
- **Profile**: Admin (signed in, modal open from EC-6)
- **Setup**: None
- **Steps**:
  1. Switch to **UAE Compliance**. Set Nationality to something other than UAE — confirm Nafis Registration stays disabled
  2. Change Nationality to **"United Arab Emirates"** — confirm Nafis Registration becomes enabled
  3. Enter Visa Number, Passport Number, Emirates ID, Labour Card, with one expiry date within 30 days
  4. In **Professional Licence**: select Authority (e.g. DHA), enter Licence Number, set a future Expiry
- **Pass**: Nafis field toggles correctly with nationality. Near-expiry dates show an amber/red badge inline. A future licence expiry shows a "Valid" badge; Authority = "None" disables the Licence Number field.
- **Bug**: doesnt show the liecense going to expire in the employee set up modal , nd change the date convention to DD/MM/YYYY (Day/Month/Year) throughout the website , make setting up employee little more strict , require some more info before finally setting up 
  - **Fixed (licence badge)**: replaced the ad-hoc `Math.ceil((new Date(expiry) - new Date()) / 86400000)` inline calc with the existing timezone-safe `daysUntil()` helper from `uaeValidators.js` (midnight-to-midnight comparison, avoids off-by-one rounding near day boundaries). Also added a visible amber prompt ("Set a licence expiry date to track renewal") when an Authority is selected but no expiry date has been entered yet, instead of showing nothing.
  - **Fixed (date format)**: audited the whole codebase — most `toLocaleDateString` calls already used the `'en-AE'` locale (correct day-first order); the gap was ~25 places displaying raw `YYYY-MM-DD` strings directly (ClinicalDashboard drill-downs, EmployeeManager probation banner, ExpensesManager/ManagerExpenseQueue/PayrollEditor expense tables, Reports.jsx Payroll Cost/Doc Expiry/Salary History tabs (+ matching CSV/PDF export rows in `reportUtils.js`), RosterManager swap requests + staffing-gate table, TrainingManager records/certifications, the employee portal's Advances/Expenses/Training tabs, and a leave-approval notification body). All now go through `formatDateUAE()` → `DD/MM/YYYY`. Left two things untouched on purpose: `<input type="date">` fields (must stay ISO — that's the HTML spec, not a display string) and the literal `EDR,...`/`SCR,...` lines in the SIF Preview modal (that's a byte-for-byte preview of the actual bank file, reformatting it would misrepresent the file).
  - **Fixed (mandatory fields)**: see EC-4 above — required-field validation was strengthened in the same change.
  - **Fixed (date format, round 2)**: a follow-up pass caught date displays that the first sweep missed because they live in template-literal strings (`${...}`) rather than JSX braces, so the earlier JSX-only search didn't catch them: the dependant DOB column in the Insurance tab's dependants table (`EmployeeModal.jsx`); all 6 expiry-notification body strings in `notificationStorage.js` (document/clinical-credential/probation/contract/certification/professional-licence expiry alerts — the raw date sat in parentheses inside the notification text, e.g. "expires in 12 days (2026-07-15)"); `req.joinDate` in 3 of the printed HR letter templates (`letterTemplates.js` — NOC, Experience Letter, Employment Certificate); and the "Unpaid Leave (start – end)" line-item label in `leaveEngine.js`'s payroll deduction breakdown. Re. the native `<input type="date">` for **Date of Birth** specifically: its on-screen display format (e.g. showing as MM/DD/YYYY) is controlled by the browser/OS locale setting, not by application code — the underlying `value` is always ISO `YYYY-MM-DD` regardless of how it's drawn, and no CSS/JS can override that rendering across browsers. Making the DOB *input* itself always render DD/MM/YYYY would require replacing the native picker with a custom date-input component — a separate, much larger UI undertaking, not done here. All *static/read-only* DOB displays (e.g. in tables) do already show DD/MM/YYYY via `formatDateUAE()`.

---

### EC-8 · Save the new employee - completed 
- **Profile**: Admin (signed in, modal filled from EC-4–EC-7)
- **Setup**: All required fields filled
- **Steps**:
  1. Click **Save**
- **Pass**: Modal closes; the new employee appears in the Employees list with the correct name, department, status.
- **Bug**:

---

### EC-9 · Edit Employee — confirm 7 tabs are visible (structural check only) - completed 
- **Profile**: Admin (signed in, on Employees)
- **Setup**: The employee from EC-8 (or any existing employee)
- **Steps**:
  1. Click the pencil/edit icon on an employee row
- **Pass**: Modal now shows **7 tabs**: Personal · Job & Contract · Salary & Bank · UAE Compliance · Documents · Insurance · Contracts.
- **Note**: Only confirm presence today — do **not** deep-test Documents/Insurance/Contracts content; that's Day 3 (see Day 3 section).
- **Bug**:

---

### EC-10 · Edit Employee — change job title, verify list updates - completed 
- **Profile**: Admin (signed in, modal open from EC-9)
- **Setup**: None
- **Steps**:
  1. On **Job & Contract**, change the Job Title → **Save**
- **Pass**: The Employees list row reflects the new job title.
- **Bug**:

---

### EC-11 · Edit Employee — change salary, verify save succeeds cleanly - completed 
- **Profile**: Admin (signed in, on Employees)
- **Setup**: An existing employee
- **Steps**:
  1. Open the employee → **Salary & Bank** tab → change **Basic Salary** → **Save**
- **Pass**: Save succeeds with no console error. (A job history entry is written silently to `employee_job_history`; there's no visible UI confirmation, but the save must not fail even if that insert fails under RLS — it's wrapped in its own try/catch.)
- **Bug**:

---

### EC-12 · Export employees to CSV - partial 
- **Profile**: Admin (signed in, on Employees)
- **Setup**: At least one employee exists
- **Steps**:
  1. Click **Export CSV**
- **Pass**: A `.csv` file downloads containing all employees with their core fields.
- **Bug**: when csv exported , MOL ID column comes like this "1.00101E+13" same for bank routing number 
  - **Fixed**: Excel auto-converts any long all-digit string to scientific notation when opening a CSV, regardless of quoting — a well-known Excel/CSV interaction, not a value of the data itself. `exportToCSV()` in `EmployeeManager.jsx` now wraps MOL ID and Bank Routing Code in an `="value"` Excel text-formula guard, which forces Excel to display/store them as plain text. Also added a **Bank Routing Code** column to the export (it was missing entirely before).

---

### EC-13 · Import employees via CSV - partrial 
- **Profile**: Admin (signed in, on Employees)
- **Setup**: None
- **Steps**:
  1. Click **Import CSV**, download the template if offered
  2. Fill 2–3 rows matching the expected column layout (EmpNo, Name, MOL ID, Bank, Routing, IBAN, Basic, Allowance, …)
  3. Upload the file
- **Pass**: Imported employees appear in the Employees list (not just the Clinical Dashboard) — `company_id` must be stamped on import. Rows with an MOL ID under 10 digits are silently skipped.
- **Caution**: Re-uploading the same file is now safe — `handleCSVImport` matches existing employees by MOL ID and updates them in place rather than creating a duplicate.
- **Bug**:when csv imported templtee , MOL ID column comes like this "1.00101E+13" same for bank routing number , and imported template doesnt have columns that are correctly linked to each other make that change if possible 
  - **Fixed**: `downloadTemplate()` now applies the same `="value"` Excel text-formula guard (see EC-12 fix) to the Labor Card No and Bank/Routing Code example columns. `parseCSV()` in `csvImport.js` was rewritten to match columns by **header name** (case-insensitive, alias-tolerant) instead of fixed column position, so a reordered or edited template still parses correctly — this addresses "columns not correctly linked to each other." The parser also strips the `="..."` guard back out (and any stray quotes) when reading values, so round-tripping export → edit → import preserves the exact digit string instead of corrupting it.

---

---

---

# DAY 3 — Employees (advanced tabs · Probation · Offboarding)

> **Before you start**
> Be signed in as **Admin**. All tests below use the Admin profile unless stated otherwise.
> **Deferred from earlier days handled today**: A-13 (Day 1) and D-10 (Day 1) — both expanded in place in the Day 1 section above. Do A-13 *after* DOC-2 below so a document-expiry notification exists alongside the probation/contract ones.
> Most tasks below need an **existing** employee (Documents/Insurance/Contracts tabs only render `employee?.id` is set — i.e. not on a brand-new unsaved employee). Use the employee created in Day 2's EC-8, or any other existing employee.

---

## 4. EMPLOYEES — Advanced tabs (Documents · Insurance · Contracts)

### DOC-1 · Upload a document - partial 
- **Profile**: Admin (signed in)
- **Setup**: An existing employee (e.g. from EC-8)
- **Steps**:
  1. Open the employee → **Documents** tab
  2. Select a document type from the grouped dropdown (optgroups: UAE Residency & Work / Clinical Credentials / General) — pick a non-clinical type, e.g. **Passport**
  3. Enter a document number, an expiry date a few months out, and a note
  4. Click the visible "Click to choose file" drop-zone and pick any small file (the underlying `input[type="file"]` is hidden by design)
  5. Click **Submit**
- **Pass**: New row appears in the documents table with a **"Pending Review"** status badge (admin-uploaded docs do **not** show a "Self-submitted" label — that's only for employee self-uploads). No clinical badge on a non-clinical type.
- **Bug**: cant  enter document number anywhere , should it be randomly generated ? , 
  - **Fixed**: The admin "Upload New Document" form in `EmployeeModal.jsx` genuinely had no Document Number input at all (the field only existed in the DB schema and in `dbToDocument`'s read mapping — never wired up for writes). It's not auto-generated; admin types it in manually (e.g. the passport/licence/certificate number printed on the document), matching how the employee self-upload path already works. Added the field to `uploadForm` state, the form JSX, `handleUpload`'s call, and `uploadEmployeeDocument()` in `storage.js` (new `documentNumber` parameter, now inserted as `document_number`).

---

### DOC-2 · Document expiry triggers the amber/red badge + Dashboard alert - partial 
- **Profile**: Admin (signed in)
- **Setup**: Same employee as DOC-1
- **Steps**:
  1. Repeat DOC-1's upload, this time setting the **expiry date within 60 days** of today (e.g. 30 days out) for a **non-clinical** type (clinical types use a 90-day threshold instead — see DOC-3)
  2. Submit, then look at the new row's expiry badge
  3. Navigate to **Dashboard**
- **Pass**: The document row shows an **amber** "Xd left" badge (≤60d, non-clinical). On the Dashboard, a document-expiry related signal appears (Doc Expiry count on the Employees page stat card, and/or a notification — see A-13 above, which should now also show this alert in the bell panel).
- **Bug**: expirey status shows in the uploaded documents modal , but doesnt come as a notification , outside , like the document expirey page 
  - **Fixed**: Root cause — `generateExpiryNotifications()` in `notificationStorage.js` only ever checked the four **employee-level** compliance fields (`visaExpiry`/`passportExpiry`/`emiratesIdExpiry`/`labourCardExpiry`) for its `document_expiry` notification type, plus a separate `clinical_credential_expiry` check that only looked at `employee_documents` rows whose type was in the clinical set (DHA/DOH/MOH Licence, BLS/ACLS/PALS/NRP/CME). A document uploaded with a *general* type (Passport, Visa, Medical Fitness Certificate, etc.) has its own independent `expiry_date` in the `employee_documents` table — completely disconnected from the employee-level fields — so it never matched either check and produced zero notifications. Same gap existed in `EmployeeManager.jsx`'s **Document Expiry** tab (`DocumentExpiryPanel`) — it also only scanned the four employee-level fields, never `employee_documents` rows, so there was no "document expiry page" surfacing it either, exactly as reported. Fixed both: added a new non-clinical document-expiry notification block (60d/30d/14d thresholds, same pattern as the clinical one), and extended `DocumentExpiryPanel` with a new "Uploaded Documents" group covering all `employee_documents` rows (90d threshold for clinical types, 60d for everything else), including a live count in the "Document Expiry" tab badge.

---

### DOC-3 · Clinical credential type uses the 90-day threshold + Clinical badge - completed 
- **Profile**: Admin (signed in)
- **Setup**: Same employee
- **Steps**:
  1. Upload another document, this time selecting a **Clinical Credentials** optgroup type (e.g. **DHA Licence**)
  2. Set the expiry date to **70 days** from today — far enough that a normal document would still be green, but within the clinical 90-day window
  3. Submit
- **Pass**: The new row shows a cyan **"Clinical"** badge, and the expiry badge is **amber** at 70 days remaining (clinical threshold is 90d, not the normal 60d) — compare against DOC-1/DOC-2's non-clinical document, which would still be green at 70 days.
- **Bug**:

---

### DOC-4 · Verify a pending document - bug → not a bug, retest on Day 12
- **Profile**: Admin (signed in)
- **Setup**: ⏭ **DEFER to Day 12** — see Fixed note below for why.
- **Steps**:
  1. Click the **✓** (verify) button on a pending document row
- **Pass**: Status badge changes to **Verified**.
- **Bug**:after uploading document it is already verified , could it be becuase a admin is uplaoding ?
  - **Fixed**: You guessed the cause correctly — it's by design, not a bug. `sql/024_employee_self_upload.sql` sets `status TEXT NOT NULL DEFAULT 'verified'` on `employee_documents`, and the admin-upload path (`uploadEmployeeDocument()`) never overrides that default. The reasoning: if HR/Admin is the one uploading the document, they've already reviewed it by virtue of uploading it — there's nothing left to verify. The **Verify/Reject** buttons exist specifically for the *employee self-upload* workflow: when an employee uploads their own document via the Employee Portal's Documents tab, that goes through the `employee_submit_document` RPC instead, which explicitly sets `status='pending', submitted_by='employee'` — only those rows need admin review. Since no employee has an activated portal account yet (that happens via self-registration on Day 12), there's currently no way to produce a genuinely-pending document to test against. **Deferred to Day 12**: after an employee registers and uploads a document via their portal, come back here, open that document in the admin Documents tab, and verify it shows "Pending Review" + a "Self-submitted" label, then test ✓ Verify.

---

### DOC-5 · Reject a pending document - bug → not a bug, retest on Day 12
- **Profile**: Admin (signed in)
- **Setup**: ⏭ **DEFER to Day 12** — same root cause as DOC-4.
- **Steps**:
  1. Click the **✗** (reject) button on a pending document row
  2. Enter a rejection reason
  3. Confirm
- **Pass**: Status badge changes to **Rejected**, and the rejection reason is visible on the row.
- **Bug**:after uploading document it is already verified , could it be becuase a admin is uplaoding ?
  - **Fixed**: Same as DOC-4 — admin uploads are auto-verified by design, not a bug. Deferred to Day 12 for the same reason: needs an employee-submitted (`status='pending'`) document, which requires portal self-registration first.

---

### INS-1 · Assign insurance coverage - completed 
- **Profile**: Admin (signed in)
- **Setup**: At least one insurance policy must exist (Day 2's CS-5 — if it was deleted in CS-7, go create one in Company Settings first)
- **Steps**:
  1. Open the employee → **Insurance** tab
  2. Select the policy from the dropdown
  3. Enter Member ID, Card Number, effective date, expiry date
  4. Click **Assign/Update Coverage**
- **Pass**: Saved successfully, the form resets, and an "Assigned" badge appears on the Coverage Assignment card. Reopening the tab pre-populates the form from the saved record.
- **Bug**:

---

### INS-2 · Add a dependant - completed 
- **Profile**: Admin (signed in)
- **Setup**: Same employee, on the Insurance tab
- **Steps**:
  1. Fill the dependant form: Name, Relationship, Date of Birth, Card Number
  2. Click **Add Dependant**
- **Pass**: New row appears in the dependants table with the entered details. The Date of Birth column displays as **DD/MM/YYYY** (formatted via `formatDateUAE`).
- **Bug**:

---

### INS-3 · Delete a dependant - completed 
- **Profile**: Admin (signed in)
- **Setup**: At least one dependant exists (INS-2)
- **Steps**:
  1. Click the delete icon on a dependant row
  2. Confirm
- **Pass**: Dependant row disappears from the table.
- **Bug**:

---

### CON-1 · View current contract status - completed 
- **Profile**: Admin (signed in)
- **Setup**: Same employee, on the **Contracts** tab
- **Steps**:
  1. Open the Contracts tab
- **Pass**: A status card shows the current contract type (Limited/Unlimited), start date, and — for Limited — an end-date countdown. Below it, a contract history table (empty on a fresh employee).
- **Bug**:

---

### CON-2 · Renew a Limited contract - completed 
- **Profile**: Admin (signed in)
- **Setup**: Employee's contract type must be **Limited** (set on Job & Contract tab if not already)
- **Steps**:
  1. On Contracts tab, click **Renew**
  2. An inline confirmation form appears — enter new start/end dates and optional notes
  3. Confirm
- **Pass**: Contract end date updates, a new row appears in the contract history table (action = "renewed"), and the modal stays open (action calls `saveEmployee` directly, not `onSave`).
- **Bug**:

---

### CON-3 · Convert Limited → Unlimited- completed 
- **Profile**: Admin (signed in)
- **Setup**: Employee's contract type is Limited
- **Steps**:
  1. Click **Convert to Unlimited** → confirm
- **Pass**: Contract type badge updates to Unlimited, history row added (action = "converted").
- **Bug**:

---

### CON-4 · Not Renewing (Limited contract) - compkleted 
- **Profile**: Admin (signed in)
- **Setup**: A **different** Limited-contract employee than CON-2/CON-3 (so you don't collide with their renewed/converted state) — or re-set this employee back to Limited first
- **Steps**:
  1. Click **Not Renewing** → confirm
- **Pass**: History row added (action = "not_renewed"). Contract status reflects the decision.
- **Bug**:

---

### CON-5 · Convert Unlimited → Limited - completed 
- **Profile**: Admin (signed in)
- **Setup**: An Unlimited-contract employee (e.g. the one from CON-3 after conversion)
- **Steps**:
  1. Click **Convert to Limited** → fill in the new end date → confirm
- **Pass**: Contract type badge updates to Limited, history row added.
- **Bug**:

---

### CON-6 · Print contract letter - completed 
- **Profile**: Admin (signed in)
- **Setup**: Same employee, Contracts tab
- **Steps**:
  1. Click **Print Letter**
- **Pass**: A new browser window/tab opens with a formatted letter referencing the employee's contract. Any date shown in the letter (e.g. join date, contract end date) is in **DD/MM/YYYY**.
- **Bug**:

---

### PORTAL-1 · Portal Role dropdown
- **Profile**: Admin
- **Setup**: ⏭ **DEFER to Day 12** — the Portal Role `<select>` only renders when `employee?.authUserId` is set, which happens when an employee completes self-registration via "Sign in as Employee / Manager → Register as Employee" — that flow is tested on Day 12. Return here after Day 12's employee registration step: open that employee's Job & Contract tab and confirm the Portal Role dropdown (Employee/Manager) appears and updates immediately on change (no Save button needed — it's a direct RPC call to `setEmployeePortalRole`).
- **Bug**:

---

## 5. PROBATION ACTIONS (Probation employees only)

### PROB-1 · Probation action icon visibility -completed 
- **Profile**: Admin (signed in)
- **Setup**: A Probation-status employee exists (Day 1's D-7 employee, if not already actioned — otherwise create a new one: Add Employee → Job & Contract tab → Employment Status = Probation, Probation End Date = a future date)
- **Steps**:
  1. Go to Employees → Employee List
  2. Locate the Probation employee's row
- **Pass**: A blue **UserCheck** icon button ("Probation actions") appears only on rows with Probation status — not on Active/On Leave rows.
- **Bug**:

---

### PROB-2 · Confirm Active - completed 
- **Profile**: Admin (signed in)
- **Setup**: PROB-1's employee
- **Steps**:
  1. Click the Probation actions icon → ProbationModal opens, showing days remaining/overdue
  2. Click **Confirm Active**
- **Pass**: Employee's status changes to Active, Probation End Date is cleared, row updates in the list.
- **Bug**:

---

### PROB-3 · Extend probation - completed 
- **Profile**: Admin (signed in)
- **Setup**: A Probation-status employee (create a fresh one if PROB-2 already confirmed the last one Active)
- **Steps**:
  1. Open Probation actions → click **Extend**
  2. A date picker appears — choose a new, later end date
  3. Click **Save Extension**
- **Pass**: `probationExtended` flag is set, the new end date is saved and reflected on the employee record.
- **Bug**:

---

### PROB-4 · Terminate from probation - completed 
- **Profile**: Admin (signed in)
- **Setup**: A Probation-status employee (create a fresh one — don't reuse PROB-2/PROB-3's employee)
- **Steps**:
  1. Open Probation actions → click **Terminate**
  2. UAE 14-day notice warning is shown → click **Confirm Terminate**
- **Pass**: Employee is archived (`employmentStatus = 'Terminated'`), disappears from the Employee List tab, and now appears in the **Terminated Employees** tab with a Terminated badge.
- **Bug**:

---

## 6. ARCHIVE EMPLOYEE (direct, non-probation path)

### ARC-1 · Archive an Active employee
- **Profile**: Admin (signed in)
- **Setup**: Any Active employee not already used in PROB-4
- **Steps**:
  1. Click the **trash icon** ("Delete employee") on the row
  2. Confirmation dialog titled **"Archive Employee"** appears → confirm
- **Pass**: Employee disappears from the Employee List tab and appears in the **Terminated Employees** tab with a Terminated badge — not deleted outright (soft-delete: `active=false, employmentStatus='Terminated'`).
- **Bug**:

---

## 7. OFFBOARDING (Terminated Employees tab only) - completed

### OFF-1 · Open the offboarding checklist - completed 
- **Profile**: Admin (signed in)
- **Setup**: A Terminated employee exists (from PROB-4 or ARC-1)
- **Steps**:
  1. Switch to the **Terminated Employees** tab (third tab, `UserX` icon — or click the "Terminated" stat card)
  2. Click the indigo **ClipboardList** icon on a Terminated row (this icon appears only on Terminated rows)
- **Pass**: OffboardingModal opens; a checklist is auto-created/loaded with default clearance tasks (9 hardcoded items, or admin-configured templates if any exist).
- **Bug**:

---

### OFF-2 · Toggle task completion - completed 
- **Profile**: Admin (signed in, OffboardingModal open)
- **Setup**: None
- **Steps**:
  1. Click a task row to toggle it complete
- **Pass**: Checkbox/icon toggles **instantly** (optimistic UI update) before the DB write completes. Reload the modal — the state persists.
- **Bug**:

---

### OFF-3 · Add a custom task - completed 
- **Profile**: Admin (signed in, OffboardingModal open)
- **Setup**: None
- **Steps**:
  1. Use the add-task form to enter a custom task name → submit
- **Pass**: New task appears in the checklist.
- **Bug**:

---

### OFF-4 · Delete a task- completed 
- **Profile**: Admin (signed in, OffboardingModal open)
- **Setup**: At least one task exists
- **Steps**:
  1. Click the trash icon on a task row
- **Pass**: Task is removed from the checklist.
- **Bug**:

---

### OFF-5 · Visa Cancellation Status- completed 
- **Profile**: Admin (signed in, OffboardingModal open)
- **Setup**: None
- **Steps**:
  1. Change the **Visa Cancellation Status** dropdown (not_started → initiated → submitted_gdrfa → cancelled)
- **Pass**: Selection saves without error.
- **Bug**:

---

### OFF-6 · EOS Calculator - completed 
- **Profile**: Admin (signed in, OffboardingModal open)
- **Setup**: None
- **Steps**:
  1. Click **EOS Calculator**
- **Pass**: `EndOfServiceScreen` renders (replaces the modal content — the only modal-within-modal pattern in the app) showing a gratuity breakdown per UAE labour law, based on the employee's service period and basic salary.
- **Bug**:

---

### OFF-7 · Outstanding advances auto-populate DEFF to Day 6 
- **Profile**: Admin (signed in, EndOfServiceScreen open from OFF-6)
- **Setup**: The Terminated employee has an active salary advance with an outstanding balance (create one in Advances if needed — covered properly on Day 6, skip this check if none exists yet and note it)
- **Steps**:
  1. Look at the "Outstanding Salary Advances" field
- **Pass**: Field is pre-populated from the Advances module with hint text "Auto-loaded from Advances module. Edit to override." Field remains editable.
- **Bug**:

---

### OFF-8 · Print Settlement letter - completed 
- **Profile**: Admin (signed in, EndOfServiceScreen open)
- **Setup**: None
- **Steps**:
  1. Click **Print Settlement**
- **Pass**: New browser window opens with the settlement letter, dates shown in DD/MM/YYYY.
- **Bug**:

---

### OFF-9 · Print NOC / Experience Letter - completed 
- **Profile**: Admin (signed in, back in OffboardingModal)
- **Setup**: None
- **Steps**:
  1. Click **Print NOC**, then separately **Print Experience Letter**
- **Pass**: Each opens a new browser window with the correct letter content; the join date (if shown) is in DD/MM/YYYY.
- **Bug**:

---

---

# DAY 4 — Departments · Letter Requests

> **Before you start**
> Be signed in as **Admin**.
> You need at least one employee to exist (e.g. from Day 2's EC-8). Have the Supabase SQL Editor open in a separate tab — you'll need it to seed a test letter request for the LR tests and to unblock the deferred D-6 check.

---

## Deferred from earlier days

### D-6 · Pending letter requests alert and navigation — ⏭ deferred from Day 1, do this now - completed
- **Profile**: Admin
- **Setup**: Run this SQL in **Supabase Dashboard → SQL Editor** to seed a pending letter request (no employee portal needed):
  ```sql
  INSERT INTO letter_requests (user_id, employee_id, letter_type, purpose, status, requested_at)
  SELECT auth.uid(), e.id, 'Salary Certificate - Bank', 'Home loan application', 'pending', now()
  FROM employees e
  WHERE e.user_id = auth.uid()
    AND e.active = true
  LIMIT 1;
  ```
  Then navigate to the **Dashboard** to trigger `generateExpiryNotifications` and refresh the pending letter count.
- **Steps**:
  1. Run the SQL above in Supabase SQL Editor
  2. Return to the app and navigate to **Dashboard** (click "Dashboard" in the sidebar)
  3. Look for an amber alert card near the top of the Dashboard that mentions pending letter requests
  4. Read the alert text
  5. Click the **"View Letter Requests"** link / button inside that alert
- **Pass**: The amber alert says something like "1 letter request pending. Employees are waiting for HR letters to be generated." and clicking it navigates directly to the **Letter Requests** admin page.
- **Bug**: ui issue — the table below the header was too close to the top, messy layout, column headers not legible
  - **Fixed**: Resolved as part of LR-1 — filter buttons moved out of `page-header` into a dedicated tab-btn row below, column headers given `minWidth`, Completed/Rejected tabs added.

---

## 5. DEPARTMENTS

### DEP-1 · Navigate to Departments page - partial  
- **Profile**: Admin (signed in)
- **Setup**: None
- **Steps**:
  1. In the sidebar, click **"Departments"** (GitBranch / network icon, between **Employees** and **Letter Requests**)
- **Pass**: The Departments page loads. The page header shows "Departments". Three tab buttons are visible: **Departments**, **Org Chart**, **Staffing Rules**.
- **Bug**: "+" sign in add department is too high , make it in line with the add department button
  - **Fixed**: Changed button to `display: inline-flex` with `alignItems: center`, increased Plus icon to size 14 with `flexShrink: 0`, tightened gap to 5px in `DepartmentManager.jsx`.

---

### DEP-2 · Add a root-level department - maybe bug 
- **Profile**: Admin (signed in, on Departments page, Departments tab active)
- **Setup**: None — starting with an empty or existing list is fine
- **Steps**:
  1. Click the **"+ Add Department"** button (or equivalent inline form)
  2. Enter a department name, e.g. `Emergency Department`
  3. Leave the **Parent Department** field blank (root level)
  4. Click one of the 10 colour swatches (e.g. red)
  5. Optionally set a **Head Employee** by typing an employee name
  6. Click **Save**
- **Pass**: The new department appears in the tree table at the root level (no `└` prefix). The colour chip in the row matches the swatch you selected.
- **Bug**:

---

### DEP-3 · Add a child department (nested under a parent) - completed 
- **Profile**: Admin (signed in, on Departments → Departments tab)
- **Setup**: DEP-2 must be done so a parent department exists
- **Steps**:
  1. Click **"+ Add Department"**
  2. Enter name `ICU`
  3. Select **Emergency Department** (from DEP-2) as the parent
  4. Pick a different colour swatch
  5. Click **Save**
- **Pass**: `ICU` appears in the tree directly under `Emergency Department` with a `└` prefix indentation. No other rows shift position unexpectedly.
- **Bug**:

---

### DEP-4 · Edit a department (name and head employee) - completed 
- **Profile**: Admin (signed in, on Departments → Departments tab)
- **Setup**: At least one department exists (e.g. Emergency Department from DEP-2)
- **Steps**:
  1. Click the **edit / pencil** icon on the `Emergency Department` row
  2. Change the name to `Emergency & Trauma`
  3. Set or change the Head Employee to any active employee
  4. Click **Save**
- **Pass**: The row now shows `Emergency & Trauma` with the chosen head employee. The child `ICU` row still shows its `└` prefix under the renamed parent.
- **Bug**:

---

### DEP-5 · Colour swatch updates row chip - completed 
- **Profile**: Admin (signed in, on Departments → Departments tab)
- **Setup**: At least one department exists
- **Steps**:
  1. Click the edit icon on any department row
  2. Click a different colour swatch than the current one
  3. Click Save
- **Pass**: The colour chip / badge on the department row changes to the new colour immediately after save.
- **Bug**:

---

### DEP-6 · Delete department with no employees — succeeds - completed 
- **Profile**: Admin (signed in, on Departments → Departments tab)
- **Setup**: Create a throwaway department with no employees assigned (e.g. `Test Dept`). Ensure no employee has their Department field set to `Test Dept`.
- **Steps**:
  1. Click the **trash / delete** icon on the `Test Dept` row
  2. Read the confirmation dialog
  3. Confirm the deletion
- **Pass**: `Test Dept` is removed from the tree. No error message.
- **Bug**:

---

### DEP-7 · Delete department that has employees — guard flash message - completed 
- **Profile**: Admin (signed in, on Departments → Departments tab)
- **Setup**: At least one employee must have their **Department** field set to one of your departments (e.g. set it in EmployeeModal → Job & Contract → Department). Then return to Departments.
- **Steps**:
  1. Click the trash icon on the department that has employees assigned (shows inline confirm buttons ✓ / ✗)
  2. Click the ✓ confirm button
  3. Observe what happens
- **Pass**: A red **flash alert** appears at the top of the page (e.g. "Cannot delete: 1 employee(s) and/or 0 sub-department(s) are still assigned."). The department is **not** deleted. (This is a flash message, not a modal.)
- **Bug**:

---

### DEP-8 · Org Chart tab renders - partial 
- **Profile**: Admin (signed in, on Departments page)
- **Setup**: At least one employee with a Reporting Manager set (so a hierarchy exists). The employees from Day 2 / Day 3 should suffice.
- **Steps**:
  1. Click the **"Org Chart"** tab
- **Pass**: An org chart renders with at least one employee node. Each node shows the employee's name and department. If no reporting relationships exist, a single root node or a flat list is shown.
- **Bug**: no way of seeing that a person is also under a parent deparment , if their under a child , i added ICU under departments but doesnt come in emplyee modal , make sure new deparments are visible , and org chart doesnt change from original department doesnt update , fix these root causes and adress any other issue in this are , be detailed. 
  - **Fixed**: Three root causes addressed: (1) EmployeeModal datalist now shows parent dept context in the suggestion label — "ICU (under Emergency & Trauma)" — while still filling the field with just "ICU" on select; (2) OrgNode dept badge now shows "Emergency & Trauma › ICU" inline when the employee's dept is a child dept, making the hierarchy visible without opening anything; (3) Added a **Refresh** button in the Org Chart toolbar — clicking it reloads employee data from the DB so changes made in EmployeeModal (dept assignment updates) appear without navigating away from DepartmentManager.

---

### DEP-9 · Org Chart search filters nodes - partial 
- **Profile**: Admin (signed in, on Departments → Org Chart tab)
- **Setup**: Org Chart is visible with multiple employee nodes
- **Steps**:
  1. Type part of an employee's name in the **search box** (e.g. first 3 letters)
  2. Observe the chart
- **Pass**: Only the matching employee node(s) remain visible / highlighted. Nodes that do not match are hidden or dimmed.
- **Bug**: new department doesnt show up in filters 
  - **Fixed**: Org Chart department filter dropdown was built exclusively from `employees.department` strings — departments created in the Departments tab but not yet assigned to any employee were invisible. Fixed by merging both sources: `[...new Set([...depts.map(d => d.name), ...employees.map(e => e.department).filter(Boolean)])]`. New departments now appear in the filter immediately after creation.

---

### DEP-10 · Org Chart expand and collapse — retest after DEP-9 fix - bug 
- **Profile**: Admin (signed in, on Departments → Org Chart tab)
- **Setup**: A manager with at least one direct report must exist in the org chart
- **Steps**:
  1. Find a node that has child nodes (a manager)
  2. Click the **collapse (▼)** arrow / chevron on that node
  3. Observe — child nodes should hide
  4. Click the **expand (►)** arrow
  5. Observe — child nodes should reappear
- **Pass**: Children hide on collapse and reappear on expand. The arrow icon toggles between ► and ▼.
- **Bug**:expand and collapse button doesnt do anything 
  - **Fixed**: `depts` prop was passed to the top-level root `OrgNode` call but omitted from the recursive child `OrgNode` calls inside `OrgNode` itself. Child nodes received `depts = undefined`, causing the dept-badge IIFE to throw a TypeError when calling `depts.find(...)`, which silently crashed child rendering and made expand/collapse appear to do nothing. Fixed by adding `depts={depts}` to the recursive `{reports.map(r => <OrgNode ... />)}` call in `DepartmentManager.jsx`.

---

### DEP-11 · Org Chart department filter - completed  
- **Profile**: Admin (signed in, on Departments → Org Chart tab)
- **Setup**: Departments have been created (DEP-2/DEP-3) and at least one employee has a department assigned
- **Steps**:
  1. Click the **department filter dropdown**
  2. Select a specific department (e.g. `Emergency & Trauma`)
- **Pass**: The org chart narrows to show only employees whose department matches the selected one. Employees in other departments are hidden.
- **Bug**:

---

### DEP-12 · Staffing Rules — add a rule - completed  
- **Profile**: Admin (signed in, on Departments page)
- **Setup**: At least one department exists (from DEP-2/DEP-3)
- **Steps**:
  1. Click the **"Staffing Rules"** tab (ShieldCheck icon, 3rd tab)
  2. The rules table loads (may be empty on first use)
  3. In the Add Rule form: type a department name in the **Department** field (the datalist should suggest your departments)
  4. Select **Shift Category** = `Morning`
  5. Set **Min Staff** = `2`
  6. Leave Effective From / To blank
  7. Click **Save**
- **Pass**: A new row appears in the table: the department name, `Morning`, minimum `2`, no dates. No error.
- **Bug**:

---

### DEP-13 · Staffing Rules — edit a rule - completed 
- **Profile**: Admin (signed in, on Departments → Staffing Rules tab)
- **Setup**: DEP-12 must be done (at least one rule exists)
- **Steps**:
  1. Click the **edit / pencil** icon on the rule from DEP-12
  2. Change **Min Staff** from `2` to `3`
  3. Click **Save**
- **Pass**: The rule row updates to show min staff = `3`. No duplicate row is created (upsert on department + shift category).
- **Bug**:

---

### DEP-14 · Staffing Rules — delete a rule - completed 
- **Profile**: Admin (signed in, on Departments → Staffing Rules tab)
- **Setup**: At least one rule exists
- **Steps**:
  1. Click the **trash** icon on any rule row
  2. Confirm if prompted
- **Pass**: The rule row disappears from the table.
- **Bug**:

---

### DEP-15 · Department autocomplete appears in EmployeeModal - completed 
- **Profile**: Admin (signed in)
- **Setup**: At least one department exists in the Departments page (DEP-2/DEP-3). An employee exists.
- **Steps**:
  1. Open any existing employee (click the pencil / edit icon)
  2. Go to the **Job & Contract** tab
  3. Click inside the **Department** text field
  4. Type the first letter(s) of your department name (e.g. `Em`)
- **Pass**: A dropdown datalist suggestion appears showing the matching department(s) (e.g. `Emergency & Trauma`). Selecting it fills the field. Free-text entry still works if you ignore the suggestions.
- **Bug**:

---

## 6. LETTER REQUESTS

### LR-1 · Navigate to Letter Requests page -bug 
- **Profile**: Admin (signed in)
- **Setup**: None (D-6's SQL seed should already have created one pending request — if not, run it now)
- **Steps**:
  1. Click **"Letter Requests"** in the sidebar (between Employees and Payroll, envelope/mail icon)
- **Pass**: The Letter Requests page loads. The page header says "Letter Requests". Tab buttons for **Pending / All / Completed / Rejected** are visible. The request seeded in D-6 appears in the Pending tab.
- **Bug**:i only see pending and , all requests , and the panel below the Letter REquets header is too close and not in line , make it neater  , and the column headers are not very legible 
  - **Fixed**: (1) Added `Completed` and `Rejected` filter tabs alongside Pending and All Requests — filter state now covers all four statuses with per-tab counts. (2) Moved filter buttons out of `page-header` into a dedicated row below the header with `tab-btn` styling for visual consistency with other modules. (3) Added explicit `minWidth` on all column headers so they render at readable widths. (4) Switched date formatting to `formatDateUAE` (DD/MM/YYYY). All changes in `LetterRequestsManager.jsx`.

---

### LR-2 · Filter tabs update the list - completed 
- **Profile**: Admin (signed in, on Letter Requests)
- **Setup**: LR-1 done — at least one pending request exists
- **Steps**:
  1. Click the **Pending** tab — confirm the seeded request is listed
  2. Click **All** — same request should still appear
  3. Click **Completed** — list should be empty (nothing completed yet)
  4. Click **Rejected** — list should be empty
  5. Click **Pending** again to return to the default view
- **Pass**: Each tab shows only the matching status records. Completed and Rejected are empty at this stage.
- **Bug**:

---

### LR-3 · Complete & Print a letter request - completed 
- **Profile**: Admin (signed in, on Letter Requests → Pending tab)
- **Setup**: A pending request exists (from D-6 SQL seed — letter type "Salary Certificate - Bank")
- **Steps**:
  1. On the pending request row, click the **printer / Complete** icon
  2. A new browser window or tab opens
  3. Read the content of the letter
  4. If the print dialog appears automatically — close it (or let it open)
  5. Switch back to the admin tab and check the request list
- **Pass**: The new window contains a properly formatted **Salary Certificate (Bank)** letter with the employee's name, company name, salary details, and today's date in DD/MM/YYYY format. Back in the admin tab, the request's status has changed from **Pending** to **Completed**. It no longer appears in the Pending tab.
- **Bug**:

---

### LR-4 · Completed request appears in Completed tab - cant be checked until LR-1 
- **Profile**: Admin (signed in, on Letter Requests)
- **Setup**: LR-3 done
- **Steps**:
  1. Click the **Completed** tab
- **Pass**: The request completed in LR-3 appears with status "Completed" and a completion timestamp.
- **Bug**:

---

### LR-5 · Seed a second pending request for rejection test - completed 
- **Profile**: Admin (using Supabase SQL Editor)
- **Setup**: The first request was completed in LR-3. We need a fresh pending request to test rejection.
- **Steps**:
  1. In **Supabase SQL Editor**, run:
     ```sql
     INSERT INTO letter_requests (user_id, employee_id, letter_type, purpose, status, requested_at)
     SELECT auth.uid(), e.id, 'NOC', 'Visa renewal', 'pending', now()
     FROM employees e
     WHERE e.user_id = auth.uid()
       AND e.active = true
     LIMIT 1;
     ```
  2. Return to the Letter Requests page and refresh (or switch tabs to trigger a reload)
  3. Click the **Pending** tab
- **Pass**: A new row appears for "NOC" letter type with purpose "Visa renewal" and status Pending.
- **Bug**:

---

### LR-6 · Reject a pending request — reason required - completed
- **Profile**: Admin (signed in, on Letter Requests → Pending tab)
- **Setup**: LR-5 done — the NOC pending request is visible
- **Steps**:
  1. Click the **reject / X** icon on the NOC request
  2. A rejection reason input field appears inline (or a small form)
  3. Try clicking Confirm/Submit **without** entering a reason — observe if it is blocked
  4. Now type a reason, e.g. `Pending further documentation from employee`
  5. Click Confirm / Submit
- **Pass**: The rejection form either blocks submission with an empty reason (ideal) or accepts it. After submission the request row disappears from the Pending tab and status changes to **Rejected**.
- **Bug**: works, but make new column with the reason for rejection next to print in admin and next to status in employee in letter requests
  - **Fixed**: Added a dedicated `Rejection Reason` column in admin `LetterRequestsManager.jsx` (7th column, between Status and Actions) and a `Reason` column in employee `EmpRequests.jsx` (5th column, after Status). Both show the rejection reason in red when rejected, `—` otherwise. Removed the old inline sub-text under the status badge since it now has its own column.

---

### LR-7 · Rejection reason visible in Rejected tab - completed 
- **Profile**: Admin (signed in, on Letter Requests)
- **Setup**: LR-6 done
- **Steps**:
  1. Click the **Rejected** tab
  2. Find the rejected NOC request
  3. Look for the rejection reason text in the row or an expandable detail
- **Pass**: The rejection reason `Pending further documentation from employee` (or whatever you entered) is visible in the row or tooltip.
- **Bug**:

---

---

# DAY 5 — Payroll (full cycle)

> **Before you start**
> At least two active employees must exist with salary data filled in (Basic Salary > 0, Bank Name, Bank Routing Code, IBAN, MOL ID all set). Company MOL Employer ID must also be set in Company Settings.
> All tests use the **Admin** profile.

---

## 7. PAYROLL MODULE

### PAY-1 · Navigate to Payroll Module -c 
- **Profile**: Admin (signed in)
- **Setup**: None
- **Steps**:
  1. Click **"Payroll Module"** in the sidebar
- **Pass**: The Payroll List page loads. A table (or empty state if no runs yet) is visible with columns for Period, Name, Status, Employees, Approval Status, WPS Status. A **`+` New Run** button is present.
- **Bug**:

---

### PAY-2 · Create a new payroll run - bug 
- **Profile**: Admin (on Payroll Module / Payroll List)
- **Setup**: At least two employees with complete salary and bank data exist
- **Steps**:
  1. Click the **`+` New Run** (or **"Create Payroll Run"**) button
  2. Select the current month and year from the period pickers
  3. Enter a payroll name (e.g. `June 2026 Payroll`)
  4. Click **Create**
- **Pass**: The PayrollEditor opens. Every active employee appears as a row. Each row shows their Basic Salary, Housing Allowance, Transport Allowance, and a Net Pay total. The run header shows the period and name you entered. The run is in **Draft** status.
- **Bug**:when the nav bar is extended , the payroll module goes off screen , make it so it is also fuly viewable when the nav bar is extended 
  - **Fixed**: Changed `.page-header` from `height` (fixed 64px) to `min-height` + `flex-wrap: wrap; row-gap: 6px; padding: 10px 22px` so the header expands and action buttons wrap to a second line when the sidebar is extended. Same `flex-wrap/row-gap` applied to `.page-header-actions`.

---

### PAY-3 · Edit salary entries in the run - c 
- **Profile**: Admin (in PayrollEditor, run in Draft)
- **Setup**: PAY-2 done
- **Steps**:
  1. Find one employee row and click into their **Basic Salary** field
  2. Change the value (e.g. add 500)
  3. Observe the **Net Pay** column for that row
  4. Click **Save** (or the save icon)
- **Pass**: Net Pay updates immediately when you change the salary value. After saving, refreshing the page shows the changed value persisted.
- **Bug**:

---

### PAY-4 · Add an allowance and a deduction - bug
- **Profile**: Admin (in PayrollEditor, run in Draft)
- **Setup**: PAY-3 done
- **Steps**:
  1. Click the **Allowances / Deductions** button (or expand the panel) for one employee
  2. Add an **allowance** with a label (e.g. `Overtime`) and an amount (e.g. `200`)
  3. Confirm the Net Pay for that employee increases by 200
  4. Add a **deduction** with a label (e.g. `Parking`) and an amount (e.g. `100`)
  5. Confirm Net Pay decreases by 100 from the previous step
- **Pass**: Net Pay = Basic + Housing + Transport + Allowances − Deductions. Both the allowance and deduction are visible in the panel. Values are saved.
- **Bug**:the housing and transport columns do not make a difference , is that by design or a bug , also on a side not , when the save draft button is clicked nothing idicates it is saved.
  - **Fixed**: (a) Added `housingAllowance` and `transportAllowance` to `computeFinalAllowance()` in `AllowDeductPanel.jsx` — they are now included in the WPS SIF variable allowance and per-row Net Pay total. (b) `handleSaveDraft` in `PayrollEditor.jsx` now calls `setAutoSaved(true)` with a 2-second timeout, showing the "Auto-saved ✓" indicator in the header when Save Draft is clicked.

---

### PAY-5 · Submit for approval (Maker-Checker) - not sure 
- **Profile**: Admin (in PayrollEditor, run in Draft)
- **Setup**: PAY-4 done. Run must still be in Draft status.
- **Steps**:
  1. Click **"Submit for Approval"**
- **Pass**: Approval status changes to **Pending Approval**. A blue info banner appears saying the run is pending approval. All salary input fields become disabled (greyed out — cannot be edited). The **Submit for Approval** button is replaced by **Recall** and **Approve** / **Reject** buttons.
- **Bug**: after clicking submit for aproval , the values are still editable , is that by deisng or a bug
  - **Fixed**: All 8 salary input fields (basicSalary, housingAllowance, transportAllowance, allowance, increment, bonus, otherPay, leaveDeduction) and the +/- click-cells now use `disabled={editingLocked || entry.excluded}` instead of `isLocked`. `editingLocked = isLocked || approvalLocked`, so they lock during both Pending Approval and Approved states, not just after Generate.

---

### PAY-6 · Recall from pending approval -c 
- **Profile**: Admin (in PayrollEditor, run Pending Approval)
- **Setup**: PAY-5 done
- **Steps**:
  1. Click **"Recall"**
- **Pass**: Approval status returns to **Draft**. Salary input fields become editable again. The "Submit for Approval" button reappears.
- **Bug**:

---

### PAY-7 · Reject while pending (with reason) - add feature 
- **Profile**: Admin (in PayrollEditor)
- **Setup**: Re-submit for approval after PAY-6 (so run is Pending Approval again)
- **Steps**:
  1. Click **"Reject"**
  2. An inline rejection reason field appears — enter a reason (e.g. `Incorrect advance deductions`)
  3. Click **Confirm Reject**
- **Pass**: Status returns to **Draft**. An amber rejection banner appears showing the rejection reason. Salary fields are editable again.
- **Bug**: add a feature , where a button on the top bar next to preview SIF , which says , View Changes , which shows all the changes made in teh file withthe name & id of the emplyee with what changes was made 
  - **Fixed**: Added **"View Changes"** button (GitCompare icon) in the PayrollEditor header toolbar. Opens a modal listing every field that differs from the employee's profile defaults, showing Employee name, Field, Default value, This Run value, and Δ (delta). Includes basic salary, housing, transport, allowance, increment, bonus, leave deductions, and any extra allowances/deductions added in the panel. Rows with no changes across all employees show "All entries match employee profile defaults".

---

### PAY-8 · Approve the run - bug 
- **Profile**: Admin (in PayrollEditor, run in Draft after rejection)
- **Setup**: PAY-7 done
- **Steps**:
  1. Click **"Submit for Approval"** again
  2. Click **"Approve"**
- **Pass**: Approval status becomes **Approved**. A green banner appears. Salary fields remain locked (cannot edit an approved run). The **"Generate Payroll"** button becomes visible.
- **Bug**: after being apporved it is still editable 
  - **Fixed**: Same fix as PAY-5 — `editingLocked` now covers Approved state too, so all salary inputs are disabled immediately on Approve.

---

### PAY-9 · Generate payroll (lock the run) -c 
- **Profile**: Admin (in PayrollEditor, run Approved)
- **Setup**: PAY-8 done
- **Steps**:
  1. Click **"Generate Payroll"**
  2. Confirm any prompt that appears
- **Pass**: Run status changes to **Generated** (irreversible). A lock banner appears ("Payroll finalised — locked."). All inputs remain disabled. The WPS Tracking card appears below the lock banner.
- **Bug**:

---

### PAY-10 · Download SIF — clean run (no compliance violations) - feature add 
- **Profile**: Admin (in PayrollEditor, run Generated)
- **Setup**: PAY-9 done. Ensure all employees have valid (non-expired) Emirates ID, Visa, and either no professional licence or a non-expired one.
- **Steps**:
  1. Click **"Download SIF"**
- **Pass**: A `.sif` file downloads immediately. Filename format: `{MOL_EMPLOYER_ID}{YYMMDD}{HHMMSS}.sif`. No modal or warning appeared. WPS status auto-advances to **sif_generated**.
- **Bug**: in the payroll editor if an employee has soemthing that is expiring , it shoild show a warning , as well as whrn genrating the payroll 
  - **Fixed**: Added amber ⚠ warning icon in the employee name cell for any employee whose Visa, Emirates ID, Passport, Labour Card, or Professional Licence expires within 90 days or is already expired. Hovering the icon shows a tooltip listing each expiring document and its date. The existing compliance gate (PAY-11) already blocks SIF download for expired docs; this warning gives earlier visibility during payroll editing.

---

### PAY-11 · Download SIF — compliance gate (expired document) - c
- **Profile**: Admin (in PayrollEditor, run Generated)
- **Setup**: PAY-9 done. Before clicking Download SIF, go to Employees → open one employee → UAE Compliance tab → set their Emirates ID Expiry to a past date (e.g. `01/01/2024`) and Save. Return to the payroll run.
- **Steps**:
  1. Click **"Download SIF"**
  2. The **"Expired Compliance Documents"** modal opens listing the violation
  3. Enter a short reason (e.g. `ok`) — try to submit
  4. Enter a valid reason of 10+ characters (e.g. `Employee renewal in progress`)
  5. Click **Override & Download**
- **Pass**: Step 3 — short reason is blocked (button disabled or error shown, minimum 10 characters required). Step 5 — SIF downloads successfully. The override is recorded (check `compliance_overrides` table in Supabase if needed). After testing, restore the employee's Emirates ID expiry to a valid future date.
- **Bug**:

---

### PAY-12 · Preview SIF -c
- **Profile**: Admin (in PayrollEditor, run Generated, SIF already downloaded)
- **Setup**: PAY-10 done
- **Steps**:
  1. Click **"Preview SIF"** (eye icon button in the top toolbar)
- **Pass**: A parsed preview table appears showing each employee's MOL ID, name, IBAN, bank routing code, and net pay amount in AED. All employees from the run are listed.
- **Bug**:

---

### PAY-13 · Download all payslips -c
- **Profile**: Admin (in PayrollEditor, run Generated)
- **Setup**: PAY-9 done
- **Steps**:
  1. Click **"All Payslips"** (document icon button in the top toolbar)
- **Pass**: A PDF is generated (or a separate PDF per employee). Each payslip shows the company name, employee name, period, and a salary breakdown (basic, housing, transport, allowances, deductions, net pay). Dates are in DD/MM/YYYY format.
- **Bug**:

---

### PAY-14 · WPS Tracking — submit and confirm - feature add  
- **Profile**: Admin (in PayrollEditor, run Generated, WPS status sif_generated)
- **Setup**: PAY-10 done
- **Steps**:
  1. In the **WPS Tracking** section, enter a **WPS Reference No** (e.g. `WPS-2026-001`)
  2. Enter today's date as the **Submission Date**
  3. Click **"Save WPS Status"** — confirm it saves
  4. Change the WPS status dropdown to **Submitted** → Save
  5. Change to **Confirmed** → enter a **Confirmation Date** → Save
- **Pass**: Each save persists — refreshing the page shows the saved WPS reference, dates, and status. Status badge in PayrollList updates accordingly.
- **Bug**: , make it so you can set all to "paid" , and you can searhc for specific employees 
  - **Fixed**: Added a **"✓ Mark All Paid"** button and a **search/filter input** above the per-employee WPS payment status list. "Mark All Paid" sets every active employee's WPS status to `paid` in one click. The search input filters the displayed employees by name in real-time (does not affect save — all statuses still persist including filtered-out employees).

---

### PAY-15 · WPS partial rejection — corrected SIF
- **Profile**: Admin (in PayrollEditor, WPS status Confirmed)
- **Setup**: PAY-14 done
- **Steps**:
  1. In the per-employee WPS payment status table, change one employee's payment status to **Rejected**
  2. Optionally enter a rejection reason for that employee
  3. Click **"Save WPS Status"**
  4. Look for a **"Download Corrected SIF"** button
  5. Click it
- **Pass**: A corrected SIF file downloads containing only the rejected employee(s). Filename is prefixed with `CORRECTED_` followed by the standard format: `CORRECTED_{MOLID}{YYMMDD}{HHMMSS}.sif`.
- **Bug**:

---

### PAY-16 · Run appears in Payroll List with correct status -c 
- **Profile**: Admin
- **Setup**: PAY-15 done
- **Steps**:
  1. Click **"Payroll Module"** in the sidebar to return to the Payroll List
- **Pass**: The run created today appears in the list. Columns show: period (e.g. `June 2026`), status badge **Generated**, approval status **Approved**, WPS status badge. Clicking the row re-opens the PayrollEditor.
- **Bug**:

---

### PAY-17 · Dashboard reflects pending approval (regression check) -c 
- **Profile**: Admin
- **Setup**: Create a **second** new payroll run for a different month and submit it for approval but do NOT approve it — leave it in Pending Approval state.
- **Steps**:
  1. Click **Dashboard** in the sidebar
  2. Look for a blue info alert about pending payroll approval
- **Pass**: A blue alert card is visible on the Dashboard saying there is a payroll run pending approval, with a link to navigate to it.
- **Bug**:

---

---

---

# DAY 6 — Advances · Expenses

> **Before you start**
> Be signed in as **Admin**. Make sure the dev server is running (`npm run dev`) — all Day 5 fixes are now in the codebase.
> Clear the "Deferred from earlier days" section first, then proceed to Advances (ADV-1) and Expenses (EXP-1).

---

## Deferred from earlier days

### A-13 · Notification bell shows unread count badge — ⏭ overdue from Day 3 -c
- **Profile**: Admin (signed in)
- **Setup**: DOC-2 must be done (a document with an expiry within 60 days was uploaded, so a `document_expiry` notification was created). The probation/contract/credential notifications were generated during Day 1's D-7/D-8 setup. Navigate to Dashboard once before testing the bell — Dashboard load is what triggers `generateExpiryNotifications` async.
- **Steps**:
  1. Click **Dashboard** in the sidebar (this triggers `generateExpiryNotifications` in the background)
  2. Wait **3 seconds** for the async notification check to run (it fires after `setLoading(false)`)
  3. Look at the **bell icon (🔔)** in the sidebar — does a red count badge appear on it?
  4. Click the bell icon — the notification panel slides in from the right
  5. Read the list of notifications: look for entries about document expiry, probation ending, contract expiry, and/or payslip available
  6. Click one notification entry to mark it as read
  7. Confirm: the red dot on that entry disappears, and the badge count on the bell icon decrements
  8. Click **"Mark all read"** (if available) and confirm the badge clears
- **Pass**: A red badge with a count (≥ 1) appears on the bell icon. Clicking it opens a right-side panel listing notifications grouped with emoji prefixes (📄 doc expiry, ⏳ probation, 📋 contract, etc.). Individual notifications can be marked read — the count badge decrements. "Mark all read" clears the badge entirely.
- **Bug**:

---

### PAY-RETEST · Re-verify Day 5 fixes and new features before continuing -c
- **Profile**: Admin (signed in, on Payroll Module)
- **Setup**: The payroll run generated on Day 5 (PAY-9) must exist. A second run in Pending Approval state may exist from PAY-17. All fixes below were applied this session — you need to run the app to verify them.
- **Steps** — work through each fix in order:
  1. **PAY-2 (header overflow)**: Expand the sidebar by hovering over it so it shows full nav labels. Open the PayrollEditor for the generated run. Confirm the top toolbar (with Download, Preview, All Payslips, View Changes, etc.) wraps onto a second line if needed rather than spilling outside the page.
  2. **PAY-4a (housing/transport → net pay)**: Create a **new Draft** payroll run (different period). In the salary table, change one employee's **Housing Allowance** or **Transport Allowance** value. Confirm the **Net Pay** column for that employee updates immediately.
  3. **PAY-4b (Save Draft feedback)**: Click **Save Draft**. Confirm a short green **"Saved!"** message or flash appears in the toolbar for ~2 seconds, then disappears.
  4. **PAY-7 (View Changes modal)**: In the same Draft run, modify at least one employee's salary or add a bonus. Click the **View Changes** button (GitCompare icon, in the toolbar). Confirm a modal opens showing a table with columns: Employee, Field, Default, This Run, Δ. The delta column shows the difference in green (positive) or red (negative).
  5. **PAY-5 (inputs lock on Submit)**: Click **Submit for Approval**. After the run moves to Pending Approval, try to edit any salary input in the table. Confirm all inputs are **greyed out / disabled** (the `editingLocked` flag is now true for both Pending and Approved states).
  6. **PAY-8 (inputs still locked on Approve)**: Click **✓ Approve**. After the run moves to Approved, again try to edit any salary input. Confirm inputs remain disabled.
  7. **PAY-10 (expiry warnings)**: If any employee has a document with an expiry within 90 days (e.g. the one uploaded in DOC-2/DOC-3), locate that employee's row in the payroll table. Confirm a **yellow ⚠ warning icon** appears next to their name. Hover over it to see the tooltip listing which document is expiring and when.
  8. **PAY-14 (WPS — Mark All Paid + search)**: Open the Day 5 generated run. In the WPS Tracking section, confirm a **search input** and a **"✓ Mark All Paid"** button appear above the per-employee status list. Type part of an employee name to filter the list. Click Mark All Paid and confirm all status dropdowns switch to `paid`.
- **Pass**: Each sub-step passes without errors. Inputs are disabled exactly when `isLocked || approvalLocked` is true. Net pay reflects housing and transport. View Changes modal shows meaningful rows.
- **Bug**:

---

### PAY-12, PAY-13, PAY-15 · Untested Day 5 items — complete these before advancing -c 
- **Profile**: Admin
- **Setup**: The generated run from PAY-9 must exist (WPS status at least `sif_generated` if PAY-14 was completed).
- **Note**: These items have no completion marker in the Day 5 checklist. Tick them off here, then mark them complete in the Day 5 section above.
- **Steps**:
  1. **PAY-12 (Preview SIF)**: Open the generated run → click the **eye icon** ("Preview SIF") in the toolbar. A parsed preview table must appear showing each employee's MOL ID, name, IBAN, bank routing code, and net pay in AED.
  2. **PAY-13 (Download all payslips)**: Click the **"All Payslips"** button (document icon). A PDF (or ZIP of PDFs) must download. Each payslip must show company name, employee name, period, and salary breakdown. Dates must be **DD/MM/YYYY**.
  3. **PAY-15 (WPS partial rejection → corrected SIF)**: In the WPS Tracking section, change one employee's payment status to **Rejected**, add an optional rejection reason, click **Save WPS Status**. A **"Download Corrected SIF"** button must appear. Click it — a SIF file downloads with the `CORRECTED_` prefix in the filename, containing only the rejected employee.
- **Pass**: All three sub-items pass as described.
- **Bug**:

---

## 8. ADVANCES

### ADV-1 · Navigate to Advances — list and stat cards -c
- **Profile**: Admin
- **Setup**: At least one active employee exists (from Day 2)
- **Steps**:
  1. Click **Advances** in the sidebar
  2. Wait for the page to load
- **Pass**: Three stat cards visible: **Pending Requests** (count, amber if > 0), **Active Advances** (count), **Total Outstanding** (AED balance). A **+ New Advance** button is in the top-right. If no advances exist yet, the list area shows an empty state rather than an error.
- **Bug**:

---

### ADV-2 · Create an admin-initiated advance -c
- **Profile**: Admin (on Advances page)
- **Setup**: ADV-1 done. At least one active employee exists.
- **Steps**:
  1. Click **+ New Advance**
  2. Select any active employee from the **Employee** dropdown
  3. Enter **Amount**: `3000`
  4. Leave **Repayment Months** as `3` (default)
  5. Observe the **Monthly Deduction** field — it should auto-calculate
  6. Enter **Reason**: `Salary advance for home repairs`
  7. Click **Save Advance**
- **Pass**: Monthly deduction auto-shows `1000.00` (3000 ÷ 3). After saving, the form closes, the advance appears in the list with status **Active** (blue badge). The **Active Advances** stat card increments by 1. The **Total Outstanding** increases by 3000.
- **Bug**:

---

### ADV-3 · Expand advance row — view repayment schedule -c
- **Profile**: Admin (on Advances page)
- **Setup**: ADV-2 done (at least one active advance exists)
- **Steps**:
  1. Find the advance created in ADV-2
  2. Click the **chevron / expand icon** on that row
- **Pass**: A repayment sub-table appears below the row. It may be empty (no payroll run has processed the deduction yet) or show processed months. The monthly deduction amount matches what was set (e.g. AED 1,000.00 per month). Clicking the chevron again collapses the row.
- **Bug**:

---

### ADV-4 · Approve a pending advance request - employee potal advances ui issue 
- **Profile**: Admin (on Advances page)
- **Setup**: ADV-1 done. Run this SQL in **Supabase SQL Editor** to seed a pending advance (simulates an employee self-request):

  ```sql
  INSERT INTO salary_advances
    (user_id, employee_id, amount, repayment_months, monthly_deduction, outstanding_balance, reason, status)
  SELECT c.user_id, e.id, 2000, 4, 500.00, 2000,
         'Employee-requested advance for school fees', 'pending'
  FROM employees e
  JOIN companies c ON c.user_id = e.user_id
  WHERE e.employment_status NOT IN ('Terminated')
  ORDER BY e.name LIMIT 1;
  ```

- **Steps**:
  1. Refresh the Advances page (or navigate away and back)
  2. Locate the **Pending** advance in the list (amber badge)
  3. Click the **✓ Approve** button on that row
- **Pass**: A confirm dialog appears. Confirming changes the status to **Active** (blue badge). The **Pending Requests** stat card decrements by 1. The **Active Advances** stat card increments by 1.
- **Bug**: i know you gave the sql but i used the employee portal anyways , the advances module , the panels are sized correctly , text comes outside the panels , and despite not having any monthly deductions bring done , the progress bar is already preogressed , make the ui neater 
  - **Fixed**: All `emp-card` sections in `EmpAdvances.jsx` now have `padding: '16px 18px'` so content no longer touches the card edges. Progress bar formula changed from `Math.max(5, ...)` to `Math.max(0, ...)` — a brand-new advance with no repayments now correctly shows 0% instead of 5%. Dates in pending/historical sections now use `formatDateUAE()` instead of `toLocaleDateString('en-AE')`. Rejection reason shown in cancelled past advances if one was recorded.

---

### ADV-5 · Reject (cancel) a pending advance request
- **Profile**: Admin (on Advances page)
- **Setup**: ADV-4 done. Seed a second pending advance using the same SQL as ADV-4 (re-run it to insert a second row).
- **Steps**:
  1. Locate the second pending advance (amber badge)
  2. Click the **✗ Reject** button on that row
- **Pass**: A confirm dialog asks "Reject advance request for AED 2,000?" Confirming changes the status to **Cancelled** (grey badge). The **Pending Requests** stat card decrements.
- **Bug**:

---

### ADV-6 · Cancel an active advance - add feature 
- **Profile**: Admin (on Advances page)
- **Setup**: ADV-2 done (at least one Active advance exists)
- **Steps**:
  1. Find an **Active** advance (the one created in ADV-2 OR the one approved in ADV-4)
  2. Click the **✗ Cancel** button on that row
- **Pass**: A confirm dialog appears ("Cancel this advance? This cannot be undone."). Confirming changes the status to **Cancelled**. The **Active Advances** stat card decrements. Total Outstanding reduces accordingly.
- **Bug**: when rejecting add a reason to be rejected 
  - **Fixed**: Replaced `window.confirm()` for both Reject (pending advances) and Cancel (active advances) with an inline form row that expands below the advance row. The form has a text input for an optional reason and a confirm button. The reason is stored in a new `rejection_reason` column on `salary_advances` (run `sql/036_advance_rejection_reason.sql` in Supabase SQL Editor). Employees see the rejection reason next to cancelled advances in their portal's "Past Advances" section.

---

### ADV-7 · Manually settle an active advance -c 
- **Profile**: Admin (on Advances page)
- **Setup**: At least one **Active** advance must remain (do not cancel all of them — if ADV-6 cancelled the only active one, create another via ADV-2)
- **Steps**:
  1. Find an **Active** advance
  2. Click the **✓ Settle** button on that row
- **Pass**: A confirm dialog appears ("Mark this advance as fully settled?"). Confirming changes the status to **Settled** (green badge). The **Total Outstanding** balance reduces by the advance's outstanding amount.
- **Bug**:

---

### ADV-8 · Filter tabs update correctly -c 
- **Profile**: Admin (on Advances page)
- **Setup**: ADV-2 through ADV-7 done (various statuses now exist)
- **Steps**:
  1. Click each filter tab: **All** · **Pending** · **Active** · **Settled** · **Cancelled**
- **Pass**: Each tab shows only advances with the matching status. The "All" tab shows everything. Counts displayed in each tab match the actual records visible.
- **Bug**:

---

## 9. EXPENSES

### EXP-1 · Navigate to Expenses — stat cards and empty / seeded state -c 
- **Profile**: Admin
- **Setup**: ADV-8 done (Expenses nav item is between Advances and Leave)
- **Steps**:
  1. Click **Expenses** in the sidebar
  2. Wait for page to load
- **Pass**: Three stat cards: **Pending Claims** (count + AED total if > 0), **Approved (Unpaid)** (AED total), **Total Paid** (AED, all time). Filter tabs visible: All · Pending · Mgr Approved · HR Approved · Paid · Rejected. If no claims exist yet, the Pending tab shows an empty state with a note saying employees can submit via their portal.
- **Bug**:

---

### EXP-2 · Seed test expense data - ui issues in expenses for employee protal 
- **Profile**: Admin
- **Setup**: EXP-1 done. Run both SQL statements below in **Supabase SQL Editor** to insert test claims:

  ```sql
  -- Claim 1: pending
  INSERT INTO expense_claims
    (user_id, employee_id, category, amount, expense_date, description, status)
  SELECT c.user_id, e.id, 'meals', 350, CURRENT_DATE - INTERVAL '2 days',
         'Team lunch — manual test', 'pending'
  FROM employees e JOIN companies c ON c.user_id = e.user_id
  WHERE e.employment_status NOT IN ('Terminated') ORDER BY e.name LIMIT 1;

  -- Claim 2: manager_approved (simulates multi-level flow)
  INSERT INTO expense_claims
    (user_id, employee_id, category, amount, expense_date, description,
     status, manager_approved_at, manager_approved_by)
  SELECT c.user_id, e.id, 'transportation', 180, CURRENT_DATE - INTERVAL '3 days',
         'Taxi to client — manual test', 'manager_approved',
         NOW() - INTERVAL '1 day', 'Manager Portal (seeded)'
  FROM employees e JOIN companies c ON c.user_id = e.user_id
  WHERE e.employment_status NOT IN ('Terminated') ORDER BY e.name LIMIT 1;
  ```

- **Steps**:
  1. Refresh the Expenses page
  2. Check the **Pending** tab and **Mgr Approved** tab
- **Pass**: Claim 1 appears in the Pending tab with status badge **Pending** (amber). Claim 2 appears in the Mgr Approved tab with status badge **Mgr Approved** (blue). The **Pending Claims** stat card now shows count = 1 with AED 350.00. Filter tabs highlight with counts.
- **Bug**: same ui issue text come outside boxes , when new clain etc clicked , make it neater 
  - **Fixed**: Added `padding: '16px 18px'` to the summary card, form card, and all `ClaimSection` cards in `EmpExpenses.jsx`. Also added `manager_approved` and `manager_rejected` to `STATUS_BADGE` / `STATUS_LABEL` maps and added separate sections for each in the portal view — claims in those states previously showed no label and no section heading. HR-approved claims now show "HR Approved — Awaiting Payroll" to distinguish them from manager-only approval.

---

### EXP-3 · Approve a pending expense claim (HR approval) -c , but add to a recheck later list 
- **Profile**: Admin (on Expenses page, Pending tab)
- **Setup**: EXP-2 done
- **Steps**:
  1. Stay on the **Pending** filter tab
  2. Find the `meals / AED 350` claim
  3. Click the **✓ Approve** button on that row
- **Pass**: A green success flash appears ("Claim approved."). The claim's status badge changes to **HR Approved** (green). It disappears from the Pending tab. Switching to the HR Approved tab shows it there. The **Approved (Unpaid)** stat card increases by AED 350.00.
- **Bug**:

---

### EXP-4 · Approve a Manager-Approved claim (final HR sign-off) deffer to when manager portal work is being done 
- **Profile**: Admin (on Expenses page, Mgr Approved tab)
- **Setup**: EXP-2 done (the `transportation / AED 180` claim has status `manager_approved`)
- **Steps**:
  1. Click the **Mgr Approved** filter tab
  2. Find the `transportation / AED 180` claim
  3. Click the **✓ Approve** button
- **Pass**: Claim moves to HR Approved status. Flash message confirms success. The Mgr Approved badge count clears.
- **Bug**:

---

### EXP-5 · Reject an expense claim (with reason)  -c
- **Profile**: Admin (on Expenses page)
- **Setup**: EXP-3 done. Seed one more pending expense first:

  ```sql
  INSERT INTO expense_claims
    (user_id, employee_id, category, amount, expense_date, description, status)
  SELECT c.user_id, e.id, 'other', 500, CURRENT_DATE, 'Extra test claim', 'pending'
  FROM employees e JOIN companies c ON c.user_id = e.user_id
  WHERE e.employment_status NOT IN ('Terminated') ORDER BY e.name LIMIT 1;
  ```

- **Steps**:
  1. Go to the **Pending** tab — the extra claim should appear
  2. Click the **✗ Reject** icon on that claim
  3. An inline form row appears — leave the reason blank and try to confirm
  4. Enter a reason: `Duplicate submission`
  5. Click **Reject**
- **Pass**: Step 3 — the Reject button is disabled (blank reason not accepted). Step 5 — success flash appears. Claim status changes to **Rejected** (red badge). The claim disappears from Pending tab and appears in the Rejected tab. The rejection reason is stored (visible if you query `expense_claims.rejection_reason`).
- **Bug**:

---

### EXP-6 · Delete an expense claim -c
- **Profile**: Admin (on Expenses page)
- **Setup**: EXP-5 done. At least one claim should remain visible (e.g. the approved ones from EXP-3/4).
- **Steps**:
  1. Click **All** filter tab to see all claims
  2. Find the **Rejected** claim from EXP-5
  3. Click the **trash icon** (Delete) on that row
  4. A confirmation dialog appears — click **Delete** / confirm
- **Pass**: Claim is permanently removed from the list. Flash message confirms "Claim deleted." The All tab count decrements.
- **Bug**:

---

### EXP-7 · Filter tabs and stat card accuracy -c
- **Profile**: Admin (on Expenses page)
- **Setup**: EXP-3 through EXP-6 done (various statuses now exist)
- **Steps**:
  1. Click each filter tab in sequence: **All** · **Pending** · **Mgr Approved** · **HR Approved** · **Paid** · **Rejected**
  2. Note the counts shown on each tab
  3. Verify the stat cards match: **Pending Claims** count, **Approved (Unpaid)** AED total, **Total Paid** AED total
- **Pass**: Each tab shows only claims with that status. Badge counts on Pending and Mgr Approved tabs match the actual visible rows. Stat card values match the filtered totals. The Paid tab is likely empty (expenses become "Paid" only when payroll runs mark them paid — covered in a later payroll cycle).
- **Bug**:

---

---

# DAY 7 — Leave (all 5 tabs)

> **Before you start**
> All tests use the **Admin** profile unless stated otherwise.
> Employees from Days 2–3 must exist. The test data seeds below create leave requests in various states — run each SQL block in **Supabase SQL Editor** before the step that needs it.

---

## Deferred from earlier days

No items were explicitly deferred to Day 7 from Days 1–6.
*(EXP-4 — Manager-Approved expense HR sign-off — is deferred to Day 11 when the Manager Portal is tested.)*

---

## 10. LEAVE

### L-1 · Navigate to Leave — Overview tab loads -c 

- **Profile**: Admin
- **Setup**: At least one active employee exists (from Day 2). No leave data needed — the module should render cleanly even with no requests.
- **Steps**:
  1. Click **Leave** in the sidebar
  2. Wait for the page to load (the default tab is **Overview**)
  3. Observe the stat card area at the top
  4. Observe the **"Today's Absences"** section below
- **Pass**: Stat cards render for each leave type (Annual Leave, Sick Leave, Hajj Leave, etc.) showing "X days taken" and "Balance: Y days" (or computed accrual). If no leave has been taken, values are 0 but cards are visible. The "Today's Absences" section either shows a list of employees on approved leave today, or an empty-state message — it never shows an error.
- **Bug**:

---

### L-2 · Seed leave test data -c 

- **Profile**: Admin
- **Setup**: L-1 done. Run all three SQL blocks below in **Supabase SQL Editor**. Each targets the first non-Terminated employee's Annual Leave type.
- **Steps**:

  ```sql
  -- Block A: One Pending request (starts 10 days from now)
  INSERT INTO leave_requests
    (user_id, employee_id, leave_type_id, leave_type_code, start_date, end_date,
     days_requested, status, reason)
  SELECT c.user_id, e.id, lt.id, lt.code,
         CURRENT_DATE + INTERVAL '10 days',
         CURRENT_DATE + INTERVAL '11 days',
         2, 'Pending', 'Manual test — Pending leave'
  FROM employees e
  JOIN companies c ON c.user_id = e.user_id
  JOIN leave_types lt ON lt.user_id = c.user_id AND lt.name ILIKE '%Annual%'
  WHERE e.employment_status NOT IN ('Terminated')
  ORDER BY e.name LIMIT 1;
  ```

  ```sql
  -- Block B: One ManagerApproved request (starts 20 days from now)
  INSERT INTO leave_requests
    (user_id, employee_id, leave_type_id, leave_type_code, start_date, end_date,
     days_requested, status, reason,
     manager_approved_at, manager_approved_by, approval_level_required)
  SELECT c.user_id, e.id, lt.id, lt.code,
         CURRENT_DATE + INTERVAL '20 days',
         CURRENT_DATE + INTERVAL '22 days',
         3, 'ManagerApproved', 'Manual test — ManagerApproved leave',
         NOW() - INTERVAL '1 day', 'Test Manager', 2
  FROM employees e
  JOIN companies c ON c.user_id = e.user_id
  JOIN leave_types lt ON lt.user_id = c.user_id AND lt.name ILIKE '%Annual%'
  WHERE e.employment_status NOT IN ('Terminated')
  ORDER BY e.name LIMIT 1;
  ```

  ```sql
  -- Block C: One already-Approved request (starts 5 days ago — so it shows on Calendar)
  INSERT INTO leave_requests
    (user_id, employee_id, leave_type_id, leave_type_code, start_date, end_date,
     days_requested, status, reason)
  SELECT c.user_id, e.id, lt.id, lt.code,
         CURRENT_DATE - INTERVAL '5 days',
         CURRENT_DATE - INTERVAL '4 days',
         2, 'Approved', 'Manual test — past Approved leave'
  FROM employees e
  JOIN companies c ON c.user_id = e.user_id
  JOIN leave_types lt ON lt.user_id = c.user_id AND lt.name ILIKE '%Annual%'
  WHERE e.employment_status NOT IN ('Terminated')
  ORDER BY e.name LIMIT 1;
  ```

  4. After running all three blocks, refresh the Leave page (navigate away and back)
  5. Click the **Requests** tab
- **Pass**: Three leave requests appear in the Requests table — one with a **Pending** amber badge, one with a **ManagerApproved** blue badge, and one with an **Approved** green badge. The Overview stat cards now show days taken > 0 for Annual Leave (the past Approved request counts).
- **Bug**:

---

### L-3 · Requests tab — Approve a Pending leave request -c 

- **Profile**: Admin (on Leave → Requests tab)
- **Setup**: L-2 done (the Pending request from Block A must be visible)
- **Steps**:
  1. Locate the **Pending** request (amber badge, dated ~10 days from now)
  2. Click the **✓ Approve** button on that row
  3. Observe the status badge and the Approved By column
- **Pass**: The status badge changes to **Approved** (green). The **Approved By** column shows the admin's name or email. The **Pending** count in the Overview stat card decrements. No page error.
- **Bug**:

---

### L-4 · Requests tab — Reject a Pending leave request (with comment) - bug

- **Profile**: Admin (on Leave → Requests tab)
- **Setup**: L-3 done. Seed a second Pending request by re-running Block A from L-2 (it will insert another row).
- **Steps**:
  1. Refresh the Requests tab — a new Pending request should appear
  2. Click the **✗ Reject** button on the new Pending row
  3. A text area / comment field appears — leave it blank and try to confirm
  4. Enter comment: `Annual leave quota exceeded this period`
  5. Click **Reject** / confirm
- **Pass**: Step 3 — the reject confirmation is blocked or the button is disabled when the comment is empty (comment is required). Step 5 — the status changes to **Rejected** (red badge). The rejection comment appears in the row (or in a tooltip). The employee's leave balance is **not** deducted for a rejected request.
- **Bug**: there are two columns of each leaeve in the balnacens pannel and calender , and the balancecs are not updating 
  - **Fixed**: React 18 StrictMode double-mounts components, causing two concurrent `loadAll()` calls → two concurrent `seedDefaultLeaveTypes()` → duplicate rows inserted. Fixed with a module-level `_seedingTypes` boolean lock in `leaveStorage.js` and code-level deduplication in `getLeaveTypes()` (filters by code using a Set). Also moved `initialiseLeaveModule()` out of `loadAll()` (was running on every approval/refresh) into the `useEffect` so it only runs once on mount.

---

### L-5 · Requests tab — Final OK on a ManagerApproved request -c 

- **Profile**: Admin (on Leave → Requests tab)
- **Setup**: L-2 done (the ManagerApproved request from Block B must be visible with blue badge)
- **Steps**:
  1. Locate the **ManagerApproved** request (blue badge, dated ~20 days from now)
  2. Confirm the row shows **"Mgr: Test Manager"** (or similar) in the Approved By column
  3. Click the **"Final OK"** button (HR final sign-off) on that row
- **Pass**: Status changes to **Approved** (green). The Approved By column now shows the HR admin's name for final sign-off. The employee's leave balance is deducted. The blue ManagerApproved badge is gone.
- **Bug**:

---

### L-6 · Requests tab — Status badge colours and Approved By column -c

- **Profile**: Admin (on Leave → Requests tab)
- **Setup**: L-3 through L-5 done (you now have Approved, Rejected, and possibly a ManagerApproved row)
- **Steps**:
  1. Scan all visible rows and their status badges:
     - Pending → amber badge
     - ManagerApproved → blue badge (if any remain)
     - Approved → green badge
     - Rejected → red badge
  2. For any Approved row that was pre-approved by manager, check the **Approved By** column shows `Mgr: Test Manager`
- **Pass**: All badge colours match the legend. Rows approved via manager-pre-approval show the `Mgr: {name}` prefix in the Approved By column. No badge shows a raw status string like `"ManagerApproved"` (must be human-readable).
- **Bug**:
  - **Fixed**: The **Status** filter dropdown in the Requests tab was missing `Manager Approved` and `Manager Rejected` options — these statuses existed in the data but were unreachable via the filter. Added both options to the `<select>` in `LeaveManager.jsx`.

---

### L-7 · Calendar tab — monthly grid renders with approved leave -c

- **Profile**: Admin (on Leave)
- **Setup**: L-3 and L-5 done (at least 2 Approved requests now exist — one past, one future)
- **Steps**:
  1. Click the **Calendar** tab (third tab)
  2. Observe the monthly grid
  3. Navigate to the **current month** if not already shown
- **Pass**: The grid shows a row per employee with their name on the left. Days with Approved leave are highlighted in the leave type's colour (e.g. Annual Leave might be blue). The past approved request (Block C) shows as coloured cells if the current month contains those dates (or navigate to the correct month). The grid has day-number headers across the top.
- **Bug**:

---

### L-8 · Calendar tab — month navigation and department filter -c

- **Profile**: Admin (on Leave → Calendar tab)
- **Setup**: L-7 done
- **Steps**:
  1. Click the **◄** (previous) button — the grid redraws for the previous month
  2. Click **►** (next) twice — forward two months
  3. Confirm the month/year label updates with each click
  4. Open the **Department** dropdown — select a department that has employees
  5. Confirm only employees from that department appear in the grid
  6. Reset department to "All"
- **Pass**: Month navigation works without errors — the grid re-renders for each month. The department filter hides employees from other departments. "All" restores all employees. No blank or broken grid at any point.
- **Bug**:

---

### L-9 · Calendar tab — print - bug 

- **Profile**: Admin (on Leave → Calendar tab)
- **Setup**: L-7 done (calendar is visible with data)
- **Steps**:
  1. Click the **Print** button in the Calendar tab toolbar
- **Pass**: The browser print dialog opens. The print preview shows the calendar grid scoped to the `#calendar-print-area` div — sidebar and other page chrome are not included in the print area.
- **Bug**: print format is messed up , search panels  header etc still visible , need just the calender 
  - **Fixed**: Added `id="calendar-print-area"` to the calendar `<div className="card">` in `LeaveManager.jsx`. Added `@media print` CSS at the end of `index.css` that hides `body *` and shows only `#calendar-print-area` and its children, positioned absolutely to fill the page.

---

### L-10 · Balances tab — loads and reflects approvals - bug

- **Profile**: Admin (on Leave)
- **Setup**: L-3 and L-5 done (at least 2 requests Approved — total ≥ 5 days taken for Annual Leave)
- **Steps**:
  1. Click the **Balances** tab
  2. Observe the table: one row per employee, one column per leave type
  3. Find the employee whose requests you approved — check their **Annual Leave** row
- **Pass**: The table loads without error. Each cell shows days taken + remaining balance. The Annual Leave "days taken" for the test employee reflects the approvals from L-3 and L-5 (2 + 3 = 5 days taken). Numbers are consistent with the Requests tab — no discrepancy.
- **Bug**: doesnt work (duplicate leave type columns prevented balance display)
  - **Fixed**: Root cause was the same as L-4 — duplicate rows from React 18 double-mount. The deduplication + init-once fixes for L-4 resolve this too. Balances now recalculate from the correct single set of leave types.

---

### L-11 · Settings tab — leave year, weekend, and carry-forward config - bug 

- **Profile**: Admin (on Leave)
- **Setup**: L-1 done
- **Steps**:
  1. Click the **Settings** tab
  2. Locate the **Leave Year** period fields — note the current start and end month
  3. Change the **weekend** config from **Fri–Sat** to **Sat–Sun** (or vice versa) and click Save
  4. Confirm the setting is persisted (navigate away and back to Settings)
  5. Change the **carry-forward** rules — toggle or adjust the max carry-over days
  6. Save and confirm persisted
  7. Revert both settings back to their original values and save
- **Pass**: Each save operation shows a success toast/flash. After navigating away and returning, the saved values are still in place. No error when saving any of these config fields.
- **Bug**: UAE weekend definition is only saturday and sunday 
  - **Fixed**: Changed default `weekendDefinition` from `'fri-sat'` to `'sat-sun'` in `LeaveManager.jsx` (UAE changed to Sat-Sun for government/healthcare in Jan 2022). Updated dropdown labels to `"Saturday – Sunday (UAE since Jan 2022)"` and `"Friday – Saturday (traditional / pre-2022)"`. Sat-Sun is now the first and default option.
  - **Fixed (propagation)**: The admin's saved `weekendDef` was not being passed to the Employee Portal `EmpLeave.jsx` — that component was hardcoding `'fri-sat'` everywhere. Fixed by: loading `getLeaveSettings()` in the employee leave `Promise.all`, storing result as `weekendDef` state, and passing it to `countLeaveDays`, `validateLeaveRequest`, and the employee mini-calendar weekend highlight check. The `fmtDate` helper inside `EmpLeave.jsx` was also updated to use `formatDateUAE` (DD/MM/YYYY) from `uaeValidators.js` instead of `toLocaleDateString('en-AE', ...)` which produces locale-dependent output.

---

### L-12 · Settings tab — Add / Edit / Delete a leave type -bug 

- **Profile**: Admin (on Leave → Settings tab)
- **Setup**: L-11 done
- **Steps**:
  1. Click **+ Add Leave Type** (or the add button in the Leave Types section)
  2. Fill in:
     - **Name**: `Emergency Leave`
     - **Allowed Days**: `3`
     - **Paid**: Yes (toggle on)
     - **Type**: Annual (or as applicable)
  3. Click **Save** — the new type appears in the list
  4. Find `Emergency Leave` in the list — click **Edit** (pencil icon)
  5. Change **Allowed Days** to `5` → Save
  6. Confirm the list now shows `Emergency Leave — 5 days`
  7. Click **Delete** (trash icon) on `Emergency Leave` → confirm deletion
  8. Confirm `Emergency Leave` is no longer in the list
- **Pass**: All three CRUD operations succeed with visible feedback. The list updates immediately after each action. The deleted type does not reappear on page refresh.
- **Bug**: no place to add allowed days , paid etc , no place to edit after making leave type 
  - **Fixed**: Added a full Leave Types management card to the Settings tab in `LeaveManager.jsx` (positioned between Leave Configuration and Public Holidays). The card has: a table listing all leave types with Name, Paid, Days/Year, Probation OK, Needs Doc columns plus Edit (pencil) and Delete (trash) icon buttons; an inline add/edit form (toggled by "+ Add Leave Type" or pencil) with Name, Colour picker, Paid/Unpaid, Unlimited/Fixed, Annual Entitlement Days fields. Extended `saveLeaveType()` in `leaveStorage.js` to support full INSERT (new type) and full UPDATE (all user-editable fields), not just the 2 boolean patches. Added `deleteLeaveType(id)` as a soft-delete (sets `is_active = false`).

---

### L-13 · Settings tab — Probation Leave Eligibility toggle -c 

- **Profile**: Admin (on Leave → Settings tab)
- **Setup**: L-12 done. A probation employee must exist (from Day 3) — but the toggle test only requires that Hajj Leave exists as a leave type.
- **Steps**:
  1. Scroll to the **"Probation Leave Eligibility"** card in Settings
  2. Find **Hajj Leave** in the list — note its current toggle state (should default to ON / eligible)
  3. Toggle **Hajj Leave** to **OFF** (probation_eligible = false)
  4. Observe: a success indicator appears
  5. Navigate away from Settings and back — Hajj Leave toggle should still be OFF
  6. Toggle it back **ON** and confirm persisted
- **Pass**: The toggle saves optimistically (UI updates immediately). After a re-navigation, the saved state is correct. Toggling back ON restores the default. No error toast.
- **Bug**:
  - **Fixed**: `seedDefaultLeaveTypes()` in `leaveStorage.js` was not mapping the `probation_eligible` column when inserting default leave types, so all types got the DB default (`true`). Fixed by adding `probation_eligible: lt.probationEligible ?? true` to the rows mapping. Also added `probationEligible: false` to ANNUAL, HAJJ, and STUDY in `DEFAULT_LEAVE_TYPES` (`leaveEngine.js`). Additionally, `saveLeaveType()` for new custom types now checks for code collisions before INSERT (appends `_1`, `_2`, etc. if needed), preventing DB unique constraint errors when two types share similar names.

---

### L-14 · Settings tab — Requires Attachment toggle -c

- **Profile**: Admin (on Leave → Settings tab)
- **Setup**: L-13 done
- **Steps**:
  1. Find **Sick Leave** in the leave type list (or whichever type you want to test)
  2. Locate the **"Requires Attachment"** toggle next to it (may be in the same Probation card or a separate card)
  3. Toggle **Sick Leave** to require an attachment
  4. Confirm: a success indicator appears
  5. Navigate away and back — Sick Leave still shows attachment required
  6. Toggle it back **OFF** and save
- **Pass**: Toggle saves and persists. No error. The toggle state is correctly read back on re-render.
- **Bug**:

---

### L-15 · Settings tab — Public Holidays CRUD -c

- **Profile**: Admin (on Leave → Settings tab)
- **Setup**: L-14 done
- **Steps**:
  1. Scroll to the **Public Holidays** section
  2. Click **+ Add Holiday**
  3. Enter:
     - **Date**: pick any future date (e.g. 2 December — UAE National Day)
     - **Name**: `UAE National Day (Test)`
  4. Click **Save** / Add — the holiday appears in the list with date formatted DD/MM/YYYY
  5. Click **Delete** (trash icon) on the holiday just added → confirm
  6. Confirm the holiday is removed from the list
- **Pass**: Holiday appears in the list immediately after adding, with the date in DD/MM/YYYY format. Deleting removes it without page refresh. No error during either operation.
- **Bug**:

---

### L-16 · Settings tab — Approval Delegation card -c

- **Profile**: Admin (on Leave → Settings tab)
- **Setup**: L-15 done. At least two employees must exist (one to be the "absent manager" and one to be the "delegate").
- **Steps**:
  1. Scroll to the **"Approval Delegation"** card
  2. Select an **Approver** (the absent manager) from the first dropdown
  3. Select a **Delegate** (the covering colleague) from the second dropdown
  4. Set a **From Date**: today
  5. Set a **To Date**: 2 weeks from today
  6. Click **Add Delegate** / Save
  7. Confirm the delegation row appears in the list with both names and the date range
  8. Click **Delete** (trash icon) on the delegation just created → confirm removal
- **Pass**: The delegation is saved and appears in the list immediately. Both the approver and delegate names are shown. Deleting removes the row. No error. If the `leave_approval_delegates` table has not been created yet, this card may show an empty state or a load error — note it in the Bug field.
- **Bug**:

---

---

# DAY 8 — Attendance · Biometric Import · Assets

> **Before you start**
> Attendance data is most meaningful if employees have clocked in/out at some point. If your test employee has not clocked in via the Employee portal yet, do the clock-in steps first (Employee portal → Attendance tab → Clock In) before running the admin-side tests below.

---

## ATTENDANCE

### AT-1 · Attendance module loads and stat cards render -c 
- **Profile**: Admin
- **Setup**: None
- **Steps**:
  1. Click **"Attendance"** in the sidebar
  2. Wait for the module to finish loading (do NOT look for a loading spinner — wait directly for the stat cards)
  3. Observe the four stat cards at the top
- **Pass**: Four stat cards visible: **Present Today**, **Absent**, **Late**, **Missing Clock-Out**. Each shows a number. No blank white box, no JS error.
- **Bug**:

---

### AT-2 · Month navigation reloads data - bug no arrows for navigation
- **Profile**: Admin (on Attendance)
- **Setup**: AT-1 done
- **Steps**:
  1. Note the current month shown in the header
  2. Click the **◄** (previous) button — the grid redraws for the previous month
  3. Click **►** (next) twice — forward to next month
  4. Confirm the month/year label updates with each click and stat cards re-render
- **Pass**: Month navigation works without errors. Stat cards update for each month. Grid rows (if any) reflect that month's data. No spinner that never resolves (the module polls every 30 s — do not use networkidle).
- **Bug**: no arrows for navigation
  - **Fixed**: Added `ChevronLeft` / `ChevronRight` arrow buttons flanking the month dropdown in `AttendanceManager.jsx`. Previous arrow steps back one month freely; next arrow is capped at the current month so future months cannot be navigated to. Also expanded the dropdown from 12 to 24 months of history.

---

### AT-3 · Refresh button reloads data -c 
- **Profile**: Admin (on Attendance)
- **Setup**: AT-1 done
- **Steps**:
  1. Click the **Refresh** button (circular arrow icon in the header)
  2. Observe whether a loading state briefly appears then resolves
- **Pass**: Data reloads. Stat cards update. No error shown.
- **Bug**:

---

### AT-4 · Employee attendance grid — daily status chips
- **Profile**: Admin (on Attendance, current month)
- **Setup**: AT-1 done. At least one employee exists and has clocked in at some point this month (or use any past month where clock-in data exists).
- **Steps**:
  1. Navigate to the current month (or a month that has clock-in data)
  2. Look at the grid — rows = employees, columns = days
  3. Observe the colour-coded status chips in each cell
- **Pass**: Cells show status chips appropriate for each day: **PRESENT** (green), **ABSENT** (red), **LATE** (amber), **WEEKEND** (grey), **HOLIDAY** (yellow), or blank for future dates. No cell shows a raw database string or `undefined`.
- **Bug**:

---

### AT-5 · Regularisation — submit a correction request
- **Profile**: Admin (on Attendance)
- **Setup**: AT-4 done. A past day with an ABSENT or missing record must be visible in the grid.
- **Steps**:
  1. Click on a past day cell for any employee (an ABSENT or empty cell works best)
  2. A regularisation form appears — fill in:
     - **Clock In Time**: `09:00`
     - **Clock Out Time**: `18:00`
     - **Reason**: `Manual correction — system missed punch`
  3. Click **Submit**
- **Pass**: The form closes or shows a success message. A pending regularisation request is created (visible in the Regularisation tab / pending list).
- **Bug**:

---

### AT-6 · Regularisation — approve and reject
- **Profile**: Admin (on Attendance)
- **Setup**: AT-5 done (a pending regularisation exists)
- **Steps**:
  1. Navigate to the **Regularisation** or **Pending** section
  2. Find the request submitted in AT-5
  3. Click **Approve** → confirm
  4. Verify the attendance record for that day updates (status chip changes to PRESENT)
  5. Submit another regularisation for a different day (repeat AT-5 steps)
  6. Click **Reject** on the new pending request
  7. Confirm the attendance record for that day is unchanged
- **Pass**: Approved regularisation updates the day's status chip. Rejected regularisation leaves the day's status as it was. Both actions show appropriate success feedback.
- **Bug**:
  - **Fixed**: `approveRegularisationRequest()` in `attendanceStorage.js` only updated the `regularisation_requests` status — it never patched the `attendance_records` row with the corrected clock times. Fixed by: (1) fetching the request row first to get `correct_clock_in`/`correct_clock_out`; (2) computing `total_hours` from the corrected times (with a 1-hour break deduction); (3) upserting `attendance_records` with the corrected clock times, total_hours, and re-derived status (`PRESENT`/`MISSING_CLOCK_OUT`/`ABSENT`). Also fixed `attendanceEngine.js` `isPast` check: `recordDate <= today` was treating today as a past day, causing employees with no clock-in yet today to show as `UNEXPLAINED_ABSENCE` instead of `ABSENT`. Changed to `recordDate < today`.

---

### AT-7 · Close Period
- **Profile**: Admin (on Attendance)
- **Setup**: AT-1 done. You must be viewing the **current or past month** (Close Period is disabled for future months).
- **Steps**:
  1. Confirm the **"Close Period"** button is visible in the header
  2. Click it — a confirmation prompt should appear
  3. Confirm the action
- **Pass**: The period status changes to closed/locked. The button is now disabled or replaced with a "Period Closed" indicator. A closed period cannot be re-opened without special action.
- **Bug**:

---

## BIOMETRIC IMPORT

### BIO-1 · Biometric Import tab loads -c
- **Profile**: Admin (on Attendance)
- **Setup**: AT-1 done
- **Steps**:
  1. Click the **"Biometric Import"** tab within the Attendance page
- **Pass**: The Biometric Import panel loads. You see a file upload area ("Choose file" or drag-and-drop), a Badge Mappings table (may be empty), and an Import button.
- **Bug**:

---

### BIO-2 · Upload and parse a biometric CSV -c 
- **Profile**: Admin (on Attendance → Biometric Import tab)
- **Setup**: BIO-1 done. A ready-made test file is at `test-data/biometric_test.csv` in the project root. It contains 2 badge numbers (101, 102) with clock-in/out pairs across 2 days in Generic format.

- **Steps**:
  1. Click **Choose File** (or drag the CSV onto the upload area)
  2. Select the test CSV file
  3. Observe the preview area
- **Pass**: The parser auto-detects the format (shown as "Generic" or "ZKTeco"). A preview table appears listing parsed punches: Badge No, Employee (matched or "Unmatched"), Date, Time, Type. No JS error.
- **Bug**:

---

### BIO-3 · Badge mapping — map an unmatched badge to an employee - bug
- **Profile**: Admin (on Attendance → Biometric Import tab)
- **Setup**: BIO-2 done with at least one unmatched badge number (badge `101` if you used the example above and haven't mapped it yet)
- **Steps**:
  1. In the **Unmatched Badges** section, find the chip for badge `101`
  2. Click the chip — it pre-fills the badge mapping form
  3. In the **Employee** dropdown, select any active employee
  4. Click **Save Mapping**
  5. Confirm the chip disappears from Unmatched and the badge now maps to that employee in the Badge Mappings table
- **Pass**: Mapping is saved and persists. The chip disappears from Unmatched Badges. The table shows Badge No → Employee Name.
- **Bug**: still shows terminated employees
  - **Fixed**: Added `.filter(e => e.employmentStatus !== 'Terminated')` to the employee `<select>` in `BiometricImport.jsx`. Terminated employees no longer appear in the badge mapping dropdown.

---

### BIO-4 · Confirm Import — new punches inserted, duplicates skipped - bug
- **Profile**: Admin (on Attendance → Biometric Import tab)
- **Setup**: BIO-3 done (badge 101 mapped to an employee)
- **Steps**:
  1. With the CSV still loaded (re-upload if needed), click **Confirm Import**
  2. Observe the import result summary
  3. Re-upload and import the same CSV a second time
  4. Observe the result — duplicate punches should be skipped
- **Pass**: First import: clock events are inserted for the mapped employee. Result shows count of punches imported. Second import: result shows 0 new punches (all duplicates skipped at the minute level — same employee + event type + minute already exists).
- **Bug**: duplicates not being skipped on second import
  - **Fixed**: Deduplication in `importBiometricPunches()` was comparing raw timestamp strings — the DB stores times in UTC while the parser generates eventTime with `+04:00` offset, so `substring(0,16)` produced `2026-07-01T05:02` (DB) vs `2026-07-01T09:02` (new punch), which never matched. Fixed by normalising both sides through `new Date(...).toISOString()` before taking the substring, ensuring both are UTC before comparison.

---

## ASSETS

### ASS-1 · Assets module loads - ui is crampped , between the assests button and the filters below it especiaplly 
- **Profile**: Admin
- **Setup**: None
- **Steps**:
  1. Click **"Assets"** in the sidebar
  2. Observe the page
- **Pass**: The Assets page loads. **Assets** tab is active by default. The asset list (or an empty state) is visible. Filter chips at the top show status labels (Available, Assigned, etc.).
- **Bug**: UI cramped between the assets button and the filters below it
  - **Fixed**: Added missing `.mb-3` CSS utility class (`margin-bottom: 12px`) to `index.css`. This class was used in 14 places across 9 components (AssetsManager, AppraisalManager, AdvancesManager, ExpensesManager, etc.) but had no CSS definition — all those spacing declarations were silently doing nothing. Now tab bars and filter chips have proper vertical spacing.

---

### ASS-2 · Add a new asset -c 
- **Profile**: Admin (on Assets)
- **Setup**: ASS-1 done
- **Steps**:
  1. Click **+ Add Asset** (or the plus button)
  2. Fill in the modal:
     - **Name**: `Dell Laptop 001`
     - **Category**: `Laptop`
     - **Serial Number**: `SN-TEST-001`
     - **Purchase Date**: any past date
     - **Purchase Value (AED)**: `4500`
     - **Condition**: `New`
  3. Click **Save**
- **Pass**: Modal closes. The asset appears in the list with status badge **Available** (green). The "Available" filter chip count increments by 1.
- **Bug**:

---

### ASS-3 · Edit an asset -c 
- **Profile**: Admin (on Assets)
- **Setup**: ASS-2 done (Dell Laptop 001 exists)
- **Steps**:
  1. Find `Dell Laptop 001` in the list
  2. Click the **Edit** button (`title="Edit asset"`, pencil icon)
  3. Change the Purchase Value to `4800`
  4. Click **Save**
- **Pass**: The modal closes. The updated value is reflected in the list. Status remains **Available** (the status dropdown in Edit does NOT include "Assigned" — that is managed only via Assign/Return).
- **Bug**:

---

### ASS-4 · Assign an asset to an employee -c 
- **Profile**: Admin (on Assets)
- **Setup**: ASS-2 done. At least one active employee must exist.
- **Steps**:
  1. Find `Dell Laptop 001` in the list (status: Available)
  2. Click the **Assign** button
  3. Select an employee from the dropdown
  4. Set **Condition at Handover**: `Good`
  5. Add **Notes**: `Assigned for remote work`
  6. Click **Assign**
- **Pass**: Status badge changes to **Assigned** (amber/orange). The asset moves to the "Assigned" filter. The employee name appears in the asset row. The Available count decrements.
- **Bug**:

---

### ASS-5 · Return an asset -c 
- **Profile**: Admin (on Assets)
- **Setup**: ASS-4 done (Dell Laptop 001 assigned)
- **Steps**:
  1. Find `Dell Laptop 001` (status: Assigned)
  2. Click the **Return** button
  3. Set **Condition at Return**: `Good`
  4. Click **Return**
- **Pass**: Status returns to **Available**. The Assigned badge is gone. The Available count increments. An entry is added to the Assignment History tab.
- **Bug**:

---

### ASS-6 · Delete asset — guard when assigned -c 
- **Profile**: Admin (on Assets)
- **Setup**: ASS-4 done. Re-assign Dell Laptop 001 (repeat ASS-4) so it has an open assignment.
- **Steps**:
  1. Find `Dell Laptop 001` (status: Assigned)
  2. Click the **Delete** button (`title="Delete asset"`)
  3. Confirm the deletion attempt
- **Pass**: Deletion is blocked — an error message appears: "Cannot delete an asset with an active assignment. Return it first." The asset is not removed.
- **Bug**:

---

### ASS-7 · Delete asset — succeeds when not assigned -c 
- **Profile**: Admin (on Assets)
- **Setup**: ASS-5 done (Dell Laptop 001 back to Available, no open assignment)
- **Steps**:
  1. Click **+ Add Asset** → add a second asset: Name `Test Asset To Delete`, Category `Equipment`, Serial `SN-DEL-001`
  2. Find it in the list (status: Available)
  3. Click **Delete** → confirm
- **Pass**: The asset is removed from the list immediately. No error.
- **Bug**:

---

### ASS-8 · Assignment History tab -c
- **Profile**: Admin (on Assets)
- **Setup**: ASS-5 done (at least one completed assignment exists — Dell Laptop 001 was assigned and returned)
- **Steps**:
  1. Click the **"Assignment History"** tab
  2. Find the Dell Laptop 001 record
- **Pass**: The log shows: Asset Name, Employee Name, Assigned Date, Returned Date, Condition at Handover, Condition at Return. The Dell Laptop row shows a return date (from ASS-5). Any currently assigned assets show no return date.
- **Bug**:

---

---

# DAY 9 — Training · Appraisals

> **Before you start**
> Be signed in as **Admin**. All tests below use the Admin profile unless stated otherwise.
> **Deferred items handled today**: D-9 (Day 1 — cert expiry alert) and D-11 (Day 1 — pending appraisals alert). Do D-9 **after TR-4** and D-11 **after AP-4**.

---

## Deferred from earlier days

### D-9 · Certification expiry alert on Dashboard - c 
- **Profile**: Admin
- **Setup**: TR-4 must be completed first — it creates a certification expiring within 30 days, which is what triggers this Dashboard alert.
- **Steps**:
  1. After completing TR-4, click **Dashboard** in the sidebar
  2. Wait for stat cards to fully load
  3. Look for an amber alert mentioning certifications expiring soon (e.g. "1 certification expiring within 60 days")
  4. Click the link or button inside the alert
  5. Also open the notification bell (🔔) and check for a `cert_expiry` notification
- **Pass**: Dashboard shows an amber certification-expiry alert with the count of near-expiry certs. Clicking it navigates to the **Training** module (Certifications tab). The notification bell shows at least one unread notification for the cert expiry.
- **Bug**:

---

### D-11 · Pending appraisals alert on Dashboard - c
- **Profile**: Admin
- **Setup**: AP-4 must be completed first — it creates an active cycle with assigned staff in "Pending" status, which is what triggers this alert.
- **Steps**:
  1. After completing AP-4, click **Dashboard** in the sidebar
  2. Wait for stat cards to fully load
  3. Look for a blue info alert about pending appraisals (e.g. "X pending appraisals in active cycle")
  4. Click the link/button inside the alert
- **Pass**: Dashboard shows a blue alert referencing the pending appraisals in the active "2026 Mid-Year Review" cycle. Clicking it navigates to the **Appraisals** module.
- **Bug**:

---

## TRAINING

### TR-1 · Navigate to Training module -c 
- **Profile**: Admin
- **Setup**: Be signed in as Admin
- **Steps**:
  1. Click **"Training"** in the sidebar (between Assets and Roster)
- **Pass**: Training module loads. Two tabs are visible: **Training Records** (default) and **Certifications**. A **+ Add Record** (or similar) button is visible. No error, no blank screen.
- **Bug**:

---

### TR-2 · Add a Training Record - bug 
- **Profile**: Admin (on Training → Training Records tab)
- **Setup**: TR-1 done. At least one active employee exists.
- **Steps**:
  1. Click **+ Add Record**
  2. Fill in:
     - **Employee**: select any active employee
     - **Training Title / Course**: `Fire Safety Training`
     - **Type**: `Internal`
     - **Provider / Trainer**: `HR Department`
     - **Start Date**: today's date
     - **End Date**: today's date
     - **Duration (hours)**: `4`
     - **Status**: `Planned`
  3. Click **Save**
- **Pass**: The new record appears in the list with a grey **Planned** badge. Employee name, title, type, and dates are all visible. No error toast.
- **Bug**: panel comes on the side not middle 
  - **Fixed**: `TrainingModal` used `className="modal-backdrop"` which had no CSS definition — the overlay div had no positioning, centering, or background. Added `.modal-backdrop` as an alias of `.modal-overlay` in `index.css` (same `position:fixed; inset:0; display:flex; align-items:center; justify-content:center` rules). This fixes all modals using `modal-backdrop` across `TrainingManager.jsx`, `AppraisalManager.jsx`, and `App.jsx`.

---

### TR-3 · Edit a Training Record — mark as Completed -c 
- **Profile**: Admin (on Training → Training Records tab)
- **Setup**: TR-2 done (Fire Safety Training record exists)
- **Steps**:
  1. Find the **"Fire Safety Training"** row
  2. Click the **pencil (Edit)** icon
  3. Change **Status** to `Completed`
  4. Set **Score**: `85`
  5. Toggle **Passed** to **Yes** (if a toggle exists)
  6. Click **Save**
- **Pass**: Row shows a green **Completed** badge. Score and Passed status are reflected. No error.
- **Bug**:

---

### TR-4 · Add a Certification with near-expiry date (needed for D-9) -c 
- **Profile**: Admin (on Training)
- **Setup**: TR-1 done. At least one active employee exists.
- **Steps**:
  1. Click the **Certifications** tab
  2. Click **+ Add Certification**
  3. Fill in:
     - **Employee**: same employee as TR-2
     - **Certification Name**: `BLS / Basic Life Support`
     - **Issuing Body**: `American Heart Association`
     - **Certificate No.**: `BLS-2024-001`
     - **Issued Date**: `2025-07-06` (approximately 1 year ago)
     - **Expiry Date**: **30 days from today** (e.g. `2026-08-05`) — this triggers the amber Dashboard alert
     - **Certificate URL**: leave blank
  4. Click **Save**
- **Pass**: Certification appears in the list. Its expiry badge shows **red "Xd left"** (≤30 days). No error toast.
- **Bug**:

> **Now do D-9** (deferred from Day 1): click Dashboard, check for the certification expiry amber alert, and click its link.

---

### TR-5 · Edit a Certification — change expiry, verify badge updates - ui bug
- **Profile**: Admin (on Training → Certifications tab)
- **Setup**: TR-4 done (BLS cert with near-expiry)
- **Steps**:
  1. Click the **pencil (Edit)** icon on the BLS certification row
  2. Change **Expiry Date** to **6 months from today** (e.g. `2027-01-06`)
  3. Click **Save** — badge should update to green **Active**
  4. Edit the same cert again and revert the expiry back to **30 days from today**
  5. Save again
- **Pass**: Badge changes from red near-expiry to green Active after the first edit, then back to red near-expiry after the revert. Each save closes the form without error.
- **Bug**: same issue panel come on the left corner not middle
  - **Fixed**: Same root cause as TR-2 — `CertModal` uses `className="modal-backdrop"` which now has proper centering CSS.

---

### TR-6 · Delete a Training Record - bug
- **Profile**: Admin (on Training → Training Records tab)
- **Setup**: TR-3 done. Optionally add a second disposable record first (so TR-3's record can remain for reference).
- **Steps**:
  1. Add a second record: **"Test Delete Record"**, type Internal, today's dates, status Planned → Save
  2. Click the **trash (Delete)** icon on **"Test Delete Record"**
  3. Confirm the deletion in the prompt
- **Pass**: Row disappears from the list immediately. No error. All other records are unaffected.
- **Bug**: panel comes on left again
  - **Fixed**: Same root cause as TR-2 — the delete confirmation dialog in `TrainingManager` uses `className="modal-backdrop"` which now has proper centering CSS.

---

### TR-7 · Certifications — Expiring Soon / Expired filter -c 
- **Profile**: Admin (on Training → Certifications tab)
- **Setup**: TR-4 done (BLS cert has expiry ≤30 days)
- **Steps**:
  1. Look for filter tabs or buttons such as **"Expiring Soon"** and/or **"Expired"**
  2. Click the **Expiring Soon** filter — only near-expiry or expired certs should remain visible
  3. Click **All** (or the default tab) to return to the full list
- **Pass**: Expiring Soon filter narrows the list to only certs with imminent expiry (≤60 days). Switching back to All restores the complete list. No error.
- **Bug**:

---

## APPRAISALS

### AP-1 · Navigate to Appraisals module -c 
- **Profile**: Admin
- **Setup**: Be signed in as Admin
- **Steps**:
  1. Click **"Appraisals"** in the sidebar (ClipboardList icon, between Training and Roster)
- **Pass**: Appraisals module loads. A **Cycles** tab is visible (default) with a list or empty state and a **+ Add Cycle** button. No error, no blank screen.
- **Bug**:

---

### AP-2 · Add an Appraisal Cycle -c 
- **Profile**: Admin (on Appraisals → Cycles tab)
- **Setup**: AP-1 done
- **Steps**:
  1. Click **+ Add Cycle**
  2. Fill in:
     - **Cycle Name**: `2026 Mid-Year Review`
     - **Review From**: `2026-01-01`
     - **Review To**: `2026-06-30`
     - **Status**: `Active`
  3. Click **Save**
- **Pass**: The cycle appears in the list with an **Active** status badge. Name and date range are shown. No error.
- **Bug**:

---

### AP-3 · Open cycle detail — Reviews tab is empty with Generate Appraisals button - c 
- **Profile**: Admin (on Appraisals → Cycles tab)
- **Setup**: AP-2 done ("2026 Mid-Year Review" cycle exists)
- **Steps**:
  1. Click the **"2026 Mid-Year Review"** row (or its name/open button) to enter the cycle detail view
  2. Locate the **Reviews** tab within the cycle detail
  3. Confirm the list is empty (no appraisal rows yet)
  4. Confirm a **"Generate Appraisals"** button is visible
- **Pass**: Cycle detail opens cleanly. Reviews tab shows an empty state with a Generate Appraisals button. The Reviews tab label shows no count badge (or "0"). No error.
- **Bug**: Checklist originally said "Assign Staff" but the actual button text is "Generate Appraisals" — not a code bug, corrected checklist wording.

---

### AP-4 · Assign Staff to cycle -c 
- **Profile**: Admin (on Appraisals, inside "2026 Mid-Year Review" cycle, Reviews tab)
- **Setup**: AP-3 done. At least 2 active employees must exist (use employees from Day 2).
- **Steps**:
  1. Click **"Generate Appraisals"**
  2. All active employees get appraisal rows generated automatically
  3. Confirm rows appear
- **Pass**: Appraisal rows appear in the Reviews list — one row per selected employee. Each row shows: employee name, overall rating (empty/zero), status badge **Pending**, and 5 default sections seeded. The Reviews tab label now shows a count badge (e.g. "Reviews 2").
- **Bug**:

> **Now do D-11** (deferred from Day 1): click Dashboard, check for the pending appraisals blue info alert, click its link.

---

### AP-5 · Fill in an Appraisal Review (admin reviewer role) - bug 
- **Profile**: Admin (on Appraisals, inside "2026 Mid-Year Review" cycle, Reviews tab)
- **Setup**: AP-4 done (at least one employee row visible in Pending status)
- **Steps**:
  1. Find any employee's appraisal row
  2. Click the **Review** (clipboard icon) to open the review form
  3. The form shows 5 sections — for each section, select **4 stars**:
     - **Clinical Competency** → 4 stars
     - **Patient Care Quality** → 4 stars
     - **Communication & Teamwork** → 4 stars
     - **Punctuality & Attendance** → 4 stars
     - **Professional Development** → 4 stars
  4. In the **Comments** field of the first section, type: `Excellent performance this period`
  5. In the **Development Plan** field (bottom of the form), type: `Attend advanced clinical training in Q3`
  6. Click **Save Review**
- **Pass**: The appraisal row's status updates to **Reviewed**. The overall weighted average rating shows approximately 4.0 stars. Reviewer comments and development plan are saved. No error.
- **Bug**: review panel comes below left , same issue as training , not centered 
  - **Fixed**: Same root cause as TR-2 — `AppraisalModal` uses `className="modal-backdrop"` which had no CSS. Now `.modal-backdrop` is defined as an alias of `.modal-overlay` with full centering styles.

---

### AP-6 · Calibrate an Appraisal -c 
- **Profile**: Admin (on Appraisals, inside "2026 Mid-Year Review" cycle, Reviews tab)
- **Setup**: AP-5 done (at least one appraisal in "Reviewed" status)
- **Steps**:
  1. Find the reviewed appraisal row (status: Reviewed)
  2. Click the **Calibrate** button
  3. An override field appears for the overall rating — click **3 stars** (or enter `3`)
  4. Confirm / click **Calibrate**
- **Pass**: Row status changes to **Calibrated**. Overall rating now shows the calibrated 3-star value. Section star inputs are **locked** (read-only — you cannot change them). No error.
- **Bug**:

---

### AP-7 · Delete an Appraisal row - c 
- **Profile**: Admin (on Appraisals, inside "2026 Mid-Year Review" cycle, Reviews tab)
- **Setup**: AP-4 done. At least 2 employees were assigned, so you can delete one and keep the other (the calibrated one from AP-6).
- **Steps**:
  1. Find the **second employee's** appraisal row (the one that was NOT reviewed/calibrated — still in Pending status)
  2. Click the **trash (Delete)** icon
  3. Confirm deletion
- **Pass**: The row disappears. The calibrated appraisal row from AP-6 is unaffected. The Reviews badge count decrements by 1. No error.
- **Bug**:

---

### AP-8 · Edit Cycle and delete a disposable Cycle -c 
- **Profile**: Admin (on Appraisals → Cycles tab)
- **Setup**: AP-2 done. Create a second disposable cycle: click + Add Cycle → name: `Test Delete Cycle`, dates: today to today, status: `Draft` → Save.
- **Steps**:
  1. Find **"Test Delete Cycle"** in the Cycles list
  2. Click the **pencil (Edit)** icon → change name to `Test Cycle (edited)` → Save
  3. Confirm the updated name is shown
  4. Click the **trash (Delete)** icon on `Test Cycle (edited)` → confirm deletion
  5. Confirm the "2026 Mid-Year Review" cycle and its appraisals are unaffected
- **Pass**: Edit saves and the updated name is shown. Deletion removes the row. The "2026 Mid-Year Review" cycle with its calibrated appraisal still exists. No error.
- **Bug**:

---

---

# DAY 10 — Roster · Reports

> **Before you start**
> Be signed in as **Admin**. All tests below use the Admin profile.
> **No deferred items for Day 10** — no previous-day items point here.
> **Prerequisite data**: At least 2–3 active employees should exist (from Day 2). If staffing rules were configured in Day 4 (Departments → Staffing Rules tab), those will be tested during Roster publish. If not, the compliance gate test (RO-8) will be skipped.

---

## ROSTER

### RO-1 · Navigate to Roster module -c
- **Profile**: Admin
- **Setup**: None
- **Steps**:
  1. Click **"Roster"** in the sidebar (between Attendance and Assets)
- **Pass**: Roster module loads. Three tabs visible: **Templates** (default active), **Roster**, **Swaps**. A **+ New Shift** button is visible. No error, no blank screen.
- **Bug**:

---

### RO-2 · Add a Shift Template -c
- **Profile**: Admin (on Roster → Templates tab)
- **Setup**: RO-1 done
- **Steps**:
  1. Click **+ New Shift**
  2. An inline form appears — fill in:
     - **Shift Name**: `Morning`
     - **Short Code**: `D` (max 3 chars, auto-uppercased)
     - **Category**: `Morning`
     - **Color**: pick any bright colour from the palette (e.g. green)
     - **Start Time**: `07:00`
     - **End Time**: `15:00`
     - **Break (minutes)**: `60`
     - Observe **Expected Hours** auto-computes to `7.0`
  3. Click **Create Shift**
  4. Repeat to add a second template:
     - **Name**: `Night`, **Code**: `N`, **Category**: `Night`, **Start**: `19:00`, **End**: `07:00`, **Break**: `60`, colour: pick blue/dark
     - Click **Create Shift**
- **Pass**: Both templates appear in the list with their name, code badge, category, colour swatch, start/end times, and expected hours. No error.
- **Bug**:

---

### RO-3 · Edit a Shift Template -c 
- **Profile**: Admin (on Roster → Templates tab)
- **Setup**: RO-2 done
- **Steps**:
  1. Find the **Morning** row
  2. Click the **pencil (Edit)** icon
  3. The form pre-fills with the template's data
  4. Change **Short Code** from `D` to `M`
  5. Click **Update Shift**
- **Pass**: The template row updates — code badge now shows `M`. No error.
- **Bug**:

---

### RO-4 · Delete a Shift Template -c
- **Profile**: Admin (on Roster → Templates tab)
- **Setup**: RO-2 done. Create a disposable template: **Name**: `Test Delete`, **Code**: `X`, **Category**: `Flexible`, any times → Create Shift
- **Steps**:
  1. Find **Test Delete** in the list
  2. Click the **trash (Delete)** icon
  3. Confirm the deletion
- **Pass**: Row disappears. The Morning and Night templates remain. No error.
- **Bug**:

---

### RO-5 · Roster grid loads and shows employee rows -c
- **Profile**: Admin (on Roster)
- **Setup**: RO-2 done (at least 1 shift template exists). At least 2 employees exist.
- **Steps**:
  1. Click the **Roster** tab
  2. Observe the monthly grid: rows = employees, columns = days of the current month
  3. Check the right edge for a **Total Hrs** column
  4. Check the bottom for **footer rows**: ☀ Morning / 🌤 Afternoon / 🌙 Night / ○ Unassigned
- **Pass**: Grid renders with employee names as row headers and day numbers as column headers. Total Hrs column shows `0` (no assignments yet). Footer rows show day-by-day counts (all zeroes initially). No error, no blank grid.
- **Bug**:

---

### RO-6 · Assign and clear a shift in the roster grid -c 
- **Profile**: Admin (on Roster → Roster tab)
- **Setup**: RO-5 done
- **Steps**:
  1. Find the first employee row
  2. Click on a cell for today (or any non-greyed day)
  3. A dropdown appears showing the shift codes — select **M** (Morning)
  4. Cell updates to show the coloured `M` code badge
  5. Check the **Total Hrs** column for that employee — should now show `7.0`
  6. Check the footer ☀ Morning row for that day — count should be `1`
  7. Click the same cell again → select the blank/empty option
  8. Cell clears
- **Pass**: Assignment creates a coloured code badge in the cell. Total Hrs updates. Footer Morning count increments. Clearing the cell reverses both. No error.
- **Bug**:

---

### RO-7 · Roster features — greyed pre-join cells, month nav, CSV export -c 
- **Profile**: Admin (on Roster → Roster tab)
- **Setup**: RO-5 done
- **Steps**:
  1. Look for any employee whose **Joining Date** is mid-month or later this month — cells before their join date should be greyed out with `–`
  2. Click **◄** (previous month arrow) — grid redraws for the prior month
  3. Click **►** twice to return to the current month
  4. Assign a few shifts across 2–3 employees for several days (use `M` and `N` codes)
  5. Click the **Export CSV** button
  6. Open the downloaded CSV file
- **Pass**: Pre-join cells show `–` and are non-interactive. Month navigation works without errors. CSV downloads in DMUH format: employee rows with day-by-day codes, M/A/N/O totals, and planned hours per employee.
- **Bug**:

---

### RO-8 · Publish Roster — with and without staffing compliance gate -bug 
- **Profile**: Admin (on Roster → Roster tab)
- **Setup**: RO-7 done (some shift assignments exist). If staffing rules were created in Day 4 (Departments → Staffing Rules tab), at least one rule exists.
- **Steps**:
  1. Click **Publish Roster**
  2. **If staffing rules exist AND any day/category is below the minimum**:
     - A "Staffing Compliance" modal appears listing violations (department × shift × date × actual count vs required)
     - In the **Override Reason** textarea, type at least 10 characters: `Short-staffed due to leave approvals`
     - Click **Confirm Publish**
  3. **If no staffing rules exist OR all rules are met**:
     - Roster publishes directly with no modal
  4. Confirm a success message appears
- **Pass**: After publish, assignments are marked `published = true`. If override was required, it is logged to `compliance_overrides`. No error. (Published assignments become visible to employees on their Schedule tab — tested on Day 12.)
- **Bug**: minimum staff required was set to one for morning, but when trying to publish it says 0 assigned even though shifts are assigned in the grid.
  - **Fixed**: `handlePublish()` iterated `Object.entries(rosterData)` treating it as a nested `empId → {date → assignment}` map, but `rosterData` is actually a flat map with keys `${empId}_${dateStr}` → assignment. `byDate[dateStr]` was always `undefined`, so `count` was always 0. Rewrote the loop to iterate `employees` and look up each assignment via the correct flat key `rosterData[\`${emp.id}_${dateStr}\`]`.

> **Note**: If no staffing rules are configured, skip the compliance gate sub-steps. You can still verify basic publish works.

---

### RO-9 · Swaps tab — view pending requests deffer to employee testing days 
- **Profile**: Admin (on Roster)
- **Setup**: RO-8 done
- **Steps**:
  1. Click the **Swaps** tab
  2. Observe the list
- **Pass**: If swap requests exist (submitted from employee portal), each row shows: requester name, target employee, dates, reason, status. Approve (✓) and Reject (✗) buttons visible for pending requests. If no swaps exist, an empty state message is shown. No error.
- **Bug**:

> **Note**: Swap requests are submitted from the Employee portal Schedule tab (Day 12). If none exist yet, verify the tab loads cleanly and note that the approve/reject flow will be tested after Day 12.

---

---

## REPORTS

### RP-1 · Navigate to Reports module -c 
- **Profile**: Admin
- **Setup**: None
- **Steps**:
  1. Click **"Reports"** in the sidebar (last item)
- **Pass**: Reports module loads. Eight tab buttons visible in a row: **Headcount**, **Payroll Cost**, **Leave Usage**, **Attendance**, **Doc Expiry**, **Salary History**, **Staff Turnover**, **Staffing Compliance**. Headcount is active by default. No error.
- **Bug**:

---

### RP-2 · Headcount tab — breakdowns and export -c 
- **Profile**: Admin (on Reports → Headcount tab)
- **Setup**: RP-1 done. At least 2 employees exist.
- **Steps**:
  1. Observe the Headcount report — breakdown cards by Department, Nationality, Gender, Contract Type
  2. Each breakdown card shows a table with category, count, and share percentage
  3. Click **Export CSV** — a CSV file downloads
  4. Click **Export PDF** — a PDF file downloads
- **Pass**: Breakdowns show correct counts matching the number of active employees. CSV and PDF both download without error. The CSV contains rows like `Department, Group, Count, Share %`.
- **Bug**:

---

### RP-3 · Payroll Cost tab -c 
- **Profile**: Admin (on Reports)
- **Setup**: At least one payroll run must have been created (from Day 5). If none exist, this tab shows an empty state — note it and skip.
- **Steps**:
  1. Click the **Payroll Cost** tab button
  2. Observe the report — period-by-period table with columns: Period, Payment Date, Employees, Basic, Allowances, Bonus/Other, Total Cost
  3. Click **Export CSV**
  4. Click **Export PDF**
- **Pass**: Table shows payroll cost breakdown per period. Totals make sense. CSV and PDF download. No error.
- **Bug**:

---

### RP-4 · Leave Usage tab -bug 
- **Profile**: Admin (on Reports)
- **Setup**: At least one approved leave request should exist (from Day 7). If none exist, the table is empty — note it and move on.
- **Steps**:
  1. Click the **Leave Usage** tab button
  2. A year selector is visible — leave it at the current year
  3. Observe the per-employee table: Employee, Department, Requests count, Total Days Taken, Leave Types used
  4. Click **Export CSV**
- **Pass**: Table shows leave utilization per employee. Export downloads. No error.
- **Bug**: leaves were given , not registering in this module 
  - **Fixed**: Three root causes: (1) Reports fetched only `status='Approved'` leaves, missing `ManagerApproved` — changed to fetch all leave requests and filter in the report builder. (2) `buildLeaveUtilizationReport` read `req.days` (non-existent field) instead of `req.daysRequested` — all days computed as 0. (3) Leave type display always fell back to 'Annual' because it read `req.leaveType` (missing) instead of `req.leaveTypeCode`.

---

### RP-5 · Attendance tab -bug 
- **Profile**: Admin (on Reports)
- **Setup**: Some attendance records should exist (from Day 8). If none exist, the table is empty — note it.
- **Steps**:
  1. Click the **Attendance** tab button
  2. A month/period picker is visible — select the current month
  3. Observe per-employee table: Employee, Department, Days, Present, Absent, Late, Early Departure, Hours
  4. Click **Export CSV**
- **Pass**: Table shows attendance summary per employee for the selected period. Export downloads. No error.
- **Bug**: same issue not registering 
  - **Investigated**: Code logic is correct — `getAttendanceRecords()` fetches all records for the admin's employees, and `buildAttendanceSummaryReport` filters by the selected month. Ensure the month picker matches when records were created (e.g. if biometric import was for a past month, select that month). No code bug found — re-test after selecting the correct period.

---

### RP-6 · Doc Expiry tab -c
- **Profile**: Admin (on Reports)
- **Setup**: At least one employee document with an expiry date should exist (from Day 3).
- **Steps**:
  1. Click the **Doc Expiry** tab button
  2. A threshold selector appears (30 / 60 / 90 days) — select **90**
  3. Observe the table: Employee, Department, Document Type, Expiry Date, Days Remaining, Status (expired / expiring / OK)
  4. Click **Export CSV**
- **Pass**: Table lists documents expiring within 90 days. Status badges show colour-coded expiry state. Export downloads. No error.
- **Bug**:

---

### RP-7 · Salary History tab -bug 
- **Profile**: Admin (on Reports)
- **Setup**: At least one salary change should have been recorded (auto-logged from employee edits on Day 2/3 via job history).
- **Steps**:
  1. Click the **Salary History** tab button
  2. Observe the table: Employee, Department, Old Salary, New Salary, Change Date, Changed By
  3. Click **Export CSV**
- **Pass**: Table shows salary change events. Export downloads. No error.
- **Bug**:salary was chnaged not registering 
  - **Fixed**: `buildSalaryMovementReport` filtered for `changeType === 'salary'` but the actual stored value is `'salary_change'` (set by `EmployeeManager.handleSaveEmployee`). Changed filter to match `'salary_change'`.

---

### RP-8 · Staff Turnover tab -bug 
- **Profile**: Admin (on Reports)
- **Setup**: At least one employee should have been hired (joining date exists).
- **Steps**:
  1. Click the **Staff Turnover** tab button
  2. A date range picker appears — select a range that covers the last 12 months
  3. Observe two sections: **Joiners** (employees hired in range) and **Leavers** (employees terminated in range)
  4. A net headcount change summary is visible
  5. Click **Export CSV**
- **Pass**: Joiners and leavers tables render. Net headcount change makes sense (joiners − leavers). Export downloads. No error.
- **Bug**: not showing leavers/terminated 
  - **Fixed**: `archiveEmployee()` set `employment_status='Terminated'` and `active=false` but never set `termination_date`. The turnover report filters leavers by `e.terminationDate` — always null, so no leavers ever appeared. Now `archiveEmployee()` also sets `termination_date` to today's date. Employees terminated before this fix will still show no termination date — edit them and set the date manually if needed.

---

### RP-9 · Staffing Compliance tab - bug 
- **Profile**: Admin (on Reports)
- **Setup**: Staffing rules must have been created (Day 4 — Departments → Staffing Rules tab). If none exist, the tab shows "No staffing rules defined" — note it and skip.
- **Steps**:
  1. Click the **Staffing Compliance** tab button (8th, ShieldCheck icon)
  2. A **month picker** appears — select the current month (or the month where RO-7/RO-8 roster was published)
  3. Observe the heatmap: one row per staffing rule (Department × Shift Category), columns = days of the month
  4. Each cell is a small coloured square:
     - **Green** = actual staff count ≥ minStaff (compliant)
     - **Red** = actual staff count < minStaff (violation)
  5. Hover or inspect cells for actual counts
- **Pass**: Heatmap renders with the correct number of rules. Days where shifts were assigned in the roster show green cells; unassigned or under-staffed days show red. If no roster is published for the selected month, an empty state message appears. No error.
- **Bug**: not working 
  - **Fixed**: `StaffingComplianceTab` compared `r.shiftCategory` on roster assignments, but that field doesn't exist — the shift category is nested at `r.shift.shiftCategory` (from the embedded shifts join). All day counts were 0, making every cell red. Changed to `r.shift?.shiftCategory`.

> **Note**: This tab requires both staffing rules (from Day 4 Departments) AND published roster data (from RO-8). If either is missing, you'll see an appropriate empty state.

---

---

# DAY 11 — Manager Portal (queue tabs · auth · appraisals · home · leave · schedule · attendance)

> **Before you start**
> The Manager Portal has **14 tabs**: 4 manager-specific tabs + 10 employee self-service tabs.
>
> You must have a manager account set up. This means:
> 1. An employee exists in the admin portal with a valid `work_email`
> 2. That employee has registered via "Sign in as Employee / Manager" → "Register as Employee"
> 3. The admin has set that employee's **Portal Role** to "Manager" (EmployeeModal → Job & Contract tab → Portal Role dropdown)
> 4. That employee has at least one **direct report** (another employee whose `Reporting Manager` is set to the manager)
>
> If you don't have a manager set up yet, do these steps first:
> - Admin portal → Employees → pick an employee → Job & Contract tab → set **Reporting Manager** to the person who will be the manager
> - Open the manager employee's record → Job & Contract tab → Portal Role dropdown → select **Manager** (only visible if that employee has already registered via the employee portal — if the dropdown doesn't appear, the employee hasn't registered yet; do that first via "Sign in as Employee / Manager" → Register)
>
> The manager's direct reports must also exist and ideally have portal accounts registered so cross-portal flows work.
>
> **Tab order in sidebar** (14 tabs):
> 1. Home · 2. Leave Queue · 3. Expense Queue · 4. Appraisals (team + my sub-views) · 5. Training (team + my sub-views) · 6. My Leave · 7. Schedule · 8. Attendance · 9. Payslips · 10. Advances · 11. Expenses (own) · 12. Documents · 13. Requests · 14. Profile
>
> **SQL prerequisites** (run in Supabase SQL Editor before testing):
> - `sql/039_shifts_read_policy.sql` — shift names visible in roster for non-admin users
> - `sql/040_training_manager_policies.sql` — manager CRUD on training/certs for direct reports + employee self-enrollment

---

## Deferred from earlier days

### EXP-4 · Approve a Manager-Approved claim (final HR sign-off) - bug
- **Profile**: Admin (sign in as Admin)
- **Setup**: From Day 6, EXP-2 seeded a `transportation / AED 180` claim with status `manager_approved`. If that claim no longer exists, re-seed it:
  ```sql
  INSERT INTO expense_claims
    (user_id, employee_id, category, amount, expense_date, description,
     status, manager_approved_at, manager_approved_by)
  SELECT c.user_id, e.id, 'transportation', 180, CURRENT_DATE - INTERVAL '3 days',
         'Taxi to client — manual test', 'manager_approved',
         NOW() - INTERVAL '1 day', 'Manager Portal (seeded)'
  FROM employees e JOIN companies c ON c.user_id = e.user_id
  WHERE e.employment_status NOT IN ('Terminated') ORDER BY e.name LIMIT 1;
  ```
- **Steps**:
  1. Sign in as **Admin**
  2. Click **Expenses** in the sidebar
  3. Click the **Mgr Approved** filter tab
  4. Find the `transportation / AED 180` claim
  5. Click the **✓ Approve** button on that row
- **Pass**: A green success flash appears ("Claim approved."). The claim's status badge changes to **HR Approved** (green). It disappears from the Mgr Approved tab. Switching to the **HR Approved** tab shows it there. The **Approved (Unpaid)** stat card increases by AED 180.00.
- **Bug**: manager cant see which employee sent the expense request , new clain button in expense clain tab is too close for bnoth manmaher nad employee , refresh button not styled and too cramped in manager and employee portal 
  - **Fixed**: (1) `ManagerExpenseQueue` now loads employees via `getEmployees()` and merges names into claims (RPC returns flat data without employee name). (2) Both `EmpExpenses` and `ManagerExpenseQueue` headers now use `display: flex; justify-content: space-between` wrapper to space title and button properly.

---

## Manager AUTH

### MA-1 · Manager sign-in -c 
- **Profile**: Manager (use the employee/manager sign-in form, NOT the admin form)
- **Setup**: Manager account must be set up (see "Before you start" above). Sign out of any current session first.
- **Steps**:
  1. Go to the login page
  2. Use the **"Sign in as Employee / Manager"** form on the right side (NOT the admin form on the left)
  3. Enter the manager's email and password
  4. Click the **Sign in** button (or `button[type="submit"]`)
- **Pass**: Lands on the **ManagerShell** with the **Leave Queue** tab active (tab 1). The sidebar shows **15 tabs** in order: Leave Queue, Expense Queue, Appraisals, Home, My Leave, Schedule, Attendance, Payslips, Advances, Expenses, Training, My Appraisals, Documents, Requests, Profile. The sidebar shows "Manager Portal" sub-label. The sidebar footer shows the manager's **name** (bold) and **job title** — NOT an email address. The notification bell icon is visible.
- **Bug**:

---

### MA-2 · Manager sign-out -c 
- **Profile**: Manager (signed in from MA-1)
- **Setup**: MA-1 done
- **Steps**:
  1. Click **Sign Out** in the sidebar footer
- **Pass**: Returns to the login page. No errors in the console.
- **Bug**:

> **After testing MA-2, sign back in as the manager for the remaining tests.**

---

## M-1. LEAVE QUEUE (tab 1)

### M1-1 · Leave Queue — view pending requests - bug - show the leave warnings for the manager as well ,
- **Profile**: Manager (signed in)
- **Setup**: The **Leave Queue** tab should be active by default after sign-in. The manager must have at least one direct report. Ideally, seed a pending leave request from a direct report. You can do this from the **employee portal** (sign in as the direct report employee, go to Leave tab, submit a leave request) or seed via SQL:
  ```sql
  INSERT INTO leave_requests
    (user_id, employee_id, leave_type_code, start_date, end_date, days_requested, reason, status)
  SELECT e.user_id, e.id, 'ANNUAL', CURRENT_DATE + INTERVAL '7 days',
         CURRENT_DATE + INTERVAL '9 days', 3, 'Family visit — manual test', 'Pending'
  FROM employees e
  WHERE e.reporting_manager_id IS NOT NULL
    AND e.employment_status NOT IN ('Terminated')
  LIMIT 1;
  ```
- **Steps**:
  1. Confirm you're on the **Leave Queue** tab (first tab, CheckSquare icon)
  2. Look at the pending requests list
- **Pass**: Pending leave requests from direct reports are shown. Each request displays: **employee name**, **leave type**, **start/end dates**, **days requested**, **reason**, and **status badge**. If no direct reports have submitted leave, an empty state message appears ("No pending leave requests" or similar).
- **Bug**:manager not getting leave requests , from employee side showing they have 0 anual leaves remaining as well 
  - **Fixed**: Root cause: `leave_requests` table had no RLS policy for managers — managers could only read their own leave requests, not their direct reports'. Created `sql/037_leave_manager_read.sql` which adds: (1) `leave_requests_manager_read` policy for manager to SELECT direct reports' requests; (2) `leave_balances_manager_read` for manager to see direct reports' balances; (3) `leave_types_authenticated_read` so all authenticated users can read active leave types (fixes the 0-balance issue — `getLeaveTypes()` was returning `[]` for non-admin users, falling back to hardcoded defaults). **Action required**: run `sql/037_leave_manager_read.sql` in Supabase SQL Editor, then run `GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;`. Also fixed nested `<tr>` HTML error in `ManagerLeaveQueue` Row component.

---

### M1-2 · Leave Queue — approve a request -c 
- **Profile**: Manager (on Leave Queue tab)
- **Setup**: M1-1 done, at least one pending request visible
- **Steps**:
  1. Find a **Pending** leave request in the queue
  2. Click the **✓ Approve** button on that row
- **Pass**: Success flash appears. The request's status changes to **ManagerApproved** (blue badge) if 2-level approval is configured, or **Approved** (green) if single-level. The request moves out of the pending section.
- **Bug**:

---

### M1-3 · Leave Queue — reject a request (with reason) -bug 
- **Profile**: Manager (on Leave Queue tab)
- **Setup**: At least one more pending request exists. If none, seed another:
  ```sql
  INSERT INTO leave_requests
    (user_id, employee_id, leave_type_code, start_date, end_date, days_requested, reason, status)
  SELECT e.user_id, e.id, 'SICK', CURRENT_DATE + INTERVAL '14 days',
         CURRENT_DATE + INTERVAL '14 days', 1, 'Medical appointment — manual test', 'Pending'
  FROM employees e
  WHERE e.reporting_manager_id IS NOT NULL
    AND e.employment_status NOT IN ('Terminated')
  LIMIT 1;
  ```
- **Steps**:
  1. Find a **Pending** request
  2. Click the **✗ Reject** button
  3. An inline reason form appears — enter reason: `Insufficient coverage during that period`
  4. Click **Reject** / confirm
- **Pass**: Success flash. Request status changes to **ManagerRejected** (red badge). The rejection reason is stored.
- **Bug**: doesnt let me type more than one letter at a time for the reason , need to click each time for next letter. 
  - **Fixed**: `RejectModal` was defined as an inner function component inside `ManagerLeaveQueue` — React created a new function identity on every parent re-render (each keystroke), causing the textarea to unmount/remount and lose focus. Inlined the modal JSX directly in the component's return statement so React preserves the textarea DOM node across re-renders.

---

### M1-4 · Leave Queue — history toggle -c 
- **Profile**: Manager (on Leave Queue tab)
- **Setup**: M1-2 and M1-3 done (at least one approved and one rejected request exist)
- **Steps**:
  1. Look for a **chevron toggle** button (ChevronDown/ChevronUp) below the pending section
  2. Click it to expand the **History** section
- **Pass**: Previously approved (ManagerApproved) and rejected (ManagerRejected) requests are visible with their status badges and reasons. Clicking the chevron again collapses the section.
- **Bug**:

---

## M-2. EXPENSE QUEUE (tab 2)

### M2-1 · Expense Queue — view pending expenses -c 
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Expense Queue** tab. A direct report must have submitted an expense claim. Seed one if needed:
  ```sql
  INSERT INTO expense_claims
    (user_id, employee_id, category, amount, expense_date, description, status)
  SELECT e.user_id, e.id, 'meals', 275, CURRENT_DATE - INTERVAL '1 day',
         'Working lunch — manager test', 'pending'
  FROM employees e
  WHERE e.reporting_manager_id IS NOT NULL
    AND e.employment_status NOT IN ('Terminated')
  LIMIT 1;
  ```
- **Steps**:
  1. Click the **Expense Queue** tab in the sidebar (Receipt icon, 2nd tab)
  2. Wait for data to load
- **Pass**: Direct reports' pending expense claims are listed. Each shows: **employee name**, **category**, **amount** (AED), **date**, **description**. If no claims exist, an empty state is shown.
- **Bug**:

---

### M2-2 · Expense Queue — approve a claim -bug 
- **Profile**: Manager (on Expense Queue tab)
- **Setup**: M2-1 done, at least one pending claim visible
- **Steps**:
  1. Find a **Pending** expense claim
  2. Click the **✓ Approve** button
- **Pass**: Success flash. Status changes to **manager_approved** (blue). The claim leaves the pending list. This is a pre-approval — HR must still do final sign-off from the admin Expenses page.
- **Bug**:show the expense approved by manager , even after it goies to HR , snow the final staus of that claim to the manager 
  - **Fixed**: Added `'approved'`, `'paid'`, and `'rejected'` to the filter tabs in `ManagerExpenseQueue.jsx` so managers can track the final HR outcome of claims they pre-approved. `STATUS_LABEL` already had entries for all these statuses.

---

### M2-3 · Expense Queue — reject a claim (with reason) -c 
- **Profile**: Manager (on Expense Queue tab)
- **Setup**: At least one more pending claim exists. Seed if needed (same SQL as M2-1 but change category/amount).
- **Steps**:
  1. Find a **Pending** expense claim
  2. Click the **✗ Reject** button
  3. Enter reason: `Missing receipt — please resubmit with proof`
  4. Confirm
- **Pass**: Success flash. Status changes to **manager_rejected** (red). The rejection reason is stored and visible.
- **Bug**:

---

## M-3. APPRAISALS — TEAM (tab 3)

### M3-1 · Appraisals — view team appraisals - ui bug 
- **Profile**: Manager (signed in)
- **Setup**: An appraisal cycle must be **open** or **active** in the admin portal, and at least one of the manager's direct reports must be **assigned** to that cycle (Admin → Appraisals → open cycle → Reviews tab → Assign Staff). If this hasn't been done yet on Day 9, do it now from the admin portal before continuing.
- **Steps**:
  1. Click the **Appraisals** tab in the sidebar (Star icon, 3rd tab)
  2. Wait for data to load
- **Pass**: Direct reports' appraisals are listed. Each shows: **employee name**, **job title**, **cycle name**, **review period**, **status badge**, **overall rating** (stars). The manager's **own** appraisal must NOT appear in this list (self-exclusion via `get_manager_employee_id` filter). If no appraisals are assigned, an empty state is shown.
- **Bug**: ui too cramped space it out and center it more 
  - **Fixed**: Restructured `ManagerAppraisals.jsx` layout — separated `emp-page-header` outside `emp-page-body` for proper page structure, increased card gaps from 12px to 16px, expanded header padding from 14px to 16px, expanded section padding from 16px to 20px/24px, added explicit cell padding to table cells, increased font sizes for employee names and overall rating.

---

### M3-2 · Appraisals — rate sections - bug 
- **Profile**: Manager (on Appraisals tab)
- **Setup**: M3-1 done, at least one appraisal visible with status `pending` or `reviewed`
- **Steps**:
  1. Click on an appraisal row to **expand** it
  2. Five sections should be visible (e.g. Clinical Competency, Patient Care, Teamwork, Professional Development, Attendance & Punctuality)
  3. Click on the **star rating** for the first section — rate it 4 out of 5
  4. Enter a comment in the comment field: `Strong clinical skills demonstrated`
  5. Rate remaining sections (any rating 1-5)
  6. Click **Save**
- **Pass**: Success flash confirms ratings saved. Stars reflect the chosen ratings. Comments are persisted. Overall rating re-computes as a weighted average. Reloading the page retains the ratings.
- **Bug**: when i click save the "saved" modal shows up, then vanishes , and remains as pedning 
  - **Fixed**: `managerRateSection()` only updated the section's rating/comments — never touched the parent appraisal's `status` or `overall_rating`. Enhanced it to fetch all sibling sections after saving, compute the weighted overall rating, and update the appraisal (status → `'reviewed'` when all sections are rated). Requires new migration `sql/038_appraisal_manager_update.sql` (manager UPDATE policy on `appraisals` table).

---

### M3-3 · Appraisals — calibrated appraisal is locked -  bug 
- **Profile**: Manager (on Appraisals tab)
- **Setup**: An appraisal with `status = 'calibrated'` must exist. If none, the admin can calibrate one: Admin portal → Appraisals → open cycle → Reviews tab → find an employee → Calibrate button. If you haven't done Day 9 yet, ⏭ **DEFER — return after completing AP-6 on Day 9**.
- **Steps**:
  1. Find an appraisal with a **Calibrated** badge (green)
  2. Try to expand it and interact with the star ratings
- **Pass**: Star rating inputs are **disabled/locked** — clicking does nothing. The manager can still read the ratings and comments but cannot change them.
- **Bug**:for the manager make the appraisals module and my appraisals module the same , in the appraisals module you can switch to "my apprsaislas" to view it , and give warning saying once apprasial is sent sayingit is final. 
  - **Fixed**: Merged My Appraisals into ManagerAppraisals as a sub-view toggle (Team Appraisals / My Appraisals buttons). Removed separate `my-appraisals` tab from ManagerShell. Added finality warning dialog before saving appraisal ratings ("Once submitted, ratings are final and sent to HR for calibration").

---

## M-4. HOME (tab 4)

### M4-1 · Home — welcome card and overview - ui issue 
- **Profile**: Manager (signed in)
- **Setup**: None
- **Steps**:
  1. Click the **Home** tab in the sidebar (Home icon, 4th tab)
  2. Check the welcome card
  3. Check for leave balance summary stat cards
  4. Check for "My Assigned Assets" card
  5. Check for upcoming schedule preview
- **Pass**: Welcome card shows the manager's name and company name. Leave balance stat cards display remaining days for each type (Annual, Sick, etc.). If the manager has assets assigned, the "My Assigned Assets" card shows them. If a roster is published for the current month, an upcoming schedule preview appears. All sections render without errors — empty sections show appropriate empty states, not crashes.
- **Bug**: make it so the home module it the first module in the nav bar . allow the nav bar t0 be closed and expaned for employee and manager like in the admin portal 
  - **Fixed**: Reordered TABS so Home is first (default tab). Added collapsible sidebar to both ManagerShell and EmployeeShell with PanelLeftClose/PanelLeftOpen toggle, localStorage persistence, and CSS transitions matching admin portal pattern.

---

## M-5. MY LEAVE (tab 5)

### M5-1 · My Leave — view balances and apply -c 
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **My Leave** tab (CalendarDays icon, 5th tab)
- **Steps**:
  1. Click the **My Leave** tab
  2. Check that leave balances are displayed (Annual, Sick, etc. with days remaining)
  3. Click the **Apply** button
  4. An inline form appears inside an `.emp-card` (NOT a modal)
  5. Select **Leave Type** from the dropdown (e.g. Annual Leave)
  6. Set **Start Date** to a date next week
  7. Set **End Date** to 2 days after start date
  8. Enter **Reason**: `Personal travel — manager test`
  9. Click **Submit**
- **Pass**: Success toast appears. The form hides. The new request appears in the history table with **Pending** status badge. Leave balance adjusts accordingly.
- **Bug**:

---

### M5-2 · My Leave — cancel a pending request -c 
- **Profile**: Manager (on My Leave tab)
- **Setup**: M5-1 done (a pending request exists)
- **Steps**:
  1. Find the pending request just submitted in the history table
  2. Click **Cancel**
- **Pass**: Request status changes to **Cancelled**. Leave balance is restored.
- **Bug**:

---

## M-6. SCHEDULE (tab 6)

### M6-1 · Schedule — view published roster -bug 
- **Profile**: Manager (signed in)
- **Setup**: The admin must have published a roster that includes the manager employee for the current month (Day 10, RO-8). If no roster is published, this tab will show an empty state.
- **Steps**:
  1. Click the **Schedule** tab (CalendarClock icon, 6th tab)
  2. Check the monthly view
- **Pass**: Published shifts for the current month are displayed. Each shift card shows: **date**, **shift name**, **colour pill**, **start/end times**. If no published roster exists for this employee, an appropriate empty state or "No shifts scheduled" message appears.
- **Bug**: roster for july waspunlished but manager and employee cant see
  - **Fixed**: Added fallback direct query in `getMyRoster()` when the `employee_get_my_roster` RPC returns empty or fails. Falls back to querying `roster_assignments` table directly via existing RLS policy `roster_assignments_employee_read`, joining with `shifts` for shift details.

---

### M6-2 · Schedule — request a shift swap - bug  
- **Profile**: Manager (on Schedule tab)
- **Setup**: M6-1 done, at least one upcoming shift visible. At least one colleague must exist (another employee in the same company).
- **Steps**:
  1. Find a shift on an **upcoming** date (today or future)
  2. Click **Request Swap**
  3. The **SwapModal** opens
  4. Select a **Target Colleague** from the dropdown
  5. Select a **Target Date**
  6. Enter **Reason**: `Schedule conflict — manual test`
  7. Click **Submit**
- **Pass**: Success flash. The swap request is created. It will appear in the admin's Roster → Swaps tab for approval.
- **Bug**: for the manager and employee , adda a feature to show their swap requests and status, should also notify admin of a swap request.

---

## M-7. ATTENDANCE (tab 7) 

### M7-1 · Attendance — clock in -c 
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Attendance** tab (Clock icon, 7th tab). The manager must NOT have already clocked in today. If they have, skip to M7-3.
- **Steps**:
  1. Click the **Attendance** tab
  2. Check today's card — should show "Not started" or similar
  3. Click **Clock In**
- **Pass**: Optimistic UI update — button immediately switches to **Clock Out**. Status changes to **PRESENT**. The clock-in time is displayed.
- **Bug**:

---

### M7-2 · Attendance — clock out -c 
- **Profile**: Manager (on Attendance tab)
- **Setup**: M7-1 done (clocked in today)
- **Steps**:
  1. Click **Clock Out**
- **Pass**: Total hours for today are displayed. Clock Out button becomes disabled. Clock In button remains disabled (cannot clock in again same day).
- **Bug**:

---

### M7-3 · Attendance — history and regularisation - bug , doesnt exist 
- **Profile**: Manager (on Attendance tab)
- **Setup**: M7-1/M7-2 done, or the manager has at least some past attendance data
- **Steps**:
  1. Scroll down to the **Attendance History** table
  2. Check past days: in/out times, total hours, status chips (PRESENT, ABSENT, etc.)
  3. Click **Request Regularisation**
  4. Fill in: a past date, expected clock-in time (e.g. 09:00), expected clock-out time (e.g. 17:00), reason: `Forgot to clock in — manual test`
  5. Submit
- **Pass**: History table shows past records with correct formatting (DD/MM/YYYY dates). Regularisation form submits successfully — the request goes to admin for approval. Success toast confirms submission.
- **Bug**:

---

## M-8. PAYSLIPS (tab 8)

### M8-1 · Payslips — view and download -c 
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Payslips** tab (FileText icon, 8th tab). Payslips must have been generated for this employee in a previous payroll run (Day 5). If no payslips exist, this will show an empty state.
- **Steps**:
  1. Click the **Payslips** tab
  2. Check the payslip list: period, basic salary, net pay
  3. If payslips exist, click the **Download** (PDF) button on one
- **Pass**: Payslip list loads with correct data. PDF downloads with company logo, employee details, and full salary breakdown (basic, allowances, deductions, net pay). If no payslips exist, an appropriate empty state is shown — not a crash or blank screen.
- **Bug**:

---

## M-9. ADVANCES (tab 9)

### M9-1 · Advances — view active advances -c 
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Advances** tab (DollarSign icon, 9th tab). If the manager has any active or pending advances, they'll appear. If none exist, this tests the empty state.
- **Steps**:
  1. Click the **Advances** tab
  2. Check for any active advances with progress bars
  3. Check for any pending advances with "Awaiting Approval" badges
- **Pass**: Active advances show a progress bar: `(disbursed – outstanding) / disbursed × 100%`. Pending advances show an amber badge. If no advances exist, an appropriate empty state is shown. No crashes or blank screen.
- **Bug**:

---

### M9-2 · Advances — request a new advance -c 
- **Profile**: Manager (on Advances tab)
- **Setup**: M9-1 done
- **Steps**:
  1. Find the **Request Advance** form
  2. Enter **Amount**: `3000`
  3. Enter **Reason**: `Emergency medical expense — manager test`
  4. Click **Submit**
- **Pass**: Success toast. A new advance appears in the list with **Pending** status (amber "Awaiting Approval" badge). The admin will see it in the Advances page for approval.
- **Bug**:

---

## M-10. EXPENSES — OWN (tab 10)

### M10-1 · Expenses — view own claims -c 
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Expenses** tab (Receipt icon, 10th tab — labelled "Expenses", distinct from "Expense Queue" which is tab 2)
- **Steps**:
  1. Click the **Expenses** tab (10th in the sidebar)
  2. Check for any existing expense claims and their status badges
- **Pass**: The manager's own expense claims are listed with status badges (Pending, Manager Approved, HR Approved, Paid, Rejected). If no claims exist, an empty state is shown. This is the manager's personal expense view — NOT the approval queue.
- **Bug**:

---

### M10-2 · Expenses — submit own expense claim -c 
- **Profile**: Manager (on Expenses tab)
- **Setup**: M10-1 done
- **Steps**:
  1. Find the **Submit Expense** form
  2. Select **Category**: `transportation`
  3. Enter **Amount**: `150`
  4. Set **Date**: today
  5. Enter **Description**: `Taxi to branch office — manager test`
  6. Optionally enter a **Receipt URL**
  7. Click **Submit**
- **Pass**: Success toast. New claim appears in the list with **Pending** status badge. The admin will see it in the admin Expenses page.
- **Bug**:

---

## M-11. TRAINING (tab 5)

### M11-1 · Training — Team Training view (manager CRUD)
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Training** tab (GraduationCap icon, 5th tab). The manager must have at least one direct report. Run `sql/040_training_manager_policies.sql` in Supabase SQL Editor if not done yet.
- **Steps**:
  1. Click the **Training** tab
  2. Confirm "Team Training" / "My Training" sub-view toggle buttons are visible at the top
  3. Confirm **Team Training** is the default view
  4. Check for summary stat cards: Total · Completed · In Progress (training) + Total · Expired · Expiring Soon (certs)
  5. Check for any expired/expiring certification warning banners
  6. Click **+ Add Training** → fill in: select a direct report employee, title `CPR Refresher`, type `Internal`, status `Planned`, today's dates → **Save**
  7. Confirm the new record appears in the list
  8. Click the **pencil (Edit)** icon on the new record → change status to `Completed` → **Save**
  9. Confirm status badge updates to green **Completed**
  10. Click the **trash (Delete)** icon → confirm deletion
  11. Switch to the **Certifications** section (if separate) → click **+ Add Certification** → fill in: select a direct report, name `ACLS`, issuing body `AHA`, expiry 60 days from today → **Save**
  12. Confirm the cert appears with an amber expiry badge
- **Pass**: Manager can create, edit, and delete training records and certifications for direct reports. The manager's own records do NOT appear in the team view. Stat cards update after each action.
- **Bug**:

---

### M11-2 · Training — My Training sub-view (read-only)
- **Profile**: Manager (on Training tab)
- **Setup**: M11-1 done. The admin should have added training records for the manager employee (Day 9) for data to appear.
- **Steps**:
  1. Click the **"My Training"** toggle button at the top
  2. View switches to the manager's own training records and certifications
  3. Confirm there are **no** Add/Edit/Delete buttons visible — view is **read-only**
  4. Click **"Team Training"** to switch back
- **Pass**: My Training shows only the manager's own records in read-only mode. Switching back to Team Training restores the interactive team view. No errors.
- **Bug**:

---

## M-12. MY APPRAISALS (sub-view within Appraisals tab)

### M12-1 · My Appraisals — view own appraisal (read-only)
- **Profile**: Manager (signed in)
- **Setup**: Click the **Appraisals** tab (Star icon, 4th tab). The manager must have been assigned to an appraisal cycle by the admin (Day 9).
- **Steps**:
  1. Click the **"My Appraisals"** toggle button at the top of the Appraisals tab (switches from Team Appraisals view)
  2. Check for appraisal rows: cycle name, review period, overall rating stars, status badge
  3. Click on a row to **expand** it
  4. Check sections: section name, weight, star rating, comments
  5. Check for development plan text and reviewer comments
  6. Try clicking on the star rating inputs
  7. Click **"Team Appraisals"** to switch back
- **Pass**: My Appraisals shows the manager's own reviews. Expanding a row shows sections with ratings and comments. Star inputs are **read-only** — the manager cannot rate themselves. Status badges display correctly: Pending (grey), Reviewed (blue), Calibrated (green). If no appraisals exist, an appropriate empty state is shown. Switching back to Team Appraisals restores the interactive view.
- **Bug**:

---

## M-13. DOCUMENTS (tab 12)

### M13-1 · Documents — view and upload
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Documents** tab (FolderOpen icon, 12th tab)
- **Steps**:
  1. Click the **Documents** tab
  2. Check for any existing documents with status badges (Pending Review / Verified / Rejected)
  3. Check that clinical credentials show a cyan "Clinical" badge
  4. Find the **Upload Document** form
  5. Select **Document Type** from the grouped dropdown (UAE Residency / Clinical Credentials / General)
  6. Enter **Document Number**: `DOC-MGR-001`
  7. Set **Expiry Date**: 6 months from today
  8. Enter **Notes**: `Manager test upload`
  9. Click the drop-zone to **choose a file** (any small file — PDF, image)
  10. Click **Submit** / Upload
- **Pass**: Upload succeeds — a new row appears with **"Pending Review"** badge and "Self-submitted" label. The admin will see it in the employee's Documents tab for verification. Document type, number, expiry, and notes are all stored correctly.
- **Bug**:

---

## M-14. REQUESTS (tab 13)

### M14-1 · Requests — submit a letter request
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Requests** tab (Mail icon, 13th tab)
- **Steps**:
  1. Click the **Requests** tab
  2. Find the **"Request a Letter"** card
  3. Select **Letter Type** from the dropdown (e.g. "Salary Certificate — Bank")
  4. Enter **Purpose / Addressed To**: `Bank mortgage application — manager test`
  5. Click **Submit Request**
- **Pass**: Success toast. Form resets. The new request appears in the **My Requests** table below with **Pending Review** status (amber clock icon). The admin will see it in their Letter Requests page with a pending count badge.
- **Bug**:

---

### M14-2 · Requests — view request history
- **Profile**: Manager (on Requests tab)
- **Setup**: M14-1 done
- **Steps**:
  1. Check the **My Requests** table below the form
  2. Verify columns: Letter Type, Purpose, Requested date (DD/MM/YYYY), Status
  3. Check status badges: Pending Review (amber) for the just-submitted request
- **Pass**: Table shows correct data. Date format is DD/MM/YYYY. Status badges render correctly. If any previous requests were completed or rejected by admin, those show "Ready" (green) or "Rejected" (red) badges respectively, with completion date or rejection reason inline.
- **Bug**:

---

## M-15. PROFILE (tab 14)

### M15-1 · Profile — view and edit
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Profile** tab (User icon, 14th/last tab)
- **Steps**:
  1. Click the **Profile** tab
  2. Verify the profile loads: **name**, **job title**, **department**, **start date**, **phone**, **emergency contact**, **bank details**
  3. All fields should be **read-only** (no inputs visible)
  4. Click the **Edit** button
  5. Input fields appear — change the **phone number** to `+971 55 999 8888`
  6. Click **Save**
  7. Verify the toast confirms the update and the new phone number is displayed
  8. Click **Edit** again → change something → click **Cancel**
- **Pass**: Step 3 — all values displayed as text, no input fields. Step 4 — inputs appear after clicking Edit. Step 6 — toast confirms success, phone number updates. Step 8 — Cancel discards the change, inputs disappear, original value restored.
- **Bug**:

---

## NOTIFICATION BELL (Manager)

### MN-1 · Notification bell — visibility and interaction
- **Profile**: Manager (signed in on any tab)
- **Setup**: Leave approval from M1-2 should have generated a `leave_approved` notification for the affected employee. If the manager has any notifications themselves, they'll appear here.
- **Steps**:
  1. Look for the **bell icon** in the sidebar (button with title "Notifications")
  2. If a red badge/count is visible, note the number
  3. Click the bell icon
  4. The notification panel opens as a right-side drawer
  5. Click on a notification to mark it as read
  6. Click the bell again to close the panel
- **Pass**: Bell is visible and clickable. Panel opens smoothly on the right side (width: 380px). Notifications show with emoji prefix icons. Clicking a notification marks it read (badge count decrements). Panel closes on second click.
- **Bug**:

---

---

# DAY 12 — Manager Portal (remaining) · Employee Auth · Employee tabs E-1 through E-7

> **Before you start**
> Sign in as **Manager** first to finish the remaining Day 11 items (M6-2, M7-3, M11-1/2, M12-1, M13-1, M14-1/2, M15-1, MN-1).
> Then sign out and set up the Employee portal account.
>
> **Deferred items handled today**: DOC-4, DOC-5 (verify/reject self-uploaded doc — needs employee self-upload first), PORTAL-1 (portal role dropdown — needs employee registration first).
>
> **SQL prerequisites** (if not already run on Day 11):
> - `sql/039_shifts_read_policy.sql`
> - `sql/040_training_manager_policies.sql`

---

## Remaining Manager Portal items — ⏭ carried from Day 11

> Sign in as the **Manager** to complete these before moving to Employee Auth below.

---

### M6-2 · Schedule — request a shift swap — ⏭ carried from Day 11
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Schedule** tab (CalendarClock icon). At least one upcoming shift must be visible (requires a published roster that includes the manager — Day 10 RO-8). At least one colleague (another employee in the same company) must exist.
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

### M7-3 · Attendance — history and regularisation — ⏭ carried from Day 11
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Attendance** tab (Clock icon). The manager must have clocked in at least once (Day 11 M7-1/M7-2) so history data exists.
- **Steps**:
  1. Scroll down to the **Attendance History** table
  2. Check past days: in/out times, total hours, status chips (PRESENT, ABSENT, etc.)
  3. Find or click **Request Regularisation**
  4. Fill in: a past date, expected clock-in time (e.g. `09:00`), expected clock-out time (e.g. `17:00`), reason: `Forgot to clock in — manual test`
  5. Submit
- **Pass**: History table shows past records with correct formatting (DD/MM/YYYY dates). Regularisation form submits successfully — the request goes to admin for approval. Success toast confirms submission.
- **Bug**:

---

### M11-1 · Training — Team Training view (manager CRUD) — ⏭ carried from Day 11
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Training** tab (GraduationCap icon). The manager must have at least one direct report. Run `sql/040_training_manager_policies.sql` in Supabase SQL Editor if not done yet.
- **Steps**:
  1. Click the **Training** tab
  2. Confirm "Team Training" / "My Training" sub-view toggle buttons are visible at the top
  3. Confirm **Team Training** is the default view
  4. Check for summary stat cards: Total · Completed · In Progress (training) + Total · Expired · Expiring Soon (certs)
  5. Check for any expired/expiring certification warning banners
  6. Click **+ Add Training** → fill in: select a direct report employee, title `CPR Refresher`, type `Internal`, status `Planned`, today's dates → **Save**
  7. Confirm the new record appears in the list
  8. Click the **pencil (Edit)** icon on the new record → change status to `Completed` → **Save**
  9. Confirm status badge updates to green **Completed**
  10. Click the **trash (Delete)** icon → confirm deletion
  11. Switch to the **Certifications** section → click **+ Add Certification** → fill in: select a direct report, name `ACLS`, issuing body `AHA`, expiry 60 days from today → **Save**
  12. Confirm the cert appears with an amber expiry badge
- **Pass**: Manager can create, edit, and delete training records and certifications for direct reports. The manager's own records do NOT appear in the team view. Stat cards update after each action.
- **Bug**:

---

### M11-2 · Training — My Training sub-view (read-only) — ⏭ carried from Day 11
- **Profile**: Manager (on Training tab)
- **Setup**: M11-1 done. The admin should have added training records for the manager employee (Day 9) for data to appear.
- **Steps**:
  1. Click the **"My Training"** toggle button at the top
  2. View switches to the manager's own training records and certifications
  3. Confirm there are **no** Add/Edit/Delete buttons visible — view is **read-only**
  4. Click **"Team Training"** to switch back
- **Pass**: My Training shows only the manager's own records in read-only mode. Switching back to Team Training restores the interactive team view. No errors.
- **Bug**:

---

### M12-1 · My Appraisals — view own appraisal (read-only) — ⏭ carried from Day 11
- **Profile**: Manager (signed in)
- **Setup**: Click the **Appraisals** tab (Star icon). The manager must have been assigned to an appraisal cycle by the admin (Day 9).
- **Steps**:
  1. Click the **"My Appraisals"** toggle button at the top of the Appraisals tab (switches from Team Appraisals view)
  2. Check for appraisal rows: cycle name, review period, overall rating stars, status badge
  3. Click on a row to **expand** it
  4. Check sections: section name, weight, star rating, comments
  5. Check for development plan text and reviewer comments
  6. Try clicking on the star rating inputs
  7. Click **"Team Appraisals"** to switch back
- **Pass**: My Appraisals shows the manager's own reviews. Expanding a row shows sections with ratings and comments. Star inputs are **read-only** — the manager cannot rate themselves. Status badges display correctly: Pending (grey), Reviewed (blue), Calibrated (green). If no appraisals exist, an appropriate empty state is shown. Switching back to Team Appraisals restores the interactive view.
- **Bug**:

---

### M13-1 · Documents — view and upload — ⏭ carried from Day 11
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Documents** tab (FolderOpen icon)
- **Steps**:
  1. Click the **Documents** tab
  2. Check for any existing documents with status badges (Pending Review / Verified / Rejected)
  3. Check that clinical credentials show a cyan "Clinical" badge
  4. Find the **Upload Document** form
  5. Select **Document Type** from the grouped dropdown (UAE Residency / Clinical Credentials / General)
  6. Enter **Document Number**: `DOC-MGR-001`
  7. Set **Expiry Date**: 6 months from today
  8. Enter **Notes**: `Manager test upload`
  9. Click the drop-zone to **choose a file** (any small file — PDF, image)
  10. Click **Submit** / Upload
- **Pass**: Upload succeeds — a new row appears with **"Pending Review"** badge and "Self-submitted" label. The admin will see it in the employee's Documents tab for verification. Document type, number, expiry, and notes are all stored correctly.
- **Bug**:

---

### M14-1 · Requests — submit a letter request — ⏭ carried from Day 11
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Requests** tab (Mail icon)
- **Steps**:
  1. Click the **Requests** tab
  2. Find the **"Request a Letter"** card
  3. Select **Letter Type** from the dropdown (e.g. "Salary Certificate — Bank")
  4. Enter **Purpose / Addressed To**: `Bank mortgage application — manager test`
  5. Click **Submit Request**
- **Pass**: Success toast. Form resets. The new request appears in the **My Requests** table below with **Pending Review** status (amber clock icon). The admin will see it in their Letter Requests page with a pending count badge.
- **Bug**:

---

### M14-2 · Requests — view request history — ⏭ carried from Day 11
- **Profile**: Manager (on Requests tab)
- **Setup**: M14-1 done
- **Steps**:
  1. Check the **My Requests** table below the form
  2. Verify columns: Letter Type, Purpose, Requested date (DD/MM/YYYY), Status
  3. Check status badges: Pending Review (amber) for the just-submitted request
- **Pass**: Table shows correct data. Date format is DD/MM/YYYY. Status badges render correctly. If any previous requests were completed or rejected by admin, those show "Ready" (green) or "Rejected" (red) badges respectively, with completion date or rejection reason inline.
- **Bug**:

---

### M15-1 · Profile — view and edit — ⏭ carried from Day 11
- **Profile**: Manager (signed in)
- **Setup**: Switch to the **Profile** tab (User icon, last tab)
- **Steps**:
  1. Click the **Profile** tab
  2. Verify the profile loads: **name**, **job title**, **department**, **start date**, **phone**, **emergency contact**, **bank details**
  3. All fields should be **read-only** (no inputs visible)
  4. Click the **Edit** button
  5. Input fields appear — change the **phone number** to `+971 55 999 8888`
  6. Click **Save**
  7. Verify the toast confirms the update and the new phone number is displayed
  8. Click **Edit** again → change something → click **Cancel**
- **Pass**: Step 3 — all values displayed as text, no input fields. Step 4 — inputs appear after clicking Edit. Step 6 — toast confirms success, phone number updates. Step 8 — Cancel discards the change, inputs disappear, original value restored.
- **Bug**:

---

### MN-1 · Notification bell — visibility and interaction — ⏭ carried from Day 11
- **Profile**: Manager (signed in on any tab)
- **Setup**: Leave approval from M1-2 (Day 11) should have generated a `leave_approved` notification for the affected employee. If the manager has any notifications themselves, they'll appear here.
- **Steps**:
  1. Look for the **bell icon** in the sidebar (button with title "Notifications")
  2. If a red badge/count is visible, note the number
  3. Click the bell icon
  4. The notification panel opens as a right-side drawer
  5. Click on a notification to mark it as read
  6. Click the bell again to close the panel
- **Pass**: Bell is visible and clickable. Panel opens smoothly on the right side (width: 380px). Notifications show with emoji prefix icons. Clicking a notification marks it read (badge count decrements). Panel closes on second click.
- **Bug**:

---

## Deferred from earlier days

### DOC-4 · Verify a pending document — ⏭ deferred from Day 3, do this now
- **Profile**: Admin (sign in as Admin)
- **Setup**: The manager (or employee) must have uploaded a document via their portal (M13-1 above). That document will have `status='pending'` and a "Self-submitted" label in the admin's view.
- **Steps**:
  1. Sign in as **Admin**
  2. Go to **Employees** → open the manager/employee's record → **Documents** tab
  3. Find the self-submitted document row (status: "Pending Review", label: "Self-submitted")
  4. Click the **✓** (verify) button
- **Pass**: Status badge changes to **Verified**. The "Self-submitted" label remains visible.
- **Bug**:

---

### DOC-5 · Reject a pending document — ⏭ deferred from Day 3, do this now
- **Profile**: Admin
- **Setup**: The employee must have uploaded a second document via their portal (do this from the employee portal after Employee Auth below, or re-upload from manager portal).
- **Steps**:
  1. Find the second self-submitted document in the admin Documents tab
  2. Click the **✗** (reject) button
  3. Enter a rejection reason
  4. Confirm
- **Pass**: Status badge changes to **Rejected**, rejection reason visible on the row.
- **Bug**:

---

### PORTAL-1 · Portal Role dropdown — ⏭ deferred from Day 3, do this now
- **Profile**: Admin
- **Setup**: An employee must have completed self-registration (Employee Auth below). Their `authUserId` is now set.
- **Steps**:
  1. Sign in as **Admin**
  2. Go to **Employees** → open the registered employee's record → **Job & Contract** tab
  3. Find the **Portal Role** dropdown (only appears when `employee.authUserId` is set)
  4. Change the role (e.g. Employee → Manager or vice versa)
- **Pass**: The dropdown appears. Changing the value takes effect immediately (direct RPC call, no Save button needed). If you changed to Manager, signing in again as that employee should load ManagerShell.
- **Bug**:

---

## Employee AUTH

### EA-1 · First-time employee registration
- **Profile**: Employee (not yet registered)
- **Setup**: Sign out of any current session. An employee must exist in the admin portal with a valid `work_email` that you can access (to receive the confirmation email or use as login).
- **Steps**:
  1. Go to `http://localhost:5173`
  2. On the right side, find the **"Sign in as Employee / Manager"** form
  3. Click **"Register as Employee"** (toggle or link)
  4. Enter the email matching the employee's `work_email` in the admin system
  5. Enter a password and confirm
  6. Click **Register**
- **Pass**: A green success banner appears ("Account created successfully" or similar). The form switches back to sign-in mode. The employee does NOT auto-login — they must manually sign in.
- **Bug**:

---

### EA-2 · Sign in as employee
- **Profile**: Employee (registered from EA-1)
- **Setup**: EA-1 done
- **Steps**:
  1. Enter the registered email and password in the **"Sign in as Employee / Manager"** form
  2. Click **Sign in**
- **Pass**: Lands on the **EmployeeShell** with the **Home** tab active. Sidebar shows the employee's **name** (bold) and **job title** below — NOT their email address. The notification bell icon is visible.
- **Bug**:

---

### EA-3 · Employee sign-out
- **Profile**: Employee (signed in from EA-2)
- **Setup**: EA-2 done
- **Steps**:
  1. Click **Sign Out** in the sidebar footer (or Profile tab)
- **Pass**: Returns to the login page. No errors in the console.
- **Note**: Sign back in as the employee for the remaining tests.
- **Bug**:

---

## E-1. HOME

### E1-1 · Home — welcome card and overview
- **Profile**: Employee (signed in)
- **Setup**: None
- **Steps**:
  1. Confirm the **Home** tab is active (first tab after sign-in)
  2. Check the welcome card at the top
  3. Check for leave balance summary stat cards below
  4. Check for "My Assigned Assets" card (may be empty)
  5. Check for upcoming schedule preview (if roster published for current month)
- **Pass**: Welcome card shows the employee's name and company name. Leave balance stat cards display remaining days per type (Annual, Sick, etc.). If assets are assigned to this employee, they appear in the assets card. If a roster is published for the current month, an upcoming schedule preview appears. All sections render without errors — empty sections show appropriate empty states, not crashes.
- **Bug**:

---

## E-2. LEAVE

### E2-1 · Leave — view balances and apply for leave
- **Profile**: Employee (signed in)
- **Setup**: Switch to the **Leave** tab
- **Steps**:
  1. Click the **Leave** tab in the sidebar
  2. Check leave balances per type: Annual, Sick, etc. with days remaining
  3. If the employee is on probation, check for an amber banner listing restricted leave types
  4. Click **Apply** — an inline form appears inside an `.emp-card` (NOT a modal)
  5. Verify the **Leave Type** dropdown shows only eligible types (restricted types hidden for probation employees)
  6. Select **Annual Leave** (or any eligible type)
  7. Set **Start Date** to a date next week
  8. Set **End Date** to 2 days after start date
  9. Enter **Reason**: `Personal travel — employee test`
  10. Click **Submit**
- **Pass**: Success toast appears. Form hides. The new request appears in the My Requests history table with **Pending** status badge. Leave balance adjusts. If the leave type has `requires_attachment = true`, a file picker + hint text appear in the form.
- **Bug**:

---

### E2-2 · Leave — validation and cancel
- **Profile**: Employee (on Leave tab)
- **Setup**: E2-1 done (a pending request exists)
- **Steps**:
  1. Click **Apply** again → set End Date **before** Start Date → try to Submit
  2. Confirm a validation error appears and submission is blocked
  3. Close the form
  4. Find the pending request from E2-1 in the My Requests table
  5. Click **Cancel** on that request
- **Pass**: Step 1 — validation error blocks submission. Step 5 — request status changes to **Cancelled**, leave balance is restored.
- **Bug**:

---

## E-3. SCHEDULE

### E3-1 · Schedule — view published roster and request swap
- **Profile**: Employee (signed in)
- **Setup**: Switch to the **Schedule** tab. The admin must have published a roster that includes this employee for the current month (Day 10 RO-8). If no roster is published, this tab will show an empty state.
- **Steps**:
  1. Click the **Schedule** tab
  2. Check the monthly view — published shifts should be displayed
  3. Each shift card shows: **date**, **shift name**, **colour pill**, **start/end times**
  4. Find a shift on an **upcoming** date (today or future)
  5. Click **Request Swap** → SwapModal opens
  6. Select a **Target Colleague** from the dropdown
  7. Select a **Target Date**
  8. Enter **Reason**: `Schedule conflict — employee test`
  9. Click **Submit**
- **Pass**: Published shifts are visible with correct details. Swap request submits successfully (success flash). If no published roster exists, an appropriate empty state or "No shifts scheduled" message appears.
- **Bug**:

---

## E-4. ATTENDANCE

### E4-1 · Attendance — clock in, clock out, and regularisation
- **Profile**: Employee (signed in)
- **Setup**: Switch to the **Attendance** tab. The employee must NOT have already clocked in today — if they have, skip to step 4.
- **Steps**:
  1. Click the **Attendance** tab
  2. Check today's card — should show "Not started" or similar
  3. Click **Clock In** — button immediately switches to **Clock Out** (optimistic UI). Clock-in time is displayed.
  4. Click **Clock Out** — total hours for today are displayed. Clock Out button becomes disabled. Clock In button stays **disabled** (cannot clock in again same day — `isEnabled()` check, not just hidden).
  5. Scroll down to the **Attendance History** table — check past days with date (DD/MM/YYYY), in/out times, hours, status chips
  6. Click **Request Regularisation** → fill in: a past date, expected in time (`09:00`), expected out time (`17:00`), reason: `Forgot to clock in — employee test`
  7. Submit
- **Pass**: Clock in/out works with optimistic UI. Cannot clock in a second time. History table shows correct data. Regularisation request submits successfully (pending for admin review).
- **Bug**:

---

## E-5. PAYSLIPS

### E5-1 · Payslips — view and download
- **Profile**: Employee (signed in)
- **Setup**: Switch to the **Payslips** tab. Payslips must have been generated for this employee in a previous payroll run (Day 5). If no payslips exist, this will show an empty state.
- **Steps**:
  1. Click the **Payslips** tab
  2. Check the payslip list: period, gross salary, deductions, net pay
  3. Check for WPS status badge on each row (if applicable)
  4. If payslips exist, click the **Download** (PDF) button on one
- **Pass**: Payslip list loads with correct data. PDF downloads with company header, employee details, and full salary breakdown (basic, allowances, deductions, net pay). If no payslips exist, an appropriate empty state is shown.
- **Bug**:

---

## E-6. ADVANCES

### E6-1 · Advances — view and request
- **Profile**: Employee (signed in)
- **Setup**: Switch to the **Advances** tab.
- **Steps**:
  1. Click the **Advances** tab
  2. Check for any active advances with progress bars — bar should show `0%` for new advances with no repayments (not 5%)
  3. Check for any pending advances with "Awaiting Approval" amber badges
  4. Find the **Request Advance** form
  5. Enter **Amount**: `2000`
  6. Enter **Reason**: `Emergency medical expense — employee test`
  7. Click **Submit**
- **Pass**: Active advances show a progress bar at correct percentage. New advance appears in the list with **Pending** status (amber "Awaiting Approval" badge). The admin will see it in the Advances page for approval. Panels are properly padded — no text overflowing card edges.
- **Bug**:

---

## E-7. EXPENSES

### E7-1 · Expenses — view and submit claim
- **Profile**: Employee (signed in)
- **Setup**: Switch to the **Expenses** tab.
- **Steps**:
  1. Click the **Expenses** tab
  2. Check expense history list with status badges (Pending, Manager Approved, HR Approved, Paid, Rejected)
  3. Find the **Submit Expense** form
  4. Select **Category**: `meals` from the dropdown
  5. Enter **Amount**: `120`
  6. Set **Date**: today
  7. Enter **Description**: `Working lunch — employee test`
  8. Optionally enter a **Receipt URL**
  9. Click **Submit**
- **Pass**: New claim appears in the list with **Pending** status badge. Status flow is visible in the history: pending → manager_approved → approved → paid. "Manager Approved" badge appears for claims that have been pre-approved by a manager but not yet HR-approved. Panels are properly padded.
- **Bug**:

---

---

# DAY 13 — Employee tabs E-8 through E-12 · Cross-portal flows · Edge cases

> **Before you start**
> Sign in as the **Employee** (not manager, not admin).
> Day 12 must be complete — employee account registered, E-1 through E-7 tested.
> Have two additional browser windows ready (one for Admin, one for Manager) for the cross-portal flows.

---

## E-8. TRAINING

### E8-1 · Training — summary cards and training records
- **Profile**: Employee (signed in)
- **Setup**: Switch to the **Training** tab. Admin or manager should have created at least one training record for this employee (Day 9 TR-1 or Day 11 M11-1). If none exist, self-enrollment will create one.
- **Steps**:
  1. Click the **Training** tab in the sidebar
  2. Check the summary stat cards at the top: **Total Trainings**, **Completed**, **Certifications**, **Active Certs**
  3. Check for **Expired certifications** alert card (red) — lists expired certs with name and date
  4. Check for **Expiring soon** alert card (amber) — lists certs expiring within 60 days
  5. In the Training Records section, check each record shows: title, type badge, date range, duration, score/passed
  6. If a certificate URL was provided, check that "View Certificate" link opens in a new tab
- **Pass**: Summary stat cards display correct counts. Alert cards appear only when relevant (expired or expiring certs). Training records show correct details with proper formatting.
- **Bug**:

---

### E8-2 · Training — employee self-enrollment
- **Profile**: Employee (on Training tab)
- **Setup**: E8-1 done
- **Steps**:
  1. Find the **Add Training** button — it should be visible (employees can self-enroll)
  2. Click **Add Training** → an inline form appears
  3. Fill in:
     - **Title**: `Employee Self-Enrollment Test`
     - **Type**: `external`
     - **Provider**: `Online Academy`
     - **Start Date**: today
     - **End Date**: one week from today
     - **Status**: `planned` (dropdown should show `planned`, `in_progress`, `completed` — NOT `cancelled`)
  4. Click **Save**
  5. Verify the new record appears in the Training Records list
  6. Click the **Edit** button on the record just created
  7. Confirm the form pre-fills with the saved data
  8. Change **Status** to `in_progress` → click **Save**
  9. Verify the record updates with the new status
- **Pass**: Employee can create and edit their own training records. Add Training button is visible. Form saves successfully. Edit pre-fills correctly. Status change persists.
- **Bug**:

---

### E8-3 · Training — certifications read-only
- **Profile**: Employee (on Training tab)
- **Setup**: E8-2 done. Admin or manager should have added at least one certification for this employee.
- **Steps**:
  1. Scroll to the **Certifications** section
  2. Check expiry badges: **Expired** (red), **≤30d** (red), **≤60d** (yellow), **Active** (green), **No Expiry** (grey)
  3. Confirm there is NO "Add Certification" button
  4. Confirm there are NO edit or delete buttons on certification rows
  5. Confirm the label **(managed by HR / manager)** or similar is displayed
- **Pass**: Certifications section is fully read-only for employees. Badges show correct colours based on expiry. The "managed by HR / manager" label is visible. No CRUD buttons are present.
- **Bug**:

---

## E-9. APPRAISALS

### E9-1 · Appraisals — view ratings (read-only)
- **Profile**: Employee (signed in)
- **Setup**: Switch to the **Appraisals** tab. An appraisal cycle must exist with this employee assigned and rated by a manager (Day 11 M12-1 or Day 9 AP-3). If none exist, this will show an empty state.
- **Steps**:
  1. Click the **Appraisals** tab
  2. Check the appraisal list: cycle name, review period, overall rating stars, status badge
  3. Click **Expand** on an appraisal row → sections expand
  4. In each section, check: **section name**, **weight**, **manager's star rating**, **comments**
  5. Check for **development plan** text (if filled by manager)
  6. Check for **reviewer comments** (if filled)
  7. Check status badges: **Pending** (grey), **Reviewed** (blue), **Calibrated** (green)
  8. Try to interact with the star rating inputs — they should NOT respond to clicks
- **Pass**: Appraisal data displays correctly with star ratings, sections, and comments. Status badges use correct colours. The view is fully read-only — employee cannot click stars or edit any fields. If no appraisals exist, an empty state message appears (not a crash).
- **Bug**:

---

## E-10. DOCUMENTS

### E10-1 · Documents — view existing and self-upload
- **Profile**: Employee (signed in)
- **Setup**: Switch to the **Documents** tab. Admin should have uploaded at least one document for this employee (Day 3).
- **Steps**:
  1. Click the **Documents** tab
  2. Check existing docs list: **type**, **document number**, **expiry** (DD/MM/YYYY), **status badge** (Pending Review / Verified / Rejected)
  3. Check that clinical credentials (DHA Licence, DOH Licence, etc.) show a cyan **"Clinical"** badge
  4. Check that admin-uploaded docs do NOT show a "Self-submitted" label
  5. Find the **Upload Document** form
  6. Select **Document type** from the grouped dropdown (groups: UAE Residency / Clinical Credentials / General)
  7. Enter **Document Number**: `TEST-DOC-001`
  8. Set **Expiry Date**: 6 months from today
  9. Enter **Notes**: `Employee self-upload test`
  10. Click **Choose File** (or the visible drop-zone) and select a test file
  11. Click **Submit**
- **Pass**: Existing documents display correctly with proper badges. The newly uploaded document appears in the list with **"Pending Review"** status badge and "Self-submitted" label. The file uploads to Supabase Storage. If an admin previously rejected a document, the rejection reason is shown inline.
- **Bug**:

---

## E-11. REQUESTS

### E11-1 · Letter Requests — submit and view history
- **Profile**: Employee (signed in)
- **Setup**: Switch to the **Requests** tab.
- **Steps**:
  1. Click the **Requests** tab
  2. Check the "Request a Letter" card has correct padding — no text overflowing onto the card border
  3. Select **Letter Type** from the dropdown (7 types: Salary Certificate — Bank / Embassy / Personal, NOC, Experience Letter, Employment Certificate, Salary Transfer Letter)
  4. Choose **Salary Certificate — Bank**
  5. Enter **Purpose**: `Bank loan application — employee test`
  6. **Addressed To** (optional): `National Bank UAE`
  7. Click **Submit Request**
  8. Verify success toast and form resets
  9. Check the **My Requests** table: columns for Letter Type, Purpose, Requested date, Status
  10. Check the new request shows **Pending Review** (amber clock badge)
- **Pass**: Form submits successfully. Request appears in the history table with correct data and Pending Review badge. If a previously completed request exists, it shows "Ready — collect from HR" with a green checkmark and completion date. If a rejected request exists, the rejection reason is shown inline with a red X badge.
- **Bug**:

---

## E-12. PROFILE

### E12-1 · Profile — view and edit
- **Profile**: Employee (signed in)
- **Setup**: Switch to the **Profile** tab.
- **Steps**:
  1. Click the **Profile** tab
  2. Verify profile loads with: **name**, **job title**, **department**, **start date**, **phone**, **emergency contact**, **bank details**, **IBAN**
  3. Confirm all fields are **read-only** (display text, not form inputs)
  4. Click the **Edit** button
  5. Confirm form inputs appear for editable fields
  6. Change **Phone** to a new number (e.g. `+971501234567`)
  7. Click **Save**
  8. Verify success toast appears and the displayed phone number updates
  9. Click **Edit** again, change something, then click **Cancel**
  10. Verify changes are discarded and the fields return to display-only mode
- **Pass**: Profile loads with correct employee data. Read-only mode shows text, not inputs. Edit mode enables inputs. Save persists changes with a toast confirmation. Cancel discards changes and returns to read-only mode.
- **Bug**:

---

## CROSS-PORTAL WORKFLOWS

> Requires two additional browser windows (or separate browser profiles) open simultaneously — one for Admin, one for Manager.

### X-1 · Leave Request Flow (Employee → Manager → Admin)
- **Profile**: Employee + Manager + Admin (three browser windows)
- **Setup**: Employee signed in (window 1). Manager signed in (window 2). Admin signed in (window 3). Employee must have leave balance remaining.
- **Steps**:
  1. **Employee** (window 1): go to Leave tab → Apply → submit a leave request (Annual, 2 days, future dates, reason: `Cross-portal test`)
  2. **Manager** (window 2): go to **Leave Queue** tab → refresh → find the request → click **Approve**
  3. Confirm the request status changes to **ManagerApproved**
  4. **Admin** (window 3): go to **Leave** → **Requests** tab → find the ManagerApproved request → click **Final OK** (Approve)
  5. **Employee** (window 1): refresh Leave tab → check the request status
- **Pass**: Request flows Pending → ManagerApproved → Approved. Employee sees final **Approved** status.
- **Bug**:

---

### X-2 · Expense Claim Flow (Employee → Manager → Admin → Payroll)
- **Profile**: Employee + Manager + Admin (three browser windows)
- **Setup**: All three signed in. A payroll run should exist (or be created) for the current month.
- **Steps**:
  1. **Employee** (window 1): go to Expenses tab → submit an expense (`meals`, AED 150, today, `Cross-portal expense test`)
  2. **Manager** (window 2): go to **Expense Queue** tab → refresh → find the claim → click **Approve**
  3. **Admin** (window 3): go to **Expenses** → find the `manager_approved` claim → click **Approve** (final)
  4. **Admin**: open the **Payroll** for the current month → verify the approved expense appears as a line item in PayrollEditor
  5. **Admin**: generate the payroll → check that the expense status changes to **Paid**
- **Pass**: Claim flows Pending → manager_approved → approved → paid. Expense auto-loads in payroll.
- **Bug**:

---

### X-3 · Advance Flow (Employee → Admin)
- **Profile**: Employee + Admin (two browser windows)
- **Setup**: Both signed in.
- **Steps**:
  1. **Employee** (window 1): go to Advances tab → request an advance (AED 2000, reason: `Cross-portal advance test`)
  2. **Admin** (window 2): go to **Advances** → find the pending advance → click **Approve** → set repayment terms
  3. **Employee** (window 1): refresh Advances tab
- **Pass**: Employee sees the advance as **Active** with a progress bar showing repayment schedule.
- **Bug**:

---

### X-4 · Letter Flow (Employee → Admin → Employee)
- **Profile**: Employee + Admin (two browser windows)
- **Setup**: Both signed in.
- **Steps**:
  1. **Employee** (window 1): go to Requests tab → submit a letter request (e.g. NOC, purpose: `Cross-portal letter test`)
  2. **Admin** (window 2): check Dashboard for pending count badge and/or go to **Letter Requests** nav item
  3. **Admin**: find the pending request → complete the letter → print → mark as Completed
  4. **Employee** (window 1): refresh Requests tab
- **Pass**: Employee sees status change to **"Ready"** with a green checkmark and "collect from HR" note with the completion date.
- **Bug**:

---

### X-5 · Appraisal Flow (Admin → Manager → Employee)
- **Profile**: Admin + Manager + Employee (three browser windows)
- **Setup**: All three signed in. The employee must be a direct report of the manager (`reporting_manager_id` set).
- **Steps**:
  1. **Admin** (window 1): go to **Appraisals** → create a new Appraisal Cycle (or use existing)
  2. **Admin**: go to the cycle's **Reviews** tab → click **Assign Staff** → assign the employee
  3. **Manager** (window 2): go to **Appraisals** tab → Team Appraisals view → find the employee → rate sections with stars → Save
  4. **Admin** (window 1): refresh → see the manager's ratings → calibrate the final score
  5. **Employee** (window 3): go to **Appraisals** tab → expand the appraisal row
- **Pass**: Employee sees the calibrated rating with section details, star ratings, and comments. Status shows **Calibrated** (green badge).
- **Bug**:

---

### X-6 · Attendance Clock (Employee → Admin visibility)
- **Profile**: Employee + Admin (two browser windows)
- **Setup**: Both signed in. Employee must NOT have already clocked in today.
- **Steps**:
  1. **Employee** (window 1): go to Attendance tab → click **Clock In**
  2. **Admin** (window 2): go to **Attendance** module → click **Refresh** (or wait for auto-poll at 30s)
- **Pass**: Admin sees the employee's status as **Present** for today with the clock-in time.
- **Bug**:

---

### X-7 · Document Self-Upload (Employee → Admin review)
- **Profile**: Employee + Admin (two browser windows)
- **Setup**: Both signed in.
- **Steps**:
  1. **Employee** (window 1): go to Documents tab → upload a clinical credential (e.g. DHA Licence, `CRED-XP-001`)
  2. **Admin** (window 2): open the employee in **EmployeeModal** → **Documents** tab
  3. Confirm the self-submitted document shows **"Self-submitted"** label and **Pending Review** badge
  4. **Admin**: click the **Verify** (✓) button on the document
  5. **Employee** (window 1): refresh Documents tab
- **Pass**: Employee sees the document status change from Pending Review to **Verified** (green badge).
- **Bug**:

---

### X-8 · Roster Publish (Admin → Employee + Manager visible)
- **Profile**: Admin + Employee + Manager (three browser windows)
- **Setup**: All three signed in. Admin must have built and published a roster for the current month (Day 10 RO-8) that includes both the employee and the manager.
- **Steps**:
  1. **Admin** (window 1): confirm the roster is published for the current month (go to Roster → check publish status)
  2. **Employee** (window 2): go to **Schedule** tab → check that shifts are visible
  3. **Manager** (window 3): go to **Schedule** tab (My Leave → Schedule in sidebar) → check that shifts are visible
- **Pass**: Both employee and manager see their assigned shifts for the published month with correct shift names, times, and colour indicators. Unpublished months show no shifts.
- **Bug**:

---

## KNOWN EDGE CASES

### EDGE-1 · Probation + Leave restriction
- **Profile**: Admin + Employee (two browser windows)
- **Setup**: Both signed in. The employee must be on Probation status.
- **Steps**:
  1. **Admin** (window 1): open the employee in EmployeeModal → set employment status to **Probation** if not already
  2. **Employee** (window 2): go to **Leave** tab → click **Apply**
  3. Check the Leave Type dropdown — restricted types (e.g. Hajj, Study) should be **hidden**
  4. Check for an amber banner listing the restricted leave types
- **Pass**: Leave Type dropdown does not show probation-restricted types. Amber banner explains which types are restricted and why.
- **Bug**:

---

### EDGE-2 · SIF Compliance Gate
- **Profile**: Admin
- **Setup**: Signed in as Admin. At least one employee with a professional licence (DHA/DOH/MOH) must exist.
- **Steps**:
  1. Open the licensed employee in EmployeeModal → Documents tab
  2. Set their **professional licence expiry** to yesterday (or confirm it's already expired)
  3. Go to **Payroll** → generate a payroll run → click **Download SIF**
  4. The compliance gate modal should fire, listing the licence violation
  5. Type a reason (≥10 characters) in the override field → confirm download
- **Pass**: SIF download is blocked with a modal listing the expired licence. Override requires ≥10 character reason. After entering reason, SIF downloads successfully.
- **Bug**:

---

### EDGE-3 · Staffing Rule Gate
- **Profile**: Admin
- **Setup**: Signed in as Admin. A staffing rule must exist requiring a minimum number of staff for a shift category (e.g. 3 Night staff).
- **Steps**:
  1. Go to **Roster** → build a roster for a day with only 1 Night shift (fewer than the rule requires)
  2. Click **Publish**
  3. The staffing gate modal should fire, listing the shortfall
- **Pass**: Publish is blocked with a modal showing the staffing rule violation. Override allows publish after entering a reason.
- **Bug**:

---

### EDGE-4 · Manager's own appraisal excluded
- **Profile**: Manager
- **Setup**: Signed in as Manager. The manager must have their own appraisal in the same cycle as their direct reports.
- **Steps**:
  1. Go to **Appraisals** tab → ensure the **Team Appraisals** view is active
  2. Check the appraisal list
- **Pass**: The manager's own appraisal does NOT appear in the Team Appraisals list. It only appears in the **My Appraisals** sub-view toggle.
- **Bug**:

---

### EDGE-5 · Salary Compliance bars
- **Profile**: Admin
- **Setup**: Signed in as Admin with the Clinical Dashboard or Salary Compliance view available.
- **Steps**:
  1. Open **Salary Compliance** (or Clinical Dashboard → Compliance section)
  2. Check employee salary breakdowns:
     - Basic < 50% of gross → **red** bar
     - Basic 50–60% of gross → **amber** bar
     - Basic ≥ 60% of gross → **green** bar
     - Housing > 25% → **amber/red** bar
     - Transport > 10% → **amber/red** bar
- **Pass**: Compliance bars use correct colour coding based on the percentages above.
- **Bug**:

---

### EDGE-6 · Notification bell on leave approval
- **Profile**: Admin + Employee (two browser windows)
- **Setup**: Both signed in. A pending leave request from the employee must exist.
- **Steps**:
  1. **Admin** (window 1): go to Leave → Requests → approve the employee's pending leave request
  2. **Employee** (window 2): check the **notification bell** icon in the sidebar
- **Pass**: The bell shows a `leave_approved` notification for the employee.
- **Bug**:

---

### EDGE-7 · Sidebar collapse persistence
- **Profile**: Employee or Manager
- **Setup**: Signed in.
- **Steps**:
  1. Click the **collapse** button on the sidebar → sidebar collapses
  2. Reload the page (F5 or Ctrl+R)
- **Pass**: Sidebar remains collapsed after page reload (state persisted via localStorage).
- **Bug**:

---

### EDGE-8 · Empty states — no crashes
- **Profile**: Admin / Manager / Employee
- **Setup**: Signed in to any portal.
- **Steps**:
  1. Open **Appraisals** before any appraisal cycles exist
  2. Open **Training** before any training records exist
  3. Open **Advances** before any advances exist
- **Pass**: Each tab shows an appropriate empty state message (e.g. "No cycles", "No training records") — NOT a blank screen or a JavaScript crash.
- **Bug**:

---

### EDGE-9 · Clinical credential 90-day threshold
- **Profile**: Admin + notification check
- **Setup**: Signed in as Admin. A clinical credential (DHA Licence) must exist.
- **Steps**:
  1. Open an employee in EmployeeModal → Documents tab
  2. Set a DHA Licence expiry to **70 days from today**
  3. Check the notification/alert for that credential
  4. Compare: a normal (non-clinical) document at 70 days would still be green (60d threshold), but clinical uses 90d
- **Pass**: The DHA Licence at 70 days shows an **amber** warning (within 90d clinical threshold). A normal document at 70 days would remain green (within 60d normal threshold).
- **Bug**:

---

### EDGE-10 · Duplicate clock-in blocked
- **Profile**: Employee
- **Setup**: Signed in. The employee must have already clocked in AND out today (from E4-1).
- **Steps**:
  1. Go to the **Attendance** tab
  2. Confirm the employee has already clocked in and out today
  3. Check the **Clock In** button — it should be **disabled** (not hidden)
- **Pass**: Clock In button is present but disabled (`isEnabled()` check, not `isVisible()`). The employee cannot clock in a second time on the same day.
- **Bug**:

---

### EDGE-11 · Multi-branch data isolation
- **Profile**: Admin
- **Setup**: Signed in as Admin with at least two companies/branches configured (multi-company feature).
- **Steps**:
  1. Switch to **Branch A** using the company switcher
  2. Check the Employees list — note which employees appear
  3. Switch to **Branch B**
  4. Check the Employees list again
- **Pass**: Branch B shows only Branch B employees. Branch A employees are NOT visible. Data is fully isolated between branches.
- **Bug**:

---

*Last updated: 2026-07-13 | Covers all features from CLAUDE.md feature map (clinic 1.1–7.2 + original 1–21) | 13-day schedule (split Day 12 into Days 12+13)*
