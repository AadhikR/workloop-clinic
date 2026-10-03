import Advances from './Advances.jsx'
import AppraisalsIncidents from './AppraisalsIncidents.jsx'
import AttendanceCalculation from './AttendanceCalculation.jsx'
import AttendanceConfiguration from './AttendanceConfiguration.jsx'
import AttendanceExceptions from './AttendanceExceptions.jsx'
import AttendanceIngestion from './AttendanceIngestion.jsx'
import AttendancePeriods from './AttendancePeriods.jsx'
import DepartmentManager from './DepartmentManager.jsx'
import DevelopmentAssets from './DevelopmentAssets.jsx'
import EmployeeDirectory from './EmployeeDirectory.jsx'
import Expenses from './Expenses.jsx'
import LeaveApprovals from './LeaveApprovals.jsx'
import LeaveConfiguration from './LeaveConfiguration.jsx'
import LeaveOverview from './LeaveOverview.jsx'
import LetterRequests from './LetterRequests.jsx'
import Offboarding from './Offboarding.jsx'
import OrganizationSettings from './OrganizationSettings.jsx'
import Payroll from './Payroll.jsx'
import Payslips from './Payslips.jsx'
import RecordsBenefits from './RecordsBenefits.jsx'
import Reports from './Reports.jsx'
import RosterDrafts from './RosterDrafts.jsx'
import ShiftSwapQueue from './ShiftSwapQueue.jsx'
import WpsNafis from './WpsNafis.jsx'
import { administratorRouteGroup } from './administratorRoutes.js'

export default function AdministratorPortal({
  account,
  authentication,
  branchId,
  clearBranch,
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
      {path === '/admin/people' && (
        <EmployeeDirectory {...shared} clearBranch={clearBranch} />
      )}
      {path === '/admin/leave' && (
        <>
          <LeaveConfiguration authentication={authentication} branchId={branchId} />
          <LeaveOverview {...shared} />
          <LeaveApprovals {...shared} />
        </>
      )}
      {path === '/admin/attendance' && (
        <>
          <AttendanceConfiguration authentication={authentication} branchId={branchId} />
          <AttendanceIngestion authentication={authentication} branchId={branchId} />
          <AttendanceCalculation authentication={authentication} branchId={branchId} />
          <AttendanceExceptions authentication={authentication} branchId={branchId} />
          <AttendancePeriods authentication={authentication} branchId={branchId} />
        </>
      )}
      {path === '/admin/roster' && (
        <>
          <RosterDrafts authentication={authentication} branchId={branchId} />
          <ShiftSwapQueue {...shared} />
        </>
      )}
      {path === '/admin/payroll' && (
        <>
          <Payroll {...shared} />
          <Expenses {...shared} />
          <Advances {...shared} />
          <Payslips account={account} authentication={authentication} />
          <WpsNafis {...shared} />
        </>
      )}
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
      {path === '/admin/reports' && (
        <Reports authentication={authentication} branchId={branchId} />
      )}
    </div>
  )
}
