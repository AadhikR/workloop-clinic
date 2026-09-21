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
      catch { setMessage('Personal attendance is unavailable.') }
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
  if (attendance === null) return <p>Loading personal attendance...</p>
  return <section aria-labelledby="personal-attendance-title"><h2 id="personal-attendance-title">My attendance</h2>{attendance.record ? <p>Today: {attendance.record.status} — {attendance.record.totalHours} hours</p> : <><p>No calculated attendance is available for today.</p><ul>{attendance.rawEvents.map((item) => <li key={item.id}>{item.eventTime} — {item.eventType}</li>)}</ul></>}<h3>Request a correction</h3><form className="settings-form" onSubmit={submit}><label>Attendance date<input required type="date" value={form.attendanceDate} onChange={(event) => { const attendanceDate = event.target.value; setForm({ ...form, attendanceDate, clockIn: `${attendanceDate}T08:00`, clockOut: `${attendanceDate}T17:00` }) }} /></label><label>Correct clock in, Dubai time<input required type="datetime-local" value={form.clockIn} onChange={(event) => setForm({ ...form, clockIn: event.target.value })} /></label><label>Correct clock out, Dubai time<input required type="datetime-local" value={form.clockOut} onChange={(event) => setForm({ ...form, clockOut: event.target.value })} /></label><label>Reason<textarea required minLength="3" maxLength="500" value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} /></label><button type="submit">Submit correction</button></form><h3>Correction history</h3><ul>{requests.map((item) => <li key={item.id}>{item.attendanceDate} — {item.status}{item.rejectionReason ? ` — ${item.rejectionReason}` : ''}</li>)}</ul><h3>Attendance history</h3><ul>{history.map((item) => <li key={item.id}>{item.date} — {item.status} — {item.totalHours} hours</li>)}</ul>{message && <p role="status">{message}</p>}</section>
}
