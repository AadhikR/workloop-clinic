import Advances from './Advances.jsx'
import AppraisalsIncidents from './AppraisalsIncidents.jsx'
import DevelopmentAssets from './DevelopmentAssets.jsx'
import EmployeeDirectory from './EmployeeDirectory.jsx'
import Expenses from './Expenses.jsx'
import LeaveApprovals from './LeaveApprovals.jsx'
import LeaveOverview from './LeaveOverview.jsx'
import LetterRequests from './LetterRequests.jsx'
import PersonalAttendance from './PersonalAttendance.jsx'
import PersonalSchedule from './PersonalSchedule.jsx'
import RecordsBenefits from './RecordsBenefits.jsx'
import { managerRouteGroup } from './managerRoutes.js'

export default function ManagerPortal({ account, authentication, branchId, path }) {
  const group = managerRouteGroup(path)
  if (group === null || path === '/manager') return null

  const shared = { account, authentication, branchId }
  return (
    <div className="manager-route" data-manager-route={path}>
      {path === '/manager/team' && <EmployeeDirectory {...shared} />}
      {path === '/manager/leave' && (
        <>
          <LeaveOverview {...shared} />
          <LeaveApprovals {...shared} />
        </>
      )}
      {path === '/manager/time' && (
        <>
          <PersonalAttendance authentication={authentication} />
          <PersonalSchedule authentication={authentication} />
        </>
      )}
      {path === '/manager/expenses' && <Expenses {...shared} />}
      {path === '/manager/development' && (
        <>
          <DevelopmentAssets {...shared} />
          <AppraisalsIncidents {...shared} />
        </>
      )}
      {path === '/manager/requests' && (
        <>
          <Advances {...shared} />
          <RecordsBenefits {...shared} />
          <LetterRequests {...shared} />
        </>
      )}
    </div>
  )
}
