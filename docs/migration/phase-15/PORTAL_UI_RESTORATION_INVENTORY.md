# Portal UI restoration inventory

## Verified reference

The restoration baseline is commit `a3b72a22924d1b56b5603ee8e0069ddecee65f43`, the last commit in the requested September 1 through September 7 window. Its frontend tree matches `b079236dad08ccf8e151b733f072a8dd297aae5d`, the last complete pre-migration product commit. The September migration commits changed the backend and migration records, but did not change `src/`.

This inventory maps the screens and interactions in that tree to the current browser route and FastAPI client. Historical storage modules are reference material only. The current client and server remain the data and authorization boundary.

## Shared shell

| Historical screen or interaction | Historical source | Current route | Current client or authority |
| --- | --- | --- | --- |
| Administrator shell, branch chooser, collapsible sidebar, active pill, identity card, notifications, dark-mode and advanced-feature footer controls, sign out | `src/App.jsx` | `/admin/*` | `portalSession.js`, `organizationApi.js`, `notificationApi.js` |
| Manager shell, collapsible sidebar, active pill, identity card, notifications, sign out, mobile bottom navigation | `src/components/ManagerShell.jsx` | `/manager/*` | `portalSession.js`, `employeeApi.js`, `organizationApi.js`, `notificationApi.js` |
| Employee shell, collapsible sidebar, active pill, identity card, notifications, sign out, mobile bottom navigation | `src/components/employee/EmployeeShell.jsx` | `/employee/*` | `portalSession.js`, `employeeApi.js`, `organizationApi.js`, `notificationApi.js` |
| Role dashboards and task navigation | `Dashboard.jsx`, `ClinicalDashboard.jsx`, `TasksPanel.jsx` | `/admin`, `/admin/clinical-dashboard`, `/admin/tasks`, `/manager`, `/manager/tasks`, `/employee`, `/employee/tasks` | `dashboardApi.js`, `taskApi.js` |

## Administrator modules

| Historical screen and main interactions | Historical source | Current route | Current client |
| --- | --- | --- | --- |
| Dashboard, setup checklist, workforce and payroll KPIs, alerts, recent payroll, compliance summary | `Dashboard.jsx` | `/admin` | `dashboardApi.js` |
| Clinical staffing and credential dashboard | `ClinicalDashboard.jsx` | `/admin/clinical-dashboard` | `dashboardApi.js` |
| Employer and branch details, WPS settings, feature controls, insurance settings | `CompanySettings.jsx` | `/admin/company-settings` | `organizationApi.js` |
| Employee directory, search and filters, create and edit dialog, lifecycle actions, job history, CSV import and export | `EmployeeManager.jsx`, `EmployeeModal.jsx` | `/admin/employees` | `employeeApi.js`, `employeeCsv.js`, `recordsBenefitsApi.js`, `offboardingApi.js` |
| Department hierarchy and staffing rules | `DepartmentManager.jsx` | `/admin/departments` | `departmentApi.js` |
| Letter and custom-request queue, filters, completion, rejection, output | `LetterRequestsManager.jsx` | `/admin/requests` | `letterRequestsApi.js`, `renderedOutputApi.js` |
| Payroll run history, summary cards, new-run dialog, run detail header, salary-entry table, allowance and deduction controls, approval actions, SIF and payslip output | `PayrollManager.jsx`, `PayrollList.jsx`, `PayrollEditor.jsx`, `AllowDeductPanel.jsx`, `SIFPreviewModal.jsx` | `/admin/payroll` | `payrollApi.js`, `wpsNafisApi.js`, `renderedOutputApi.js` |
| Salary-advance KPIs, status tabs, create dialog, approval, schedule, repayment and settlement actions | `AdvancesManager.jsx` | `/admin/advances` | `advanceApi.js` |
| Expense KPIs, status filters, claims table, receipt handling and decision actions | `ExpensesManager.jsx` | `/admin/expenses` | `expenseApi.js` |
| Leave requests, balances, policy settings, calendar, approval queue and decision dialogs | `LeaveManager.jsx`, `LeaveRequestModal.jsx` | `/admin/leave` | `leaveConfigurationApi.js`, `leaveBalanceApi.js`, `leaveRequestApi.js`, `leaveAttachmentApi.js`, `leaveApprovalApi.js` |
| Attendance summary, time records, corrections, rules, periods and close actions | `AttendanceManager.jsx` | `/admin/attendance` | `attendanceConfigurationApi.js`, `attendanceIngestionApi.js`, `attendanceCalculationApi.js`, `attendanceExceptionsApi.js`, `attendancePeriodsApi.js` |
| Asset register, assignment and return dialogs | `AssetsManager.jsx` | `/admin/assets` | `developmentAssetsApi.js` |
| Training, certification and CME tabs, evidence actions and review controls | `TrainingManager.jsx` | `/admin/training` | `developmentAssetsApi.js` |
| Appraisal cycles, ratings, calibration and closure | `AppraisalManager.jsx` | `/admin/appraisals` | `appraisalsIncidentsApi.js` |
| Shift templates, monthly roster grid, validation, publication and swap queue | `RosterManager.jsx` | `/admin/roster` | `rosterApi.js`, `shiftSwapApi.js` |
| Incident register, investigation, corrective action and closure | `IncidentManager.jsx` | `/admin/incidents` | `appraisalsIncidentsApi.js` |
| Report family selector, filters, preview and server-generated downloads | `Reports.jsx` | `/admin/reports` | `reportApi.js`, `outputApi.js`, `renderedOutputApi.js` |
| Role-aware operational task groups and module links | `TasksPanel.jsx` | `/admin/tasks` | `taskApi.js` |

