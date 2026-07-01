# Manual Test Checklist — Workloop Clinic HRMS

Three portals, all from `http://localhost:5173`.  
Sign in as **Admin** → AppShell | **Employee/Manager** → respective Shell.

Legend: `[ ]` = not tested · `[x]` = pass · `[!]` = bug found

---

## 12-DAY SCHEDULE

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
| 11 | Manager Portal (all 8 tabs) | Manager |
| 12 | Employee Portal (all 12 tabs) · Cross-portal flows · Edge cases | Employee |

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

### D-9 · Certification expiry alert and navigation
- **Setup**: ⏭ **DEFER to Day 9** — certifications are created in the Training module on Day 9. Return here after adding a certification with an expiry date within 60 days.
- **Bug**:

---

### D-10 · Document expiry alert — ⏭ deferred from Day 1, covered by DOC-2 on Day 3
- **Profile**: Admin
- **Setup**: Completed as part of **DOC-2** in the Day 3 section below — upload a document with an expiry date within 60 days, then return to Dashboard.
- **Steps**: see DOC-2.
- **Pass**: see DOC-2's Pass criteria, plus: a "Doc Expiry Alerts" or document-expiry related alert/count is visible on the Dashboard or Employees page after the upload.
- **Bug**:

---

### D-11 · Pending appraisals alert and navigation
- **Setup**: ⏭ **DEFER to Day 9** — appraisal cycles and staff assignments are created on Day 9. Return here after an active cycle has pending appraisals.
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

### D-6 · Pending letter requests alert and navigation — ⏭ deferred from Day 1, do this now - ui issue , the table bellow the header seems messy too close to the top bad , space it correctly , and make it neater 
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
- **Bug**:

---

## 5. DEPARTMENTS

### DEP-1 · Navigate to Departments page - partial  
- **Profile**: Admin (signed in)
- **Setup**: None
- **Steps**:
  1. In the sidebar, click **"Departments"** (GitBranch / network icon, between **Employees** and **Letter Requests**)
- **Pass**: The Departments page loads. The page header shows "Departments". Three tab buttons are visible: **Departments**, **Org Chart**, **Staffing Rules**.
- **Bug**: "+" sign in add department is too high , make it in line with the add department button

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

### DEP-10 · Org Chart expand and collapse — retest after DEP-9 fix
- **Profile**: Admin (signed in, on Departments → Org Chart tab)
- **Setup**: A manager with at least one direct report must exist in the org chart
- **Steps**:
  1. Find a node that has child nodes (a manager)
  2. Click the **collapse (▼)** arrow / chevron on that node
  3. Observe — child nodes should hide
  4. Click the **expand (►)** arrow
  5. Observe — child nodes should reappear
- **Pass**: Children hide on collapse and reappear on expand. The arrow icon toggles between ► and ▼.
- **Bug**:

---

### DEP-11 · Org Chart department filter - partial 
- **Profile**: Admin (signed in, on Departments → Org Chart tab)
- **Setup**: Departments have been created (DEP-2/DEP-3) and at least one employee has a department assigned
- **Steps**:
  1. Click the **department filter dropdown**
  2. Select a specific department (e.g. `Emergency & Trauma`)
- **Pass**: The org chart narrows to show only employees whose department matches the selected one. Employees in other departments are hidden.
- **Bug**:

---

### DEP-12 · Staffing Rules — add a rule
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

### DEP-13 · Staffing Rules — edit a rule
- **Profile**: Admin (signed in, on Departments → Staffing Rules tab)
- **Setup**: DEP-12 must be done (at least one rule exists)
- **Steps**:
  1. Click the **edit / pencil** icon on the rule from DEP-12
  2. Change **Min Staff** from `2` to `3`
  3. Click **Save**
- **Pass**: The rule row updates to show min staff = `3`. No duplicate row is created (upsert on department + shift category).
- **Bug**:

---

### DEP-14 · Staffing Rules — delete a rule
- **Profile**: Admin (signed in, on Departments → Staffing Rules tab)
- **Setup**: At least one rule exists
- **Steps**:
  1. Click the **trash** icon on any rule row
  2. Confirm if prompted
- **Pass**: The rule row disappears from the table.
- **Bug**:

---

### DEP-15 · Department autocomplete appears in EmployeeModal
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

