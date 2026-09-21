import { useCallback, useEffect, useMemo, useState } from 'react'

import { readShifts } from './attendanceConfigurationApi.js'
import { readAllEmployees } from './employeeApi.js'
import {
  createRosterDraft,
  createRosterOverride,
  deleteRosterDraft,
  readRosterMonth,
  readRosterValidation,
  replaceRosterDraft,
} from './rosterApi.js'

function currentPeriod() { return new Date().toISOString().slice(0, 7) }
function monthEnd(period) { return new Date(`${period}-01T00:00:00Z`).toISOString().slice(0, 8) + new Date(Number(period.slice(0, 4)), Number(period.slice(5, 7)), 0).getDate() }
const empty = { employeeId: '', shiftId: '', date: '', plannedHours: '8.00', notes: '' }

export default function RosterDrafts({ authentication, branchId }) {
  const [period, setPeriod] = useState(currentPeriod())
  const [employees, setEmployees] = useState([])
  const [shifts, setShifts] = useState([])
  const [assignments, setAssignments] = useState([])
  const [validation, setValidation] = useState(null)
  const [department, setDepartment] = useState('')
  const [employeeFilter, setEmployeeFilter] = useState('')
  const [draft, setDraft] = useState(empty)
  const [editing, setEditing] = useState(null)
  const [message, setMessage] = useState('')

  const departments = useMemo(() => [...new Set(employees.map((item) => item.department).filter(Boolean))].sort(), [employees])
  const load = useCallback(async () => {
    const [month, gates] = await Promise.all([
      readRosterMonth(authentication, branchId, period, { department, employeeId: employeeFilter, limit: 100 }),
      readRosterValidation(authentication, branchId, period),
    ])
    setAssignments(month.data); setValidation(gates)
  }, [authentication, branchId, department, employeeFilter, period])

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      readAllEmployees(authentication, branchId, { signal: controller.signal }),
      readShifts(authentication, branchId, { limit: 100, signal: controller.signal }),
    ]).then(([nextEmployees, nextShifts]) => {
      if (!controller.signal.aborted) { setEmployees(nextEmployees); setShifts(nextShifts.data.filter((item) => item.isActive)) }
    }).catch(() => { if (!controller.signal.aborted) setMessage('Roster source lists are unavailable.') })
    return () => controller.abort()
  }, [authentication, branchId])

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      load().catch(() => setMessage('Roster drafts are unavailable.'))
    }, 0)
    return () => window.clearTimeout(timeout)
  }, [load])

  const save = async (event) => {
    event.preventDefault(); setMessage('')
    try {
      if (editing) await replaceRosterDraft(authentication, branchId, period, editing.id, { ...draft, expectedVersion: editing.version }, { idempotencyKey: crypto.randomUUID() })
      else await createRosterDraft(authentication, branchId, period, draft, { idempotencyKey: crypto.randomUUID() })
      setDraft(empty); setEditing(null); await load(); setMessage('Roster draft saved.')
    } catch { setMessage('Nothing changed. Check leave, employee, shift, duplicate-date, or stale-version conflicts.') }
  }

  const remove = async (item) => {
    try { await deleteRosterDraft(authentication, branchId, period, item, { idempotencyKey: crypto.randomUUID() }); await load(); setMessage('Roster draft deleted.') }
    catch { setMessage('This draft is published, retained by a workflow, or has changed.') }
  }

  const override = async (item) => {
    const reason = window.prompt('State the operational reason for this staffing exception.')
    if (!reason) return
    try { await createRosterOverride(authentication, branchId, period, item.violationDigest, reason, { idempotencyKey: crypto.randomUUID() }); await load(); setMessage('Immutable staffing override recorded.') }
    catch { setMessage('The violation changed or the override could not be recorded.') }
  }

  return (
    <section className="roster-drafts" aria-labelledby="roster-drafts-title">
      <h2 id="roster-drafts-title">Roster drafts</h2>
      <p>Build a selected-branch month, review leave and staffing gates, and record exact compliance exceptions. Publication remains disabled.</p>
      <div className="roster-filters">
        <label>Month<input type="month" value={period} onChange={(event) => setPeriod(event.target.value)} /></label>
        <label>Department<select value={department} onChange={(event) => setDepartment(event.target.value)}><option value="">All departments</option>{departments.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Employee<select value={employeeFilter} onChange={(event) => setEmployeeFilter(event.target.value)}><option value="">All employees</option>{employees.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      </div>
      <form onSubmit={save} className="roster-editor">
        <select aria-label="Roster employee" required value={draft.employeeId} onChange={(event) => setDraft({ ...draft, employeeId: event.target.value })}><option value="">Employee</option>{employees.filter((item) => item.active && ['active', 'probation'].includes(item.employmentStatus)).map((item) => <option key={item.id} value={item.id}>{item.name} — {item.department}</option>)}</select>
        <select aria-label="Roster shift" required value={draft.shiftId} onChange={(event) => setDraft({ ...draft, shiftId: event.target.value })}><option value="">Shift</option>{shifts.map((item) => <option key={item.id} value={item.id}>{item.code ?? item.name} — {item.name}</option>)}</select>
        <input aria-label="Roster date" required type="date" min={`${period}-01`} max={monthEnd(period)} value={draft.date} onChange={(event) => setDraft({ ...draft, date: event.target.value })} />
        <input aria-label="Planned hours" required type="number" min="0.25" max="24" step="0.25" value={draft.plannedHours} onChange={(event) => setDraft({ ...draft, plannedHours: event.target.value })} />
        <input aria-label="Roster notes" maxLength="500" value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} />
        <button type="submit">{editing ? 'Replace draft' : 'Add draft'}</button>
        {editing && <button type="button" className="secondary" onClick={() => { setEditing(null); setDraft(empty) }}>Cancel</button>}
      </form>
      <ul className="roster-list">
        {assignments.map((item) => <li key={item.id}><span><strong>{item.date} — {item.employeeName}</strong><small>{item.shiftCode ?? item.shiftName}, {item.plannedHours} hours · {item.department}{item.leaveConflict ? ' · Leave conflict' : ''}</small></span><span><button type="button" disabled={item.published} onClick={() => { setEditing(item); setDraft({ employeeId: item.employeeId, shiftId: item.shiftId, date: item.date, plannedHours: item.plannedHours, notes: item.notes }) }}>Edit</button><button type="button" className="secondary" disabled={item.published} onClick={() => remove(item)}>Delete</button></span></li>)}
      </ul>
      {validation && <section className="roster-gates"><h3>Publication gates</h3>{validation.leaveConflicts.map((item) => <p key={`${item.rosterAssignmentId}-${item.leaveRequestId}`}>{item.employeeName} has {item.leaveStatus.toLowerCase()} leave on {item.date}. {item.overridden ? <strong>Override recorded</strong> : <button type="button" onClick={() => override(item)}>Record override</button>}</p>)}{validation.staffingViolations === null ? <p>Staffing enforcement is disabled for this branch.</p> : validation.staffingViolations.map((item) => <p key={item.violationDigest}>{item.date}: {item.department} {item.shiftCategory} needs {item.required}; {item.assigned} assigned. {item.overridden ? <strong>Override recorded</strong> : <button type="button" onClick={() => override(item)}>Record override</button>}</p>)}<p><strong>{validation.ready ? 'All current gates pass.' : 'The roster is not ready for publication.'}</strong></p></section>}
      {message && <p role="status">{message}</p>}
    </section>
  )
}
