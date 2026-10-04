import { useState } from 'react'

import Advances from './Advances.jsx'
import AppraisalsIncidents from './AppraisalsIncidents.jsx'
import AttendanceManager from './AttendanceManager.jsx'
import Dashboard from './Dashboards.jsx'
import DepartmentManager from './DepartmentManager.jsx'
import DevelopmentAssets from './DevelopmentAssets.jsx'
import EmployeeDirectory from './EmployeeDirectory.jsx'
import Expenses from './Expenses.jsx'
import LeaveManager from './LeaveManager.jsx'
import LetterRequests from './LetterRequests.jsx'
import ModuleWorkspace from './ModuleWorkspace.jsx'
import Offboarding from './Offboarding.jsx'
import DeferredModule from './DeferredModule.jsx'
import RecordsBenefits from './RecordsBenefits.jsx'
import RosterManager from './RosterManager.jsx'
import Tasks from './Tasks.jsx'
import { administratorRouteGroup } from './administratorRoutes.js'

const loadSettings = () => import('./OrganizationSettings.jsx')
const loadReports = () => import('./Reports.jsx')
const loadCompliance = () => import('./WpsNafis.jsx')
const loadPayroll = () => import('./Payroll.jsx')
const OrganizationSettings = (props) => <DeferredModule load={loadSettings} {...props} />
const Reports = (props) => <DeferredModule load={loadReports} {...props} />
const WpsNafis = (props) => <DeferredModule load={loadCompliance} {...props} />
const Payroll = (props) => <DeferredModule load={loadPayroll} {...props} />

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
        <LeaveManager {...shared} />
      )}
      {path === '/admin/attendance' && (
        <AttendanceManager {...shared} />
      )}
      {path === '/admin/roster' && (
        <RosterManager {...shared} />
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
