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

### A-13 · Notification bell shows unread count badge
- **Profile**: Admin (signed in)
- **Setup**: ⏭ **DEFER to Day 3** — this badge only appears when notifications exist. Notifications are auto-generated when the Dashboard loads and finds employees with expiring documents, visas, or certifications. Since no employees exist yet, come back to this check after Day 3 when employees with expiry dates have been created. At that point: navigate to Dashboard, wait a few seconds for expiry checks to run, then look at the bell icon for a red count badge.
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

### D-10 · Document expiry alert
- **Setup**: ⏭ **DEFER to Day 3** — employee documents with expiry dates are added on Day 3. Return here after uploading a document with an expiry date within 60 days.
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
  1. Click through the status filter: **All Statuses → Active → Probation → Terminated**
- **Pass**: List updates to show only matching employees at each step; "All Statuses" restores everyone.
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
  - **Fixed**: Checked both pickers that list "all employees". `DepartmentManager.jsx`'s Department Head dropdown was already correctly filtering out Terminated employees at load time. The real gap was `EmployeeModal.jsx`'s **Reporting Manager** dropdown, which only excluded the employee being edited (`e.id !== form.id`) and listed Terminated staff alongside active ones — fixed to also filter `e.employmentStatus !== 'Terminated'`. The main Employees list intentionally still shows Terminated employees with a badge (not removed) — that's documented soft-delete behavior in CLAUDE.md backed by existing Playwright assertions, so it was left unchanged.

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

## 4. EMPLOYEES — Advanced tabs

### Documents tab (existing employee)
- [ ] Open employee modal → Documents tab
- [ ] Upload a file → select document type from grouped dropdown (UAE Residency / Clinical Credentials / General)
- [ ] Enter document number, expiry date, notes → Submit
- [ ] New row appears with "Pending Review" status badge
- [ ] Clinical credential type (e.g. DHA Licence) shows cyan "Clinical" badge + 90-day amber threshold
- [ ] Verify document (✓ button) → status changes to Verified
- [ ] Reject document (✗ button) → enter rejection reason → status changes to Rejected

### Insurance tab (existing employee)
- [ ] Open Insurance tab
- [ ] Select insurance policy from dropdown, enter Member ID, Card Number, effective/expiry dates
- [ ] Click Assign Coverage → saved, form resets
- [ ] Add Dependant → name, relationship, DOB → appears in dependants table
- [ ] Delete dependant → confirmed, removed

### Contracts tab (existing employee)
- [ ] Open Contracts tab
- [ ] Current contract type, end date countdown, start date all visible
- [ ] **Limited contract**: click Renew → inline confirmation form with new dates → confirm → history row added
- [ ] Convert to Unlimited → confirm → contract type updates, history row added
- [ ] Not Renewing → confirm → history row added
- [ ] **Unlimited contract**: Convert to Limited → confirm
- [ ] Print Letter button → letter opens in new window

### Portal Role (Job & Contract tab, employee with activated portal)
- [ ] Portal Role dropdown visible only when employee has linked their portal account
- [ ] Change role Employee → Manager → RPC call updates role (no Save button needed)
- [ ] Change back Manager → Employee

## Probation actions (Probation employees only)
- [ ] Blue UserCheck icon appears only on rows with Probation status
- [ ] Click → ProbationModal opens showing days remaining / overdue
- [ ] Confirm Active → status changes to Active, probation end date cleared
- [ ] Extend → date picker → confirm → `probationExtended` flag set, new end date saved
- [ ] Terminate → UAE 14-day notice warning shown → confirm → employee archived (Terminated badge)

## Archive employee
- [ ] Trash icon (Delete employee) → "Archive Employee" confirmation dialog
- [ ] Confirm → employee stays in list with Terminated badge (not deleted from list)

## Offboarding (Terminated employees only)
- [ ] Indigo ClipboardList icon appears only on Terminated rows
- [ ] Click → OffboardingModal opens, checklist created/loaded automatically
- [ ] Toggle task completion (click row) → checkbox toggles optimistically (instant UI, then DB write)
- [ ] Add custom task → appears in checklist
- [ ] Delete task (trash icon) → removed
- [ ] Visa Cancellation Status dropdown → change → save
- [ ] Open EOS Calculator → EndOfServiceScreen renders with gratuity breakdown (UAE law)
- [ ] Outstanding advances auto-populated from Advances module
- [ ] Print Settlement letter → new window with letter
- [ ] Print NOC / Experience Letter → new window

---

---

# DAY 4 — Departments · Letter Requests

## 5. DEPARTMENTS

### Departments tab (default)
- [ ] Navigate → Departments
- [ ] Department list loads as indented tree (child depts show `└` prefix)
- [ ] Add Department → enter name, select Parent (leave blank for root), choose colour swatch (10 colours), optionally set Head Employee → Save → appears in tree at correct level
- [ ] Edit Department → change name or head → Save
- [ ] Delete Department → guard modal if employees are assigned, else confirms deletion
- [ ] Colour swatches render and selecting one updates the row colour chip

### Org Chart tab
- [ ] Switch to Org Chart tab
- [ ] Org tree renders employee cards grouped by reporting structure
- [ ] Search box → type employee name → matching nodes highlighted/filtered
- [ ] Department filter dropdown → narrows chart to selected dept
- [ ] Click expand arrow (►) on a node → children expand
- [ ] Click collapse (▼) → children collapse

### Staffing Rules tab (3rd tab, ShieldCheck icon)
- [ ] Switch to Staffing Rules tab
- [ ] Rules table loads (department, shift category, min staff, effective dates)
- [ ] Add Rule: Department field (datalist autocomplete from departments), Shift Category dropdown (Morning / Afternoon / Night / Flexible), Min Staff number, optional dates → Save → row appears
- [ ] Edit rule inline → Save
- [ ] Delete rule (trash icon) → confirmed, removed

## 6. LETTER REQUESTS

- [ ] Navigate → Letter Requests
- [ ] Pending requests list loads with employee name, letter type, purpose, date
- [ ] Filter tabs: Pending / All / Completed / Rejected → list updates
- [ ] **Complete & Print** (printer icon on a pending request)
  - [ ] Letter HTML renders in new browser window (correct template for the requested type)
  - [ ] Status changes to "Completed" in the list
- [ ] **Reject** (X icon) → rejection reason input appears → enter reason → confirm → status changes to Rejected
- [ ] Rejected reason visible in the row

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
