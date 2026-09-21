import { useEffect, useState } from 'react'

import { readAllEmployees } from './employeeApi.js'
import { calculateAttendance, calculateAttendanceBatch, readAttendanceRecords } from './attendanceCalculationApi.js'

export default function AttendanceCalculation({ authentication, branchId }) {
  const [employees, setEmployees] = useState([])
  const [records, setRecords] = useState([])
  const [form, setForm] = useState({ employeeId: '', attendanceDate: new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' }) })
  const [message, setMessage] = useState('')
  const load = async () => {
    const [nextEmployees, nextRecords] = await Promise.all([readAllEmployees(authentication, branchId), readAttendanceRecords(authentication, branchId, { limit: 50 })])
    setEmployees(nextEmployees); setRecords(nextRecords.data)
  }
  useEffect(() => { load().catch(() => setMessage('Attendance records are unavailable.')) }, [authentication, branchId])
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
  return <section className="attendance-calculation" aria-labelledby="attendance-calculation-title"><h2 id="attendance-calculation-title">Attendance calculation</h2><form className="settings-form" onSubmit={submit}><label>Employee<select required value={form.employeeId} onChange={(event) => setForm({ ...form, employeeId: event.target.value })}><option value="">Select employee</option>{employees.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.employeeNo} — {item.name}</option>)}</select></label><label>Dubai attendance date<input required type="date" value={form.attendanceDate} onChange={(event) => setForm({ ...form, attendanceDate: event.target.value })} /></label><button type="submit">Calculate day</button><button type="button" onClick={submitBatch}>Calculate active employees</button></form><ul>{records.map((item) => <li key={item.id}>{item.date} — {item.status} — {item.totalHours} hours{item.sourceStale ? ' — recalculation needed' : ''}</li>)}</ul>{message && <p role="status">{message}</p>}</section>
}
