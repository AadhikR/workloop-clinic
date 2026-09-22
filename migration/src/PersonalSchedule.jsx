import { useEffect, useMemo, useState } from 'react'

import { readPersonalSchedule, readRosterColleagues } from './rosterApi.js'
import { cancelShiftSwap, readPersonalShiftSwaps, submitShiftSwap } from './shiftSwapApi.js'

function currentPeriod() { return new Date().toISOString().slice(0, 7) }

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
      <h2 id="personal-schedule-title">My schedule</h2>
      <p>Only your current published roster is shown here.</p>
      <label>Month<input type="month" value={period} onChange={(event) => setPeriod(event.target.value)} /></label>
      {schedule.length === 0 && !message && <p>No published shifts for this month.</p>}
      <ul>{schedule.map((item) => <li key={item.rosterAssignmentId}><strong>{item.date} — {item.shiftCode ?? item.shiftName}</strong><span>{item.plannedHours} planned hours{item.actualHours === null ? '' : ` · ${item.actualHours} actual hours`}{item.overtimeHours === '0.00' ? '' : ` · ${item.overtimeHours} approved overtime hours`}</span></li>)}</ul>
      <section className="shift-swaps"><h3>Request a shift swap</h3><form onSubmit={submit}>
        <label>Your shift<select required value={requesterAssignmentId} onChange={(event) => setRequesterAssignmentId(event.target.value)}><option value="">Choose a published shift</option>{schedule.filter((item) => item.actualHours === null).map((item) => <option key={item.rosterAssignmentId} value={item.rosterAssignmentId}>{item.date} — {item.shiftCode ?? item.shiftName}</option>)}</select></label>
        <label>Colleague shift date<input required type="date" value={targetDate} onChange={(event) => { setTargetDate(event.target.value); setTargetEmployeeId(''); setColleagues([]) }} /></label>
        <label>Colleague<select required value={targetEmployeeId} onChange={(event) => setTargetEmployeeId(event.target.value)}><option value="">Choose a same-branch colleague</option>{colleagues.map((item) => <option key={item.rosterAssignmentId} value={item.employeeId}>{item.employeeName} — {item.shiftCode ?? item.shiftName}</option>)}</select></label>
        <label>Reason<input required minLength="3" maxLength="500" value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <button type="submit">Request swap</button>
      </form></section>
      <section className="shift-swap-history"><h3>My swap requests</h3>{swaps.length === 0 ? <p>No swap requests.</p> : <ul>{swaps.map((swap) => <li key={swap.id}><span><strong>{swap.requesterDate} ↔ {swap.targetDate}</strong><small>{swap.requesterEmployeeName} and {swap.targetEmployeeName} · {swap.status}</small></span>{swap.status === 'pending' && <button type="button" className="secondary" onClick={() => cancel(swap)}>Cancel request</button>}</li>)}</ul>}</section>
      {message && <p role="status">{message}</p>}
    </section>
  )
}
