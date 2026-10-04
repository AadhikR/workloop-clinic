import LeaveApprovals from './LeaveApprovals.jsx'
import LeaveConfiguration from './LeaveConfiguration.jsx'
import LeaveOverview from './LeaveOverview.jsx'
import ModuleWorkspace from './ModuleWorkspace.jsx'

export default function LeaveManager({ account, authentication, branchId }) {
  const shared = { account, authentication, branchId }
  return (
    <section className="restored-domain-workspace leave-management" aria-labelledby="leave-management-title">
      <header className="employee-module-toolbar">
        <div>
          <h2 id="leave-management-title">Leave Management</h2>
          <p>Review leave activity, decide requests, manage balances, and maintain branch policy.</p>
        </div>
      </header>
      <ModuleWorkspace label="Leave management views" views={[
        { id: 'overview', label: 'Overview', content: <LeaveOverview {...shared} view="overview" /> },
        { id: 'requests', label: 'Requests', content: <><LeaveApprovals {...shared} queueOnly /><LeaveOverview {...shared} view="requests" /></> },
        { id: 'calendar', label: 'Calendar', content: <LeaveOverview {...shared} view="calendar" /> },
        { id: 'balances', label: 'Balances', content: <LeaveOverview {...shared} view="balances" /> },
        { id: 'settings', label: 'Settings', content: <><LeaveConfiguration authentication={authentication} branchId={branchId} /><LeaveApprovals {...shared} delegationsOnly /></> },
      ]} />
    </section>
  )
}
