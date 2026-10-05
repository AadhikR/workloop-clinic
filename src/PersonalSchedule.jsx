import { useEffect, useMemo, useState } from 'react'

import { readPersonalSchedule, readRosterColleagues } from './rosterApi.js'
import { cancelShiftSwap, readPersonalShiftSwaps, submitShiftSwap } from './shiftSwapApi.js'
import { FormDialog, SummaryCards } from './PortalUi.jsx'

function currentPeriod() { return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' }).slice(0, 7) }

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
  const [loadState, setLoadState] = useState('loading')
  const [showForm, setShowForm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(null)
  const [refresh, setRefresh] = useState(0)
  const changePeriod = (value) => { if (!/^\d{4}-\d{2}$/.test(value)) return; setPeriod(value); setSchedule([]); setLoadState('loading'); setShowForm(false); setRequesterAssignmentId(''); setTargetDate(''); setTargetEmployeeId(''); setColleagues([]); setMessage('') }
  const requesterAssignment = useMemo(() => schedule.find((item) => item.rosterAssignmentId === requesterAssignmentId) ?? null, [requesterAssignmentId, schedule])

  const loadSwaps = () => readPersonalShiftSwaps(authentication).then(setSwaps)

  useEffect(() => {
    let active = true
    Promise.all([readPersonalSchedule(authentication, period), readPersonalShiftSwaps(authentication)])
      .then(([items, requests]) => { if (active) { setSchedule(items); setSwaps(requests); setLoadState('ready') } })
      .catch(() => { if (active) { setSchedule([]); setSwaps([]); setLoadState('error') } })
    return () => { active = false }
  }, [authentication, period, refresh])

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
    if (!requesterAssignment || busy) return
    setBusy(true); setMessage('')
    const payload = { requesterDate: requesterAssignment.date, targetEmployeeId, targetDate, reason, expectedSourceVersion: requesterAssignment.sourceVersion }
    const attempt = retry && JSON.stringify(retry.payload) === JSON.stringify(payload) ? retry : { payload, key: crypto.randomUUID() }
    setRetry(attempt)
    try {
      await submitShiftSwap(authentication, payload, { idempotencyKey: attempt.key })
      setRetry(null); setShowForm(false)
      setRequesterAssignmentId(''); setTargetDate(''); setTargetEmployeeId(''); setReason('')
      setMessage('Shift swap request submitted.')
      await loadSwaps().catch(() => setMessage('Shift swap request submitted. Reload to see its status.'))
    } catch { setMessage('The swap request could not be submitted. Your entries have been kept.') }
    finally { setBusy(false) }
  }

  const cancel = async (swap) => {
    if (busy) return
    setBusy(true)
    try { await cancelShiftSwap(authentication, swap, { idempotencyKey: crypto.randomUUID() }); await loadSwaps(); setMessage('Pending swap request cancelled.') }
    catch { setMessage('The swap request has already changed and could not be cancelled.') }
    finally { setBusy(false) }
  }

  return (
    <section className="personal-schedule" aria-labelledby="personal-schedule-title">
      <div className="employee-section-heading"><div><h2 id="personal-schedule-title">Schedule</h2><p>Only your published shifts are shown.</p></div></div>
      <div className="month-toolbar"><button type="button" className="secondary" aria-label="Previous month" onClick={() => changePeriod(movePeriod(period, -1))}>‹</button><strong>{periodLabel(period)}</strong><button type="button" className="secondary" aria-label="Next month" onClick={() => changePeriod(movePeriod(period, 1))}>›</button><label><span className="sr-only">Choose month</span><input type="month" value={period} onChange={(event) => changePeriod(event.target.value)} /></label></div>
      {loadState === 'loading' && <p role="status">Loading published schedule...</p>}
      {loadState === 'error' && <p role="alert">Your published schedule is unavailable. <button type="button" onClick={() => { setLoadState('loading'); setRefresh((value) => value + 1) }}>Retry</button></p>}
      {loadState === 'ready' && <><SummaryCards items={[{ label: 'Scheduled shifts', value: schedule.length }, { label: 'Expected hours', value: schedule.reduce((sum, item) => sum + Number(item.plannedHours), 0).toFixed(2) }, { label: 'Upcoming', value: schedule.filter((item) => item.date >= new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' })).length }]} />{schedule.length === 0 ? <div className="empty-state"><h3>No published shifts</h3><p>Your schedule for this month has not been published.</p></div> : <ol className="schedule-list">{schedule.map((item) => <li key={item.rosterAssignmentId} data-shift-category={item.shiftCategory}><time dateTime={item.date}><strong>{new Date(`${item.date}T00:00:00Z`).toLocaleDateString('en-AE', { weekday: 'short', day: 'numeric', timeZone: 'Asia/Dubai' })}</strong><span>{item.date}</span></time><div><strong>{item.shiftName}{item.shiftCode ? ` · ${item.shiftCode}` : ''}</strong><span>{item.plannedHours} expected hours{item.actualHours === null ? '' : ` · ${item.actualHours} actual`}{item.overtimeHours === '0.00' ? '' : ` · ${item.overtimeHours} overtime`}</span>{item.notes && <small>{item.notes}</small>}</div>{item.date >= new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' }) && item.actualHours === null && <button type="button" className="secondary" disabled={busy} onClick={() => { setRequesterAssignmentId(item.rosterAssignmentId); setTargetDate(''); setTargetEmployeeId(''); setColleagues([]); setReason(''); setMessage(''); setRetry(null); setShowForm(true) }}>Swap</button>}</li>)}</ol>}</>}
      <FormDialog title="Request a shift swap" open={showForm} onClose={() => { if (!busy) setShowForm(false) }}><form className="settings-form" onSubmit={submit}>
        <label>Your shift<select required value={requesterAssignmentId} onChange={(event) => setRequesterAssignmentId(event.target.value)}><option value="">Choose a published shift</option>{schedule.filter((item) => item.actualHours === null).map((item) => <option key={item.rosterAssignmentId} value={item.rosterAssignmentId}>{item.date} · {item.shiftCode ?? item.shiftName}</option>)}</select></label>
        <label>Colleague shift date<input required type="date" value={targetDate} onChange={(event) => { setTargetDate(event.target.value); setTargetEmployeeId(''); setColleagues([]) }} /></label>
        <label>Colleague<select required value={targetEmployeeId} onChange={(event) => setTargetEmployeeId(event.target.value)}><option value="">Choose a same-branch colleague</option>{colleagues.map((item) => <option key={item.rosterAssignmentId} value={item.employeeId}>{item.employeeName} · {item.shiftCode ?? item.shiftName}</option>)}</select></label>
        <label>Reason<input required minLength="3" maxLength="500" value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        {message && <p role="alert">{message}</p>}<button type="submit" disabled={busy}>{busy ? 'Submitting...' : 'Request swap'}</button>
      </form></FormDialog>
      <section className="shift-swap-history employee-panel"><h3>My swap requests</h3>{swaps.length === 0 ? <p className="empty-copy">No swap requests.</p> : <ul className="employee-detail-list">{swaps.map((swap) => <li key={swap.id}><span><strong>{swap.requesterDate} ↔ {swap.targetDate}</strong><small>{swap.requesterEmployeeName} and {swap.targetEmployeeName}</small></span><span className="status-pill" data-status={swap.status}>{swap.status}</span>{swap.status === 'pending' && <button type="button" className="secondary" onClick={() => cancel(swap)}>Cancel request</button>}</li>)}</ul>}</section>
      {message && <p role="status" className="feedback">{message}</p>}
    </section>
  )
}
