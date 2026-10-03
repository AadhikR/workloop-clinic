import { useEffect, useMemo, useState } from 'react'

import { readPersonalSchedule, readRosterColleagues } from './rosterApi.js'
import { cancelShiftSwap, readPersonalShiftSwaps, submitShiftSwap } from './shiftSwapApi.js'

function currentPeriod() { return new Date().toISOString().slice(0, 7) }

function movePeriod(period, amount) {
  const [year, month] = period.split('-').map(Number)
  const value = new Date(Date.UTC(year, month - 1 + amount, 1))
  return value.toISOString().slice(0, 7)
}

function periodLabel(period) {
  return new Intl.DateTimeFormat('en', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${period}-01T00:00:00Z`))
}

export default function PersonalSchedule({ authentication }) {
  const [period, setPeriod] = useState(currentPeriod())
  const [schedule, setSchedule] = useState([])
  const [swaps, setSwaps] = useState([])
  const [colleagues, setColleagues] = useState([])
  const [requesterAssignmentId, setRequesterAssignmentId] = useState('')
  const [targetDate, setTargetDate] = useState('')
  const [targetEmployeeId, setTargetEmployeeId] = useState('')
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState('')
  const requesterAssignment = useMemo(() => schedule.find((item) => item.rosterAssignmentId === requesterAssignmentId) ?? null, [requesterAssignmentId, schedule])

  const loadSwaps = () => readPersonalShiftSwaps(authentication).then(setSwaps)

  useEffect(() => {
    let active = true
    Promise.all([readPersonalSchedule(authentication, period), readPersonalShiftSwaps(authentication)])
      .then(([items, requests]) => { if (active) { setSchedule(items); setSwaps(requests); setMessage('') } })
      .catch(() => { if (active) { setSchedule([]); setMessage('Your published schedule is unavailable.') } })
    return () => { active = false }
  }, [authentication, period])

  useEffect(() => {
    let active = true
    if (!targetDate) return () => { active = false }
    readRosterColleagues(authentication, targetDate)
      .then((items) => { if (active) setColleagues(items) })
      .catch(() => { if (active) setColleagues([]) })
    return () => { active = false }
  }, [authentication, targetDate])

  const submit = async (event) => {
    event.preventDefault()
    if (!requesterAssignment) return
    try {
      await submitShiftSwap(authentication, {
        requesterDate: requesterAssignment.date,
        targetEmployeeId,
        targetDate,
        reason,
        expectedSourceVersion: requesterAssignment.sourceVersion,
      }, { idempotencyKey: crypto.randomUUID() })
      setRequesterAssignmentId(''); setTargetDate(''); setTargetEmployeeId(''); setReason('')
      await loadSwaps(); setMessage('Shift swap request submitted.')
    } catch { setMessage('The swap request was not submitted. Reload the published schedule and try again.') }
  }

  const cancel = async (swap) => {
    try { await cancelShiftSwap(authentication, swap, { idempotencyKey: crypto.randomUUID() }); await loadSwaps(); setMessage('Pending swap request cancelled.') }
    catch { setMessage('The swap request has already changed and could not be cancelled.') }
  }

  return (
    <section className="personal-schedule" aria-labelledby="personal-schedule-title">
      <div className="employee-section-heading"><div><h2 id="personal-schedule-title">Schedule</h2><p>Only your published shifts are shown.</p></div></div>
      <div className="month-toolbar"><button type="button" className="secondary" aria-label="Previous month" onClick={() => setPeriod(movePeriod(period, -1))}>‹</button><strong>{periodLabel(period)}</strong><button type="button" className="secondary" aria-label="Next month" onClick={() => setPeriod(movePeriod(period, 1))}>›</button><label><span className="sr-only">Choose month</span><input type="month" value={period} onChange={(event) => setPeriod(event.target.value)} /></label></div>
      {schedule.length === 0 && !message ? <div className="empty-state"><h3>No published shifts</h3><p>Your schedule for this month has not been published.</p></div> : <ol className="schedule-list">{schedule.map((item) => <li key={item.rosterAssignmentId} data-shift-category={item.shiftCategory}><time dateTime={item.date}><strong>{new Date(`${item.date}T00:00:00`).toLocaleDateString([], { weekday: 'short', day: 'numeric' })}</strong><span>{item.date}</span></time><div><strong>{item.shiftName}{item.shiftCode ? ` · ${item.shiftCode}` : ''}</strong><span>{item.plannedHours} expected hours{item.actualHours === null ? '' : ` · ${item.actualHours} actual`}{item.overtimeHours === '0.00' ? '' : ` · ${item.overtimeHours} overtime`}</span>{item.notes && <small>{item.notes}</small>}</div></li>)}</ol>}
      <section className="shift-swaps employee-panel"><h3>Request a shift swap</h3><form className="settings-form" onSubmit={submit}>
        <label>Your shift<select required value={requesterAssignmentId} onChange={(event) => setRequesterAssignmentId(event.target.value)}><option value="">Choose a published shift</option>{schedule.filter((item) => item.actualHours === null).map((item) => <option key={item.rosterAssignmentId} value={item.rosterAssignmentId}>{item.date} — {item.shiftCode ?? item.shiftName}</option>)}</select></label>
        <label>Colleague shift date<input required type="date" value={targetDate} onChange={(event) => { setTargetDate(event.target.value); setTargetEmployeeId(''); setColleagues([]) }} /></label>
        <label>Colleague<select required value={targetEmployeeId} onChange={(event) => setTargetEmployeeId(event.target.value)}><option value="">Choose a same-branch colleague</option>{colleagues.map((item) => <option key={item.rosterAssignmentId} value={item.employeeId}>{item.employeeName} — {item.shiftCode ?? item.shiftName}</option>)}</select></label>
        <label>Reason<input required minLength="3" maxLength="500" value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <button type="submit">Request swap</button>
      </form></section>
      <section className="shift-swap-history employee-panel"><h3>My swap requests</h3>{swaps.length === 0 ? <p className="empty-copy">No swap requests.</p> : <ul className="employee-detail-list">{swaps.map((swap) => <li key={swap.id}><span><strong>{swap.requesterDate} ↔ {swap.targetDate}</strong><small>{swap.requesterEmployeeName} and {swap.targetEmployeeName}</small></span><span className="status-pill" data-status={swap.status}>{swap.status}</span>{swap.status === 'pending' && <button type="button" className="secondary" onClick={() => cancel(swap)}>Cancel request</button>}</li>)}</ul>}</section>
      {message && <p role="status" className="feedback">{message}</p>}
    </section>
  )
}
