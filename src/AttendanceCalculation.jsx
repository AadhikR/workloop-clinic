import { useCallback, useEffect, useState } from 'react'

import { readAllEmployees } from './employeeApi.js'
import { calculateAttendance, calculateAttendanceBatch, readAttendanceRecords } from './attendanceCalculationApi.js'

export default function AttendanceCalculation({ authentication, branchId, view = 'records' }) {
  const [employees, setEmployees] = useState([])
  const [records, setRecords] = useState([])
  const [form, setForm] = useState({ employeeId: '', attendanceDate: new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' }) })
  const [message, setMessage] = useState('')
  const load = useCallback(async () => {
    const [nextEmployees, nextRecords] = await Promise.all([readAllEmployees(authentication, branchId), readAttendanceRecords(authentication, branchId, { limit: 50 })])
    setEmployees(nextEmployees); setRecords(nextRecords.data)
  }, [authentication, branchId])
  useEffect(() => {
    let active = true
    Promise.all([readAllEmployees(authentication, branchId), readAttendanceRecords(authentication, branchId, { limit: 50 })])
      .then(([nextEmployees, nextRecords]) => { if (active) { setEmployees(nextEmployees); setRecords(nextRecords.data) } })
      .catch(() => { if (active) setMessage('Attendance records are unavailable.') })
    return () => { active = false }
  }, [authentication, branchId])
  const submit = async (event) => {
    event.preventDefault(); setMessage('')
    try {
      const current = records.find((item) => item.employeeId === form.employeeId && item.date === form.attendanceDate)
      await calculateAttendance(authentication, branchId, { ...form, expectedSourceDigest: current?.sourceDigest, expectedCalculationVersion: current?.calculationVersion }, { idempotencyKey: crypto.randomUUID() })
      await load(); setMessage('Attendance calculated.')
    }
    catch { setMessage('Attendance could not be calculated from the current source data.') }
  }
  const submitBatch = async () => {
    const active = employees.filter((item) => item.active)
    if (active.length < 1 || active.length > 100) { setMessage('Daily batches require between 1 and 100 active employees.'); return }
    try {
      const items = active.map((employee) => {
        const current = records.find((item) => item.employeeId === employee.id && item.date === form.attendanceDate)
        return { employeeId: employee.id, attendanceDate: form.attendanceDate, expectedSourceDigest: current?.sourceDigest, expectedCalculationVersion: current?.calculationVersion }
      })
      await calculateAttendanceBatch(authentication, branchId, items, { idempotencyKey: crypto.randomUUID() })
      await load(); setMessage('Daily attendance batch calculated.')
    }
    catch { setMessage('The daily batch was not changed because one or more source records were unavailable or stale.') }
  }
  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' })
  const todayRecords = records.filter((item) => item.date === today)
  if (view === 'dashboard') return <section className="attendance-dashboard" aria-labelledby="attendance-dashboard-title"><h2 id="attendance-dashboard-title">Attendance summary</h2><div className="stats-grid module-summary-grid"><div className="stat-card"><div className="stat-label">Active employees</div><div className="stat-value">{employees.filter((item) => item.active).length}</div><div className="stat-sub">selected branch</div></div><div className="stat-card"><div className="stat-label">Present today</div><div className="stat-value">{todayRecords.filter((item) => ['PRESENT', 'PRESENT_REMOTE', 'LATE', 'EARLY_DEPARTURE', 'OVERTIME'].includes(item.status)).length}</div><div className="stat-sub">calculated records</div></div><div className="stat-card"><div className="stat-label">Late today</div><div className="stat-value">{todayRecords.filter((item) => item.lateMinutes > 0).length}</div><div className="stat-sub">past branch grace</div></div><div className="stat-card"><div className="stat-label">Open absences</div><div className="stat-value">{records.filter((item) => item.status === 'UNEXPLAINED_ABSENCE' && item.resolutionType === null).length}</div><div className="stat-sub">need a resolution</div></div></div><div className="employee-panel"><div className="panel-heading"><h3>Today&apos;s records</h3></div>{todayRecords.length === 0 ? <div className="empty-state">No attendance has been calculated for today.</div> : <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Status</th><th>Hours</th><th>Late</th><th>Overtime</th></tr></thead><tbody>{todayRecords.map((item) => <tr key={item.id}><td>{employees.find((employee) => employee.id === item.employeeId)?.name ?? item.employeeId}</td><td>{item.status.replaceAll('_', ' ')}</td><td>{item.totalHours}</td><td>{item.lateMinutes} min</td><td>{item.overtimeHours} h</td></tr>)}</tbody></table></div>}</div>{message && <p role="status">{message}</p>}</section>
  return <section className="attendance-calculation" aria-labelledby="attendance-calculation-title"><h2 id="attendance-calculation-title">Attendance records</h2><form className="settings-form attendance-calculation-controls" onSubmit={submit}><label>Employee<select required value={form.employeeId} onChange={(event) => setForm({ ...form, employeeId: event.target.value })}><option value="">Select employee</option>{employees.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.empNo} — {item.name}</option>)}</select></label><label>Dubai attendance date<input required type="date" value={form.attendanceDate} onChange={(event) => setForm({ ...form, attendanceDate: event.target.value })} /></label><button type="submit">Calculate day</button><button type="button" onClick={submitBatch}>Calculate active employees</button></form>{records.length === 0 ? <div className="empty-state">No attendance records are available.</div> : <div className="table-wrap"><table><thead><tr><th>Date</th><th>Employee</th><th>Status</th><th>Clock in</th><th>Clock out</th><th>Hours</th><th>Overtime</th><th>Source</th></tr></thead><tbody>{records.map((item) => <tr key={item.id}><td>{item.date}</td><td>{employees.find((employee) => employee.id === item.employeeId)?.name ?? item.employeeId}</td><td>{item.status.replaceAll('_', ' ')}</td><td>{item.clockInTime ?? 'Not recorded'}</td><td>{item.clockOutTime ?? 'Not recorded'}</td><td>{item.totalHours}</td><td>{item.overtimeHours}</td><td>{item.sourceStale ? 'Recalculation needed' : `Version ${item.calculationVersion}`}</td></tr>)}</tbody></table></div>}{message && <p role="status">{message}</p>}</section>
}