Payroll, Advances, and Expenses keep separate routes and separate module headers. No current route combines them.

## Manager modules

| Historical screen and main interactions | Historical source | Current route | Current client |
| --- | --- | --- | --- |
| Personal summary and priority cards | `employee/EmpHome.jsx` | `/manager` | `dashboardApi.js` |
| Direct-report leave queue and decision actions | `manager/ManagerLeaveQueue.jsx` | `/manager/leave-queue` | `leaveApprovalApi.js` |
| Direct-report expense queue and decision actions | `manager/ManagerExpenseQueue.jsx` | `/manager/expense-queue` | `expenseApi.js` |
| Direct-report appraisal reviews and own results | `manager/ManagerAppraisals.jsx` | `/manager/appraisals` | `appraisalsIncidentsApi.js` |
| Leave balances, request dialog, history and calendar | `employee/EmpLeave.jsx` | `/manager/leave` | `leaveBalanceApi.js`, `leaveRequestApi.js`, `leaveAttachmentApi.js` |
| Published schedule, colleagues and shift-swap actions | `employee/EmpSchedule.jsx` | `/manager/schedule` | `rosterApi.js`, `shiftSwapApi.js` |
| Personal attendance summary, history and correction form | `employee/EmpAttendance.jsx` | `/manager/attendance` | `attendanceExceptionsApi.js` |
| Payslip list and protected PDF action | `employee/EmpPayslips.jsx` | `/manager/payslips` | `payrollApi.js`, `renderedOutputApi.js` |
| Salary-advance request, active schedule and history | `employee/EmpAdvances.jsx` | `/manager/advances` | `advanceApi.js` |
| Personal expense submission, receipt and claim history | `employee/EmpExpenses.jsx` | `/manager/expenses` | `expenseApi.js` |
| Team and personal training, certifications, CME and evidence | `manager/ManagerTraining.jsx` | `/manager/training` | `developmentAssetsApi.js` |
| Personal document list and upload | `employee/EmpDocuments.jsx` | `/manager/documents` | `recordsBenefitsApi.js` |
| Letter and custom requests with completed output | `employee/EmpRequests.jsx` | `/manager/requests` | `letterRequestsApi.js`, `renderedOutputApi.js` |
| Employment profile and permitted contact edit | `employee/EmpProfile.jsx` | `/manager/profile` | `employeeApi.js` |
| Personal and team task groups | `TasksPanel.jsx` | `/manager/tasks` | `taskApi.js` |

## Employee modules

| Historical screen and main interactions | Historical source | Current route | Current client |
| --- | --- | --- | --- |
| Welcome header, personal KPIs and quick actions | `employee/EmpHome.jsx` | `/employee` | `dashboardApi.js` |
| Leave balances, request dialog, history and calendar | `employee/EmpLeave.jsx` | `/employee/leave` | `leaveBalanceApi.js`, `leaveRequestApi.js`, `leaveAttachmentApi.js` |
| Published schedule, colleagues and shift-swap actions | `employee/EmpSchedule.jsx` | `/employee/schedule` | `rosterApi.js`, `shiftSwapApi.js` |
| Personal attendance summary, history and correction form | `employee/EmpAttendance.jsx` | `/employee/attendance` | `attendanceExceptionsApi.js` |
| Payslip list and protected PDF action | `employee/EmpPayslips.jsx` | `/employee/payslips` | `payrollApi.js`, `renderedOutputApi.js` |
| Salary-advance request, active schedule and history | `employee/EmpAdvances.jsx` | `/employee/advances` | `advanceApi.js` |
| Expense submission, receipt and claim history | `employee/EmpExpenses.jsx` | `/employee/expenses` | `expenseApi.js` |
| Training, certifications, CME and evidence | `employee/EmpTraining.jsx` | `/employee/training` | `developmentAssetsApi.js` |
| Appraisal results and development plan | `employee/EmpAppraisal.jsx` | `/employee/appraisals` | `appraisalsIncidentsApi.js` |
| Personal documents and protected file actions | `employee/EmpDocuments.jsx` | `/employee/documents` | `recordsBenefitsApi.js` |
| Letter and custom requests with completed output | `employee/EmpRequests.jsx` | `/employee/requests` | `letterRequestsApi.js`, `renderedOutputApi.js` |
| Employment profile and permitted contact edit | `employee/EmpProfile.jsx` | `/employee/profile` | `employeeApi.js` |
| Personal task groups | `TasksPanel.jsx` | `/employee/tasks` | `taskApi.js` |

## Restoration rules

- Use the historical DOM hierarchy, visible labels, control order, density, table columns, dialogs, filters, status pills, and responsive transitions when the current API supports the interaction.
- Keep current FastAPI payloads, optimistic version fields, idempotency keys, protected file delivery, Keycloak session handling, and server-derived role and scope.
- Omit a historical action when no current endpoint supports it. Do not replace it with local state, a fabricated result, or a revived retired-service call.
- Keep route-level loading, empty, denied, validation, conflict, and unavailable states visible inside the historical module layout.
