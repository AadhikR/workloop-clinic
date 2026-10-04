import { useState } from 'react'

import Advances from './Advances.jsx'
import AppraisalsIncidents from './AppraisalsIncidents.jsx'
import AttendanceCalculation from './AttendanceCalculation.jsx'
import AttendanceConfiguration from './AttendanceConfiguration.jsx'
import AttendanceExceptions from './AttendanceExceptions.jsx'
import AttendanceIngestion from './AttendanceIngestion.jsx'
import AttendancePeriods from './AttendancePeriods.jsx'
import Dashboard from './Dashboards.jsx'
import DepartmentManager from './DepartmentManager.jsx'
import DevelopmentAssets from './DevelopmentAssets.jsx'
import EmployeeDirectory from './EmployeeDirectory.jsx'
import Expenses from './Expenses.jsx'
import LeaveApprovals from './LeaveApprovals.jsx'
import LeaveConfiguration from './LeaveConfiguration.jsx'
import LeaveOverview from './LeaveOverview.jsx'
import LetterRequests from './LetterRequests.jsx'
import ModuleWorkspace from './ModuleWorkspace.jsx'
import Offboarding from './Offboarding.jsx'
import OrganizationSettings from './OrganizationSettings.jsx'
import Payroll from './Payroll.jsx'
import RecordsBenefits from './RecordsBenefits.jsx'
import Reports from './Reports.jsx'
import RosterDrafts from './RosterDrafts.jsx'
import ShiftSwapQueue from './ShiftSwapQueue.jsx'
import Tasks from './Tasks.jsx'
import WpsNafis from './WpsNafis.jsx'
import { administratorRouteGroup } from './administratorRoutes.js'

function PayrollWorkspace({ shared }) {
  const [view, setView] = useState('runs')
  return (
    <div className="financial-workspace" data-financial-workspace="payroll">
      <div className="tabs module-subnav" role="tablist" aria-label="Payroll module views">
        <button type="button" className={`tab-btn${view === 'runs' ? ' active' : ''}`} role="tab" aria-selected={view === 'runs'} onClick={() => setView('runs')}>Payroll Runs</button>
        <button type="button" className={`tab-btn${view === 'compliance' ? ' active' : ''}`} role="tab" aria-selected={view === 'compliance'} onClick={() => setView('compliance')}>WPS &amp; Nafis</button>
      </div>
      {view === 'runs' ? <Payroll {...shared} /> : <WpsNafis {...shared} />}
    </div>
  )
}

export default function AdministratorPortal({
  account,
  authentication,
  branchId,
  clearBranch,
  navigator,
  path,
}) {
  const group = administratorRouteGroup(path)
  if (group === null || path === '/admin') return null

  const shared = { account, authentication, branchId }
  return (
    <div className="portal-route administrator-route" data-administrator-route={path}>
      {path === '/admin/organization' && (
        <>
          <OrganizationSettings authentication={authentication} />
          <DepartmentManager authentication={authentication} branchId={branchId} clearBranch={clearBranch} />
        </>
      )}
      {path === '/admin/clinical-dashboard' && (
        <Dashboard authentication={authentication} branchId={branchId} kind="clinical" />
      )}
      {path === '/admin/company-settings' && (
        <OrganizationSettings authentication={authentication} />
      )}
      {path === '/admin/employees' && (
        <ModuleWorkspace label="Employee views" views={[
          { id: 'directory', label: 'Employees', content: <EmployeeDirectory {...shared} clearBranch={clearBranch} /> },
          { id: 'records', label: 'Documents & Benefits', content: <RecordsBenefits {...shared} /> },
          { id: 'offboarding', label: 'Offboarding', content: <Offboarding {...shared} /> },
        ]} />
      )}
      {path === '/admin/departments' && (
        <DepartmentManager authentication={authentication} branchId={branchId} clearBranch={clearBranch} />
      )}
      {path === '/admin/requests' && <LetterRequests {...shared} />}
      {path === '/admin/people' && (
        <EmployeeDirectory {...shared} clearBranch={clearBranch} />
      )}
      {path === '/admin/leave' && (
        <ModuleWorkspace label="Leave module views" views={[
          { id: 'overview', label: 'Overview', content: <LeaveOverview {...shared} /> },
          { id: 'approvals', label: 'Approvals', content: <LeaveApprovals {...shared} /> },
          { id: 'settings', label: 'Settings', content: <LeaveConfiguration authentication={authentication} branchId={branchId} /> },
        ]} />
      )}
      {path === '/admin/attendance' && (
        <ModuleWorkspace label="Attendance module views" views={[
          { id: 'records', label: 'Records', content: <AttendanceCalculation authentication={authentication} branchId={branchId} /> },
          { id: 'entry', label: 'Manual Entry', content: <AttendanceIngestion authentication={authentication} branchId={branchId} /> },
          { id: 'corrections', label: 'Corrections & Absences', content: <AttendanceExceptions authentication={authentication} branchId={branchId} /> },
          { id: 'periods', label: 'Periods', content: <AttendancePeriods authentication={authentication} branchId={branchId} /> },
          { id: 'settings', label: 'Settings', content: <AttendanceConfiguration authentication={authentication} branchId={branchId} /> },
        ]} />
      )}
      {path === '/admin/roster' && (
        <ModuleWorkspace label="Roster module views" views={[
          { id: 'roster', label: 'Roster', content: <RosterDrafts authentication={authentication} branchId={branchId} /> },
          { id: 'swaps', label: 'Shift Swaps', content: <ShiftSwapQueue {...shared} /> },
        ]} />
      )}
      {path === '/admin/payroll' && (
        <PayrollWorkspace shared={shared} />
      )}
      {path === '/admin/advances' && <Advances {...shared} />}
      {path === '/admin/expenses' && <Expenses {...shared} />}
      {path === '/admin/records' && (
        <>
          <RecordsBenefits {...shared} />
          <LetterRequests {...shared} />
          <Offboarding {...shared} />
        </>
      )}
      {path === '/admin/development' && (
        <>
          <DevelopmentAssets {...shared} />
          <AppraisalsIncidents {...shared} />
        </>
      )}
      {path === '/admin/assets' && <DevelopmentAssets {...shared} assetsOnly />}
      {path === '/admin/training' && <DevelopmentAssets {...shared} trainingOnly />}
      {path === '/admin/appraisals' && <AppraisalsIncidents {...shared} view="appraisals" />}
      {path === '/admin/incidents' && <AppraisalsIncidents {...shared} view="incidents" />}
      {path === '/admin/reports' && (
        <Reports authentication={authentication} branchId={branchId} />
      )}
      {path === '/admin/tasks' && (
        <Tasks account={account} authentication={authentication} branchId={branchId} navigator={navigator} />
      )}
    </div>
  )
}
