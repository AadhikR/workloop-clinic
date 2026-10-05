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
  const [showForm, setShowForm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(null)
  const [loadState, setLoadState] = useState('loading')
  const [form, setForm] = useState(() => { const date = today(); return { attendanceDate: date, clockIn: `${date}T08:00`, clockOut: `${date}T17:00`, reason: '' } })
  const load = useCallback(() => Promise.all([readPersonalAttendance(authentication), readPersonalAttendanceHistory(authentication, { limit: 31 }), readPersonalRegularisations(authentication, { limit: 50 })])
    .then(([current, previous, regularisations]) => { setAttendance(current); setHistory(previous.data); setRequests(regularisations.data); setLoadState('ready') })
  , [authentication])
  useEffect(() => {
    const refresh = async () => {
      try { await load() }
      catch {
        setAttendance({ record: null, rawEvents: [] })
        setHistory([])
        setRequests([])
        setMessage('Personal attendance is unavailable.')
        setLoadState('error')
      }
    }
    void refresh()
  }, [load])

  const submit = async (event) => {
    event.preventDefault(); setMessage(''); setBusy(true)
    const payload = { attendanceDate: form.attendanceDate, correctClockIn: dubaiInstant(form.clockIn), correctClockOut: dubaiInstant(form.clockOut), reason: form.reason }
    const attempt = retry && JSON.stringify(retry.payload) === JSON.stringify(payload) ? retry : { payload, key: crypto.randomUUID() }
    setRetry(attempt)
    try {
      await submitRegularisation(authentication, payload, { idempotencyKey: attempt.key })
      setRetry(null); setShowForm(false); setForm({ ...form, reason: '' }); setMessage('Attendance correction submitted for review.')
      await load().catch(() => setMessage('Attendance correction submitted. Reload to see its status.'))
    }
    catch { setMessage('The correction was not submitted. Check the dates, monthly limit, and any existing pending request.') }
    finally { setBusy(false) }
  }
  if (attendance === null) return <section className="personal-attendance"><p>Loading personal attendance...</p></section>
  const record = loadState === 'ready' ? attendance.record : null
  return <section className="personal-attendance" aria-labelledby="personal-attendance-title">
    <div className="employee-section-heading"><div><h2 id="personal-attendance-title">Attendance</h2><p>Your attendance is read-only apart from correction requests.</p></div></div>
    {loadState === 'error' && <p role="alert">Personal attendance is unavailable. <button type="button" onClick={() => load().catch(() => setLoadState('error'))}>Retry</button></p>}
    <section className="today-attendance employee-panel" aria-labelledby="today-attendance-title">
      <div className="employee-section-heading"><h3 id="today-attendance-title">Today</h3><span className="status-pill" data-status={record?.status.toLowerCase() ?? 'not-calculated'}>{record?.status.replaceAll('_', ' ') ?? 'Not calculated'}</span></div>
      {record ? <dl className="attendance-metrics">
        <div><dt>Clock in</dt><dd>{record.clockInTime ? new Date(record.clockInTime).toLocaleTimeString('en-AE', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Dubai' }) : 'Not recorded'}</dd></div>
        <div><dt>Clock out</dt><dd>{record.clockOutTime ? new Date(record.clockOutTime).toLocaleTimeString('en-AE', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Dubai' }) : 'Not recorded'}</dd></div>
        <div><dt>Total hours</dt><dd>{record.totalHours}</dd></div>
        <div><dt>Late</dt><dd>{record.lateMinutes} min</dd></div>
        <div><dt>Early departure</dt><dd>{record.earlyDepartureMinutes} min</dd></div>
        <div><dt>Overtime</dt><dd>{record.overtimeHours} hr</dd></div>
      </dl> : <><p>No calculated attendance is available for today.</p>{attendance.rawEvents.length > 0 && <ul>{attendance.rawEvents.map((item) => <li key={item.id}>{new Date(item.eventTime).toLocaleTimeString('en-AE', { timeZone: 'Asia/Dubai' })} · {item.eventType.replaceAll('_', ' ')}</li>)}</ul>}</>}
    </section>
    <button type="button" className="btn btn-outline" aria-expanded={showForm} disabled={busy} onClick={() => { setShowForm(!showForm); setMessage('') }}>Request Attendance Correction</button><div className="employee-split-grid">
      {showForm && <section className="employee-panel"><h3>Correction request</h3><form className="settings-form" onSubmit={submit}><label>Attendance date<input required type="date" value={form.attendanceDate} onChange={(event) => { const attendanceDate = event.target.value; setForm({ ...form, attendanceDate, clockIn: `${attendanceDate}T08:00`, clockOut: `${attendanceDate}T17:00` }) }} /></label><label>Correct clock in, Dubai time<input required type="datetime-local" value={form.clockIn} onChange={(event) => setForm({ ...form, clockIn: event.target.value })} /></label><label>Correct clock out, Dubai time<input required type="datetime-local" value={form.clockOut} onChange={(event) => setForm({ ...form, clockOut: event.target.value })} /></label><label>Reason<textarea required minLength="3" maxLength="500" value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} /></label><button type="submit" disabled={busy}>{busy ? 'Submitting...' : 'Submit correction'}</button><button type="button" disabled={busy} onClick={() => setShowForm(false)}>Cancel</button>{message && <p role="alert">{message}</p>}</form></section>}
      <section className="employee-panel"><h3>Correction history</h3>{requests.length === 0 ? <p className="empty-copy">No correction requests.</p> : <ul className="employee-detail-list">{requests.map((item) => <li key={item.id}><strong>{item.attendanceDate}</strong><span className="status-pill" data-status={item.status.toLowerCase()}>{item.status}</span>{item.rejectionReason && <span>{item.rejectionReason}</span>}</li>)}</ul>}</section>
    </div>
    <section><h3>Recent history</h3>{history.length === 0 ? <p className="empty-copy">No attendance history is available.</p> : <div className="staff-records">{history.map((item) => <article className="employee-panel staff-record" key={item.id}><header><div><strong>{item.date}</strong><p>{item.clockInTime ? new Date(item.clockInTime).toLocaleTimeString('en-AE', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Dubai' }) : 'Not recorded'} to {item.clockOutTime ? new Date(item.clockOutTime).toLocaleTimeString('en-AE', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Dubai' }) : 'Not recorded'} · {item.totalHours} hours</p></div><span className="status-pill" data-status={item.status.toLowerCase()}>{item.status.replaceAll('_', ' ')}</span></header></article>)}</div>}</section>
    {message && <p role="status" className="feedback">{message}</p>}
  </section>
}
