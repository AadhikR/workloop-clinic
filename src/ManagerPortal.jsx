import Advances from './Advances.jsx'
import AppraisalsIncidents from './AppraisalsIncidents.jsx'
import DevelopmentAssets from './DevelopmentAssets.jsx'
import EmployeeDirectory from './EmployeeDirectory.jsx'
import EmployeeProfile from './EmployeeProfile.jsx'
import EmployeeHome from './EmployeeHome.jsx'
import Expenses from './Expenses.jsx'
import LeaveApprovals from './LeaveApprovals.jsx'
import LeaveOverview from './LeaveOverview.jsx'
import LetterRequests from './LetterRequests.jsx'
import PersonalAttendance from './PersonalAttendance.jsx'
import PersonalSchedule from './PersonalSchedule.jsx'
import Payslips from './Payslips.jsx'
import RecordsBenefits from './RecordsBenefits.jsx'
import Tasks from './Tasks.jsx'
import { managerRouteGroup } from './managerRoutes.js'

export default function ManagerPortal({ account, authentication, branchId, navigator, path }) {
  const group = managerRouteGroup(path)
  if (group === null) return null

  const shared = { account, authentication, branchId }
  return (
    <div className="portal-route manager-route" data-manager-route={path}>
      {path === '/manager' && <EmployeeHome authentication={authentication} navigator={navigator} role="manager" />}
      {path === '/manager/team' && <EmployeeDirectory {...shared} />}
      {path === '/manager/leave-queue' && <LeaveApprovals {...shared} />}
      {path === '/manager/expense-queue' && <Expenses {...shared} view="queue" />}
      {path === '/manager/appraisals' && <AppraisalsIncidents {...shared} view="appraisals" />}
      {path === '/manager/leave' && <LeaveOverview {...shared} />}
      {path === '/manager/schedule' && <PersonalSchedule authentication={authentication} />}
      {path === '/manager/attendance' && <PersonalAttendance authentication={authentication} />}
      {path === '/manager/payslips' && <Payslips account={account} authentication={authentication} />}
      {path === '/manager/advances' && <Advances {...shared} />}
      {path === '/manager/expenses' && <Expenses {...shared} view="self" />}
      {path === '/manager/training' && <DevelopmentAssets {...shared} trainingOnly />}
      {path === '/manager/documents' && <RecordsBenefits {...shared} documentsOnly />}
      {path === '/manager/requests' && <LetterRequests {...shared} />}
      {path === '/manager/profile' && (
        <EmployeeProfile authentication={authentication} onSignOut={() => authentication.logout()} />
      )}
      {path === '/manager/tasks' && <Tasks {...shared} navigator={navigator} />}
      {path === '/manager/time' && (
        <>
          <PersonalAttendance authentication={authentication} />
          <PersonalSchedule authentication={authentication} />
        </>
      )}
      {path === '/manager/development' && (
        <>
          <DevelopmentAssets {...shared} />
          <AppraisalsIncidents {...shared} />
        </>
      )}
    </div>
  )
}
