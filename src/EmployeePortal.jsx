import Advances from './Advances.jsx'
import AppraisalsIncidents from './AppraisalsIncidents.jsx'
import DevelopmentAssets from './DevelopmentAssets.jsx'
import EmployeeDirectory from './EmployeeDirectory.jsx'
import Expenses from './Expenses.jsx'
import LeaveOverview from './LeaveOverview.jsx'
import LetterRequests from './LetterRequests.jsx'
import Payslips from './Payslips.jsx'
import PersonalAttendance from './PersonalAttendance.jsx'
import PersonalSchedule from './PersonalSchedule.jsx'
import RecordsBenefits from './RecordsBenefits.jsx'
import { employeeRouteGroup } from './employeeRoutes.js'

export default function EmployeePortal({ account, authentication, branchId, path }) {
  const group = employeeRouteGroup(path)
  if (group === null || path === '/employee') return null

  const shared = { account, authentication, branchId }
  return (
    <div className="employee-route" data-employee-route={path}>
      {path === '/employee/profile' && <EmployeeDirectory {...shared} />}
      {path === '/employee/leave' && <LeaveOverview {...shared} />}
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
