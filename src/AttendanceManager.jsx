import AttendanceCalculation from './AttendanceCalculation.jsx'
import AttendanceConfiguration from './AttendanceConfiguration.jsx'
import AttendanceExceptions from './AttendanceExceptions.jsx'
import AttendanceIngestion from './AttendanceIngestion.jsx'
import AttendancePeriods from './AttendancePeriods.jsx'
import ModuleWorkspace from './ModuleWorkspace.jsx'

export default function AttendanceManager({ authentication, branchId }) {
  const shared = { authentication, branchId }
  return (
    <section className="restored-domain-workspace attendance-management" aria-labelledby="attendance-management-title">
      <header className="employee-module-toolbar">
        <div>
          <h2 id="attendance-management-title">Attendance</h2>
          <p>Review branch attendance, resolve exceptions, approve overtime, and close payroll periods.</p>
        </div>
      </header>
      <ModuleWorkspace label="Attendance management views" views={[
        { id: 'dashboard', label: 'Dashboard', content: <AttendanceCalculation {...shared} view="dashboard" /> },
        { id: 'manual', label: 'Manual Entry', content: <AttendanceIngestion {...shared} /> },
        { id: 'records', label: 'Records', content: <AttendanceCalculation {...shared} /> },
        { id: 'absences', label: 'Absences', content: <AttendanceExceptions {...shared} view="absences" /> },
        { id: 'overtime', label: 'Overtime', content: <AttendanceExceptions {...shared} view="overtime" /> },
        { id: 'corrections', label: 'Corrections', content: <AttendanceExceptions {...shared} view="corrections" /> },
        { id: 'periods', label: 'Periods', content: <AttendancePeriods {...shared} /> },
        { id: 'settings', label: 'Settings', content: <AttendanceConfiguration {...shared} view="rules" /> },
      ]} />
    </section>
  )
}
