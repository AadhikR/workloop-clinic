import { useCallback, useEffect, useState } from 'react'

import { readPersonalAttendance, readPersonalAttendanceHistory } from './attendanceCalculationApi.js'
import { readPersonalRegularisations, submitRegularisation } from './attendanceExceptionsApi.js'

const today = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' })
const dubaiInstant = (value) => new Date(`${value}:00+04:00`).toISOString()

export default function PersonalAttendance({ authentication }) {
  const [attendance, setAttendance] = useState(null)
  const [history, setHistory] = useState([])
  const [requests, setRequests] = useState([])
  const [message, setMessage] = useState('')
  const [form, setForm] = useState(() => { const date = today(); return { attendanceDate: date, clockIn: `${date}T08:00`, clockOut: `${date}T17:00`, reason: '' } })
  const load = useCallback(() => Promise.all([readPersonalAttendance(authentication), readPersonalAttendanceHistory(authentication, { limit: 31 }), readPersonalRegularisations(authentication, { limit: 50 })])
    .then(([current, previous, regularisations]) => { setAttendance(current); setHistory(previous.data); setRequests(regularisations.data) })
  , [authentication])
  useEffect(() => {
    const refresh = async () => {
      try { await load() }
      catch {
        setAttendance({ record: null, rawEvents: [] })
        setHistory([])
        setRequests([])
        setMessage('Personal attendance is unavailable.')
      }
    }
    void refresh()
  }, [load])

  const submit = async (event) => {
    event.preventDefault(); setMessage('')
    try {
      await submitRegularisation(authentication, { attendanceDate: form.attendanceDate, correctClockIn: dubaiInstant(form.clockIn), correctClockOut: dubaiInstant(form.clockOut), reason: form.reason }, { idempotencyKey: crypto.randomUUID() })
      await load(); setMessage('Attendance correction submitted for review.')
    }
    catch { setMessage('The correction was not submitted. Check the dates, monthly limit, and any existing pending request.') }
  }
  if (attendance === null) return <section className="personal-attendance"><p>Loading personal attendance...</p></section>
  const record = attendance.record
  return <section className="personal-attendance" aria-labelledby="personal-attendance-title">
    <div className="employee-section-heading"><div><h2 id="personal-attendance-title">Attendance</h2><p>Your attendance is read-only apart from correction requests.</p></div></div>
    <section className="today-attendance employee-panel" aria-labelledby="today-attendance-title">
      <div className="employee-section-heading"><h3 id="today-attendance-title">Today</h3><span className="status-pill" data-status={record?.status.toLowerCase() ?? 'not-calculated'}>{record?.status.replaceAll('_', ' ') ?? 'Not calculated'}</span></div>
      {record ? <dl className="attendance-metrics">
        <div><dt>Clock in</dt><dd>{record.clockInTime ? new Date(record.clockInTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Not recorded'}</dd></div>
        <div><dt>Clock out</dt><dd>{record.clockOutTime ? new Date(record.clockOutTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Not recorded'}</dd></div>
        <div><dt>Total hours</dt><dd>{record.totalHours}</dd></div>
        <div><dt>Late</dt><dd>{record.lateMinutes} min</dd></div>
        <div><dt>Early departure</dt><dd>{record.earlyDepartureMinutes} min</dd></div>
        <div><dt>Overtime</dt><dd>{record.overtimeHours} hr</dd></div>
      </dl> : <><p>No calculated attendance is available for today.</p>{attendance.rawEvents.length > 0 && <ul>{attendance.rawEvents.map((item) => <li key={item.id}>{new Date(item.eventTime).toLocaleTimeString()} · {item.eventType.replaceAll('_', ' ')}</li>)}</ul>}</>}
    </section>
    <div className="employee-split-grid">
      <section className="employee-panel"><h3>Correction request</h3><form className="settings-form" onSubmit={submit}><label>Attendance date<input required type="date" value={form.attendanceDate} onChange={(event) => { const attendanceDate = event.target.value; setForm({ ...form, attendanceDate, clockIn: `${attendanceDate}T08:00`, clockOut: `${attendanceDate}T17:00` }) }} /></label><label>Correct clock in, Dubai time<input required type="datetime-local" value={form.clockIn} onChange={(event) => setForm({ ...form, clockIn: event.target.value })} /></label><label>Correct clock out, Dubai time<input required type="datetime-local" value={form.clockOut} onChange={(event) => setForm({ ...form, clockOut: event.target.value })} /></label><label>Reason<textarea required minLength="3" maxLength="500" value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} /></label><button type="submit">Submit correction</button></form></section>
      <section className="employee-panel"><h3>Correction history</h3>{requests.length === 0 ? <p className="empty-copy">No correction requests.</p> : <ul className="employee-detail-list">{requests.map((item) => <li key={item.id}><strong>{item.attendanceDate}</strong><span className="status-pill" data-status={item.status.toLowerCase()}>{item.status}</span>{item.rejectionReason && <span>{item.rejectionReason}</span>}</li>)}</ul>}</section>
    </div>
    <section className="employee-panel"><h3>Recent history</h3>{history.length === 0 ? <p className="empty-copy">No attendance history is available.</p> : <div className="table-wrap"><table><thead><tr><th>Date</th><th>Status</th><th>Clock in</th><th>Clock out</th><th>Total</th><th>Late</th><th>Overtime</th></tr></thead><tbody>{history.map((item) => <tr key={item.id}><td>{item.date}</td><td><span className="status-pill" data-status={item.status.toLowerCase()}>{item.status.replaceAll('_', ' ')}</span></td><td>{item.clockInTime ? new Date(item.clockInTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}</td><td>{item.clockOutTime ? new Date(item.clockOutTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}</td><td>{item.totalHours} hr</td><td>{item.lateMinutes} min</td><td>{item.overtimeHours} hr</td></tr>)}</tbody></table></div>}</section>
    {message && <p role="status" className="feedback">{message}</p>}
  </section>
}
