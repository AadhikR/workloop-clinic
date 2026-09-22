import { useCallback, useEffect, useMemo, useState } from 'react'

import { readShifts } from './attendanceConfigurationApi.js'
import { readAllEmployees } from './employeeApi.js'
import {
  createRosterDraft,
  createRosterOverride,
  deleteRosterDraft,
  approveRosterOvertime,
  publishRosterMonth,
  readAllRosterMonth,
  readRosterPublication,
  readRosterMonth,
  readRosterValidation,
  recordRosterActualHours,
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
  const [publicationAssignments, setPublicationAssignments] = useState([])
  const [validation, setValidation] = useState(null)
  const [publication, setPublication] = useState(null)
  const [department, setDepartment] = useState('')
  const [employeeFilter, setEmployeeFilter] = useState('')
  const [draft, setDraft] = useState(empty)
  const [editing, setEditing] = useState(null)
  const [message, setMessage] = useState('')

  const departments = useMemo(() => [...new Set(employees.map((item) => item.department).filter(Boolean))].sort(), [employees])
  const load = useCallback(async () => {
    const [month, allAssignments, gates, state] = await Promise.all([
      readRosterMonth(authentication, branchId, period, { department, employeeId: employeeFilter, limit: 100 }),
      readAllRosterMonth(authentication, branchId, period),
      readRosterValidation(authentication, branchId, period),
      readRosterPublication(authentication, branchId, period),
    ])
    setAssignments(month.data); setPublicationAssignments(allAssignments); setValidation(gates); setPublication(state)
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

  const publish = async () => {
    if (!validation?.ready || publicationAssignments.length === 0) return
    try {
      await publishRosterMonth(authentication, branchId, period, publicationAssignments, publication?.sourceVersion ?? null, { idempotencyKey: crypto.randomUUID() })
      await load(); setMessage('Roster published. Employees can now see their schedules.')
    } catch { setMessage('Publication failed because a gate or roster row changed. Reload and review the month.') }
  }

  const actualHours = async (item) => {
    const hours = window.prompt(`Actual hours worked by ${item.employeeName} on ${item.date}:`, item.plannedHours)
    if (hours === null) return
    const reason = window.prompt('Evidence note:', 'Manager-confirmed timesheet')
    if (!reason) return
    try {
      await recordRosterActualHours(authentication, branchId, period, item.id, hours, 'manager_attestation', reason, publication.sourceVersion, { idempotencyKey: crypto.randomUUID() })
      await load(); setMessage('Actual-hours evidence recorded in a new roster version.')
    } catch { setMessage('Actual hours were not recorded. The published source may have changed.') }
  }

  const approveOvertime = async (item) => {
    const reason = window.prompt('Reason for approving roster overtime:', 'Approved against the roster timesheet')
    if (!reason) return
    try {
      await approveRosterOvertime(authentication, branchId, period, item.id, reason, publication.sourceVersion, [], { idempotencyKey: crypto.randomUUID() })
      await load(); setMessage('Roster overtime approved in a new source version.')
    } catch { setMessage('Overtime is not ready. Record actual hours first and resolve attendance overlap.') }
  }

  return (
    <section className="roster-drafts" aria-labelledby="roster-drafts-title">
      <h2 id="roster-drafts-title">Roster drafts</h2>
      <p>Build a selected-branch month, clear its publication gates, publish an immutable version, and record actual-hours evidence separately.</p>
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
        {assignments.map((item) => <li key={item.id}><span><strong>{item.date} — {item.employeeName}</strong><small>{item.shiftCode ?? item.shiftName}, {item.plannedHours} hours · {item.department}{item.leaveConflict ? ' · Leave conflict' : ''}</small></span><span><button type="button" disabled={item.published} onClick={() => { setEditing(item); setDraft({ employeeId: item.employeeId, shiftId: item.shiftId, date: item.date, plannedHours: item.plannedHours, notes: item.notes }) }}>Edit</button><button type="button" className="secondary" disabled={item.published} onClick={() => remove(item)}>Delete</button>{item.published && <><button type="button" onClick={() => actualHours(item)}>Actual hours</button><button type="button" className="secondary" onClick={() => approveOvertime(item)}>Approve overtime</button></>}</span></li>)}
      </ul>
      {validation && <section className="roster-gates"><h3>Publication gates</h3>{validation.leaveConflicts.map((item) => <p key={`${item.rosterAssignmentId}-${item.leaveRequestId}`}>{item.employeeName} has {item.leaveStatus.toLowerCase()} leave on {item.date}. {item.overridden ? <strong>Override recorded</strong> : <button type="button" onClick={() => override(item)}>Record override</button>}</p>)}{validation.staffingViolations === null ? <p>Staffing enforcement is disabled for this branch.</p> : validation.staffingViolations.map((item) => <p key={item.violationDigest}>{item.date}: {item.department} {item.shiftCategory} needs {item.required}; {item.assigned} assigned. {item.overridden ? <strong>Override recorded</strong> : <button type="button" onClick={() => override(item)}>Record override</button>}</p>)}<p><strong>{validation.ready ? 'All current gates pass.' : 'The roster is not ready for publication.'}</strong></p></section>}
      <section className="roster-publication"><h3>Publication</h3><p>{publication?.status === 'published' ? `Version ${publication.version} · ${publication.recordCount} assignments · ${publication.sourceVersion}` : 'This month is still a draft.'}</p><button type="button" disabled={!validation?.ready || publicationAssignments.length === 0 || publication?.status === 'published'} onClick={publish}>Publish exact roster</button></section>
      {message && <p role="status">{message}</p>}
    </section>
  )
}
