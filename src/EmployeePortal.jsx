import Advances from './Advances.jsx'
import AppraisalsIncidents from './DeferredAppraisalsIncidents.jsx'
import DevelopmentAssets from './DevelopmentAssets.jsx'
import EmployeeHome from './EmployeeHome.jsx'
import EmployeeProfile from './EmployeeProfile.jsx'
import Expenses from './Expenses.jsx'
import LeaveOverview from './LeaveOverview.jsx'
import LetterRequests from './LetterRequests.jsx'
import Payslips from './Payslips.jsx'
import PersonalAttendance from './PersonalAttendance.jsx'
import PersonalSchedule from './PersonalSchedule.jsx'
import RecordsBenefits from './DeferredRecordsBenefits.jsx'
import Tasks from './Tasks.jsx'
import { employeeRouteGroup } from './employeeRoutes.js'

export default function EmployeePortal({ account, authentication, branchId, navigator, path }) {
  const group = employeeRouteGroup(path)
  if (group === null) return null

  const shared = { account, authentication, branchId }
  return (
    <div className="portal-route employee-route" data-employee-route={path}>
      {path === '/employee' && <EmployeeHome authentication={authentication} navigator={navigator} />}
      {path === '/employee/profile' && <EmployeeProfile authentication={authentication} onSignOut={() => authentication.logout()} />}
      {path === '/employee/leave' && <LeaveOverview {...shared} />}
      {path === '/employee/schedule' && <PersonalSchedule authentication={authentication} />}
      {path === '/employee/attendance' && <PersonalAttendance authentication={authentication} />}
      {path === '/employee/payslips' && <Payslips account={account} authentication={authentication} />}
      {path === '/employee/advances' && <Advances {...shared} />}
      {path === '/employee/expenses' && <Expenses {...shared} />}
      {path === '/employee/training' && <DevelopmentAssets {...shared} trainingOnly />}
      {path === '/employee/appraisals' && <AppraisalsIncidents {...shared} />}
      {path === '/employee/documents' && <RecordsBenefits {...shared} documentsOnly />}
      {path === '/employee/tasks' && <Tasks {...shared} navigator={navigator} />}
      {path === '/employee/time' && (
        <>
          <PersonalAttendance authentication={authentication} />
          <PersonalSchedule authentication={authentication} />
        </>
      )}
      {path === '/employee/pay' && (
        <>
          <Payslips account={account} authentication={authentication} />
          <Expenses {...shared} />
          <Advances {...shared} />
        </>
      )}
      {path === '/employee/records' && <RecordsBenefits {...shared} />}
      {path === '/employee/development' && (
        <>
          <DevelopmentAssets {...shared} />
          <AppraisalsIncidents {...shared} />
        </>
      )}
      {path === '/employee/requests' && <LetterRequests {...shared} />}
    </div>
  )
}