### LR-1 · Navigate to Letter Requests page
- **Profile**: Admin (signed in)
- **Setup**: None (D-6's SQL seed should already have created one pending request — if not, run it now)
- **Steps**:
  1. Click **"Letter Requests"** in the sidebar (between Employees and Payroll, envelope/mail icon)
- **Pass**: The Letter Requests page loads. The page header says "Letter Requests". Tab buttons for **Pending / All / Completed / Rejected** are visible. The request seeded in D-6 appears in the Pending tab.
- **Bug**:

---

### LR-2 · Filter tabs update the list
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

### LR-3 · Complete & Print a letter request
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

### LR-4 · Completed request appears in Completed tab
- **Profile**: Admin (signed in, on Letter Requests)
- **Setup**: LR-3 done
- **Steps**:
  1. Click the **Completed** tab
- **Pass**: The request completed in LR-3 appears with status "Completed" and a completion timestamp.
- **Bug**:

---

### LR-5 · Seed a second pending request for rejection test
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

### LR-6 · Reject a pending request — reason required
- **Profile**: Admin (signed in, on Letter Requests → Pending tab)
- **Setup**: LR-5 done — the NOC pending request is visible
- **Steps**:
  1. Click the **reject / X** icon on the NOC request
  2. A rejection reason input field appears inline (or a small form)
  3. Try clicking Confirm/Submit **without** entering a reason — observe if it is blocked
  4. Now type a reason, e.g. `Pending further documentation from employee`
  5. Click Confirm / Submit
- **Pass**: The rejection form either blocks submission with an empty reason (ideal) or accepts it. After submission the request row disappears from the Pending tab and status changes to **Rejected**.
- **Bug**:

---

### LR-7 · Rejection reason visible in Rejected tab
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

## 7. PAYROLL MODULE

- [ ] Navigate → Payroll Module
- [ ] Payroll List loads: all past runs with period, status, employee count, WPS status badge

### Create & edit a payroll run
- [ ] Click `+` → select period (month/year), enter Payroll Name → Create → opens PayrollEditor
- [ ] Employee rows load with current salary breakdown (basic, housing, transport, allowances, deductions)
- [ ] Edit Basic Salary for one employee → net pay total updates
- [ ] Add allowance via AllowDeductPanel → amount added to total
- [ ] Add deduction → amount deducted from total
- [ ] Leave deductions column shows calculated deductions for employees who took leave this period
- [ ] Advance repayments panel lists active advances
- [ ] Approved unpaid expenses auto-loaded in expense reimbursements column

### Maker-Checker approval flow
- [ ] Click "Submit for Approval" → `approval_status` → `pending_approval`, all salary inputs disabled (locked)
- [ ] Click "Recall" → returns to `draft`, inputs unlock
- [ ] Re-submit → click "Approve" → status `approved`, green banner shows
- [ ] Click "Reject" (while pending) → enter rejection reason (≥1 char) → returns to draft, amber rejection notice shown
- [ ] With `approved` status: click "Generate Payroll" → `status = generated`, fully locked, lock banner shown

### SIF download & compliance gate
- [ ] Click "Download SIF" on an approved/generated run
  - [ ] **No expired compliance docs** → `.sif` file downloads immediately (check filename format: `{MOLID}{YYMMDD}{HHMMSS}.sif`)
  - [ ] **Expired licence/EID/Visa present** → "Expired Compliance Documents" modal fires
    - [ ] Each violation listed: employee name, doc type, expiry date
    - [ ] Override reason textarea (must be ≥10 chars) — short reason blocked
    - [ ] Enter valid reason → submit → SIF downloads, override record saved to `compliance_overrides`
- [ ] "View SIF" preview → parsed table shows all employees with amounts
- [ ] "Download Payslips" → PDF generated per employee (company header, salary breakdown)

### WPS Tracking (after SIF downloaded)
- [ ] WPS status auto-sets to `sif_generated` after download
- [ ] Enter WPS Reference No, Submission Date → "Save WPS Status" → saved
- [ ] Change status to Submitted → Saved
- [ ] Change status to Confirmed → Saved
- [ ] Set one employee's payment status to `rejected` → "Download Corrected SIF" button appears → downloads

---

---

# DAY 6 — Advances · Expenses

## 8. ADVANCES

- [ ] Navigate → Advances
- [ ] List loads with filter tabs: All / Pending / Active / Settled / Cancelled
- [ ] **Create Advance** (`+` button)
  - [ ] Select employee, enter amount, repayment months → monthly deduction auto-calculated (amount ÷ months)
  - [ ] Save → new advance appears as Active
- [ ] **Approve a pending advance** (e.g. one created via employee portal)
  - [ ] Click Approve (✓) → status Active
  - [ ] Click Reject (✗) → status Cancelled
- [ ] **Expand advance row** (chevron icon) → repayment schedule table visible with monthly amounts
- [ ] **Settle advance** (when balance is zero or manual settle) → status Settled
- [ ] **Cancel active advance** → status Cancelled
- [ ] Filter tabs update counts correctly after each action

## 9. EXPENSES

- [ ] Navigate → Expenses
- [ ] Stat cards load: Pending count, Approved total (AED), Paid total (AED)
- [ ] Filter tabs: All / Pending / Manager Approved / Approved / Paid / Rejected → list filters
- [ ] **Approve expense claim** (✓ button)
  - [ ] Claim must be Pending or Manager Approved
  - [ ] Status changes to Approved
- [ ] **Reject expense claim** (✗ button)
  - [ ] Inline reason field appears → enter reason → confirm
  - [ ] Status changes to Rejected
- [ ] **View receipt** (external link icon) → opens receipt URL in new tab
- [ ] **Delete expense** (trash icon) → confirmation → removed
- [ ] Status badge colours correct: `pending` amber · `manager_approved` blue · `approved` green · `paid` green · `rejected` / `manager_rejected` red

---

---

# DAY 7 — Leave (all 5 tabs)

## 10. LEAVE

### Overview tab (default)
- [ ] Navigate → Leave
- [ ] Leave type stat cards load: Annual, Sick, Hajj, etc. with days taken / balance
- [ ] Today's absences section lists employees currently on approved leave

### Requests tab
- [ ] Switch to Requests tab
- [ ] All leave requests load: employee name, type, dates, days, status badge
- [ ] **Approve** (✓) a Pending request → status Approved, leave balance deducted
- [ ] **Reject** (✗) → enter rejection comment → status Rejected
- [ ] **Final OK** on a ManagerApproved request (HR gives final sign-off) → status Approved
- [ ] Status badges correct: Pending (amber) · ManagerApproved (blue) · Approved (green) · Rejected / ManagerRejected (red)
- [ ] `Mgr: {name}` shown in Approved By column for manager-pre-approved requests

### Calendar tab
- [ ] Switch to Calendar tab
- [ ] Monthly grid renders with colour-coded leave bars per employee per day
- [ ] Navigate months with ◄ ► buttons → grid updates
- [ ] Department filter dropdown → only that dept's employees shown
- [ ] Print button → browser print dialog opens scoped to calendar area

### Balances tab
- [ ] Switch to Balances tab
- [ ] Table: all employees × all leave types showing days taken and remaining
- [ ] Numbers match Requests tab approvals

### Settings tab
- [ ] Switch to Settings tab
- [ ] Leave year period fields (start/end month)
- [ ] Weekend config (Sat–Sun or Fri–Sat)
- [ ] Carry-forward rules toggle/amount
- [ ] **Add Leave Type** → name, allowed days, paid/unpaid, annual/on-request → Save → appears in list
- [ ] Edit leave type → change days → Save
- [ ] Delete leave type → confirmed, removed
- [ ] **Probation Leave Eligibility card**: toggle off Hajj → `probation_eligible = false` saved · toggle back on
- [ ] **Requires Attachment toggle**: enable for Sick Leave → `requires_attachment = true` saved
- [ ] **Public Holidays**: Add holiday → date + name → appears in list · Delete holiday → removed
- [ ] **Approval Delegation card**: Add delegate (absent manager + covering colleague + date range) → Save · Delete delegate

---

---

# DAY 8 — Attendance · Biometric Import · Assets

## 11. ATTENDANCE

- [ ] Navigate → Attendance
- [ ] Stat cards load: Present Today, Absent, Late, Missing Clock-Out (do not assert loading spinner — wait directly for stat cards)
- [ ] Month navigation (◄ ►) → data reloads, stat cards update
- [ ] Refresh button → loading spinner appears then cards reload
- [ ] Close Period button (if visible at month end) → period locked for payroll

### Employee attendance grid
- [ ] Each employee row shows daily status chips: PRESENT / ABSENT / LATE / WEEKEND / HOLIDAY
- [ ] Click on a day cell → regularisation form opens for that employee + date
- [ ] Submit regularisation → pending record created

### Regularisation approvals
- [ ] View pending regularisation requests
- [ ] Approve a regularisation → attendance record updated
- [ ] Reject a regularisation → record unchanged

### Biometric Import tab
- [ ] Switch to Biometric Import tab
- [ ] Upload a CSV file (ZKTeco Report format, ZKTeco Simple format, or Generic format)
- [ ] Parser auto-detects format → preview of parsed punches shown (employee, date, time, type)
- [ ] Unmatched badge numbers listed as chips → click a chip → pre-fills the badge mapping form
- [ ] Map badge number to employee → Save mapping
- [ ] Confirm Import → new clock events inserted, duplicates at same minute skipped
- [ ] "Unmatched Badges" count reduces as mappings are added

## 12. ASSETS

### Assets tab (default)
- [ ] Navigate → Assets
- [ ] Asset list loads with status chips: Available / Assigned / Under Repair / Retired / Lost
- [ ] Filter chips show count in parentheses (e.g. "Available (4)") — click each to filter
- [ ] **Add Asset** (`+`) → modal: name, category, serial number, purchase date, value, condition → Save → appears as Available
- [ ] **Edit Asset** (pencil icon, `title="Edit asset"`) → change description or value → Save
- [ ] **Assign Asset** → select employee, set condition at handover → Assign → status → Assigned
- [ ] **Return Asset** → condition at return → Return → status → Available
- [ ] **Delete Asset** (`title="Delete asset"`) → if open assignment exists: guard error · else: confirmed, removed

### Assignment History tab
- [ ] Switch to Assignment History tab
- [ ] Full log: asset name, employee, assigned date, returned date, condition at each stage
- [ ] Open (current) assignments show no return date

---

---

# DAY 9 — Training · Appraisals

## 13. TRAINING

### Training Records tab (default)
- [ ] Navigate → Training
- [ ] Records load (list by employee or flat table)
- [ ] **Add Training Record** → select employee, title, type (Internal / External / Online / Conference), provider, start/end dates, duration hours, initial status (Planned) → Save
- [ ] **Edit** (pencil) → change status to Completed, add score, set Passed/Failed → Save
- [ ] **Delete** (trash) → confirmed, removed
- [ ] Status badges correct: Planned (grey) · In Progress (blue) · Completed (green) · Cancelled (red)
- [ ] Filter by employee or status works

### Certifications tab
- [ ] Switch to Certifications tab
- [ ] Cert list loads with expiry badges: Expired (red) / Xd left (red ≤30d · yellow ≤60d) / Active (green) / No Expiry (grey)
- [ ] **Add Certification** → employee, cert name, issuing body, cert number, issued date, expiry date (blank = No Expiry), certificate URL → Save
- [ ] **Edit Certification** → change expiry date to within 30 days → badge updates to red
- [ ] **Delete Certification** → confirmed, removed
- [ ] Expiring Soon / Expired filter toggles

## 14. APPRAISALS

### Cycles tab (default)
- [ ] Navigate → Appraisals
- [ ] Cycle list loads: name, review period, status badge (Draft / Open / Active / Closed)
- [ ] **Add Cycle** (`+`) → name, review_from date, review_to date, status → Save → appears in list
- [ ] **Edit Cycle** (pencil) → change status to Active → Save
- [ ] **Delete Cycle** (trash) → confirmed if no appraisals exist for it

### Reviews tab (click into a cycle)
- [ ] Cycle detail opens showing assigned appraisals (or empty + Assign Staff button)
- [ ] **Assign Staff** → select one or more employees → confirm → appraisal rows created with 5 default sections seeded
- [ ] Appraisal rows list: employee name, overall rating (star display), status badge
- [ ] **Open Review** (clipboard icon) → review form opens
  - [ ] 5 sections shown: Clinical Competency · Patient Care Quality · Communication & Teamwork · Punctuality & Attendance · Professional Development
  - [ ] Set star rating (1–5) per section via star widget
  - [ ] Add reviewer comments per section
  - [ ] Add overall development plan text
  - [ ] Save Review → overall weighted average rating computed, status → `reviewed`
- [ ] **Calibrate** → override overall rating field → submit → status → `calibrated`, star inputs locked
- [ ] **Delete Appraisal** (trash) → confirmed, removed

---

---

# DAY 10 — Roster · Reports

## 15. ROSTER

### Templates tab (default)
- [ ] Navigate → Roster
- [ ] Shift templates list: name, start/end time, short code, category, colour, expected hours
- [ ] **Add Template** → name, start time, end time (expected hours auto-calculates), short code (max 3 chars, e.g. D/N/M/A), category (Morning / Afternoon / Night / Flexible), colour picker → Save
- [ ] **Edit Template** (pencil) → change code or times → Save
- [ ] **Delete Template** (trash) → confirmed

### Roster tab
- [ ] Switch to Roster tab
- [ ] Monthly grid: employees as rows, days as columns
- [ ] Each assigned cell shows coloured shift code badge (not a full-name dropdown)
- [ ] Cells before an employee's joining date are greyed with "–" (non-interactive)
- [ ] **Assign shift**: click empty cell → select code from dropdown → cell updates
- [ ] **Clear assignment**: select blank option → cell clears
- [ ] **Total Hrs column** (right edge) shows sum of planned hours per employee
- [ ] **Footer rows** show counts per day: ☀ Morning / 🌤 Afternoon / 🌙 Night / ○ Unassigned
- [ ] Navigate months (◄ ►) → grid updates
- [ ] **Export CSV** → downloads DMUH-format CSV (employee rows, day codes, M/A/N/O totals, planned hours)
- [ ] **Publish Roster**
  - [ ] If staffing rules violated (headcount < minStaff on any day) → Staffing Compliance Gate modal appears with violations table
  - [ ] Override reason (≥10 chars required) → Confirm Publish → assignments set to `published = true`, override logged
  - [ ] If no violations → publishes directly, no modal

### Swaps tab
- [ ] Switch to Swaps tab
- [ ] Pending swap requests: requester, target employee, dates, reason
- [ ] **Approve** (✓) → assignments swapped, status approved
- [ ] **Reject** (✗) → optional reason → status rejected

## 16. REPORTS

- [ ] Navigate → Reports
- [ ] **Headcount tab** (default) — breakdowns by dept, nationality, gender, contract type · Export CSV / PDF
- [ ] **Payroll Cost tab** — period-by-period bars, total and avg per employee · Export CSV / PDF
- [ ] **Leave Usage tab** — per-employee days taken vs. entitlement, filter by leave type · Export CSV / PDF
- [ ] **Attendance tab** — Present / Absent / Late counts per employee, date range filter · Export CSV / PDF
- [ ] **Doc Expiry tab** — documents expiring within N days (threshold selector 30/60/90) · Export CSV / PDF
- [ ] **Salary History tab** — salary change events (employee, old/new salary, date, changed by) · Export CSV / PDF
- [ ] **Staff Turnover tab** — joiners and leavers for a date range, net headcount change · Export CSV / PDF
- [ ] **Staffing Compliance tab** (8th, ShieldCheck icon) — month picker → per-rule heatmap of green/red day cells showing actual vs. minStaff · Export CSV / PDF

---

---

# DAY 11 — Manager Portal (all 8 tabs)

## Manager AUTH

- [ ] Go to login page → use "Sign in as Employee / Manager" form (not Admin form)
- [ ] Enter manager credentials → lands on ManagerShell, Leave Queue tab active
- [ ] Sidebar shows "Manager Portal" sub-label below manager's name
- [ ] Sidebar shows manager name (bold) and job title — NOT email address
- [ ] Notification bell visible and functional
- [ ] Sign Out → returns to login

## M-1. LEAVE QUEUE

- [ ] Tab loads direct reports' pending leave requests
- [ ] Each request shows: employee name, leave type, dates, days, reason
- [ ] **Approve** (✓) → status changes to ManagerApproved (or Approved if single-level config)
- [ ] **Reject** (✗) → inline reason input appears → enter reason → confirm → status ManagerRejected
- [ ] **History section** (toggle chevron) → previously approved / rejected requests visible
- [ ] Empty state "No pending leave requests" when queue is clear

## M-2. EXPENSE QUEUE

- [ ] Switch to Expense Queue tab
- [ ] Direct reports' pending expense claims load: employee, category, amount, date, description
- [ ] **Approve** (✓) → status → `manager_approved` (awaits HR final sign-off)
- [ ] **Reject** (✗) → enter reason → status → `manager_rejected`
- [ ] View receipt link opens in new tab (if provided)
- [ ] Empty state when no pending expenses

## M-3. APPRAISALS

- [ ] Switch to Appraisals tab
- [ ] Team appraisals load (direct reports only — manager's own appraisal must NOT appear)
- [ ] Each row shows: employee name, job title, cycle name, review period, status badge, overall rating stars
- [ ] **Expand row** → 5 sections visible with current ratings and comments
- [ ] **Star Rating** per section (1–5, interactive) → click to rate
- [ ] Enter comment per section
- [ ] **Save** → ratings persisted via `appraisal_sections_manager_update` RLS policy
- [ ] Calibrated appraisal (`calibrated` status) → star inputs disabled (locked)
- [ ] Empty state if no direct reports assigned to any open cycle

## M-4. MY LEAVE

- [ ] Switch to My Leave tab
- [ ] Leave balances per type, accrued days shown
- [ ] **Apply** button → inline form appears (inside emp-card, not a modal)
  - [ ] Leave type dropdown shows available types
  - [ ] Set Start and End Date
  - [ ] If type has `requires_attachment = true` → file upload UI appears with hint text
  - [ ] Enter reason
  - [ ] Submit → success toast, form hides, request appears in history table
- [ ] **My Requests table**: status badges visible
- [ ] **Cancel** a Pending request → status Cancelled

## M-5. SCHEDULE

- [ ] Switch to Schedule tab
- [ ] Monthly roster loads (published assignments only)
- [ ] Each shift card shows: date, shift name, colour pill, start/end times
- [ ] **Request Swap** on an upcoming shift → SwapModal opens
  - [ ] Target colleague dropdown (colleagues from same company)
  - [ ] Target date
  - [ ] Reason
  - [ ] Submit → swap request created, appears in admin Swaps tab

## M-6. ATTENDANCE

- [ ] Switch to Attendance tab
- [ ] Today's card shows current clock status
- [ ] **Clock In** (enabled only if not yet clocked in today) → click → status PRESENT, button switches to Clock Out
- [ ] **Clock Out** (enabled after clock in) → click → total hours shown
- [ ] Clock In button disabled (not just hidden) after already clocking in today
- [ ] Attendance history table: past days with in/out times, hours, status chips
- [ ] **Request Regularisation** → form with date, expected times, reason → Submit → pending for admin

## M-7. PAYSLIPS

- [ ] Switch to Payslips tab
- [ ] Payslip list: period, basic salary, net pay, status
- [ ] **Download Payslip** (PDF button) → PDF downloads with company logo and salary breakdown
- [ ] Empty state if no payslips generated yet

## M-8. PROFILE

- [ ] Switch to Profile tab
- [ ] Profile page loads: name, job title, department, start date, phone, emergency contact, bank details
- [ ] Fields are read-only until Edit is clicked
- [ ] **Edit button** → form inputs appear
- [ ] Edit phone number → Save → toast confirms
- [ ] **Cancel** → discards changes, fields hidden again

---

---

# DAY 12 — Employee Portal · Cross-portal flows · Edge cases

## Employee AUTH

- [ ] Go to login → use "Sign in as Employee / Manager" form
- [ ] **First-time registration**: click "Register as Employee" → enter email matching an existing employee's work_email → success banner shown → switch to sign-in form → sign in normally
- [ ] Sign in with employee credentials → lands on EmpHome tab
- [ ] Sidebar shows employee name (bold) and job title below
- [ ] Sidebar does NOT display email address
- [ ] Sign Out → returns to login

## E-1. HOME

- [ ] Welcome card loads with employee name and company name
- [ ] Leave balance summary stat cards visible
- [ ] My Assigned Assets card shows any assets assigned to this employee
- [ ] Upcoming schedule preview (if roster published for current month)

## E-2. LEAVE

- [ ] Switch to Leave tab
- [ ] Leave balances per type: Annual, Sick, etc. with days remaining
- [ ] Probation amber banner visible if employee is on probation, listing restricted types
- [ ] **Apply** → inline form appears (inside `.emp-card`, NOT a modal)
  - [ ] Leave Type dropdown shows only eligible types (restricted types hidden for probation employees)
  - [ ] If type `requires_attachment = true` → file picker + hint text appear
  - [ ] Set Start Date and End Date
  - [ ] Enter reason
  - [ ] **Submit** → success toast, form hides, request in history table
  - [ ] End date before start date → validation error
  - [ ] Attachment required but not uploaded → blocked with error
- [ ] **My Requests table**: type, dates, days, status badge per row
- [ ] **Cancel** a Pending request → status Cancelled
- [ ] Attachment link (📎) visible on requests that included a file

## E-3. SCHEDULE

- [ ] Switch to Schedule tab
- [ ] Monthly roster loads (published shifts only)
- [ ] Each shift: date, shift name, times, colour indicator
- [ ] **Request Swap** on a shift → SwapModal
  - [ ] Select colleague, target date, reason → Submit → swap request sent
- [ ] Empty state if no published roster this month

## E-4. ATTENDANCE

- [ ] Switch to Attendance tab
- [ ] Today's card shows current clock status
- [ ] **Clock In** (enabled only if not yet clocked in today) → click → optimistic UI update, button → Clock Out
- [ ] **Clock Out** (enabled after clock in) → click → total hours displayed
- [ ] Cannot Clock In a second time same day (button disabled, not just hidden — `isEnabled()` check)
- [ ] History table: past days with date, in/out times, hours, status chip
- [ ] **Request Regularisation** → select date, expected in/out, reason → Submit → pending for admin review

## E-5. PAYSLIPS

- [ ] Switch to Payslips tab
- [ ] Payslip list: period, gross, deductions, net pay
- [ ] **Download** (PDF button) → PDF with company header and full salary breakdown
- [ ] WPS status badge visible on each row if applicable

## E-6. ADVANCES

- [ ] Switch to Advances tab
- [ ] Active advance: progress bar shows `(disbursed – outstanding) / disbursed × 100%`
- [ ] Repayment schedule table: monthly amount, paid/pending status per instalment
- [ ] **Request Advance form**
  - [ ] Amount field
  - [ ] Reason field
  - [ ] Submit → pending advance created (admin must approve before active)
- [ ] Pending advance shows amber "Awaiting Approval" badge

## E-7. EXPENSES

- [ ] Switch to Expenses tab
- [ ] Expense history list with status badges
- [ ] **Submit Expense form**
  - [ ] Category dropdown (from EXPENSE_CATEGORIES)
  - [ ] Amount, Date, Description
  - [ ] Receipt URL (text field — no file upload)
  - [ ] Submit → new claim in list as Pending
- [ ] Status flow visible: pending → manager_approved → approved → paid
- [ ] "Manager Approved" badge appears before HR final sign-off

## E-8. TRAINING

- [ ] Switch to Training tab
- [ ] Summary stat cards: Total Trainings · Completed · Certifications · Active Certs
- [ ] Expired certifications alert card (red) lists expired certs with name and date
- [ ] Expiring soon alert card (amber) lists certs expiring within 60 days
- [ ] Training Records section: each record shows title, type badge, date range, duration, score/passed
- [ ] "View Certificate" link opens cert URL in new tab (if provided)
- [ ] Certifications section: expiry badges correct (Expired red · ≤30d red · ≤60d yellow · Active green · No Expiry grey)
- [ ] Read-only — no add/edit/delete buttons visible

## E-9. APPRAISALS

- [ ] Switch to Appraisals tab
- [ ] Appraisal list: cycle name, review period, overall rating stars, status badge
- [ ] **Expand row** → sections expand showing section name, weight, manager's star rating, comments
- [ ] Development plan text visible if filled
- [ ] Reviewer comments visible
- [ ] Status badges: Pending (grey) · Reviewed (blue) · Calibrated (green)
- [ ] Read-only — employee cannot interact with star inputs

## E-10. DOCUMENTS

- [ ] Switch to Documents tab
- [ ] Existing docs list: type, document number, expiry, status badge (Pending Review / Verified / Rejected)
- [ ] Clinical credentials show cyan "Clinical" badge
- [ ] Admin-uploaded docs show no "Self-submitted" label
- [ ] **Upload Document form**
  - [ ] Document type dropdown (grouped: UAE Residency / Clinical Credentials / General)
  - [ ] Document Number, Expiry Date, Notes
  - [ ] **Choose File** (click visible drop-zone — hidden `input[type="file"]` is triggered)
  - [ ] Submit → uploads to Storage, DB row created with `status = 'pending'`
  - [ ] New row appears with "Pending Review" badge
  - [ ] Rejection reason shown inline if admin rejected it

## E-11. REQUESTS

- [ ] Switch to Requests tab
- [ ] "Request a Letter" card has correct padding — no text overflowing onto card border
- [ ] **Submit form**
  - [ ] Letter Type dropdown (7 types: Salary Certificate — Bank / Embassy / Personal, NOC, Experience Letter, Employment Certificate, Salary Transfer Letter)
  - [ ] Purpose / Addressed To (optional)
  - [ ] Submit Request → success toast, form resets, request in history
- [ ] **My Requests table**: Letter Type, Purpose, Requested date, Status columns
- [ ] Status badges: Pending Review (amber clock) · Ready (green checkmark) · Rejected (red X)
- [ ] Completed request shows "Ready — collect from HR" note with completion date
- [ ] Rejected request shows rejection reason inline

## E-12. PROFILE

- [ ] Switch to Profile tab
- [ ] Profile loads: name, job title, department, start date, phone, emergency contact, bank details, IBAN
- [ ] All fields are read-only (display only) before Edit is clicked
- [ ] **Edit button** → all form inputs appear
- [ ] Edit phone number → Save → toast confirms, display updates
- [ ] **Cancel** → discards changes, inputs hidden again

---

## CROSS-PORTAL WORKFLOWS

> Requires two browser windows (or separate browser profiles) open simultaneously.

### X-1. Leave Request Flow (Employee → Manager → Admin)
- [ ] Employee submits leave request (E-2)
- [ ] Manager sees it in Leave Queue (M-1) → Approves
- [ ] Admin sees ManagerApproved status in Leave → Requests tab → clicks Final OK
- [ ] Employee sees Approved status in their requests list

### X-2. Expense Claim Flow (Employee → Manager → Admin → Payroll)
- [ ] Employee submits expense claim (E-7)
- [ ] Manager sees it in Expense Queue (M-2) → Approves
- [ ] Admin sees `manager_approved` in Expenses → Approves (final)
- [ ] Open next payroll run → approved expense auto-loaded in PayrollEditor
- [ ] Generate payroll → expense status → Paid

### X-3. Advance Flow (Employee → Admin)
- [ ] Employee requests advance (E-6)
- [ ] Admin sees Pending in Advances → Approves
- [ ] Employee sees Active advance with progress bar

### X-4. Letter Flow (Employee → Admin → Employee)
- [ ] Employee requests letter (E-11)
- [ ] Admin sees pending count badge on Dashboard and in Letter Requests nav
- [ ] Admin completes letter → prints → status Completed
- [ ] Employee sees status "Ready" with collection note

### X-5. Appraisal Flow (Admin → Manager → Employee)
- [ ] Admin creates Appraisal Cycle, assigns employees to cycle (Reviews tab → Assign Staff)
- [ ] Manager sees appraisals for direct reports in M-3 → rates sections
- [ ] Admin calibrates final score
- [ ] Employee sees calibrated rating in E-9

### X-6. Attendance Clock (Employee → Admin visibility)
- [ ] Employee clocks in (E-4)
- [ ] Admin refreshes Attendance module → employee shows as Present today

### X-7. Document Self-Upload (Employee → Admin review)
- [ ] Employee uploads clinical credential (E-10)
- [ ] Admin opens EmployeeModal → Documents tab → sees "Self-submitted" label, Pending Review
- [ ] Admin verifies (✓) → Employee sees Verified badge

### X-8. Roster Publish (Admin → Employee + Manager visible)
- [ ] Admin builds and publishes roster (Day 10)
- [ ] Employee sees shifts in Schedule tab (E-3)
- [ ] Manager sees own shifts in Schedule tab (M-5)

---

## KNOWN EDGE CASES

- [ ] **Probation + Leave**: set employee to Probation → their Leave dropdown hides restricted types (e.g. Hajj), amber banner lists them
- [ ] **SIF Compliance Gate**: set a licensed employee's licence expiry to yesterday → try to download SIF → gate modal fires listing the violation
- [ ] **Staffing Rule Gate**: add rule requiring 3 Night staff → build roster with only 1 Night shift on a day → try Publish → gate lists the shortfall
- [ ] **Manager's own appraisal**: manager must NOT see their own appraisal in Manager Appraisals tab (only direct reports)
- [ ] **Salary Compliance bars**: Basic < 50% of gross → red; 50–60% → amber; ≥60% → green; Housing > 25% → amber/red; Transport > 10% → amber/red
- [ ] **Notification bell**: approve a leave request → affected employee's bell shows a `leave_approved` notification
- [ ] **Sidebar collapse persistence**: collapse → reload page → stays collapsed
- [ ] **Empty states**: open Appraisals before any cycles exist → "No cycles" empty state, not a crash or blank screen
- [ ] **Clinical credential 90-day threshold**: add DHA Licence expiring in 70 days → shows amber (clinical uses 90d) vs a normal doc at 70 days which would still be green (normal uses 60d)
- [ ] **Duplicate clock-in blocked**: employee clocks in and out → Clock In button stays disabled for the rest of the day (`isEnabled()`, not `isVisible()`)
- [ ] **Multi-branch data isolation**: switch to Branch B → Employees list shows only Branch B employees, not Branch A

---

*Last updated: 2026-06-29 | Covers all features from CLAUDE.md feature map (clinic 1.1–7.2 + original 1–21)*
