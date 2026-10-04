import AttendanceConfiguration from './AttendanceConfiguration.jsx'
import ModuleWorkspace from './ModuleWorkspace.jsx'
import RosterDrafts from './RosterDrafts.jsx'
import ShiftSwapQueue from './ShiftSwapQueue.jsx'

export default function RosterManager({ authentication, branchId }) {
  const shared = { authentication, branchId }
  return (
    <section className="restored-domain-workspace roster-management" aria-labelledby="roster-management-title">
      <header className="employee-module-toolbar">
        <div>
          <h2 id="roster-management-title">Shift Scheduling &amp; Roster</h2>
          <p>Maintain shift templates, build the monthly roster, pass publication checks, and decide swaps.</p>
        </div>
      </header>
      <ModuleWorkspace label="Roster management views" views={[
        { id: 'templates', label: 'Shift Templates', content: <AttendanceConfiguration {...shared} view="shifts" /> },
        { id: 'roster', label: 'Monthly Roster', content: <RosterDrafts {...shared} /> },
        { id: 'swaps', label: 'Swap Requests', content: <ShiftSwapQueue {...shared} /> },
      ]} />
    </section>
  )
}
